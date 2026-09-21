import asyncio, logging, os, re
from dataclasses import dataclass
from functools import wraps
from typing import Any
from langchain_core.tools import BaseTool, StructuredTool
logger = logging.getLogger(__name__)
_PATTERNS = [(re.compile(p, re.IGNORECASE), n) for p, n in [
    (r"(ignore|disregard)\s+(all\s+)?(previous|prior|above|your)?\s*(instructions|rules|guidelines)", "instruction_override"),
    (r"you\s+are\s+now\s+(a|an)\s+", "role_manipulation"),
    (r"(reveal|show|output|print)\s+(your\s+)?(system\s+prompt|instructions)", "prompt_disclosure"),
    (r"<\|im_start\|>", "delimiter_escape"), (r"\[SYSTEM\]", "delimiter_escape"),
]]
@dataclass
class ScanResult:
    is_suspicious: bool; pattern_matched: str | None; original_content: str; sanitized_content: str

def scan_content(content):
    if not content: return ScanResult(False, None, content, content)
    for pattern, name in _PATTERNS:
        if pattern.search(content): return ScanResult(True, name, content, f"[CONTENT BLOCKED: ({name})]")
    return ScanResult(False, None, content, content)

async def scan_tool_result_async(tool_name, result):
    if os.environ.get("PROMPT_INJECTION_DETECTION", "true").lower() != "true": return result
    s = scan_content(result)
    if s.is_suspicious and os.environ.get("PROMPT_INJECTION_MODE", "block").lower() == "block": return s.sanitized_content
    return result

def wrap_tool(tool: BaseTool) -> BaseTool:
    orig = tool.coroutine or tool.func
    if orig is None: return tool
    @wraps(orig)
    async def wrapped(**kw): return await scan_tool_result_async(tool.name, str(await tool.coroutine(**kw) if tool.coroutine else await asyncio.to_thread(tool.func, **kw)) or "")
    return StructuredTool(name=tool.name, description=tool.description, args_schema=tool.args_schema, coroutine=wrapped, handle_tool_error=getattr(tool, "handle_tool_error", True))
