# Specification: report-generation-agent

> **Guidelines**: Read [guidelines.md](../guidelines.md), [guidelines-agent.md](../guidelines-agent.md), [guidelines-agent-python.md](../guidelines-agent-python.md) before executing.

---

## Role
Builds the structured exception report and Executive KPI dashboard summary.
Receives classified exceptions from the Exception Management Agent (via Orchestrator).
Returns the final formatted report to the Orchestrator for presentation to the user.

---

## Basic Setup

- [ ] Bootstrap agent in `assets/report-generation-agent/` using `sap-agent-bootstrap`
- [ ] Write `app/main.py` — A2A server, agent card: "Report Generation Agent"
- [ ] Write `app/agent.py` — system prompt focused on report formatting; 9 decorators
- [ ] Write supporting files, `requirements.txt`, `Dockerfile`
- [ ] Note: this agent has **no MCP server dependencies** — it works only with data passed to it

## System Prompt Requirements

**Exception Report — one row per exception:**
- [ ] Exception ID (`EXC-YYYY-MM-NNNN`)
- [ ] Period (daily / monthly)
- [ ] Plant, Tank / Storage Location, Material
- [ ] Variance in MT and %
- [ ] Severity: INFO / ADVISORY / WARNING / CRITICAL
- [ ] Root Cause: MC / TX / MD / TF / PL / SY
- [ ] Supporting Documents (material document numbers)
- [ ] Recommended Correction
- [ ] Status: OPEN / PENDING_APPROVAL / APPROVED / POSTED

**Executive KPI Summary:**
- [ ] Overall variance % for the period
- [ ] Total exceptions by severity (INFO count, ADVISORY count, WARNING count, CRITICAL count)
- [ ] Count of pending approvals
- [ ] Count of tanks/materials fully reconciled (zero variance)
- [ ] Period and plant header

**Formatting rules:**
- [ ] CRITICAL exceptions always listed first
- [ ] Summary appears before the detailed exception table
- [ ] Proposed corrections clearly marked as PENDING_APPROVAL — never POSTED without approval

## Runtime Skills

- [ ] Create `app/skills/exception-report/SKILL.md` — report template; field definitions; formatting rules; KPI calculation method

## Business Instrumentation

- [ ] No new milestones for this agent — it is the final step before Orchestrator presents to user
- [ ] Log `REPORT_GENERATED: plant={plant} period={period} exceptions={count} critical={count} pending_approvals={count}`

## Testing

- [ ] `tests/test_report_structure.py` — verify all required fields present in exception report
- [ ] `tests/test_kpi_summary.py` — verify KPI counts calculated correctly from exception list
- [ ] `tests/test_sort_order.py` — verify CRITICAL exceptions appear first
- [ ] `tests/test_status_field.py` — verify no exception has status POSTED without approval
- [ ] `tests/test_empty_exceptions.py` — verify graceful report when no exceptions (clean reconciliation)
- [ ] `tests/test_integration.py` — end-to-end: receive exception list → format report → return to caller
- [ ] Run `pytest` from `assets/report-generation-agent/`; coverage ≥ 70%; `test_report.json` produced
