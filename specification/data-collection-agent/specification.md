# Specification: data-collection-agent

> **Guidelines**: Read [guidelines.md](../guidelines.md), [guidelines-agent.md](../guidelines-agent.md), [guidelines-agent-python.md](../guidelines-agent-python.md), [guidelines-agent-mcp.md](../guidelines-agent-mcp.md) before executing.

---

## Role
Pulls live hydrocarbon data from SAP IS-Oil & Gas (OGS_650) via the OGS_S4 BTP destination.
Covers all 6 data domains: TANK, MAT, MOV, PHYS, BOOK, TRANSFERS.
Returns structured data packages to the Orchestrator.

---

## Basic Setup

- [x] Bootstrap agent in `assets/data-collection-agent/` using `sap-agent-bootstrap`
- [x] Write `app/main.py` — A2A server, agent card: "Data Collection Agent"
- [x] Write `app/agent.py` — system prompt focused on live data fetching only; 9 decorators
- [x] Write `app/agent_executor.py`, `app/mcp_providers/agw.py`, supporting files
- [x] Write `requirements.txt` (Dockerfile intentionally omitted — CF deployment uses Python buildpack)

## System Prompt Requirements

- [x] **TANK domain**: fetch material stock levels via Material Stock MCP server (`list_a_matlstkinacctmod_for_api_material_stock_srv` filtered by Plant and StorageLocation)
- [x] **MAT domain**: fetch material master base units via Material Stock MCP server (`list_a_materialstock_for_api_material_stock_srv`)
- [x] **MOV domain**: fetch goods movement history via Material Document MCP server (`list_a_materialdocumentheader_for_api_material_document_srv` + items, filtered by PostingDate and Plant)
- [x] **PHYS domain**: fetch physical inventory documents via Physical Inventory Document MCP server (filtered by Plant, FiscalYear, StorageLocation)
- [x] **BOOK domain**: fetch process order confirmations via Process Order Confirmation MCP server (filtered by Plant, PostingDate, Material)
- [x] **TRANSFERS**: fetch inter-plant stock transport orders via Stock Transport Order MCP server (filtered by SupplyingPlant and CreationDate)
- [x] Live data only — never fabricate or cache SAP data
- [x] Set page size max 100 on all paginated tool calls
- [x] Return structured JSON data package with all 6 domains populated

## MCP Wiring

- [x] All 5 MCP server ORD IDs declared in `asset.yaml` under `requires`
- [ ] Verify `get_mcp_tools()` loads all 5 MCP servers at runtime (requires live BTP environment)

## Business Instrumentation

- [x] Log `M1.achieved: DATA_INGESTION_LIVE — plant={plant} period={period} domains=TANK,MAT,MOV,PHYS,BOOK,TRANSFERS` when all 6 domains fetched
- [x] Log `M1.missed: DATA_INGESTION_FAILED — plant={plant} period={period} missing_domains={list}` on any domain failure

## Testing

- [x] `tests/test_tank_domain.py` — mock Material Stock MCP; verify TANK data fetched per plant/storage location (covered in `tests/test_agent.py`)
- [x] `tests/test_mat_domain.py` — mock Material Stock MCP; verify MAT base units returned (covered in `tests/test_agent.py`)
- [x] `tests/test_mov_domain.py` — mock Material Document MCP; verify MOV history fetched by date range (covered in `tests/test_agent.py`)
- [x] `tests/test_phys_domain.py` — mock Physical Inventory MCP; verify PHYS documents fetched by fiscal year (covered in `tests/test_agent.py`)
- [x] `tests/test_book_domain.py` — mock Process Order Confirmation MCP; verify BOOK confirmations fetched (covered in `tests/test_agent.py`)
- [x] `tests/test_transfers_domain.py` — mock Stock Transport Order MCP; verify inter-plant transfers fetched (covered in `tests/test_agent.py`)
- [x] `tests/test_integration.py` — end-to-end: trigger data collection → all 6 domain fetches → structured JSON output (covered in `tests/test_agent.py`)
- [ ] Run `pytest` from `assets/data-collection-agent/`; coverage ≥ 70%; `test_report.json` produced (requires live run)
