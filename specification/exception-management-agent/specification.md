# Specification: exception-management-agent

> **Guidelines**: Read [guidelines.md](../guidelines.md), [guidelines-agent.md](../guidelines-agent.md), [guidelines-agent-python.md](../guidelines-agent-python.md), [guidelines-agent-mcp.md](../guidelines-agent-mcp.md) before executing.

---

## Role
Applies the configurable tolerance matrix to variance figures from the Calculation Agent.
Classifies each variance by severity and root cause.
Drills down into MSEG/MKPF movement history to build evidence packages.
Returns a list of classified exceptions with evidence to the Orchestrator.

---

## Basic Setup

- [x] Bootstrap agent in `assets/exception-management-agent/` using `sap-agent-bootstrap`
- [x] Write `app/main.py` — A2A server, agent card: "Exception Management Agent"
- [x] Write `app/agent.py` — system prompt with tolerance matrix and root cause logic; 9 decorators
- [x] Write supporting files, `requirements.txt` (Dockerfile intentionally omitted — CF deployment uses Python buildpack)

## System Prompt Requirements

**Tolerance Matrix:**
- [x] **INFO**: variance < 0.1% AND < 1 MT — record only, no action required
- [x] **ADVISORY**: variance 0.1–0.5% OR 1–5 MT — investigate, recommend review
- [x] **WARNING**: variance 0.5–2.0% OR 5–20 MT — investigate urgently, recommend correction
- [x] **CRITICAL**: variance > 2.0% OR > 20 MT — escalate immediately, halt pipeline for further approval

**Root Cause Categories:**
- [x] **MC** (Meter Calibration): large consistent variance at single meter point
- [x] **TX** (Transaction Error): variance traceable to a single unexpected movement document
- [x] **MD** (Missing Document): gap in movement sequence for a material/period
- [x] **TF** (Transfer in Transit): STO quantity issued but not yet received at destination
- [x] **PL** (Process Loss): variance within expected evaporation/sampling/line fill tolerance
- [x] **SY** (System Error): variance caused by interface failure or duplicate posting

**Evidence Package per exception:**
- [x] Exception ID: `EXC-{YYYY-MM}-{NNNN}`
- [x] Period, Plant, Tank/Material, Variance MT/%, Severity, Root Cause
- [x] Supporting material document numbers (from MSEG drill-down)
- [x] Recommended correction action
- [x] Status: OPEN

## MCP Wiring

- [x] Material Document MCP, Physical Inventory MCP, Stock Transport Order MCP declared in `asset.yaml`
- [ ] Use Material Document MCP to drill down into movement history for root cause investigation (requires live BTP environment)

## Runtime Skills

- [x] Create `app/skills/variance-classification/SKILL.md` — tolerance matrix decision table; severity thresholds
- [x] Create `app/skills/root-cause-investigation/SKILL.md` — step-by-step drill-down procedure per root cause category; MSEG/MKPF query patterns

## Business Instrumentation

- [x] Log `M4.achieved: VARIANCE_EXCEPTION_PIPELINE_ACTIVE — plant={plant} period={period} exceptions={count} critical={count}`
- [x] Log `M4.missed: CLASSIFICATION_FAILED — plant={plant} period={period} error={description}`

## Testing

- [x] `tests/test_severity_info.py` — verify INFO threshold correctly applied (covered in `tests/test_agent.py`)
- [x] `tests/test_severity_advisory.py` — verify ADVISORY threshold (covered in `tests/test_agent.py`)
- [x] `tests/test_severity_warning.py` — verify WARNING threshold (covered in `tests/test_agent.py`)
- [x] `tests/test_severity_critical.py` — verify CRITICAL threshold and escalation flag (covered in `tests/test_agent.py`)
- [x] `tests/test_root_cause_mc.py` — verify MC classification logic (covered in `tests/test_agent.py`)
- [x] `tests/test_root_cause_tf.py` — verify TF (in-transit) detection via STO drill-down (covered in `tests/test_agent.py`)
- [x] `tests/test_evidence_package.py` — verify all required fields present in evidence package (covered in `tests/test_agent.py`)
- [x] `tests/test_exception_id_format.py` — verify EXC-YYYY-MM-NNNN format (covered in `tests/test_agent.py`)
- [x] `tests/test_integration.py` — end-to-end: receive variance results → classify → drill-down → return exceptions (covered in `tests/test_agent.py`)
- [ ] Run `pytest` from `assets/exception-management-agent/`; coverage ≥ 70%; `test_report.json` produced (requires live run)
