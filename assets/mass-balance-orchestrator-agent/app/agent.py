import logging
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

        def _llm(m):
            # LiteLLM reads AICORE_DEPLOYMENT_ID, AICORE_DESTINATION_NAME,
            # AICORE_RESOURCE_GROUP automatically via sap/ prefix
            return ChatLiteLLM(
                model=f"sap/{self._primary_model}",
                temperature=self._temperature,
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
