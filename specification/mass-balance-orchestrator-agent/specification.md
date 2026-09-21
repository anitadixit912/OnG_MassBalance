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

- [ ] Bootstrap agent in `assets/mass-balance-orchestrator-agent/` using `sap-agent-bootstrap`
- [ ] Write `app/main.py` — A2A server, agent card: "Mass Balance Orchestrator Agent"
- [ ] Write `app/agent.py` — orchestration system prompt; 9 decorators
- [ ] Write supporting files, `requirements.txt`, `Dockerfile`

## System Prompt Requirements

**Pipeline sequence (enforce this order):**
1. Call **Data Collection Agent** → get data package (TANK, MAT, MOV, PHYS, BOOK)
2. Call **Validation & Anomaly Agent** with data package → get PASS or FAIL
   - On FAIL: halt pipeline, surface validation error to user, stop
3. Call **Calculation & Reconciliation Agent** with validated data → get variance results
4. Call **Exception Management Agent** with variance results → get classified exceptions + evidence
5. Call **Report Generation Agent** with exceptions → get formatted report
6. Present report to user

**Human approval gate (Step 6 onwards):**
- [ ] Present the exception report to the user
- [ ] For any CRITICAL or WARNING exception with a proposed correction, ask: "Do you approve posting this correction? Please confirm with your name and role."
- [ ] Wait for explicit named-user confirmation before proceeding
- [ ] **NEVER auto-post** — no SAP document is created without approval in the conversation
- [ ] Log approval: `M5.achieved: HUMAN_APPROVAL_GATES_DEPLOYED — approver={username} role={role} correction_id={id} timestamp={ts}`
- [ ] Log bypass attempt: `M5.missed: APPROVAL_GATE_BYPASSED — correction_id={id} timestamp={ts} — CRITICAL ALERT`

**Dynamic replanning:**
- [ ] If any sub-agent returns an error, attempt one retry before escalating to the user
- [ ] If the Data Collection Agent fails on a specific domain, surface which domain failed with the error message
- [ ] If the Validation Agent returns FAIL, present the specific validation errors clearly to the user

**Audit trail:**
- [ ] Log every sub-agent call with input parameters and response status
- [ ] Log every approval and rejection with approver identity and timestamp
- [ ] All logs are append-only

## Sub-agent A2A Wiring

- [x] All 5 sub-agent ORD IDs declared in `asset.yaml` under `requires` (kind: agent)
- [ ] Implement A2A calls to sub-agents using the A2A SDK client
- [ ] Pass plant, period, and relevant data between agents using structured JSON

## Business Instrumentation (All 5 Milestones)

- [ ] M1: delegate to Data Collection Agent; log achievement/miss from its response
- [ ] M2: delegate to Validation Agent; log achievement/miss from its response
- [ ] M3: delegate to Calculation Agent; log achievement/miss from its response
- [ ] M4: delegate to Exception Management Agent; log achievement/miss from its response
- [ ] M5: log directly in Orchestrator when approval gate fires

## Runtime Skills

- [ ] Create `app/skills/approval-governance/SKILL.md` — approval gate workflow; confirmation format; audit log format; escalation rules

## Testing

- [ ] `tests/test_pipeline_happy_path.py` — mock all 5 sub-agents; verify full pipeline executes in correct sequence
- [ ] `tests/test_pipeline_validation_fail.py` — mock Validation Agent returning FAIL; verify pipeline halts after step 2
- [ ] `tests/test_approval_gate.py` — verify no SAP write proceeds without named-user approval
- [ ] `tests/test_approval_gate_bypass.py` — verify CRITICAL ALERT logged if approval gate bypassed
- [ ] `tests/test_retry_on_agent_error.py` — verify orchestrator retries once on sub-agent error before escalating
- [ ] `tests/test_audit_log.py` — verify all approvals logged with username, role, timestamp
- [ ] `tests/test_integration.py` — full end-to-end: user triggers reconciliation → all 5 agents called → report presented → approval gate enforced
- [ ] Run `pytest` from `assets/mass-balance-orchestrator-agent/`; coverage ≥ 70%; `test_report.json` produced

## Final Validation

- [ ] `grep -r "M[0-9]\.achieved" assets/mass-balance-orchestrator-agent/app/` — must return results
- [ ] `grep -r "sap_cloud_sdk.agent_decorators" assets/mass-balance-orchestrator-agent/app/` — must return results
- [ ] `ls assets/mass-balance-orchestrator-agent/test_report.json` — must exist
- [ ] Confirm no Z programs referenced anywhere
- [ ] Confirm no direct HTTP calls to SAP APIs — all data comes from sub-agents
- [ ] Confirm all 5 sub-agent ORD IDs in `asset.yaml` use `kind: agent` (not `kind: mcp-server`)
