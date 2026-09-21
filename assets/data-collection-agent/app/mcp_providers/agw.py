import json
import logging
import os
import base64
from contextvars import ContextVar, Token
from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import Field, create_model
from sap_cloud_sdk.agentgateway import create_client
from sap_cloud_sdk.agentgateway.converters import mcp_tool_to_langchain

from util import call_mcp_tool_with_retry

logger = logging.getLogger(__name__)

_user_token_context: ContextVar[str | None] = ContextVar("user_token", default=None)
_MOCK_FILE = Path(__file__).parent.parent.parent / "mcp-mock.json"

def set_user_token(token: str | None) -> Token:
    return _user_token_context.set(token)

def get_user_token() -> str | None:
    return _user_token_context.get()

def _get_user_token() -> str:
    return _user_token_context.get()

def _build_mock_tools() -> list[BaseTool]:
    if not _MOCK_FILE.exists():
        return []
    try:
        mock_data = json.loads(_MOCK_FILE.read_text())
    except Exception:
        return []
    tools: list[BaseTool] = []
    for _server_slug, server in mock_data.get("servers", {}).items():
        for tool_name, tool_def in server.get("tools", {}).items():
            description = tool_def.get("description", "")
            mock_response = tool_def.get("mock_response", {})
            input_schema = tool_def.get("input_schema", {})
            props = input_schema.get("properties", {})
            required_fields = set(input_schema.get("required", []))
            field_definitions: dict[str, Any] = {}
            for field_name, field_info in props.items():
                json_type = field_info.get("type", "string")
                python_type: type = int if json_type == "integer" else float if json_type == "number" else bool if json_type == "boolean" else str
                if field_name in required_fields:
                    field_definitions[field_name] = (python_type, Field(description=field_info.get("description", "")))
                else:
                    field_definitions[field_name] = (python_type, Field(default=None, description=field_info.get("description", "")))
            args_schema = create_model(f"{tool_name}_args", **field_definitions) if field_definitions else create_model(f"{tool_name}_args")
            _response = json.dumps(mock_response)
            async def _coroutine(_resp: str = _response, **kwargs: Any) -> str:
                return _resp
            tools.append(StructuredTool(name=tool_name, description=description, args_schema=args_schema, coroutine=_coroutine, handle_tool_error=True))
    return tools

async def get_mcp_tools() -> list[BaseTool]:
    if os.environ.get("IBD_TESTING") == "1":
        return _build_mock_tools()
    agw_client = create_client()
    mcp_tools = await agw_client.list_mcp_tools(user_token=_get_user_token)
    if not mcp_tools:
        return []
    def _make_caller(t: Any):
        async def call(**kwargs: Any) -> str:
            return await call_mcp_tool_with_retry(agw_client, t, user_token=_get_user_token(), **kwargs)
        return call
    return sorted([mcp_tool_to_langchain(t, _make_caller(t), _get_user_token) for t in mcp_tools], key=lambda t: t.name)

def get_user_sub() -> str:
    token = _user_token_context.get()
    if not token:
        if os.environ.get("IBD_TESTING") == "1":
            return "unknown"
        raise ValueError("No user token in context")
    try:
        payload_segment = token.split(".")[1]
        padding = 4 - len(payload_segment) % 4
        if padding != 4:
            payload_segment += "=" * padding
        payload = json.loads(base64.urlsafe_b64decode(payload_segment))
        sub = payload.get("sub")
        if not sub:
            raise ValueError("JWT payload contains no 'sub' claim")
        return sub
    except Exception as e:
        raise ValueError(f"Failed to decode JWT payload: {e}") from e

def reset_user_token(token: Token) -> None:
    _user_token_context.reset(token)
