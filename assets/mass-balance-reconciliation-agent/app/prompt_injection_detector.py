import asyncio
import logging
import os
import re
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


_INJECTION_PATTERNS = [
    (r"(ignore|disregard)\s+(all\s+)?(previous|prior|above|your)?\s*(instructions|rules|guidelines)", "instruction_override"),
    (r"forget\s+(everything|all)\s+(you\s+)?know", "instruction_override"),
    (r"you\s+are\s+now\s+(a|an)\s+", "role_manipulation"),
    (r"your\s+new\s+(role|persona|identity)\s+is", "role_manipulation"),
    (r"from\s+now\s+on\s+you\s+(are|will|must)", "role_manipulation"),
    (r"(reveal|show|output|print)\s+(your\s+)?(system\s+prompt|instructions)", "prompt_disclosure"),
    (r"what\s+are\s+your\s+(system\s+)?instructions", "prompt_disclosure"),
    (r"<\|im_start\|>", "delimiter_escape"),
    (r"<\|im_end\|>", "delimiter_escape"),
    (r"\[SYSTEM\]", "delimiter_escape"),
    (r"\[INST\]", "delimiter_escape"),
    (r"###\s*SYSTEM", "delimiter_escape"),
    (r"===\s*(NEW\s+)?INSTRUCTIONS", "delimiter_escape"),
]

_COMPILED_PATTERNS = [(re.compile(pattern, re.IGNORECASE), name) for pattern, name in _INJECTION_PATTERNS]


def _get_detection_enabled() -> bool:
    return os.environ.get("PROMPT_INJECTION_DETECTION", "true").lower() == "true"


def _get_detection_mode() -> DetectionMode:
    mode = os.environ.get("PROMPT_INJECTION_MODE", "block").lower()
    return DetectionMode.BLOCK if mode == "block" else DetectionMode.LOG


def scan_content(content: str) -> ScanResult:
    if not content:
        return ScanResult(is_suspicious=False, pattern_matched=None, original_content=content, sanitized_content=content)
    for pattern, name in _COMPILED_PATTERNS:
        if pattern.search(content):
            return ScanResult(is_suspicious=True, pattern_matched=name, original_content=content, sanitized_content=f"[CONTENT BLOCKED: Suspicious pattern detected ({name})]")
    return ScanResult(is_suspicious=False, pattern_matched=None, original_content=content, sanitized_content=content)


async def scan_tool_result_async(tool_name: str, result: str) -> str:
    if not _get_detection_enabled():
        return result
    scan = scan_content(result)
    if scan.is_suspicious:
        mode = _get_detection_mode()
        logger.warning("Prompt injection detected in tool '%s'. Pattern: %s. Mode: %s", tool_name, scan.pattern_matched, mode.value)
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

    return StructuredTool(
        name=tool.name, description=tool.description, args_schema=tool.args_schema,
        coroutine=wrapped, handle_tool_error=getattr(tool, "handle_tool_error", True),
    )
