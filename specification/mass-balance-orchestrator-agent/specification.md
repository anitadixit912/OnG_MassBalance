# Specification: mass-balance-orchestrator-agent

> **Guidelines**: Read [guidelines.md](../guidelines.md), [guidelines-agent.md](../guidelines-agent.md), [guidelines-agent-python.md](../guidelines-agent-python.md), [guidelines-agent-mcp.md](../guidelines-agent-mcp.md) before executing.

---

## Role
The top-level orchestrator for the refinery mass balance reconciliation pipeline.
Coordinates the 5 sub-agents via A2A protocol in sequence.
Handles goal decomposition, dynamic replanning on failure, human approval gates, and audit logging.
This is the **only agent the user interacts with directly**.

---

## Basic Setup

- [x] Bootstrap agent in `assets/mass-balance-orchestrator-agent/` using `sap-agent-bootstrap`
- [x] Write `app/main.py` — A2A server, agent card: "Mass Balance Orchestrator Agent"
- [x] Write `app/agent.py` — orchestration system prompt; 9 decorators
- [x] Write supporting files, `requirements.txt` (Dockerfile intentionally omitted — CF deployment uses Python buildpack)

## System Prompt Requirements

**Pipeline sequence (enforce this order):**
1. Call **Data Collection Agent** → get data package (TANK, MAT, MOV, PHYS, BOOK, TRANSFERS)
2. Call **Validation & Anomaly Agent** with data package → get PASS or FAIL
   - On FAIL: halt pipeline, surface validation error to user, stop
3. Call **Calculation & Reconciliation Agent** with validated data → get variance results
4. Call **Exception Management Agent** with variance results → get classified exceptions + evidence
5. Call **Report Generation Agent** with exceptions → get formatted report
6. Present report to user

**Human approval gate (Step 6 onwards):**
- [x] Present the exception report to the user
- [x] For any CRITICAL or WARNING exception with a proposed correction, ask: "Do you approve posting this correction? Please confirm with your name and role."
- [x] Wait for explicit named-user confirmation before proceeding
- [x] **NEVER auto-post** — no SAP document is created without approval in the conversation
- [x] Log approval: `M5.achieved: HUMAN_APPROVAL_GATES_DEPLOYED — approver={username} role={role} correction_id={id} timestamp={ts}`
- [x] Log bypass attempt: `M5.missed: APPROVAL_GATE_BYPASSED — correction_id={id} timestamp={ts} — CRITICAL ALERT`

**Dynamic replanning:**
- [x] If any sub-agent returns an error, attempt one retry before escalating to the user
- [x] If the Data Collection Agent fails on a specific domain, surface which domain failed with the error message
- [x] If the Validation Agent returns FAIL, present the specific validation errors clearly to the user

**Audit trail:**
- [x] Log every sub-agent call with input parameters and response status
- [x] Log every approval and rejection with approver identity and timestamp
- [x] All logs are append-only

## Sub-agent A2A Wiring

- [x] All 5 sub-agent ORD IDs declared in `asset.yaml` under `requires` (kind: a2a — matches sub-agent `provides`)
- [x] A2A calls implemented via Agent Gateway — sub-agents surface as LangChain tools
- [x] Pass plant, period, and relevant data between agents using structured JSON

## Business Instrumentation (All 5 Milestones)

- [x] M1: delegate to Data Collection Agent; log achievement/miss from its response
- [x] M2: delegate to Validation Agent; log achievement/miss from its response
- [x] M3: delegate to Calculation Agent; log achievement/miss from its response
- [x] M4: delegate to Exception Management Agent; log achievement/miss from its response
- [x] M5: log directly in Orchestrator when approval gate fires

## Runtime Skills

- [x] Create `app/skills/approval-governance/SKILL.md` — approval gate workflow; confirmation format; audit log format; escalation rules

## Testing

- [x] `tests/test_pipeline_happy_path.py` — mock all 5 sub-agents; verify full pipeline executes in correct sequence (covered in `tests/test_agent.py`)
- [x] `tests/test_pipeline_validation_fail.py` — mock Validation Agent returning FAIL; verify pipeline halts after step 2 (covered in `tests/test_agent.py`)
- [x] `tests/test_approval_gate.py` — verify no SAP write proceeds without named-user approval (covered in `tests/test_agent.py`)
- [x] `tests/test_approval_gate_bypass.py` — verify CRITICAL ALERT logged if approval gate bypassed (covered in `tests/test_agent.py`)
- [x] `tests/test_retry_on_agent_error.py` — verify orchestrator retries once on sub-agent error before escalating (covered in `tests/test_agent.py`)
- [x] `tests/test_audit_log.py` — verify all approvals logged with username, role, timestamp (covered in `tests/test_agent.py`)
- [x] `tests/test_integration.py` — full end-to-end: user triggers reconciliation → all 5 agents called → report presented → approval gate enforced (covered in `tests/test_agent.py`)
- [ ] Run `pytest` from `assets/mass-balance-orchestrator-agent/`; coverage ≥ 70%; `test_report.json` produced (requires live run)

## Final Validation

- [x] `grep -r "M[0-9]\.achieved" assets/mass-balance-orchestrator-agent/app/` — results confirmed in system prompt and skills
- [x] `grep -r "sap_cloud_sdk.agent_decorators" assets/mass-balance-orchestrator-agent/app/` — confirmed in `app/agent.py`
- [ ] `ls assets/mass-balance-orchestrator-agent/test_report.json` — produced by pytest run (requires live run)
- [x] Confirm no Z programs referenced anywhere
- [x] Confirm no direct HTTP calls to SAP APIs — all data comes from sub-agents via Agent Gateway tools
- [x] All 5 sub-agent ORD IDs in `asset.yaml` use `kind: a2a` (consistent with sub-agent `provides.apis[].kind`)
