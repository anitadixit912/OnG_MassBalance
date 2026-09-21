# Specification: validation-anomaly-agent

> **Guidelines**: Read [guidelines.md](../guidelines.md), [guidelines-agent.md](../guidelines-agent.md), [guidelines-agent-python.md](../guidelines-agent-python.md), [guidelines-agent-mcp.md](../guidelines-agent-mcp.md) before executing.

---

## Role
Validates completeness, consistency, and referential integrity of the data package received from the Data Collection Agent.
Detects sensor faults, missing readings, and statistical outliers.
**Blocks the pipeline on any validation failure** — returns PASS or FAIL with details to the Orchestrator.

---

## Basic Setup

- [ ] Bootstrap agent in `assets/validation-anomaly-agent/` using `sap-agent-bootstrap`
- [ ] Write `app/main.py` — A2A server, agent card: "Validation & Anomaly Agent"
- [ ] Write `app/agent.py` — system prompt focused on validation rules; 9 decorators
- [ ] Write supporting files, `requirements.txt`, `Dockerfile`

## System Prompt Requirements

- [ ] **Completeness check**: all 5 domains (TANK, MAT, MOV, PHYS, BOOK) must have records for the requested plant and period; halt if any domain is empty
- [ ] **Consistency check**: opening stock + movements must be internally consistent across domains; flag discrepancies
- [ ] **Referential integrity**: all material document items must reference valid materials in MAT; all PHYS items must reference valid plant/storage locations
- [ ] **Outlier detection**: flag any quantity that deviates more than 3 standard deviations from the period average
- [ ] **Missing readings**: flag any tank/material with no PHYS count in the period
- [ ] On validation failure: return structured FAIL response with domain name, field, and error description; do NOT proceed with calculation
- [ ] On validation pass: return structured PASS response with count of records validated per domain

## MCP Wiring

- [x] Material Stock MCP and Material Document MCP declared in `asset.yaml` under `requires`
- [ ] Verify both MCP servers load at runtime for cross-domain referential checks

## Runtime Skills

- [ ] Create `app/skills/data-validation/SKILL.md` — detailed validation rules per domain: completeness thresholds, consistency rules, outlier detection algorithm, referential integrity checks

## Business Instrumentation

- [ ] Log `M2.achieved: VALIDATION_ENGINE_OPERATIONAL — plant={plant} period={period} checks_passed={count}` when all checks pass
- [ ] Log `M2.missed: VALIDATION_FAILED — plant={plant} period={period} error={description}` on failure

## Testing

- [ ] `tests/test_completeness.py` — verify pipeline halts when a domain has zero records
- [ ] `tests/test_consistency.py` — verify inconsistencies between domains are flagged
- [ ] `tests/test_referential_integrity.py` — verify orphan document items are detected
- [ ] `tests/test_outlier_detection.py` — verify quantities > 3 std dev are flagged
- [ ] `tests/test_pass_response.py` — verify structured PASS response format on clean data
- [ ] `tests/test_integration.py` — end-to-end: receive data package → run all checks → return PASS/FAIL
- [ ] Run `pytest` from `assets/validation-anomaly-agent/`; coverage ≥ 70%; `test_report.json` produced
