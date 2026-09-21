# Specification: data-collection-agent

> **Guidelines**: Read [guidelines.md](../guidelines.md), [guidelines-agent.md](../guidelines-agent.md), [guidelines-agent-python.md](../guidelines-agent-python.md), [guidelines-agent-mcp.md](../guidelines-agent-mcp.md) before executing.

---

## Role
Pulls live hydrocarbon data from SAP IS-Oil & Gas (OGS_650) via the OGS_S4 BTP destination.
Covers all 5 data domains: TANK, MAT, MOV, PHYS, BOOK.
Returns structured data packages to the Orchestrator.

---

## Basic Setup

- [ ] Bootstrap agent in `assets/data-collection-agent/` using `sap-agent-bootstrap`
- [ ] Write `app/main.py` — A2A server, agent card: "Data Collection Agent"
- [ ] Write `app/agent.py` — system prompt focused on live data fetching only; 9 decorators
- [ ] Write `app/agent_executor.py`, `app/mcp_providers/agw.py`, supporting files
- [ ] Write `requirements.txt` and `Dockerfile`

## System Prompt Requirements

- [ ] **TANK domain**: fetch material stock levels via Material Stock MCP server (`list_a_matlstkinacctmod_for_api_material_stock_srv` filtered by Plant and StorageLocation)
- [ ] **MAT domain**: fetch material master base units via Material Stock MCP server (`list_a_materialstock_for_api_material_stock_srv`)
- [ ] **MOV domain**: fetch goods movement history via Material Document MCP server (`list_a_materialdocumentheader_for_api_material_document_srv` + items, filtered by PostingDate and Plant)
- [ ] **PHYS domain**: fetch physical inventory documents via Physical Inventory Document MCP server (filtered by Plant, FiscalYear, StorageLocation)
- [ ] **BOOK domain**: fetch process order confirmations via Process Order Confirmation MCP server (filtered by Plant, PostingDate, Material)
- [ ] **TRANSFERS**: fetch inter-plant stock transport orders via Stock Transport Order MCP server (filtered by SupplyingPlant and CreationDate)
- [ ] Live data only — never fabricate or cache SAP data
- [ ] Set page size max 100 on all paginated tool calls
- [ ] Return structured JSON data package with all 5 domains populated

## MCP Wiring

- [x] All 5 MCP server ORD IDs declared in `asset.yaml` under `requires`
- [ ] Verify `get_mcp_tools()` loads all 5 MCP servers at runtime

## Business Instrumentation

- [ ] Log `M1.achieved: DATA_INGESTION_LIVE — plant={plant} period={period} domains=TANK,MAT,MOV,PHYS,BOOK` when all 5 domains fetched
- [ ] Log `M1.missed: DATA_INGESTION_FAILED — plant={plant} period={period} missing_domains={list}` on any domain failure

## Testing

- [ ] `tests/test_tank_domain.py` — mock Material Stock MCP; verify TANK data fetched per plant/storage location
- [ ] `tests/test_mat_domain.py` — mock Material Stock MCP; verify MAT base units returned
- [ ] `tests/test_mov_domain.py` — mock Material Document MCP; verify MOV history fetched by date range
- [ ] `tests/test_phys_domain.py` — mock Physical Inventory MCP; verify PHYS documents fetched by fiscal year
- [ ] `tests/test_book_domain.py` — mock Process Order Confirmation MCP; verify BOOK confirmations fetched
- [ ] `tests/test_transfers_domain.py` — mock Stock Transport Order MCP; verify inter-plant transfers fetched
- [ ] `tests/test_integration.py` — end-to-end: trigger data collection → all 6 domain fetches → structured JSON output
- [ ] Run `pytest` from `assets/data-collection-agent/`; coverage ≥ 70%; `test_report.json` produced
