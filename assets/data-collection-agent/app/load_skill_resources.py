import re
from pathlib import Path
import yaml
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

_SKILLS_DIR = (Path(__file__).parent / "skills").resolve()
_LOAD_TOOL_NAME = "load"

def _validate_and_parse_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---"):
        raise ValueError("missing frontmatter opening '---'")
    closing_fence = re.search(r"\n---\s*(\n|$)", text[3:])
    if not closing_fence:
        raise ValueError("frontmatter is not closed with '---'")
    meta = yaml.safe_load(text[3: closing_fence.start() + 3]) or {}
    for field in ("name", "description"):
        if field not in meta or not isinstance(meta[field], str):
            raise ValueError(f"frontmatter missing or invalid field '{field}'")
    return meta["name"], meta["description"]

async def _load(path: str) -> str:
    try:
        target = (_SKILLS_DIR / path).resolve()
    except (ValueError, OSError):
        return f"Error: invalid path '{path}'"
    if _SKILLS_DIR not in target.parents:
        return f"Error: invalid path '{path}'"
    if target.is_dir():
        target = target / "SKILL.md"
    if not target.exists():
        return f"Error: '{path}' not found"
    return target.read_text(encoding="utf-8")

class _LoadInput(BaseModel):
    path: str = Field(description="Skill folder name or path to a specific resource")

def get_load_skill_resource_tool() -> list[StructuredTool]:
    if not _SKILLS_DIR.is_dir() or not any(_SKILLS_DIR.iterdir()):
        return []
    lines = ['This tool loads runtime skills. Available:', ""]
    for entry in _SKILLS_DIR.iterdir():
        skill_md = entry / "SKILL.md"
        if not entry.is_dir() or not skill_md.exists():
            continue
        try:
            name, description = _validate_and_parse_frontmatter(skill_md.read_text(encoding="utf-8"))
            lines.append(f"  name: {name} | description: {description} | path: {entry.name}")
        except ValueError:
            pass
    lines.extend(["", "To load: use load(path)"])
    return [StructuredTool(name=_LOAD_TOOL_NAME, description="\n".join(lines), args_schema=_LoadInput, coroutine=_load)]
