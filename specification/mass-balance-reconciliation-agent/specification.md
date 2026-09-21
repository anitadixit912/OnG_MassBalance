# Specification: mass-balance-reconciliation-agent

> **Guidelines**: Read all applicable guidelines before executing ANY tasks below:
> - [guidelines.md](../guidelines.md) — Universal execution rules
> - [guidelines-agent.md](../guidelines-agent.md) — Universal agent patterns
> - [guidelines-agent-python.md](../guidelines-agent-python.md) — Python implementation details
> - [guidelines-agent-skills.md](../guidelines-agent-skills.md) — Runtime skills patterns
> - [guidelines-agent-mcp.md](../guidelines-agent-mcp.md) — MCP integration patterns

---

## Basic Setup

- [x] Bootstrap agent code in `assets/mass-balance-reconciliation-agent/` using `sap-agent-bootstrap`
- [x] Write `app/main.py` — A2A server with JWT middleware and agent card
- [x] Write `app/agent.py` — Orchestrator with mass balance system prompt and 9 decorators
- [x] Write `app/agent_executor.py` — A2A protocol executor, loads MCP tools per request
- [x] Write `app/mcp_providers/agw.py` — Agent Gateway connector for OGS_S4 destination
- [x] Write `app/circuit_breaker.py` — Per-model fallback circuit breaker
- [x] Write `app/util.py` — MCP response minification, truncation, retry logic
- [x] Write `app/load_skill_resources.py` — Runtime skill loader
- [x] Write `app/prompt_injection_detector.py` — Prompt injection scanner
- [x] Write `requirements.txt` and `Dockerfile`

---

## MCP Integration (Path A — All 5 APIs via OGS_S4)

- [x] API specs downloaded for all 5 SAP OData APIs from SAP Business Accelerator Hub
- [x] MCP translation files generated for all 5 APIs using `mcp-translation-file` skill
- [x] 5 MCP server assets created in `assets/` with correct `asset.yaml` files
- [x] Agent `asset.yaml` declares all 5 MCP servers under `requires`
- [x] ORD IDs in `requires` match exactly the `provides.apis[].ordId` in each MCP server `asset.yaml`

**MCP Server ORD IDs wired in agent `asset.yaml`:**
| MCP Server | ORD ID |
|---|---|
| Material Stock | `customer.build:apiResource:mass-balance-reconciliation-a37df.sap-s4-material-stock-mcp-server:v1` |
| Material Document | `customer.build:apiResource:mass-balance-reconciliation-a37df.sap-s4-material-document-mcp-server:v1` |
| Physical Inventory | `customer.build:apiResource:mass-balance-reconciliation-a37df.sap-s4-physical-inventory-mcp-server:v1` |
| Stock Transport Order | `customer.build:apiResource:mass-balance-reconciliation-a37df.sap-s4-stock-transport-order-mcp-server:v1` |
| Process Order Confirmation | `customer.build:apiResource:mass-balance-reconciliation-a37df.sap-s4-proc-order-confirmation-mcp-server:v1` |

---

## System Prompt Requirements

- [x] **Live data only** — system prompt explicitly forbids fabricating, guessing, or inventing any SAP data
- [x] **No auto-posting** — system prompt requires named-user approval before any SAP document is created, modified, or cancelled
- [x] **Pipeline halt** — system prompt requires halting on validation failure before any calculation proceeds
- [x] **Relay errors verbatim** — tool errors reported exactly as received
- [x] **Page size limit** — all paginated tool calls capped at 100 items
- [x] All 6 root cause categories defined: MC / TX / MD / TF / PL / SY
- [x] All 4 severity levels defined: INFO / ADVISORY / WARNING / CRITICAL with thresholds
- [x] Exception report format defined: Exception ID, Period, Plant/Tank/Material, Variance MT/%, Severity, Root Cause, Supporting Docs, Recommendation, Status

---

## Runtime Skills

- [ ] Create `app/skills/data-validation/SKILL.md` — step-by-step data validation rules for TANK, MAT, MOV, PHYS, BOOK domains
- [ ] Create `app/skills/mass-balance-calculation/SKILL.md` — formula: Closing = Opening + Receipts − Issues − Consumption ± Transfers ± Adjustments; temperature/density/meter factor corrections
- [ ] Create `app/skills/variance-classification/SKILL.md` — tolerance matrix: INFO (<0.1% or <1MT), ADVISORY (0.1–0.5% or 1–5MT), WARNING (0.5–2.0% or 5–20MT), CRITICAL (>2.0% or >20MT)
- [ ] Create `app/skills/root-cause-investigation/SKILL.md` — root cause drill-down via MSEG/MKPF; assign MC/TX/MD/TF/PL/SY
- [ ] Create `app/skills/approval-governance/SKILL.md` — human approval gate workflow; confirmation format; audit log format
- [ ] Create `app/skills/exception-report/SKILL.md` — exception report generation template; executive KPI summary format

---

## Business Instrumentation (5 Milestones from PRD)

- [ ] Implement M1 — `DATA_INGESTION_LIVE`: log when all 5 domains fetched successfully; log `DATA_INGESTION_FAILED` with missing domains on failure
- [ ] Implement M2 — `VALIDATION_ENGINE_OPERATIONAL`: log when all validation checks pass; log `VALIDATION_FAILED` with error description on failure
- [ ] Implement M3 — `MASS_BALANCE_CALCULATION_VALIDATED`: log when closing stock calculated at Plant/Tank/Material level; log `CALCULATION_ERROR` on failure
- [ ] Implement M4 — `VARIANCE_EXCEPTION_PIPELINE_ACTIVE`: log when all variances classified with exception count; log `CLASSIFICATION_FAILED` on failure
- [ ] Implement M5 — `HUMAN_APPROVAL_GATES_DEPLOYED`: log when approval received with approver name/role/timestamp; log `APPROVAL_GATE_BYPASSED` as CRITICAL ALERT if gate skipped
- [ ] Extract business logic from `stream()` into plain async helper `_run_reconciliation()` to avoid GeneratorExit with OTel spans
- [ ] Add OpenTelemetry span for each milestone using `@tracer.start_as_current_span` decorator pattern
- [ ] Verify `grep -r "M[0-9]\.achieved" assets/mass-balance-reconciliation-agent/app/` returns results

---

## Agent Decorators Validation

- [ ] Verify `app/agent.py` has exactly 9 decorated functions:
  - `@agent_model` — primary model (`sap/anthropic--claude-4.5-sonnet`)
  - `@agent_model` — fallback models
  - `@agent_model` — summarization model
  - `@agent_config` — circuit breaker failure threshold
  - `@agent_config` — circuit breaker cooldown seconds
  - `@agent_config` — temperature
  - `@agent_config` — checkpointer TTL
  - `@agent_config` — summarization trigger tokens
  - `@prompt_section` — system prompt
- [ ] Run: `grep -c "^@agent_model\|^@agent_config\|^@prompt_section" assets/mass-balance-reconciliation-agent/app/agent.py` — must return 9

---

## Testing

- [ ] Write `conftest.py` — sets `IBD_TESTING=true`, patches `mcp_tools.get_mcp_tools` with mock tools from `mcp-mock.json`
- [ ] Write `pytest.ini` — configures test discovery for `prebuilt_tests/` and `tests/`
- [ ] Write `requirements-test.txt`
- [ ] Generate `mcp-mock.json` using `mcp-mock-config` skill (requires translation files to be in place)

**Unit tests — one per MCP tool domain:**
- [ ] `tests/test_data_ingestion.py` — mock all 5 MCP servers; verify live data fetch per domain
- [ ] `tests/test_data_validation.py` — test completeness/consistency checks; verify pipeline halts on failure
- [ ] `tests/test_mass_balance_calculation.py` — test closing stock formula at Plant/Tank/Material level
- [ ] `tests/test_variance_classification.py` — test tolerance matrix; verify all 4 severity levels
- [ ] `tests/test_root_cause_investigation.py` — test drill-down via material document items
- [ ] `tests/test_approval_governance.py` — verify no SAP document created without approval; test approval log format
- [ ] `tests/test_exception_report.py` — verify report structure: Exception ID, Severity, Root Cause, Status

**Integration test:**
- [ ] `tests/test_integration.py` — end-to-end flow: trigger reconciliation → fetch data → validate → calculate → classify → report → approval gate; all external systems mocked

**Coverage & reporting:**
- [ ] Run `pytest` (no args) from `assets/mass-balance-reconciliation-agent/`
- [ ] Verify coverage ≥ 70%; add tests if below threshold
- [ ] Verify `test_report.json` exists in `assets/mass-balance-reconciliation-agent/`

---

## Final Validation

- [ ] `grep -r "M[0-9]\.achieved" assets/mass-balance-reconciliation-agent/app/` — must return results
- [ ] `grep -r "sap_cloud_sdk.agent_decorators" assets/mass-balance-reconciliation-agent/app/` — must return results
- [ ] `ls assets/mass-balance-reconciliation-agent/test_report.json` — must exist
- [ ] `ls assets/mass-balance-reconciliation-agent/Dockerfile` — must exist
- [ ] Confirm no Z programs referenced anywhere in solution
- [ ] Confirm no direct HTTP calls to SAP APIs anywhere in agent code
- [ ] Confirm OGS_S4 destination name used consistently across all 5 MCP server translation files
