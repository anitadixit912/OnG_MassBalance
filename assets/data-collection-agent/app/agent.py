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
from litellm.exceptions import (
    APIConnectionError, InternalServerError, RateLimitError,
    ServiceUnavailableError, Timeout,
)
from sap_cloud_sdk.agent_decorators import agent_config, agent_model, prompt_section
from sap_cloud_sdk.agent_memory.factory.langgraph_checkpoint import create_checkpointer
from circuit_breaker import CircuitBreaker
from mcp_providers.agw import get_user_sub

logger = logging.getLogger(__name__)

RETRYABLE_ERRORS: tuple[type[Exception], ...] = (
    APIConnectionError, Timeout, RateLimitError, ServiceUnavailableError, InternalServerError,
)


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


@prompt_section(key="prompts.system", label="System Prompt", description="System prompt for the Data Collection Agent", validation={"format": "markdown", "max_length": 5000})
def get_system_prompt() -> str:
    return """You are the Data Collection Agent for a refinery mass balance reconciliation system.

## Your Mission
Fetch live hydrocarbon data from SAP IS-Oil & Gas (OGS_650) via the OGS_S4 BTP destination.
You cover all five data domains needed for mass balance reconciliation.

## Data Domains to Collect

**TANK domain** — Material stock levels:
- Use `list_a_matlstkinacctmod_for_api_material_stock_srv` filtered by Plant and StorageLocation
- Returns: Material, Plant, StorageLocation, Batch, MatlWrhsStkQtyInMatlBaseUnit

**MAT domain** — Material master base units:
- Use `list_a_materialstock_for_api_material_stock_srv` filtered by Material
- Returns: Material, MaterialBaseUnit

**MOV domain** — Goods movement history (MSEG/MKPF):
- Use `list_a_materialdocumentheader_for_api_material_document_srv` filtered by PostingDate range and Plant
- Expand items: `list_a_materialdocumentitem_for_api_material_document_srv` filtered by Plant and Material
- Returns: MaterialDocument, PostingDate, GoodsMovementType, Material, Plant, QuantityInBaseUnit

**PHYS domain** — Physical inventory documents:
- Use `list_physicalinventorydocument_for_sap_self` filtered by Plant, FiscalYear
- Expand items to get BookQtyBfrCountInMatlBaseUnit and Quantity
- Returns: PhysicalInventoryDocument, FiscalYear, Plant, StorageLocation, count status

**BOOK domain** — Process order confirmations (yield/consumption):
- Use `list_procordconf2_for_api_proc_order_confirmation_2_srv` filtered by Plant and PostingDate
- Returns: OrderID, Material, Plant, ConfirmationYieldQuantity, ConfirmationScrapQuantity

**TRANSFERS domain** — Inter-plant stock transport orders:
- Use `list_stocktransportorder_for_sap_self` filtered by SupplyingPlant and CreationDate
- Expand items for quantities and receiving plant
- Returns: StockTransportOrder, SupplyingPlant, Product, Plant, OrderQuantity

## Critical Rules
- **LIVE DATA ONLY** — never fabricate, estimate, or cache any SAP data
- Set page size (`$top`) to maximum 100 on ALL paginated tool calls
- Relay tool errors verbatim — do not add suggestions
- Return a structured JSON data package with all 6 domains populated
- Log M1.achieved when all domains fetched; log M1.missed with missing domain list on failure

## Output Format
Return a structured JSON object:
```json
{
  "plant": "<plant>",
  "period": "<period>",
  "domains": {
    "TANK": [...],
    "MAT": [...],
    "MOV": [...],
    "PHYS": [...],
    "BOOK": [...],
    "TRANSFERS": [...]
  },
  "status": "COMPLETE" | "PARTIAL",
  "missing_domains": []
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
        self._model_chain: list[tuple[str, ChatLiteLLM]] = [(name, _build_llm(name)) for name in ordered_models]
        self.llm = self._model_chain[0][1]

        threshold = get_circuit_breaker_failure_threshold()
        self._breaker: CircuitBreaker | None = (
            CircuitBreaker(failure_threshold=threshold, cooldown_seconds=get_circuit_breaker_cooldown_seconds())
            if threshold >= 1 else None
        )
        self._checkpointer = create_checkpointer(ttl_seconds=thread_ttl_seconds() or None)
        summarization_llm = ChatLiteLLM(model=get_summarization_model_name(), temperature=0.0)
        self._summarization_middleware = SummarizationMiddleware(
            model=summarization_llm,
            trigger=("tokens", summarization_trigger_tokens()),
            keep=("messages", 4),
        )

    def _create_graph(self, llm: ChatLiteLLM, tools: Sequence[BaseTool], system_prompt: str) -> CompiledStateGraph:
        return create_agent(llm, tools=list(tools), system_prompt=system_prompt, checkpointer=self._checkpointer, middleware=[self._summarization_middleware])

    async def _invoke_with_fallback(self, tools: Sequence[BaseTool], system_prompt: str, query: str, context_id: str, extra_messages: list | None = None) -> dict[str, Any]:
        config = {"configurable": {"thread_id": f"{get_user_sub()}:{context_id}"}}
        messages = {"messages": (extra_messages or []) + [HumanMessage(content=query)]}

        async def _run(llm: ChatLiteLLM) -> dict[str, Any]:
            graph = self._create_graph(llm, tools, system_prompt)
            return await graph.ainvoke(messages, config)

        last_error: Exception | None = None
        for model_name, llm in self._model_chain:
            if self._breaker and not await self._breaker.allows(model_name):
                continue
            try:
                result = await _run(llm)
                if self._breaker:
                    await self._breaker.record_success(model_name)
                return result
            except RETRYABLE_ERRORS as err:
                last_error = err
                if self._breaker:
                    await self._breaker.record_failure(model_name)
                continue

        if last_error:
            raise last_error
        model_name, llm = self._model_chain[0]
        return await _run(llm)

    async def stream(self, query: str, context_id: str, tools: Sequence[BaseTool] | None = None) -> AsyncGenerator[dict, None]:
        yield {"is_task_complete": False, "require_user_input": False, "content": "Collecting SAP data..."}
        try:
            extra: list = []
            if not tools:
                extra.append(SystemMessage(content="IMPORTANT: No MCP tools available. Inform the user that SAP data cannot be fetched."))
            result = await self._invoke_with_fallback(tools=tools or [], system_prompt=get_system_prompt(), query=query, context_id=context_id, extra_messages=extra or None)
            response = result["messages"][-1].content
            # M1 instrumentation
            if '"status": "COMPLETE"' in response or "COMPLETE" in response:
                logger.info("M1.achieved: DATA_INGESTION_LIVE — data collection completed successfully")
            else:
                logger.warning("M1.missed: DATA_INGESTION_FAILED — data collection returned partial or failed result")
            yield {"is_task_complete": True, "require_user_input": False, "content": response}
        except Exception:
            logger.exception("Data Collection Agent stream() failed")
            logger.warning("M1.missed: DATA_INGESTION_FAILED — agent stream exception")
            yield {"is_task_complete": True, "require_user_input": False, "content": "Error collecting SAP data. Please try again."}

    async def invoke(self, query: str, context_id: str, tools: Sequence[BaseTool] | None = None) -> AgentResponse:
        last: dict = {}
        async for chunk in self.stream(query, context_id, tools=tools):
            last = chunk
        if last.get("is_task_complete"):
            return AgentResponse(status="completed", message=last["content"])
        if last.get("require_user_input"):
            return AgentResponse(status="input_required", message=last["content"])
        return AgentResponse(status="error", message=last.get("content", "Unknown error"))
