# Specification — Refinery Mass Balance Reconciliation — Multi-Agent

> **Guidelines**: Read [guidelines.md](./guidelines.md) before executing ANY tasks below.

Check off items as completed.

---

## Solution Setup

- [x] Create solution structure: `solution.yaml` + `assets/` folder
- [x] Create 5 MCP server assets (one per SAP OData API via OGS_S4 destination)
- [x] Create 5 sub-agent assets + 1 orchestrator agent asset
- [x] Validate all `asset.yaml` and `solution.yaml` files exist and are well-formed

## MCP Server Assets

- [x] `assets/sap-s4-material-stock-mcp-server/` — `API_MATERIAL_STOCK_SRV:v1` via OGS_S4
- [x] `assets/sap-s4-material-document-mcp-server/` — `API_MATERIAL_DOCUMENT_SRV:v1` via OGS_S4
- [x] `assets/sap-s4-physical-inventory-mcp-server/` — `CE_PHYSICALINVENTORYDOCUMENT_0001:v1` via OGS_S4
- [x] `assets/sap-s4-stock-transport-order-mcp-server/` — `CE_STOCKTRANSPORTORDER_0001:v1` via OGS_S4
- [x] `assets/sap-s4-proc-order-confirmation-mcp-server/` — `API_PROC_ORDER_CONFIRMATION_2_SRV:v1` via OGS_S4
- [x] All `translation.json` files written from real API specs (no Z programs, no mock data)

## Agent Asset Implementation

### Sub-agents

- [ ] Execute [specification/data-collection-agent/specification.md](./data-collection-agent/specification.md)
- [ ] Execute [specification/validation-anomaly-agent/specification.md](./validation-anomaly-agent/specification.md)
- [ ] Execute [specification/calculation-reconciliation-agent/specification.md](./calculation-reconciliation-agent/specification.md)
- [ ] Execute [specification/exception-management-agent/specification.md](./exception-management-agent/specification.md)
- [ ] Execute [specification/report-generation-agent/specification.md](./report-generation-agent/specification.md)

### Orchestrator

- [ ] Execute [specification/mass-balance-orchestrator-agent/specification.md](./mass-balance-orchestrator-agent/specification.md)

### Cross-agent compatibility check

- [ ] Verify all A2A ORD IDs in orchestrator `asset.yaml` `requires` match the `provides.apis[].ordId` in each sub-agent `asset.yaml`
- [ ] Verify all sub-agent A2A endpoints respond at `/.well-known/agent.json`
- [ ] Verify data shapes passed between orchestrator → sub-agents are consistent (plant, period, domain data)

## Deployment

- [ ] Run deploy via `deploy_solution`
- [ ] Verify orchestrator registers at `/.well-known/agent.json`
- [ ] Verify all 5 sub-agents are reachable by orchestrator via A2A
- [ ] Verify all 5 MCP servers are discoverable via Agent Gateway
- [ ] Confirm OGS_S4 destination resolves to OGS_650 successfully
