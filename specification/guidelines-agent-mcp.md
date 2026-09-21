# MCP Tool Integration Guidelines

## Core Principle
**NEVER call SAP APIs directly.** All API consumption MUST go through MCP servers.

Forbidden: direct HTTP clients (`requests`, `httpx`), hand-rolled OData clients, custom tool files for SAP API access.

## MCP Tool Loading (Python)
```python
from mcp_tools import get_mcp_tools
tools = await get_mcp_tools()
```

## MCP Server Dependencies in asset.yaml
```yaml
requires:
  - name: sap-s4-material-stock-mcp-server
    kind: mcp-server
    ordId: customer.build:apiResource:mass-balance-reconciliation-a37df.sap-s4-material-stock-mcp-server:v1
```

## System Prompt Requirements
- Instruct agent: never fabricate data, always use tools
- Set page size max 100 on all paginated tool calls
- Relay tool errors verbatim

## Mock MCP Configuration
- `conftest.py` sets `IBD_TESTING=true` → agent uses `mcp-mock.json`
- Do NOT branch on `IBD_TESTING` in application code
