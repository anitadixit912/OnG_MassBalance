import logging
import os
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Literal, Sequence

from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langchain_litellm import ChatLiteLLM
from litellm.exceptions import APIConnectionError, InternalServerError, RateLimitError, ServiceUnavailableError, Timeout
try:
    from sap_cloud_sdk.agent_decorators import agent_config, agent_model, prompt_section
    from sap_cloud_sdk.agent_memory.factory.langgraph_checkpoint import create_checkpointer
except ImportError:
    # Running in CF without sap-cloud-sdk — use no-op decorators
    def agent_model(**kwargs):
        def decorator(fn): return fn
        return decorator
    def agent_config(**kwargs):
        def decorator(fn): return fn
        return decorator
    def prompt_section(**kwargs):
        def decorator(fn): return fn
        return decorator
    def create_checkpointer(**kwargs):
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()
from circuit_breaker import CircuitBreaker
from mcp_providers.agw import get_user_sub
from mcp_providers.aicore import get_aicore_litellm_params

logger = logging.getLogger(__name__)
RETRYABLE_ERRORS = (APIConnectionError, Timeout, RateLimitError, ServiceUnavailableError, InternalServerError)


@agent_model(key="config.model", label="LLM Model", description="LLM model")
def get_model_name() -> str:
    return "sap/anthropic--claude-4.5-sonnet"

@agent_model(key="config.fallback_models", label="Fallback LLM Models", description="Fallback models")
def get_fallback_model_names() -> str:
    return ""

@agent_model(key="config.summarization.model", label="Summarization Model", description="Summarization model")
def get_summarization_model_name() -> str:
    return "sap/anthropic--claude-4.5-haiku"

@agent_config(key="config.temperature", label="LLM Temperature", description="Temperature")
def get_temperature() -> float:
    return 0.0

@agent_config(key="config.checkpointer.ttl_seconds", label="Thread TTL", description="Thread TTL")
def thread_ttl_seconds() -> int:
    return 3600

@agent_config(key="config.summarization.trigger_tokens", label="Summarization Trigger", description="Token threshold")
def summarization_trigger_tokens() -> int:
    return 30_000

@agent_config(key="config.circuit_breaker.failure_threshold", label="CB Failure Threshold", description="CB threshold")
def get_circuit_breaker_failure_threshold() -> int:
    return 3

@agent_config(key="config.circuit_breaker.cooldown_seconds", label="CB Cooldown", description="CB cooldown")
def get_circuit_breaker_cooldown_seconds() -> float:
    return 30.0

@prompt_section(key="prompts.system", label="System Prompt", description="System prompt", validation={"format": "markdown", "max_length": 10000})
def get_system_prompt() -> str:
    return """You are the Mass Balance Reconciliation Agent for a refinery hydrocarbon mass balance system.
You execute the full reconciliation pipeline yourself using the tools available to you.

## Pipeline (execute in this exact order)

---

### Step 1 — Data Collection
Use the following tools to fetch live data from SAP IS-Oil & Gas via OGS_S4:

- **TANK/MAT domain**: `get_material_stock(plant, material=None)` — material stock levels (MARD)
- **MOV domain**: `get_material_documents(plant, posting_date)` — goods movements (MSEG/MKPF). Call once per day in the period.
- **PHYS domain**: `get_physical_inventory_documents(plant)` — physical inventory counts
- **TRANSFERS domain**: `get_stock_transport_orders(supplying_plant)` — in-transit STOs
- **BOOK domain**: `get_process_order_confirmations(plant)` — yield/consumption confirmations

Use `$top=100` on all paginated calls. Collect all 6 domains before proceeding.

On success log: `M1.achieved: DATA_INGESTION_LIVE — plant={plant} period={period} domains=TANK,MAT,MOV,PHYS,BOOK,TRANSFERS`
On partial failure log: `M1.missed: DATA_INGESTION_FAILED — plant={plant} period={period} missing_domains={list}`

---

### Step 2 — Validation
Validate the collected data package before any calculation:

1. **Completeness**: All 6 domains must have ≥1 record. If any domain is empty → FAIL. HALT pipeline. Report which domain failed.
2. **Consistency**: Material numbers in MOV must exist in MAT. PHYS items must reference valid plant/storage locations in TANK.
3. **Referential integrity**: All material document items must reference existing materials.
4. **Outlier detection**: Flag quantities deviating >3 standard deviations from period average. Flag materials with no PHYS count.

On PASS log: `M2.achieved: VALIDATION_ENGINE_OPERATIONAL — plant={plant} period={period} checks_passed={count}`
On FAIL log: `M2.missed: VALIDATION_FAILED — plant={plant} period={period} error={description}` — then STOP and present errors to user.

---

### Step 3 — Calculation
Apply the mass balance formula at Plant, Tank/Storage Location, and Material level:

**Closing = Opening + Receipts − Issues − Consumption ± Transfers ± Adjustments**

- **Opening** = MatlWrhsStkQtyInMatlBaseUnit from TANK (start of period)
- **Receipts** = sum of MOV items with GoodsMovementType in [101, 501]
- **Issues** = sum of MOV items with GoodsMovementType in [201, 261, 601]
- **Consumption** = sum of ConfirmationYieldQuantity from BOOK domain
- **Transfers** = sum of OrderQuantity from TRANSFERS domain
- **Adjustments** = sum of (Quantity − BookQtyBfrCountInMatlBaseUnit) from PHYS domain

Apply corrections before Physical vs. Book comparison: temperature, density, meter factor, water bottom deduction.

Compute: closing_stock_MT, physical_stock_MT, book_stock_MT, variance_MT, variance_pct at all 3 levels.

On success log: `M3.achieved: MASS_BALANCE_CALCULATION_VALIDATED — plant={plant} period={period} levels=plant,tank,material`
On error log: `M3.missed: CALCULATION_ERROR — plant={plant} period={period} error={description}`

---

### Step 4 — Exception Classification
Apply tolerance matrix to each variance result:

| Severity | Condition |
|---|---|
| INFO | variance < 0.1% AND < 1 MT |
| ADVISORY | variance 0.1–0.5% OR 1–5 MT |
| WARNING | variance 0.5–2.0% OR 5–20 MT |
| CRITICAL | variance > 2.0% OR > 20 MT |

Root cause categories: MC (meter calibration), TX (transaction error), MD (missing document), TF (transfer in transit), PL (process loss), SY (system error).

For each exception build an evidence package by drilling into:
- Material document items (movement history) via `get_material_documents`
- STOs for in-transit transfers via `get_stock_transport_orders`
- Physical inventory items via `get_physical_inventory_documents`

Exception ID format: EXC-{YYYY-MM}-{NNNN} e.g. EXC-2026-09-0001. All exceptions start with status OPEN.

On success log: `M4.achieved: VARIANCE_EXCEPTION_PIPELINE_ACTIVE — plant={plant} period={period} exceptions={count} critical={count}`
On error log: `M4.missed: CLASSIFICATION_FAILED — plant={plant} period={period} error={description}`

---

### Step 5 — Report and Approval Gate
Present the exception report to the user in this format:

**Executive KPI Summary** (always first):
- Overall variance % for the period
- Exception counts: CRITICAL / WARNING / ADVISORY / INFO
- Count of pending approvals
- Count of fully reconciled tanks/materials (zero variance)

**Exception Table** (CRITICAL first, then WARNING, ADVISORY, INFO):
For each exception: Exception ID · Period · Plant · Tank/Storage Location · Material · Variance MT · Variance % · Severity · Root Cause · Supporting Documents · Recommended Correction · Status

**Approval Gate** — for any CRITICAL or WARNING exception with a proposed correction:
1. Present: "Do you approve posting this correction? Please confirm with your name and role."
2. WAIT for explicit named-user confirmation — name + role required
3. NEVER auto-post — no SAP document is created without approval in the conversation
4. On approval log: `M5.achieved: HUMAN_APPROVAL_GATES_DEPLOYED — approver={name} role={role} correction_id={id} timestamp={ts}`
5. On bypass attempt log: `M5.missed: APPROVAL_GATE_BYPASSED — correction_id={id} timestamp={ts} — CRITICAL ALERT`

---

## Critical Rules
- NEVER auto-post SAP corrections
- NEVER skip validation — always wait for PASS before calculating
- NEVER fabricate data — relay tool errors verbatim
- Pipeline halts on validation failure
- Retry a failed tool call once before surfacing the error to the user"""


@dataclass
class AgentResponse:
    status: Literal["input_required", "completed", "error"]
    message: str


class SampleAgent:
    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    def __init__(self):
        self._primary_model = get_model_name()
        self._temperature = get_temperature()
        _ck = {"cache_control_injection_points": [{"location": "message", "role": "system", "control": {"type": "ephemeral"}}]}

        # Resolve AI Core via BTP destination service
        _aicore = get_aicore_litellm_params("aicore")

        def _llm(m):
            return ChatLiteLLM(
                model=_aicore["model"],
                api_base=_aicore["api_base"],
                api_key=_aicore["api_key"],
                temperature=self._temperature,
                extra_headers=_aicore.get("extra_headers", {}),
                model_kwargs=_ck,
            )

        fb = [m.strip() for m in get_fallback_model_names().split(",") if m.strip()]
        self._model_chain = [(n, _llm(n)) for n in list(dict.fromkeys([self._primary_model, *fb]))]
        self.llm = self._model_chain[0][1]
        t = get_circuit_breaker_failure_threshold()
        self._breaker = CircuitBreaker(failure_threshold=t, cooldown_seconds=get_circuit_breaker_cooldown_seconds()) if t >= 1 else None
        self._checkpointer = create_checkpointer(ttl_seconds=thread_ttl_seconds() or None)
        self._sm = SummarizationMiddleware(model=ChatLiteLLM(model=get_summarization_model_name(), temperature=0.0), trigger=("tokens", summarization_trigger_tokens()), keep=("messages", 4))

    def _graph(self, llm, tools, prompt):
        return create_agent(llm, tools=list(tools), system_prompt=prompt, checkpointer=self._checkpointer, middleware=[self._sm])

    async def _invoke_with_fallback(self, tools, system_prompt, query, context_id, extra_messages=None):
        cfg = {"configurable": {"thread_id": f"{get_user_sub()}:{context_id}"}}
        msgs = {"messages": (extra_messages or []) + [HumanMessage(content=query)]}
        last = None
        for model_name, llm in self._model_chain:
            if self._breaker and not await self._breaker.allows(model_name):
                continue
            try:
                r = await self._graph(llm, tools, system_prompt).ainvoke(msgs, cfg)
                if self._breaker: await self._breaker.record_success(model_name)
                return r
            except RETRYABLE_ERRORS as e:
                last = e
                if self._breaker: await self._breaker.record_failure(model_name)
        if last: raise last
        return await self._graph(self._model_chain[0][1], tools, system_prompt).ainvoke(msgs, cfg)

    async def stream(self, query: str, context_id: str, tools=None) -> AsyncGenerator[dict, None]:
        yield {"is_task_complete": False, "require_user_input": False, "content": "Starting mass balance reconciliation pipeline..."}
        try:
            extra = [SystemMessage(content="No sub-agent tools available.")] if not tools else []
            result = await self._invoke_with_fallback(tools=tools or [], system_prompt=get_system_prompt(), query=query, context_id=context_id, extra_messages=extra or None)
            response = result["messages"][-1].content
            # Approval gate instrumentation
            if "approve" in response.lower() or "approval" in response.lower():
                yield {"is_task_complete": False, "require_user_input": True, "content": response}
            else:
                yield {"is_task_complete": True, "require_user_input": False, "content": response}
        except Exception:
            logger.exception("Orchestrator stream() failed")
            yield {"is_task_complete": True, "require_user_input": False, "content": "Orchestration error. Please try again."}

    async def handle_approval(self, approval_text: str, context_id: str, tools=None) -> AsyncGenerator[dict, None]:
        """Handle named-user approval response."""
        approval_lower = approval_text.lower()
        if any(word in approval_lower for word in ["approve", "yes", "confirmed", "proceed"]):
            logger.info("M5.achieved: HUMAN_APPROVAL_GATES_DEPLOYED — approval received: %s", approval_text[:100])
            async for chunk in self.stream(f"User approved: {approval_text}. Proceed with posting correction.", context_id, tools=tools):
                yield chunk
        else:
            logger.info("Correction rejected by user: %s", approval_text[:100])
            yield {"is_task_complete": True, "require_user_input": False, "content": f"Correction rejected. No SAP document will be posted. Reason: {approval_text}"}

    async def invoke(self, query, context_id, tools=None):
        last = {}
        async for chunk in self.stream(query, context_id, tools=tools):
            last = chunk
        if last.get("is_task_complete"):
            return AgentResponse(status="completed", message=last["content"])
        if last.get("require_user_input"):
            return AgentResponse(status="input_required", message=last["content"])
        return AgentResponse(status="error", message=last.get("content", "Unknown error"))
