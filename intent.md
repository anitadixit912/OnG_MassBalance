# Refinery Mass Balance Reconciliation Agent

## Business challenge

Mass balance data is fragmented across LIMS, SAP IS-Oil & Gas (OGS_650), tank gauges, and flow meters — requiring heavy manual consolidation. Engineers spend 2–4 days per month gathering, validating, and reconciling data before reports can be compiled. Rules-based systems cannot handle the contextual judgment needed for unaccounted losses, measurement discrepancies, and unit reconciliation failures. Late reporting limits timely corrective action on process inefficiencies, compliance gaps, or yield optimisation.

## Business Goals & Success Criteria

| Metric | Baseline | Target | Timeline | Process / Capability | Source |
|--------|----------|--------|----------|----------------------|--------|
| Reporting cycle time | 2–4 days | Same-day automated reporting | Go-live | Hydrocarbon mass balance reporting | user |
| UAL detection latency | Monthly review | Real-time continuous monitoring | Go-live | Unaccounted loss monitoring | user |
| Data accuracy (error rate) | Manual / unknown | Near-zero transcription errors | 3 months post go-live | Data validation & anomaly detection | user |
| Engineer hours on data gathering | ~2–4 days/month per engineer | >70% reduction | 3 months post go-live | Mass balance reconciliation cycle | user |

## Key Milestones

1. **Data Ingestion Live** — SAP IS-Oil & Gas (OGS_650) data successfully pulled via OGS_S4 BTP destination; all five data domains (TANK, MAT, MOV, PHYS, BOOK) available to agent
2. **Validation Engine Operational** — Completeness, consistency, and referential integrity checks running; validation failures surfaced before any calculation proceeds
3. **Mass Balance Calculation Validated** — Daily and monthly closing stock formula (Opening + Receipts − Issues − Consumption ± Transfers ± Adjustments) verified against known historical periods at Plant, Tank, and Material level
4. **Variance & Exception Pipeline Active** — Tolerance matrix applied; severity classification (INFO / ADVISORY / WARNING / CRITICAL) and root cause categories (MC / TX / MD / TF / PL / SY) operational; exception report with evidence package generated
5. **Human Approval Gates Deployed** — Exception report review and SAP stock correction approval workflow live; no auto-posting confirmed; full audit log active

## Business Architecture (RBA)

### End-to-End Process

Hydrocarbon Supply and Refining

### Process Hierarchy

```
Hydrocarbon Supply and Refining (E2E)
└── Deliver Product to Fulfill (hydrocarbon supply and distribution)
    └── Manage hydrocarbon logistics and inventory (BPS-348_007)
        └── Manage inventory operations
    └── Manage hydrocarbon supply and primary distribution (BPS-355_001)
        └── Balance inventory
└── Make to Inspect (hydrocarbon refining)
    └── Manage warehouse and inventory — inbound, intra-company (BPS-348_004)
        └── Manage stock transfers
└── Manage Fulfillment
    └── Manage supply chain data and operations (BPS-342_002)
        └── Manage inventory and warehouse operations
```

### Summary

The refinery mass balance challenge maps to the Hydrocarbon Supply and Refining E2E, spanning hydrocarbon logistics & inventory management, supply & primary distribution (balance inventory), and inbound warehouse & inventory management for material movements. The bulk petro-chemicals variant applies, covering daily/monthly reconciliation cycles and SAP-posted corrections.

## Fit Gap Analysis

| Requirement (business) | Standard asset(s) found | API ORD ID | MCP Server ORD ID | MCP Server Version | Gap? | Notes / assumptions |
|------------------------|-------------------------|------------|-------------------|--------------------|------|---------------------|
| Read material stock levels from SAP | Material Stock - Read | `sap.s4:apiResource:API_MATERIAL_STOCK_SRV:v1` | — | — | No | No MCP server found; agent calls API directly via OGS_S4 destination |
| Read & create physical inventory documents | Physical Inventory Document | `sap.s4:apiResource:CE_PHYSICALINVENTORYDOCUMENT_0001:v1` | — | — | No | No MCP server found; agent calls API directly |
| Read material movement documents (MSEG/MKPF) | Material Documents - Read, Create | `sap.s4:apiResource:API_MATERIAL_DOCUMENT_SRV:v1` | — | — | No | No MCP server found; agent calls API directly |
| Stock transport order management | Stock Transport Order | `sap.s4:apiResource:CE_STOCKTRANSPORTORDER_0001:v1` | — | — | No | No MCP server found; agent calls API directly |
| Process order confirmation (yield/consumption) | Process Order Confirmation | `sap.s4:apiResource:API_PROC_ORDER_CONFIRMATION_2_SRV:v1` | — | — | No | No MCP server found; agent calls API directly |
| Hydrocarbon quantity/unit conversion | Quantity Conversion Defaults | `sap.s4:apiResource:OP_QUANTITYCONVERSIONDEFAULTS_0001:v1` | — | — | No | Covers volume → MT, API gravity, density conversions |
| LIMS integration (product quality, density) | — | — | — | — | Yes | No standard SAP API available; custom connector required |
| SCADA / tank gauge integration (real-time meter readings) | — | — | — | — | Yes | No standard SAP API; custom connector or OPC-UA bridge required |
| Root cause classification (MC/TX/MD/TF/PL/SY) | — | — | — | — | Yes | Custom AI reasoning capability; no standard SAP asset |
| Human approval workflow for SAP corrections | — | — | — | — | Yes | Custom approval gate built into agent; no standard asset |

### Key findings

- SAP S/4HANA IS-Oil & Gas (OGS_650) via BTP destination OGS_S4 is the primary data source, accessed through standard OData APIs (material stock, physical inventory, material documents, process orders)
- No pre-built MCP servers exist for any of the discovered APIs; the agent will call all SAP APIs directly via the OGS_S4 BTP destination using HTTP/OData
- LIMS and SCADA/tank gauge integrations are gaps requiring custom connectors or adapters — these are a key build risk
- Root cause classification across six categories (MC/TX/MD/TF/PL/SY) and human-in-the-loop approval governance are fully custom AI capabilities
- SAP S/4HANA Cloud Private Edition covers the core capabilities: Stock Reconciliation (SC5299), Physical Inventory Management for Hydrocarbons (SC5303), Hydrocarbon Quantity Conversion (SC5281), and Internal Goods Movement Management (SC5484)
- The agent must never auto-post SAP corrections — every adjustment requires named-user approval before any SAP document is created or modified

## Recommendations

### Refinery Mass Balance Reconciliation — AI Agent on SAP BTP

#### Executive Summary

Pro-code Python orchestrator agent with 5 sub-agents on SAP AI Core / SAP BTP

#### Recommended Solution

A Python-based multi-agent system (A2A protocol) deployed on SAP AI Core / SAP BTP, comprising:

- **Orchestrator Agent** — goal decomposition, dynamic replanning on failure, human-in-the-loop escalation, audit logging
- **Data Collection Sub-Agent** — pulls readings from SAP IS-Oil & Gas (OGS_650) via OGS_S4 destination; covers TANK, MAT, MOV, PHYS, BOOK data domains (MARA, MARC, MSEG, MARD, MKPF, MI01/MI07)
- **Validation & Anomaly Sub-Agent** — checks completeness, consistency, referential integrity; detects sensor faults, missing readings, statistical outliers; blocks progression on failure
- **Calculation & Reconciliation Sub-Agent** — applies formula (Closing = Opening + Receipts − Issues − Consumption ± Transfers ± Adjustments) at Plant, Tank, and Material level; applies temperature/density/meter factor/water bottom corrections before Physical vs. Book comparison
- **Exception Management Sub-Agent** — applies configurable tolerance matrix; classifies severity (INFO/ADVISORY/WARNING/CRITICAL); investigates via MSEG/MKPF drill-down; assigns root cause (MC/TX/MD/TF/PL/SY)
- **Report Generation Sub-Agent** — builds structured exception report (Exception ID, Period, Plant/Tank/Mat, Variance MT/%, Severity, Root Cause, Supporting Docs, Recommendation, Status) and Executive Summary KPI dashboard

Human approval gates are enforced at Step 9 (exception report review) and Step 10 (SAP stock correction sign-off). No SAP document is created or modified without explicit named-user approval.

#### Affected User Roles

- Refinery Engineer — reviews daily/monthly exception reports, investigates flagged variances
- Plant Manager — approves corrections at plant level, reviews KPI dashboard
- Compliance Officer — reviews audit trail, monitors regulatory thresholds

#### Recommended solution category

AI Agent

#### Intent fit
92%
