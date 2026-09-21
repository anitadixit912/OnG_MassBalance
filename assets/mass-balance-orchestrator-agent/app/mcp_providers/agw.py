import json, logging, os, base64
from contextvars import ContextVar, Token
from pathlib import Path
from typing import Any
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import Field, create_model
try:
    from sap_cloud_sdk.agentgateway import create_client
    from sap_cloud_sdk.agentgateway.converters import mcp_tool_to_langchain
except ImportError:
    create_client = None
    mcp_tool_to_langchain = None
from util import call_mcp_tool_with_retry
logger = logging.getLogger(__name__)
_user_token_context: ContextVar[str | None] = ContextVar("user_token", default=None)
_MOCK_FILE = Path(__file__).parent.parent.parent / "mcp-mock.json"
def set_user_token(token): return _user_token_context.set(token)
def get_user_token(): return _user_token_context.get()
def _get_user_token(): return _user_token_context.get()
def _build_mock_tools():
    if not _MOCK_FILE.exists(): return []
    try: mock_data = json.loads(_MOCK_FILE.read_text())
    except Exception: return []
    tools = []
    for _, server in mock_data.get("servers", {}).items():
        for tool_name, tool_def in server.get("tools", {}).items():
            props = tool_def.get("input_schema", {}).get("properties", {}); required = set(tool_def.get("input_schema", {}).get("required", []))
            fd = {fn: ((int if fi.get("type")=="integer" else float if fi.get("type")=="number" else bool if fi.get("type")=="boolean" else str), Field(description=fi.get("description",""))) if fn in required else ((int if fi.get("type")=="integer" else float if fi.get("type")=="number" else bool if fi.get("type")=="boolean" else str), Field(default=None, description=fi.get("description",""))) for fn, fi in props.items()}
            schema = create_model(f"{tool_name}_args", **fd) if fd else create_model(f"{tool_name}_args")
            _r = json.dumps(tool_def.get("mock_response", {}))
            async def _c(_resp=_r, **kw): return _resp
            tools.append(StructuredTool(name=tool_name, description=tool_def.get("description",""), args_schema=schema, coroutine=_c, handle_tool_error=True))
    return tools
async def get_mcp_tools():
    if os.environ.get("IBD_TESTING") == "1": return _build_mock_tools()
    agw = create_client(); mcp = await agw.list_mcp_tools(user_token=_get_user_token)
    if not mcp: return []
    def _mk(t):
        async def call(**kw): return await call_mcp_tool_with_retry(agw, t, user_token=_get_user_token(), **kw)
        return call
    return sorted([mcp_tool_to_langchain(t, _mk(t), _get_user_token) for t in mcp], key=lambda t: t.name)
def get_user_sub():
    token = _user_token_context.get()
    if not token:
        if os.environ.get("IBD_TESTING") == "1": return "unknown"
        raise ValueError("No user token")
    try:
        seg = token.split(".")[1]; pad = 4 - len(seg) % 4
        if pad != 4: seg += "=" * pad
        return json.loads(base64.urlsafe_b64decode(seg)).get("sub", "unknown")
    except Exception: return "unknown"
def reset_user_token(token: Token): _user_token_context.reset(token)
