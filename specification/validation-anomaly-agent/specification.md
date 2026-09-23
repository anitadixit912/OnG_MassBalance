# Specification: validation-anomaly-agent

> **Guidelines**: Read [guidelines.md](../guidelines.md), [guidelines-agent.md](../guidelines-agent.md), [guidelines-agent-python.md](../guidelines-agent-python.md), [guidelines-agent-mcp.md](../guidelines-agent-mcp.md) before executing.

---

## Role
Validates completeness, consistency, and referential integrity of the data package received from the Data Collection Agent.
Detects sensor faults, missing readings, and statistical outliers.
**Blocks the pipeline on any validation failure** — returns PASS or FAIL with details to the Orchestrator.

---

## Basic Setup

- [x] Bootstrap agent in `assets/validation-anomaly-agent/` using `sap-agent-bootstrap`
- [x] Write `app/main.py` — A2A server, agent card: "Validation & Anomaly Agent"
- [x] Write `app/agent.py` — system prompt focused on validation rules; 9 decorators
- [x] Write supporting files, `requirements.txt` (Dockerfile intentionally omitted — CF deployment uses Python buildpack)

## System Prompt Requirements

- [x] **Completeness check**: all 6 domains (TANK, MAT, MOV, PHYS, BOOK, TRANSFERS) must have records for the requested plant and period; halt if any domain is empty
- [x] **Consistency check**: opening stock + movements must be internally consistent across domains; flag discrepancies
- [x] **Referential integrity**: all material document items must reference valid materials in MAT; all PHYS items must reference valid plant/storage locations
- [x] **Outlier detection**: flag any quantity that deviates more than 3 standard deviations from the period average
- [x] **Missing readings**: flag any tank/material with no PHYS count in the period
- [x] On validation failure: return structured FAIL response with domain name, field, and error description; do NOT proceed with calculation
- [x] On validation pass: return structured PASS response with count of records validated per domain

## MCP Wiring

- [x] Material Stock MCP and Material Document MCP declared in `asset.yaml` under `requires`
- [ ] Verify both MCP servers load at runtime for cross-domain referential checks (requires live BTP environment)

## Runtime Skills

- [x] Create `app/skills/data-validation/SKILL.md` — detailed validation rules per domain: completeness thresholds, consistency rules, outlier detection algorithm, referential integrity checks

## Business Instrumentation

- [x] Log `M2.achieved: VALIDATION_ENGINE_OPERATIONAL — plant={plant} period={period} checks_passed={count}` when all checks pass
- [x] Log `M2.missed: VALIDATION_FAILED — plant={plant} period={period} error={description}` on failure

## Testing

- [x] `tests/test_completeness.py` — verify pipeline halts when a domain has zero records (covered in `tests/test_agent.py`)
- [x] `tests/test_consistency.py` — verify inconsistencies between domains are flagged (covered in `tests/test_agent.py`)
- [x] `tests/test_referential_integrity.py` — verify orphan document items are detected (covered in `tests/test_agent.py`)
- [x] `tests/test_outlier_detection.py` — verify quantities > 3 std dev are flagged (covered in `tests/test_agent.py`)
- [x] `tests/test_pass_response.py` — verify structured PASS response format on clean data (covered in `tests/test_agent.py`)
- [x] `tests/test_integration.py` — end-to-end: receive data package → run all checks → return PASS/FAIL (covered in `tests/test_agent.py`)
- [ ] Run `pytest` from `assets/validation-anomaly-agent/`; coverage ≥ 70%; `test_report.json` produced (requires live run)
