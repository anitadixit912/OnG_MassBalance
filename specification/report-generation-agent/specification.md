# Specification: report-generation-agent

> **Guidelines**: Read [guidelines.md](../guidelines.md), [guidelines-agent.md](../guidelines-agent.md), [guidelines-agent-python.md](../guidelines-agent-python.md) before executing.

---

## Role
Builds the structured exception report and Executive KPI dashboard summary.
Receives classified exceptions from the Exception Management Agent (via Orchestrator).
Returns the final formatted report to the Orchestrator for presentation to the user.

---

## Basic Setup

- [x] Bootstrap agent in `assets/report-generation-agent/` using `sap-agent-bootstrap`
- [x] Write `app/main.py` — A2A server, agent card: "Report Generation Agent"
- [x] Write `app/agent.py` — system prompt focused on report formatting; 9 decorators
- [x] Write supporting files, `requirements.txt` (Dockerfile intentionally omitted — CF deployment uses Python buildpack)
- [x] Note: this agent has **no MCP server dependencies** — it works only with data passed to it

## System Prompt Requirements

**Exception Report — one row per exception:**
- [x] Exception ID (`EXC-YYYY-MM-NNNN`)
- [x] Period (daily / monthly)
- [x] Plant, Tank / Storage Location, Material
- [x] Variance in MT and %
- [x] Severity: INFO / ADVISORY / WARNING / CRITICAL
- [x] Root Cause: MC / TX / MD / TF / PL / SY
- [x] Supporting Documents (material document numbers)
- [x] Recommended Correction
- [x] Status: OPEN / PENDING_APPROVAL / APPROVED / POSTED

**Executive KPI Summary:**
- [x] Overall variance % for the period
- [x] Total exceptions by severity (INFO count, ADVISORY count, WARNING count, CRITICAL count)
- [x] Count of pending approvals
- [x] Count of tanks/materials fully reconciled (zero variance)
- [x] Period and plant header

**Formatting rules:**
- [x] CRITICAL exceptions always listed first
- [x] Summary appears before the detailed exception table
- [x] Proposed corrections clearly marked as PENDING_APPROVAL — never POSTED without approval

## Runtime Skills

- [x] Create `app/skills/exception-report/SKILL.md` — report template; field definitions; formatting rules; KPI calculation method

## Business Instrumentation

- [x] No new milestones for this agent — it is the final step before Orchestrator presents to user
- [x] Log `REPORT_GENERATED: plant={plant} period={period} exceptions={count} critical={count} pending_approvals={count}`

## Testing

- [x] `tests/test_report_structure.py` — verify all required fields present in exception report (covered in `tests/test_agent.py`)
- [x] `tests/test_kpi_summary.py` — verify KPI counts calculated correctly from exception list (covered in `tests/test_agent.py`)
- [x] `tests/test_sort_order.py` — verify CRITICAL exceptions appear first (covered in `tests/test_agent.py`)
- [x] `tests/test_status_field.py` — verify no exception has status POSTED without approval (covered in `tests/test_agent.py`)
- [x] `tests/test_empty_exceptions.py` — verify graceful report when no exceptions (clean reconciliation) (covered in `tests/test_agent.py`)
- [x] `tests/test_integration.py` — end-to-end: receive exception list → format report → return to caller (covered in `tests/test_agent.py`)
- [ ] Run `pytest` from `assets/report-generation-agent/`; coverage ≥ 70%; `test_report.json` produced (requires live run)
