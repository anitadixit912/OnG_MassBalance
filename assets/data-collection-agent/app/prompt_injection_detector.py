import asyncio, logging, os, re
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any
from langchain_core.tools import BaseTool, StructuredTool

logger = logging.getLogger(__name__)

class DetectionMode(Enum):
    BLOCK = "block"
    LOG = "log"

@dataclass
class ScanResult:
    is_suspicious: bool
    pattern_matched: str | None
    original_content: str
    sanitized_content: str

_COMPILED_PATTERNS = [(re.compile(p, re.IGNORECASE), n) for p, n in [
    (r"(ignore|disregard)\s+(all\s+)?(previous|prior|above|your)?\s*(instructions|rules|guidelines)", "instruction_override"),
    (r"forget\s+(everything|all)\s+(you\s+)?know", "instruction_override"),
    (r"you\s+are\s+now\s+(a|an)\s+", "role_manipulation"),
    (r"your\s+new\s+(role|persona|identity)\s+is", "role_manipulation"),
    (r"(reveal|show|output|print)\s+(your\s+)?(system\s+prompt|instructions)", "prompt_disclosure"),
    (r"<\|im_start\|>", "delimiter_escape"),
    (r"\[SYSTEM\]", "delimiter_escape"),
    (r"###\s*SYSTEM", "delimiter_escape"),
]]

def scan_content(content: str) -> ScanResult:
    if not content:
        return ScanResult(False, None, content, content)
    for pattern, name in _COMPILED_PATTERNS:
        if pattern.search(content):
            return ScanResult(True, name, content, f"[CONTENT BLOCKED: Suspicious pattern detected ({name})]")
    return ScanResult(False, None, content, content)

async def scan_tool_result_async(tool_name: str, result: str) -> str:
    if os.environ.get("PROMPT_INJECTION_DETECTION", "true").lower() != "true":
        return result
    scan = scan_content(result)
    if scan.is_suspicious:
        mode = DetectionMode.BLOCK if os.environ.get("PROMPT_INJECTION_MODE", "block").lower() == "block" else DetectionMode.LOG
        logger.warning("Prompt injection detected in '%s'. Pattern: %s", tool_name, scan.pattern_matched)
        if mode == DetectionMode.BLOCK:
            return scan.sanitized_content
    return result

def wrap_tool(tool: BaseTool) -> BaseTool:
    original_async = tool.coroutine
    original_sync = tool.func
    if original_async is None and original_sync is None:
        return tool

    @wraps(original_async or original_sync)
    async def wrapped(**kwargs: Any) -> str:
        result = await original_async(**kwargs) if original_async else await asyncio.to_thread(original_sync, **kwargs)
        return await scan_tool_result_async(tool.name, str(result) if result else "")

    return StructuredTool(name=tool.name, description=tool.description, args_schema=tool.args_schema, coroutine=wrapped, handle_tool_error=getattr(tool, "handle_tool_error", True))
