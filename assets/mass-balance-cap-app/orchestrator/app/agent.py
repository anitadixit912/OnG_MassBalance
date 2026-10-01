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

@prompt_section(key="prompts.system", label="System Prompt", description="System prompt", validation={"format": "markdown", "max_length": 5000})
def get_system_prompt() -> str:
    return """You are the Mass Balance Orchestrator Agent for a refinery hydrocarbon mass balance reconciliation system.
You are the ONLY agent the user interacts with directly. You coordinate 5 specialist sub-agents.

## Pipeline (execute in this exact order)

**Step 1 — Data Collection**
Call the Data Collection Agent: "Collect all hydrocarbon data for plant {plant} period {period}"
→ Receive structured data package (TANK, MAT, MOV, PHYS, BOOK, TRANSFERS domains)

**Step 2 — Validation**
Call the Validation & Anomaly Agent with the data package.
→ If FAIL: HALT pipeline. Present the validation errors to the user. STOP here.
→ If PASS: proceed to Step 3.

**Step 3 — Calculation**
Call the Calculation & Reconciliation Agent with the validated data package.
→ Receive variance results at Plant, Tank, and Material level.

**Step 4 — Exception Classification**
Call the Exception Management Agent with the variance results.
→ Receive classified exceptions with severity and root cause.

**Step 5 — Report Generation**
Call the Report Generation Agent with the classified exceptions.
→ Receive formatted exception report and KPI summary.

**Step 6 — Present Report and Approval Gate**
Present the full report to the user.
For any CRITICAL or WARNING exception with a proposed correction:
- Ask: "Do you approve posting this correction? Please confirm with your name and role."
- WAIT for explicit named-user confirmation before any SAP document is created
- NEVER auto-post — no SAP document is created without approval in the conversation
- On approval: log M5.achieved: HUMAN_APPROVAL_GATES_DEPLOYED with approver details
- If gate bypassed: log M5.missed: APPROVAL_GATE_BYPASSED — CRITICAL ALERT

## Dynamic Replanning
- If any sub-agent returns an error: retry once before escalating to user
- If Data Collection Agent fails a specific domain: surface which domain failed with error
- If Validation fails: present specific validation errors clearly

## Audit Trail
- Log every sub-agent call result
- Log every approval and rejection with approver identity and timestamp
- All logs are append-only

## Critical Rules
- NEVER auto-post SAP corrections
- NEVER skip validation — always wait for PASS before calculating
- NEVER fabricate data — relay tool and sub-agent errors verbatim
- Pipeline halts on validation failure"""


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

    def _mock_response(self, query: str) -> str:
        """Return a canned but meaningful response when IBD_TESTING=1 (no LLM available)."""
        q = query.lower()
        if any(w in q for w in ["run", "reconcil", "plant", "period", "trigger"]):
            return (
                "**Mass Balance Reconciliation — Demo Run (IBD_TESTING mode)**\n\n"
                "**Plant 1000 · Period 2026-09**\n\n"
                "**Step 1 — Data Collection:** ✅ All 5 domains collected\n"
                "- TANK: 24 records (4 storage locations)\n"
                "- MAT: 8 material master records\n"
                "- MOV: 342 material documents\n"
                "- PHYS: 12 physical inventory records\n"
                "- BOOK: 4 process order confirmations\n\n"
                "**Step 2 — Validation:** ✅ PASS — Data completeness 100%\n\n"
                "**Step 3 — Calculation:**\n"
                "- Overall refinery variance: **-0.08%** (within monthly tolerance of 0.08%)\n"
                "- Tank T001 (CRUDE01): -18.5 MT / -1.85% ⚠ CRITICAL — exceeds threshold\n"
                "- Tank T003 (GASOIL01): +6.2 MT / +0.62% ⚠ WARNING — in-transit STO\n"
                "- Tank T005 (NAPHTHA01): -2.1 MT / -0.21% ℹ ADVISORY — within evaporation range\n\n"
                "**Step 4 — Exception Classification:** 3 exceptions raised\n"
                "- EXC-2026-09-0001: CRITICAL · Root cause: Measurement/Calibration (MC)\n"
                "- EXC-2026-09-0002: WARNING · Root cause: In-Transit Transfer (TF)\n"
                "- EXC-2026-09-0003: ADVISORY · Root cause: Process Loss (PL)\n\n"
                "**Step 5 — Approval Gate:**\n"
                "EXC-2026-09-0001 requires Plant Manager approval before MI07 correction is posted.\n"
                "Please use the **Approval Workflow** screen to approve or reject."
            )
        if any(w in q for w in ["exception", "variance", "exc-"]):
            return (
                "**Exception Summary — Plant 1000**\n\n"
                "There are currently **3 open exceptions** for period 2026-09:\n\n"
                "1. **EXC-2026-09-0001** — CRITICAL — Tank T001 CRUDE01\n"
                "   Variance: -18.5 MT (-1.85%). Root cause: Measurement/Calibration.\n"
                "   Action: Recalibrate dip gauge, repost MI07. Awaiting approval.\n\n"
                "2. **EXC-2026-09-0002** — WARNING — Tank T003 GASOIL01\n"
                "   Variance: +6.2 MT (+0.62%). Root cause: In-transit stock transfer.\n"
                "   Action: Confirm receipt at plant 2000. Under review.\n\n"
                "3. **EXC-2026-09-0003** — ADVISORY — Tank T005 NAPHTHA01\n"
                "   Variance: -2.1 MT (-0.21%). Root cause: Evaporation loss.\n"
                "   Action: Monitor next 3 days. Within tolerance for light distillates."
            )
        if any(w in q for w in ["approv", "reject", "workflow", "pending"]):
            return (
                "**Approval Workflow Status**\n\n"
                "**Pending approvals:** 2\n\n"
                "- EXC-2026-09-0001 (CRITICAL): Awaiting Plant Manager sign-off for MI07 gauge correction\n"
                "- EXC-2026-09-0002 (WARNING): Under review — awaiting transit confirmation from plant 2000\n\n"
                "Use the **Approval Workflow** screen to approve or reject these exceptions.\n"
                "No SAP correction document will be posted without your explicit approval."
            )
        if any(w in q for w in ["tank", "domain", "s4", "s/4", "data", "stock"]):
            return (
                "**S/4HANA Domain Status — Plant 1000 (Mock Data)**\n\n"
                "- **TANK** (Material Stock): 4 materials across 4 tanks\n"
                "  CRUDE01: 15,000 MT · CRUDE02: 8,500 MT · NAPHTHA01: 3,200 MT · DIESEL01: 5,800 MT\n\n"
                "- **MOV** (Material Documents): 4 postings (GR 101, GI 201/261/601)\n\n"
                "- **PHYS** (Physical Inventory): 2 documents — book vs count delta tracked\n\n"
                "- **BOOK** (Process Orders): 2 confirmations — NAPHTHA01 yield 280 MT, DIESEL01 yield 1,180 MT\n\n"
                "- **TRANSFERS** (Stock Transport Orders): 1 STO in transit — 500 MT CRUDE01 to plant 2000\n\n"
                "All domains: **LIVE** status. Data fetched at run start."
            )
        if any(w in q for w in ["tolerance", "threshold", "config"]):
            return (
                "**Tolerance Configuration — Plant 1000**\n\n"
                "| Material Group       | Daily Tolerance | Monthly Tolerance | Escalation |\n"
                "|----------------------|-----------------|-------------------|------------|\n"
                "| Crude / Residual     | 0.15%           | 0.08%             | Plant manager review |\n"
                "| Light Distillates    | 0.10%           | 0.05%             | Operations review |\n"
                "| Finished Products    | 0.12%           | 0.06%             | Quality + ops |\n"
                "| Specialty / Blends   | 0.08%           | 0.04%             | Blending supervisor |\n\n"
                "Update tolerances in the **Tolerance Config** screen (Engineer role required)."
            )
        # Generic help response
        return (
            "Hello! I am the **Mass Balance Reconciliation Agent**.\n\n"
            "I can help you with:\n"
            "- **Run a reconciliation**: 'Run mass balance for plant 1000 period 2026-09'\n"
            "- **Explain exceptions**: 'Explain the CRITICAL exception for CRUDE01'\n"
            "- **Check domain data**: 'What is the stock data for plant 1000?'\n"
            "- **Approval status**: 'What approvals are pending?'\n"
            "- **Tolerance config**: 'Show tolerance thresholds for plant 1000'\n\n"
            "*Note: Running in IBD_TESTING demo mode — responses use mock S/4HANA data.*\n"
            "*For live data, connect real AI Core credentials.*"
        )

    async def stream(self, query: str, context_id: str, tools=None) -> AsyncGenerator[dict, None]:
        yield {"is_task_complete": False, "require_user_input": False, "content": "Starting mass balance reconciliation pipeline..."}

        # IBD_TESTING=1: skip LLM entirely, return canned analysis from mock data
        if os.environ.get("IBD_TESTING") == "1":
            response = self._mock_response(query)
            needs_approval = "approval" in response.lower() and "approval workflow" in response.lower()
            yield {"is_task_complete": not needs_approval, "require_user_input": needs_approval, "content": response}
            return

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
