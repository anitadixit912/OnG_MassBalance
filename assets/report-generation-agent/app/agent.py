import logging
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Literal, Sequence

from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langchain_litellm import ChatLiteLLM
from litellm.exceptions import APIConnectionError, InternalServerError, RateLimitError, ServiceUnavailableError, Timeout
from sap_cloud_sdk.agent_decorators import agent_config, agent_model, prompt_section
from sap_cloud_sdk.agent_memory.factory.langgraph_checkpoint import create_checkpointer
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
    return """You are the Report Generation Agent for a refinery mass balance reconciliation system.

## Your Mission
Build the structured exception report and Executive KPI dashboard summary from the classified exceptions.
Return the formatted report to the Orchestrator for presentation to the user.

## Exception Report Format (one row per exception)
Each exception must include ALL of these fields:
- Exception ID (EXC-YYYY-MM-NNNN)
- Period (daily / monthly)
- Plant, Tank/Storage Location, Material
- Variance in MT and %
- Severity: INFO / ADVISORY / WARNING / CRITICAL
- Root Cause: MC / TX / MD / TF / PL / SY
- Supporting Documents (material document numbers)
- Recommended Correction
- Status: OPEN / PENDING_APPROVAL / APPROVED / POSTED

## Executive KPI Summary (always at the top)
- Overall variance % for the period
- Exception counts by severity: INFO, ADVISORY, WARNING, CRITICAL
- Count of pending approvals
- Count of fully reconciled tanks/materials (zero variance)
- Period and plant header

## Formatting Rules
- CRITICAL exceptions always listed FIRST
- Executive KPI Summary appears BEFORE the detailed exception table
- Proposed corrections clearly marked as PENDING_APPROVAL — NEVER as POSTED without approval
- If no exceptions: show clean reconciliation message with zero-variance KPIs

## Critical Rules
- No exception may have status POSTED without explicit approval
- OPEN is the only valid initial status for all new exceptions
- Log REPORT_GENERATED with exception counts on completion"""


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

        def _llm(m): return ChatLiteLLM(model=m, temperature=self._temperature, model_kwargs=_ck)
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
        yield {"is_task_complete": False, "require_user_input": False, "content": "Generating report..."}
        try:
            extra = [SystemMessage(content="No tools available.")] if not tools else []
            result = await self._invoke_with_fallback(tools=tools or [], system_prompt=get_system_prompt(), query=query, context_id=context_id, extra_messages=extra or None)
            response = result["messages"][-1].content
            logger.info("REPORT_GENERATED: report produced successfully")
            yield {"is_task_complete": True, "require_user_input": False, "content": response}
        except Exception:
            logger.exception("Report Generation Agent stream() failed")
            yield {"is_task_complete": True, "require_user_input": False, "content": "Report generation error. Please try again."}

    async def invoke(self, query, context_id, tools=None):
        last = {}
        async for chunk in self.stream(query, context_id, tools=tools):
            last = chunk
        if last.get("is_task_complete"):
            return AgentResponse(status="completed", message=last["content"])
        if last.get("require_user_input"):
            return AgentResponse(status="input_required", message=last["content"])
        return AgentResponse(status="error", message=last.get("content", "Unknown error"))
