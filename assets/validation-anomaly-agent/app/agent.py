import logging
import os
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Literal, Sequence

from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langchain_litellm import ChatLiteLLM
from langgraph.graph.state import CompiledStateGraph
from litellm.exceptions import APIConnectionError, InternalServerError, RateLimitError, ServiceUnavailableError, Timeout
from sap_cloud_sdk.agent_decorators import agent_config, agent_model, prompt_section
from sap_cloud_sdk.agent_memory.factory.langgraph_checkpoint import create_checkpointer
from circuit_breaker import CircuitBreaker
from mcp_providers.agw import get_user_sub

logger = logging.getLogger(__name__)
RETRYABLE_ERRORS = (APIConnectionError, Timeout, RateLimitError, ServiceUnavailableError, InternalServerError)


@agent_model(key="config.model", label="LLM Model", description="The language model powering this agent")
def get_model_name() -> str:
    return "sap/anthropic--claude-4.5-sonnet"

@agent_model(key="config.fallback_models", label="Fallback LLM Models", description="Comma-separated fallback models")
def get_fallback_model_names() -> str:
    return ""

@agent_model(key="config.summarization.model", label="Summarization Model", description="Model for history summarization")
def get_summarization_model_name() -> str:
    return "sap/anthropic--claude-4.5-haiku"

@agent_config(key="config.temperature", label="LLM Temperature", description="Controls randomness")
def get_temperature() -> float:
    return 0.0

@agent_config(key="config.checkpointer.ttl_seconds", label="Thread TTL (seconds)", description="Thread inactivity TTL")
def thread_ttl_seconds() -> int:
    return 3600

@agent_config(key="config.summarization.trigger_tokens", label="Summarization Trigger (tokens)", description="Token threshold for summarization")
def summarization_trigger_tokens() -> int:
    return 30_000

@agent_config(key="config.circuit_breaker.failure_threshold", label="Circuit Breaker Failure Threshold", description="Failures before circuit opens")
def get_circuit_breaker_failure_threshold() -> int:
    return 3

@agent_config(key="config.circuit_breaker.cooldown_seconds", label="Circuit Breaker Cooldown (seconds)", description="Cooldown after circuit opens")
def get_circuit_breaker_cooldown_seconds() -> float:
    return 30.0

@prompt_section(key="prompts.system", label="System Prompt", description="System prompt for Validation & Anomaly Agent", validation={"format": "markdown", "max_length": 5000})
def get_system_prompt() -> str:
    return """You are the Validation & Anomaly Agent for a refinery mass balance reconciliation system.

## Your Mission
Validate the data package received from the Data Collection Agent.
Return PASS or FAIL with full details. NEVER proceed if validation fails.

## Validation Rules

### 1. Completeness Check
- All 6 domains must be present: TANK, MAT, MOV, PHYS, BOOK, TRANSFERS
- Each domain must have at least one record for the requested plant and period
- If any domain is empty: FAIL with domain name

### 2. Consistency Check
- Opening stock + receipts - issues - consumption ± transfers must be internally consistent
- Material numbers in MOV must exist in MAT domain
- Physical inventory items must reference valid plant/storage locations in TANK

### 3. Referential Integrity
- All material document items must reference existing materials
- All PHYS items must reference valid plant/storage combinations
- All BOOK confirmations must reference existing OrderIDs

### 4. Outlier Detection
- Flag any quantity deviating more than 3 standard deviations from the period average
- Flag any material/tank with zero PHYS count in the period (missing reading)

## Critical Rules
- On validation failure: return structured FAIL response with domain, field, and error description
- On validation pass: return structured PASS response with count of records validated per domain
- NEVER proceed to calculation if validation fails — halt the pipeline
- Log M2.achieved: VALIDATION_ENGINE_OPERATIONAL on pass; M2.missed: VALIDATION_FAILED on any failure

## Output Format
```json
{
  "status": "PASS" | "FAIL",
  "plant": "<plant>",
  "period": "<period>",
  "records_validated": {"TANK": 0, "MAT": 0, "MOV": 0, "PHYS": 0, "BOOK": 0, "TRANSFERS": 0},
  "errors": [{"domain": "<domain>", "field": "<field>", "error": "<description>"}],
  "warnings": [{"domain": "<domain>", "field": "<field>", "warning": "<description>"}]
}
```"""


@dataclass
class AgentResponse:
    status: Literal["input_required", "completed", "error"]
    message: str


class SampleAgent:
    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    def __init__(self):
        self._primary_model = get_model_name()
        self._temperature = get_temperature()
        _cache_kwargs = {"cache_control_injection_points": [{"location": "message", "role": "system", "control": {"type": "ephemeral"}}]}

        def _build_llm(model: str) -> ChatLiteLLM:
            return ChatLiteLLM(model=model, temperature=self._temperature, model_kwargs=_cache_kwargs)

        fallback_models = [m.strip() for m in get_fallback_model_names().split(",") if m.strip()]
        ordered_models = list(dict.fromkeys([self._primary_model, *fallback_models]))
        self._model_chain = [(name, _build_llm(name)) for name in ordered_models]
        self.llm = self._model_chain[0][1]
        threshold = get_circuit_breaker_failure_threshold()
        self._breaker = CircuitBreaker(failure_threshold=threshold, cooldown_seconds=get_circuit_breaker_cooldown_seconds()) if threshold >= 1 else None
        self._checkpointer = create_checkpointer(ttl_seconds=thread_ttl_seconds() or None)
        self._summarization_middleware = SummarizationMiddleware(model=ChatLiteLLM(model=get_summarization_model_name(), temperature=0.0), trigger=("tokens", summarization_trigger_tokens()), keep=("messages", 4))

    def _create_graph(self, llm, tools, system_prompt):
        return create_agent(llm, tools=list(tools), system_prompt=system_prompt, checkpointer=self._checkpointer, middleware=[self._summarization_middleware])

    async def _invoke_with_fallback(self, tools, system_prompt, query, context_id, extra_messages=None):
        config = {"configurable": {"thread_id": f"{get_user_sub()}:{context_id}"}}
        messages = {"messages": (extra_messages or []) + [HumanMessage(content=query)]}
        last_error = None
        for model_name, llm in self._model_chain:
            if self._breaker and not await self._breaker.allows(model_name):
                continue
            try:
                result = await self._create_graph(llm, tools, system_prompt).ainvoke(messages, config)
                if self._breaker:
                    await self._breaker.record_success(model_name)
                return result
            except RETRYABLE_ERRORS as err:
                last_error = err
                if self._breaker:
                    await self._breaker.record_failure(model_name)
        if last_error:
            raise last_error
        return await self._create_graph(self._model_chain[0][1], tools, system_prompt).ainvoke(messages, config)

    async def stream(self, query: str, context_id: str, tools=None) -> AsyncGenerator[dict, None]:
        yield {"is_task_complete": False, "require_user_input": False, "content": "Validating data..."}
        try:
            extra = [SystemMessage(content="No tools available.")] if not tools else []
            result = await self._invoke_with_fallback(tools=tools or [], system_prompt=get_system_prompt(), query=query, context_id=context_id, extra_messages=extra or None)
            response = result["messages"][-1].content
            if '"status": "PASS"' in response or '"PASS"' in response:
                logger.info("M2.achieved: VALIDATION_ENGINE_OPERATIONAL — all checks passed")
            else:
                logger.warning("M2.missed: VALIDATION_FAILED — validation returned FAIL or error")
            yield {"is_task_complete": True, "require_user_input": False, "content": response}
        except Exception:
            logger.exception("Validation Agent stream() failed")
            logger.warning("M2.missed: VALIDATION_FAILED — agent exception")
            yield {"is_task_complete": True, "require_user_input": False, "content": "Validation error. Please try again."}

    async def invoke(self, query, context_id, tools=None):
        last = {}
        async for chunk in self.stream(query, context_id, tools=tools):
            last = chunk
        if last.get("is_task_complete"):
            return AgentResponse(status="completed", message=last["content"])
        if last.get("require_user_input"):
            return AgentResponse(status="input_required", message=last["content"])
        return AgentResponse(status="error", message=last.get("content", "Unknown error"))
