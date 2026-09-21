# Python Agent Implementation Guidelines

## Tech Stack
- Python 3.13, LangChain 1.0+ / LangGraph, A2A protocol
- Asset root: `assets/<asset-name>/`

## Key Constraints
- NEVER use `create_react_agent` — use `from langchain.agents import create_agent`
- No `.env` files — environment variables supplied at runtime
- No `src.` import patterns
- All imports must be peer-level within `app/`

## MCP Tool Loading
```python
from mcp_tools import get_mcp_tools  # always import from mcp_tools, never from sap_cloud_sdk.agentgateway
```

## Business Instrumentation
- Log pattern: `[MILESTONE_ID].[achieved|missed]: [description]`
- Use `@tracer.start_as_current_span` decorator on regular async methods
- NEVER use `with tracer.start_as_current_span(...)` inside async generators (causes GeneratorExit errors)
- Extract business logic from `stream()` into a plain async helper, instrument the helper

## Testing
- All tests go in `assets/<asset-name>/tests/`
- Run as: `pytest` (no args) from asset root
- Coverage must be ≥ 70%
- Mock all LLM calls — AI Core credentials NOT available in tests
- Final `pytest` run (no args) produces `test_report.json`
