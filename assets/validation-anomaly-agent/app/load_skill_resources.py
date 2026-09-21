import re
from pathlib import Path
import yaml
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

_SKILLS_DIR = (Path(__file__).parent / "skills").resolve()

async def _load(path: str) -> str:
    try: target = (_SKILLS_DIR / path).resolve()
    except: return f"Error: invalid path '{path}'"
    if _SKILLS_DIR not in target.parents: return f"Error: invalid path '{path}'"
    if target.is_dir(): target = target / "SKILL.md"
    if not target.exists(): return f"Error: '{path}' not found"
    return target.read_text(encoding="utf-8")

class _LoadInput(BaseModel):
    path: str = Field(description="Skill folder name or path")

def get_load_skill_resource_tool():
    if not _SKILLS_DIR.is_dir() or not any(_SKILLS_DIR.iterdir()): return []
    return [StructuredTool(name="load", description="Load runtime skills.", args_schema=_LoadInput, coroutine=_load)]
