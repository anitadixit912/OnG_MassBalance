# Product Requirements Document (PRD)

**Title:** Refinery Mass Balance Reconciliation Agent  
**Date:** 2026-09-21  
**Owner:** Refinery Operations / SAP Centre of Excellence  
**Solution Category:** AI Agent

---

## Product Purpose & Value Proposition

**Elevator Pitch:**  
Refinery engineers spend 2–4 days per month manually consolidating hydrocarbon mass balance data from SAP IS-Oil & Gas, LIMS, tank gauges, and flow meters. This AI agent automates that cycle — delivering same-day reconciliation reports, real-time unaccounted loss detection, and human-approved SAP corrections.

**Business Need:**  
Mass balance data is fragmented across multiple systems. Rules-based systems cannot handle the contextual judgement needed for unaccounted losses, measurement discrepancies, and unit reconciliation failures. Late reporting limits timely corrective action on process inefficiencies, compliance gaps, and yield optimisation.

**Expected Value:**  
- Reporting cycle time reduced from 2–4 days to same-day automated reporting
- Real-time continuous monitoring of unaccounted losses (vs. monthly review today)
- Near-zero transcription errors (vs. manual / unknown baseline)
- Engineer time on data gathering reduced by more than 70% within 3 months of go-live

**Product Objectives (Prioritised):**
1. Automate daily and monthly mass balance reconciliation using live SAP S/4HANA data via OGS_S4 → OGS_650
2. Surface variance exceptions with severity classification and root cause investigation in real time
3. Enforce human approval gates — no SAP correction is ever posted without named-user sign-off
4. Reduce engineer effort on data gathering by more than 70% within 3 months of go-live

---

## Business Metrics

| Metric | Baseline | Target | Timeline | Process / Capability | Source |
|--------|----------|--------|----------|----------------------|--------|
| Reporting cycle time | 2–4 days | Same-day automated reporting | Go-live | Hydrocarbon mass balance reporting | user |
| UAL detection latency | Monthly review | Real-time continuous monitoring | Go-live | Unaccounted loss monitoring | user |
| Data accuracy (error rate) | Manual / unknown | Near-zero transcription errors | 3 months post go-live | Data validation & anomaly detection | user |
| Engineer hours on data gathering | ~2–4 days/month per engineer | >70% reduction | 3 months post go-live | Mass balance reconciliation cycle | user |

---

## User Profiles & Personas

### Primary Persona: Refinery Engineer

Ahmed is a 34-year-old process engineer at a petroleum refinery responsible for daily and monthly hydrocarbon mass balance reporting. He manages data from tank gauges, flow meters, LIMS, and SAP IS-Oil & Gas. He currently spends 2–4 days per month manually gathering, validating, and reconciling data before reports can be compiled. He is technically proficient with SAP but frustrated by the time lost to data consolidation that should be automated. His success measure: a reconciliation report he can trust, produced on the same day, with clear explanations for any variance.

### Secondary Persona: Plant Manager

Priya is a 47-year-old plant operations manager who needs to approve stock corrections and review KPI dashboards before any SAP document is posted. She does not run the calculations herself but is accountable for the accuracy of inventory records. She needs a clear exception report with evidence before she approves anything — and she needs confidence that no correction has been posted without her sign-off.

### Other User Types

- **Compliance Officer**: Reviews the full audit trail; monitors regulatory thresholds; requires immutable logs of every approval and correction.

---

## User Goals & Tasks

### For Refinery Engineer:

**Goals:**
- Produce a validated daily mass balance report without manual data gathering
- Identify and investigate unaccounted losses in real time
- Submit proposed SAP corrections for approval with supporting evidence

**Key Tasks:**
- Trigger daily/monthly reconciliation run for a given plant and period
- Review exception report flagged by the agent
- Investigate CRITICAL and WARNING variances using drill-down into movement history
- Submit approved corrections for Plant Manager sign-off

### For Plant Manager:

**Goals:**
- Approve or reject SAP stock corrections with full evidence
- Monitor plant-level KPI dashboard

**Key Tasks:**
- Review exception report and evidence package
- Provide named-user approval (or rejection) for each proposed correction
- Review executive KPI summary

---

## Product Principles

1. **Live data only**: The agent must never fabricate, estimate, or cache SAP data. Every reading is fetched live from OGS_650 via the OGS_S4 BTP destination.
2. **Human in the loop**: The agent proposes; humans approve. No SAP document is created, modified, or cancelled without explicit named-user sign-off in the conversation.
3. **Pipeline halt on failure**: If data validation fails at any stage, the reconciliation pipeline stops and surfaces the issue before any calculation proceeds.
4. **Evidence before action**: Every exception report must include supporting document numbers, quantities, and movement history before a correction is proposed.
5. **Immutable audit trail**: Every approval, rejection, and correction is logged with timestamp, username, and role — append-only, non-deletable.

---

## Goals and Non-Goals

### Goals (In Scope)

- Automated daily and monthly mass balance calculation at Plant, Tank, and Material level
- Data validation across all five domains: TANK, MAT, MOV, PHYS, BOOK
- Variance classification by severity (INFO / ADVISORY / WARNING / CRITICAL) and root cause (MC / TX / MD / TF / PL / SY)
- Structured exception report with evidence package
- Human approval gate for all proposed SAP corrections
- Full audit log of all approvals and corrections

### Non-Goals (Out of Scope)

- LIMS integration (no standard SAP API available — custom connector required in a future phase)
- SCADA / tank gauge real-time integration (OPC-UA bridge required in a future phase)
- Automatic posting of SAP corrections without human approval — this is permanently out of scope
- Replacement of SAP IS-Oil & Gas configuration or master data management

---

## Requirements

### Must-Have Requirements

**R1: Live Data Ingestion from SAP IS-Oil & Gas**
- **Problem to Solve**: Engineers waste 2–4 days per month manually collecting data from SAP.
- **User Story**: As a Refinery Engineer, I need the agent to pull live stock, movement, physical inventory, process order, and transfer data from SAP OGS_650 so that reconciliation starts from accurate, real-time figures.
- **Acceptance Criteria**:
  - Given a plant and period, when the reconciliation run is triggered, then the agent fetches live data from all five domains (TANK, MAT, MOV, PHYS, BOOK) via OGS_S4 MCP servers without any manual data entry.
- **Maps to Objective**: Objective 1
- **Priority Rank**: 1

**R2: Data Validation Engine**
- **Problem to Solve**: Calculations based on incomplete or inconsistent data produce unreliable reports.
- **User Story**: As a Refinery Engineer, I need all data to be validated for completeness, consistency, and referential integrity before any calculation proceeds so that the report is trustworthy.
- **Acceptance Criteria**:
  - Given fetched data, when validation fails on any domain, then the pipeline halts and surfaces the specific validation error before any mass balance calculation runs.
- **Maps to Objective**: Objective 1
- **Priority Rank**: 2

**R3: Mass Balance Calculation**
- **Problem to Solve**: Manual calculation is error-prone and time-consuming.
- **User Story**: As a Refinery Engineer, I need the agent to apply the closing stock formula (Opening + Receipts − Issues − Consumption ± Transfers ± Adjustments) at Plant, Tank, and Material level so that I receive an accurate reconciliation figure.
- **Acceptance Criteria**:
  - Given validated data, when the calculation runs, then closing stock is computed at all three levels with temperature/density/meter factor corrections applied before Physical vs. Book comparison.
- **Maps to Objective**: Objective 1
- **Priority Rank**: 3

**R4: Variance & Exception Classification**
- **Problem to Solve**: Engineers cannot prioritise which variances require immediate action.
- **User Story**: As a Refinery Engineer, I need variances classified by severity and root cause so that I can focus investigation on the most critical exceptions first.
- **Acceptance Criteria**:
  - Given a calculated variance, when the tolerance matrix is applied, then each exception receives a severity (INFO / ADVISORY / WARNING / CRITICAL) and a root cause category (MC / TX / MD / TF / PL / SY).
- **Maps to Objective**: Objective 2
- **Priority Rank**: 4

**R5: Structured Exception Report with Evidence Package**
- **Problem to Solve**: Plant Managers cannot approve corrections without clear evidence.
- **User Story**: As a Plant Manager, I need a structured exception report with supporting document numbers and a recommended correction so that I can make an informed approval decision.
- **Acceptance Criteria**:
  - Given classified exceptions, when the report is generated, then each exception includes: Exception ID, Period, Plant/Tank/Material, Variance MT/%, Severity, Root Cause, Supporting Documents, Recommendation, and Status.
- **Maps to Objective**: Objectives 2 and 3
- **Priority Rank**: 5

**R6: Human Approval Gate for SAP Corrections**
- **Problem to Solve**: Incorrect automatic postings create compliance and financial risk.
- **User Story**: As a Plant Manager, I need to explicitly approve each proposed SAP correction before it is posted so that no document is created without my authorisation.
- **Acceptance Criteria**:
  - Given a proposed correction, when the agent presents it for approval, then it waits for explicit named-user confirmation (name + role) before proceeding; no SAP document is created without this confirmation.
- **Maps to Objective**: Objective 3
- **Priority Rank**: 6

**R7: Immutable Audit Log**
- **Problem to Solve**: Compliance officers require a full traceable record of all approvals, rejections, and postings.
- **User Story**: As a Compliance Officer, I need every approval, rejection, and correction logged with timestamp, username, and role so that I can demonstrate regulatory compliance.
- **Acceptance Criteria**:
  - Given any approval or correction event, when it occurs, then a structured log entry is written that is append-only, includes the approver's identity and timestamp, and cannot be deleted or modified.
- **Maps to Objective**: Objective 3
- **Priority Rank**: 7

**R8: Executive KPI Dashboard Summary**
- **Problem to Solve**: Plant Managers need a quick overview without reading every line of the exception report.
- **User Story**: As a Plant Manager, I need an executive KPI summary showing variance %, tanks reconciled, and pending approvals so that I can assess plant health at a glance.
- **Acceptance Criteria**:
  - Given a completed reconciliation run, when the report is generated, then an executive summary is included showing aggregate KPIs: overall variance %, count of exceptions by severity, and count of pending approvals.
- **Maps to Objective**: Objective 4
- **Priority Rank**: 8

---

## Solution Architecture

**Architecture Overview:**  
A Python-based multi-agent system (A2A protocol) deployed on SAP BTP / Joule Studio Runtime. All SAP data access is routed through five MCP servers connected to SAP IS-Oil & Gas (OGS_650) via the OGS_S4 BTP destination. No Z programs. No direct HTTP calls to SAP.

**Key Components:**

**Orchestrator:**
- **Mass Balance Orchestrator Agent** — goal decomposition, pipeline coordination, dynamic replanning on failure, human approval gates, audit logging

**Sub-agents (called by Orchestrator via A2A protocol):**
- **Data Collection Agent** — pulls live data from SAP IS-Oil & Gas (OGS_650) via OGS_S4; covers all five data domains (TANK, MAT, MOV, PHYS, BOOK); uses all 5 MCP servers
- **Validation & Anomaly Agent** — checks completeness, consistency, referential integrity; detects sensor faults, missing readings, statistical outliers; blocks pipeline on failure
- **Calculation & Reconciliation Agent** — applies closing stock formula at Plant, Tank, and Material level with temperature/density/meter factor corrections; performs Physical vs. Book comparison
- **Exception Management Agent** — applies configurable tolerance matrix; classifies severity (INFO/ADVISORY/WARNING/CRITICAL) and root cause (MC/TX/MD/TF/PL/SY); investigates via MSEG/MKPF drill-down; builds evidence packages
- **Report Generation Agent** — builds structured exception reports and Executive KPI dashboard summaries

**MCP Servers (SAP OData APIs via OGS_S4 destination):**
- **Material Stock MCP Server** — exposes `API_MATERIAL_STOCK_SRV` (TANK / MAT domain)
- **Material Document MCP Server** — exposes `API_MATERIAL_DOCUMENT_SRV` (MOV domain — MSEG/MKPF)
- **Physical Inventory Document MCP Server** — exposes `CE_PHYSICALINVENTORYDOCUMENT_0001` (PHYS domain)
- **Process Order Confirmation MCP Server** — exposes `API_PROC_ORDER_CONFIRMATION_2_SRV` (BOOK domain)
- **Stock Transport Order MCP Server** — exposes `CE_STOCKTRANSPORTORDER_0001` (inter-plant transfers)

**Integration Points:**

- SAP IS-Oil & Gas OGS_650 — via OGS_S4 BTP destination — all five data domains — read (and write only after human approval)

**Deployment:**  
SAP BTP Cloud Foundry (eu12 region) via Joule Studio Runtime.

### Agent Extensibility & Instrumentation

**Agent Extensibility:**
- The agent exposes extension points for adding future data connectors (LIMS, SCADA/OPC-UA) without modifying the core reconciliation pipeline
- Root cause classification categories (MC / TX / MD / TF / PL / SY) are configurable via the agent's system prompt
- Tolerance matrix thresholds (INFO / ADVISORY / WARNING / CRITICAL) are configurable per plant

**Business Step Instrumentation:**
All five business milestones emit structured log statements for observability in production:
- `M1.achieved: DATA_INGESTION_LIVE` — all five domains available
- `M1.missed: DATA_INGESTION_FAILED` — one or more domains unavailable
- `M2.achieved: VALIDATION_ENGINE_OPERATIONAL` — all checks passed
- `M2.missed: VALIDATION_FAILED` — pipeline halted, error surfaced
- `M3.achieved: MASS_BALANCE_CALCULATION_VALIDATED` — formula verified
- `M3.missed: CALCULATION_ERROR` — formula could not be applied
- `M4.achieved: VARIANCE_EXCEPTION_PIPELINE_ACTIVE` — tolerance matrix applied, exceptions classified
- `M4.missed: CLASSIFICATION_FAILED` — tolerance matrix could not be applied
- `M5.achieved: HUMAN_APPROVAL_GATES_DEPLOYED` — approval workflow live, no auto-posting confirmed
- `M5.missed: APPROVAL_GATE_BYPASSED` — approval gate not enforced (critical alert)

### Automation & Agent Behaviour

**Automation Level:** Autonomous agent with mandatory human approval gates for all write operations

**Actions the system performs without human approval:**
- Reading live data from all five SAP domains via MCP servers
- Validating data completeness, consistency, and referential integrity
- Calculating mass balance at Plant, Tank, and Material level
- Classifying variances and generating exception reports
- Investigating root causes via MSEG/MKPF drill-down

**Actions that require human review or approval:**
- Creating any SAP material document (goods movement)
- Creating or updating any physical inventory document
- Creating or updating any process order confirmation
- Cancelling any existing SAP document

**Model:** `sap/anthropic--claude-4.5-sonnet` via SAP AI Core / SAP Generative AI Hub

**Knowledge & data sources accessed:**
- SAP IS-Oil & Gas OGS_650 — via OGS_S4 BTP destination — all hydrocarbon inventory and movement data

**Tools or connectors invoked:**
- Material Stock MCP Server — reads tank levels and material stock quantities (read-only)
- Material Document MCP Server — reads movement history; writes corrections after approval
- Physical Inventory Document MCP Server — reads/writes physical inventory (write requires approval)
- Process Order Confirmation MCP Server — reads yield/consumption; writes confirmations after approval
- Stock Transport Order MCP Server — reads/writes inter-plant transfer orders (write requires approval)

**Guardrails & fail-safes:**
- No SAP document is ever created, modified, or cancelled without explicit named-user approval in the conversation
- Pipeline halts on any data validation failure before calculation proceeds
- All tool results are scanned for prompt injection before entering the agent's context
- Circuit breaker skips unresponsive LLM models and falls back to the next in chain
- MCP tool responses are capped at 30,000 characters to prevent context overflow

---

## Milestones

### M1: Data Ingestion Live

- **Description**: SAP IS-Oil & Gas (OGS_650) data successfully pulled via OGS_S4 BTP destination; all five data domains (TANK, MAT, MOV, PHYS, BOOK) available to the agent
- **Achieved when**: Agent successfully fetches at least one record from each of the five MCP servers for the requested plant and period
- **Log on achievement**: `M1.achieved: DATA_INGESTION_LIVE — plant={plant} period={period} domains=TANK,MAT,MOV,PHYS,BOOK`
- **Log on miss**: `M1.missed: DATA_INGESTION_FAILED — plant={plant} period={period} missing_domains={list}`

### M2: Validation Engine Operational

- **Description**: Completeness, consistency, and referential integrity checks running; validation failures surfaced before any calculation proceeds
- **Achieved when**: All validation checks pass for the requested plant and period
- **Log on achievement**: `M2.achieved: VALIDATION_ENGINE_OPERATIONAL — plant={plant} period={period} checks_passed={count}`
- **Log on miss**: `M2.missed: VALIDATION_FAILED — plant={plant} period={period} error={description}`

### M3: Mass Balance Calculation Validated

- **Description**: Daily and monthly closing stock formula verified against known historical periods at Plant, Tank, and Material level
- **Achieved when**: Closing stock calculated at all three levels with corrections applied
- **Log on achievement**: `M3.achieved: MASS_BALANCE_CALCULATION_VALIDATED — plant={plant} period={period} levels=plant,tank,material`
- **Log on miss**: `M3.missed: CALCULATION_ERROR — plant={plant} period={period} error={description}`

### M4: Variance & Exception Pipeline Active

- **Description**: Tolerance matrix applied; severity classification and root cause categories operational; exception report with evidence package generated
- **Achieved when**: All variances classified and exception report produced
- **Log on achievement**: `M4.achieved: VARIANCE_EXCEPTION_PIPELINE_ACTIVE — plant={plant} period={period} exceptions={count} critical={count}`
- **Log on miss**: `M4.missed: CLASSIFICATION_FAILED — plant={plant} period={period} error={description}`

### M5: Human Approval Gates Deployed

- **Description**: Exception report review and SAP stock correction approval workflow live; no auto-posting confirmed; full audit log active
- **Achieved when**: Agent presents correction for approval and waits for named-user confirmation before proceeding
- **Log on achievement**: `M5.achieved: HUMAN_APPROVAL_GATES_DEPLOYED — approver={username} role={role} correction_id={id} timestamp={ts}`
- **Log on miss**: `M5.missed: APPROVAL_GATE_BYPASSED — correction_id={id} timestamp={ts} — CRITICAL ALERT`

---

## Risks, Assumptions, and Dependencies

### Risks

- **LIMS / SCADA integration gap**: No standard SAP API exists for LIMS or tank gauge data. Unaccounted losses caused by sensor faults cannot be fully diagnosed without this data in Phase 1.
- **OGS_S4 destination availability**: All five MCP servers depend on the OGS_S4 BTP destination being correctly configured and the OGS_650 backend being reachable.
- **LLM accuracy on root cause classification**: The six root cause categories (MC / TX / MD / TF / PL / SY) require contextual judgement; occasional misclassification is expected and must be reviewable by the engineer.

### Assumptions

- The OGS_S4 BTP destination is already configured and pointing to OGS_650.
- SAP IS-Oil & Gas data in OGS_650 is current and complete for the requested plant and period.
- Plant Managers have the authority to approve SAP stock corrections within the system.

### Dependencies

- SAP BTP Cloud Foundry environment (eu12) with Joule Studio Runtime entitlement
- SAP AI Core with access to `sap/anthropic--claude-4.5-sonnet`
- OGS_S4 BTP destination configured and accessible
- Standard SAP S/4HANA OData APIs: `API_MATERIAL_STOCK_SRV`, `API_MATERIAL_DOCUMENT_SRV`, `CE_PHYSICALINVENTORYDOCUMENT_0001`, `CE_STOCKTRANSPORTORDER_0001`, `API_PROC_ORDER_CONFIRMATION_2_SRV`

---

## Appendix

### Glossary

| Term | Definition |
|------|-----------|
| UAL | Unaccounted Loss — hydrocarbon volume that cannot be accounted for by known receipts, issues, or consumption |
| OGS_650 | SAP IS-Oil & Gas backend system (the source of truth for all hydrocarbon inventory data) |
| OGS_S4 | BTP destination name used by the agent to connect to OGS_650 |
| TANK | Data domain: tank gauge readings and physical stock levels |
| MAT | Data domain: material master data |
| MOV | Data domain: goods movements (MSEG / MKPF tables) |
| PHYS | Data domain: physical inventory documents |
| BOOK | Data domain: process order confirmations (yield and consumption) |
| MC | Root cause: Meter calibration error |
| TX | Root cause: Transaction / data entry error |
| MD | Root cause: Missing or delayed document |
| TF | Root cause: Transfer in transit (not yet received at destination) |
| PL | Root cause: Process loss (evaporation, sampling, line fill) |
| SY | Root cause: System / interface error |
| MCP | Model Context Protocol — the integration layer connecting the agent to SAP OData APIs |
| A2A | Agent-to-Agent protocol — the communication standard used by the deployed agent |

### References

- SAP IS-Oil & Gas OData APIs: SAP Business Accelerator Hub
- SAP BTP Joule Studio Runtime documentation
- SAP AI Core: Generative AI Hub model catalogue
- SAP S/4HANA Cloud Private Edition: SC5299 (Stock Reconciliation), SC5303 (Physical Inventory for Hydrocarbons), SC5281 (Hydrocarbon Quantity Conversion), SC5484 (Internal Goods Movement Management)
