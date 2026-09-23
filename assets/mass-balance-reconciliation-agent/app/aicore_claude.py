"""
Custom LangChain ChatModel for SAP AI Core Claude deployments.

AI Core's Claude deployments only accept POST /invoke with Bedrock-format bodies
(anthropic_version: bedrock-2023-05-31). They reject /chat/completions and /messages.
This module provides a drop-in BaseChatModel replacement for ChatLiteLLM.
"""
import json
import logging
from typing import Any, Iterator, Optional, Sequence

import httpx
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool
from pydantic import Field

logger = logging.getLogger(__name__)


def _lc_to_bedrock(messages: list[BaseMessage]) -> tuple[str | None, list]:
    """Convert LangChain messages to Bedrock Anthropic request format."""
    system: str | None = None
    result: list = []

    for msg in messages:
        if isinstance(msg, SystemMessage):
            text = msg.content if isinstance(msg.content, str) else json.dumps(msg.content)
            system = text

        elif isinstance(msg, HumanMessage):
            if isinstance(msg.content, str):
                result.append({"role": "user", "content": msg.content})
            else:
                result.append({"role": "user", "content": msg.content})

        elif isinstance(msg, AIMessage):
            content: list = []
            text = msg.content if isinstance(msg.content, str) else ""
            if text:
                content.append({"type": "text", "text": text})
            for tc in (msg.tool_calls or []):
                content.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["name"],
                    "input": tc.get("args", {}),
                })
            if content:
                result.append({"role": "assistant", "content": content})
            else:
                result.append({"role": "assistant", "content": text or ""})

        elif isinstance(msg, ToolMessage):
            result.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": msg.tool_call_id,
                    "content": msg.content if isinstance(msg.content, str) else json.dumps(msg.content),
                }],
            })

    return system, result


def _bedrock_to_lc(data: dict) -> AIMessage:
    """Convert Bedrock Anthropic response to LangChain AIMessage."""
    text_parts: list[str] = []
    tool_calls: list[dict] = []

    for block in data.get("content", []):
        if block.get("type") == "text":
            text_parts.append(block["text"])
        elif block.get("type") == "tool_use":
            tool_calls.append({
                "id": block["id"],
                "name": block["name"],
                "args": block.get("input", {}),
                "type": "tool_call",
            })

    text = "\n".join(text_parts)
    if tool_calls:
        return AIMessage(content=text, tool_calls=tool_calls)
    return AIMessage(content=text)


def _tool_to_bedrock(tool: Any) -> dict:
    """Convert a LangChain tool or OpenAI-format dict to Bedrock Anthropic tool spec."""
    if isinstance(tool, BaseTool):
        schema = tool.args_schema.schema() if tool.args_schema else {"type": "object", "properties": {}, "required": []}
        schema.pop("title", None)
        return {"name": tool.name, "description": tool.description or "", "input_schema": schema}

    if isinstance(tool, dict):
        if "function" in tool:
            fn = tool["function"]
            params = fn.get("parameters", {"type": "object", "properties": {}, "required": []})
            return {"name": fn["name"], "description": fn.get("description", ""), "input_schema": params}
        if "input_schema" in tool:
            return tool

    return {"name": str(tool), "description": "", "input_schema": {"type": "object", "properties": {}}}


class AICoreClaudeChatModel(BaseChatModel):
    """LangChain BaseChatModel backed by SAP AI Core /invoke (Bedrock Anthropic format)."""

    api_base: str
    api_key: str
    resource_group: str = "default"
    temperature: float = 0.0
    max_tokens: int = 4096
    bound_tools: list = Field(default_factory=list, exclude=True)

    def bind_tools(self, tools: Sequence, tool_choice: Any = None, **kwargs) -> "AICoreClaudeChatModel":
        bedrock_tools = [_tool_to_bedrock(t) for t in tools]
        return self.model_copy(update={"bound_tools": bedrock_tools})

    def _build_body(self, messages: list[BaseMessage], stop: list[str] | None = None) -> dict:
        system, converted = _lc_to_bedrock(messages)
        body: dict = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": self.max_tokens,
            "messages": converted,
        }
        if system:
            body["system"] = system
        if stop:
            body["stop_sequences"] = stop
        if self.bound_tools:
            body["tools"] = self.bound_tools
        return body

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self._agenerate(messages, stop=stop))
        finally:
            loop.close()

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        body = self._build_body(messages, stop=stop)
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.api_base}/invoke",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "AI-Resource-Group": self.resource_group,
                    "Content-Type": "application/json",
                },
                json=body,
            )
            resp.raise_for_status()

        ai_msg = _bedrock_to_lc(resp.json())
        return ChatResult(generations=[ChatGeneration(message=ai_msg)])

    @property
    def _llm_type(self) -> str:
        return "aicore-claude"
