import asyncio, json, logging, os
from typing import Any
import httpx
from langchain_core.tools import ToolException
logger = logging.getLogger(__name__)
_MCP_RETRY_ATTEMPTS = 4; _MCP_RETRY_DELAY = 4.0
MCP_CALL_TIMEOUT_SECONDS = float(os.environ.get("MCP_CALL_TIMEOUT_SECONDS", 30.0))
MCP_MAX_RESPONSE_CHARS = int(os.environ.get("MCP_MAX_RESPONSE_CHARS", 30_000))
def minify_json(text):
    try: return json.dumps(json.loads(text), separators=(",", ":"), ensure_ascii=False)
    except: return text
def truncate_response(text, max_chars=MCP_MAX_RESPONSE_CHARS):
    if len(text) <= max_chars: return text
    w = text[:max_chars]; f = int(max_chars * 0.9)
    b = max(w.rfind("\n"), w.rfind(","), w.rfind(" "))
    return (w[:b] if b >= f else w) + "\n...[truncated]"
async def call_mcp_tool_with_retry(agw, mcp_tool, user_token=None, **kwargs):
    if mcp_tool is None: raise ValueError("Tool cannot be None")
    last = None
    for attempt in range(1 + _MCP_RETRY_ATTEMPTS):
        try:
            p = {"tool": mcp_tool, **kwargs}
            if user_token: p["user_token"] = user_token
            r = await asyncio.wait_for(agw.call_mcp_tool(**p), timeout=MCP_CALL_TIMEOUT_SECONDS)
            if r is None: raise RuntimeError(f"None result for {mcp_tool.name}")
            return truncate_response(minify_json(str(r)))
        except Exception as e:
            last = e
            if attempt < _MCP_RETRY_ATTEMPTS: await asyncio.sleep(_MCP_RETRY_DELAY)
    raise ToolException(f"Tool '{mcp_tool.name}' failed: {last}") from last
