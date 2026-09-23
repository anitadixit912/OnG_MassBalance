---
name: exception-report
description: Report template and formatting rules for the Mass Balance Exception Report and Executive KPI Summary. Defines section order, table structure, and approval gate presentation.
---

# Exception Report Skill

## When to Use
Load this skill when generating the final exception report for user review.

## Report Structure

### Section 1 — Executive KPI Summary (always first)
| KPI | Value |
|-----|-------|
| Plant | {plant} |
| Period | {period} |
| Overall Variance % | {plant_level.variance_pct:.2f}% |
| Overall Variance MT | {plant_level.variance_MT:.1f} MT |
| CRITICAL exceptions | {count} |
| WARNING exceptions | {count} |
| ADVISORY exceptions | {count} |
| INFO exceptions | {count} |
| Fully Reconciled Tanks/Materials | {count} |
| Pending Approvals | {count of CRITICAL+WARNING} |

### Section 2 — Exception Table
Present one row per exception, CRITICAL first, then WARNING, ADVISORY, INFO.

| Exception ID | Period | Plant | Storage Location | Material | Variance MT | Variance % | Severity | Root Cause | Supporting Docs | Recommendation | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| EXC-2026-09-0001 | 2026-09 | 1000 | TK01 | 100000001 | 12.5 | 0.8% | WARNING | TF | 4900001234 | Await GR posting | OPEN |

### Section 3 — Approval Gate (for CRITICAL and WARNING exceptions)
For each CRITICAL or WARNING exception, present individually:

```
Exception: EXC-2026-09-0001
Severity: WARNING | Variance: 12.5 MT (0.8%)
Root Cause: TF — Transfer in Transit
Proposed Correction: Await GR posting; re-run balance after goods receipt confirmation
Supporting Docs: 4900001234, 4900001235

Do you approve posting this correction? Please confirm with your name and role.
```

**WAIT for explicit confirmation** — do NOT proceed to the next exception without a response.
**Required fields**: Approver name + role (e.g., "Anna Müller, Refinery Controller").

### Section 4 — Reconciled Items
List tanks/materials with zero variance for completeness. Keep brief — table format only.

## Formatting Rules
- Use markdown tables throughout
- Bold CRITICAL severity labels
- Show variance_pct with 2 decimal places; variance_MT with 1 decimal place
- Exception IDs must be clickable-looking (code format): `EXC-2026-09-0001`
- Report header: `## Mass Balance Exception Report — Plant {plant} | Period {period}`

## Instrumentation
After generating the report:
- `M4.achieved: VARIANCE_EXCEPTION_PIPELINE_ACTIVE — plant={plant} period={period} exceptions={total} critical={count}`

After each approval received:
- `M5.achieved: HUMAN_APPROVAL_GATES_DEPLOYED — approver={username} role={role} correction_id={exception_id} timestamp={ts}`

If approval gate is bypassed:
- `M5.missed: APPROVAL_GATE_BYPASSED — correction_id={exception_id} timestamp={ts} — CRITICAL ALERT`
