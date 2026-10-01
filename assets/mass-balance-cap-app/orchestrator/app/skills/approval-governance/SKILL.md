---
name: approval-governance
description: Enforces human approval gates for SAP corrections. Formats exception reports and KPI summaries. Manages audit logging.
---

# Approval Governance Skill

## When to Use
Load this skill when presenting the exception report to the user and handling correction approvals.

## Exception Report Format
Present one row per exception with ALL fields:
- Exception ID (EXC-YYYY-MM-NNNN)
- Period, Plant, Tank/Storage Location, Material
- Variance MT and %
- Severity: INFO / ADVISORY / WARNING / CRITICAL
- Root Cause: MC / TX / MD / TF / PL / SY
- Supporting Documents (material document numbers)
- Recommended Correction
- Status: OPEN

**CRITICAL exceptions must appear FIRST in the report.**

## Executive KPI Summary (always at the top)
- Overall variance % for the period
- Exception counts: CRITICAL / WARNING / ADVISORY / INFO
- Count of pending approvals
- Count of fully reconciled tanks/materials (zero variance)

## Approval Gate
For any CRITICAL or WARNING exception with a proposed correction:

1. Present: "Do you approve posting this correction? Please confirm with your name and role."
2. WAIT for explicit named-user confirmation — name + role required
3. NEVER auto-post — no SAP document created without approval
4. On approval: log `M5.achieved: HUMAN_APPROVAL_GATES_DEPLOYED — approver={username} role={role} correction_id={id} timestamp={ts}`
5. On bypass attempt: log `M5.missed: APPROVAL_GATE_BYPASSED — correction_id={id} timestamp={ts} — CRITICAL ALERT`

## Audit Log Format
Every event must be logged with:
- Timestamp
- Approver username and role
- Exception ID / Correction ID
- Action taken (APPROVED / REJECTED / POSTED)
