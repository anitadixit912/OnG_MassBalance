---
name: approval-governance
description: Human approval gate workflow for SAP stock corrections. Defines confirmation format, required fields, audit log format, and bypass detection. No SAP document may be created without explicit named-user approval.
---

# Approval Governance Skill

## When to Use
Load this skill at Step 9 (exception report review) and Step 10 (SAP stock correction sign-off) of the reconciliation pipeline.

## Core Rule
**NEVER create, modify, or cancel any SAP document without explicit named-user approval in the current conversation.**

If approval is bypassed for any reason, immediately log:
`M5.missed: APPROVAL_GATE_BYPASSED — CRITICAL ALERT: correction_id={id} plant={plant} material={mat}`

## Step 1 — Present Correction for Approval

Before requesting approval, present the proposed correction in this exact format:

```
PROPOSED SAP CORRECTION — Awaiting Approval
────────────────────────────────────────────
Exception ID  : EXC-YYYY-MM-NNNN
Plant         : {plant}
Material      : {material}
Storage Loc   : {sloc}
Document Type : Physical Inventory Count | Goods Movement | Transfer Order
Movement Type : {mvt_type} — {mvt_description}
Quantity      : {qty} {unit}
Posting Date  : {date}
Root Cause    : {root_cause_code} — {root_cause_name}
Recommended By: Refinery Mass Balance Reconciliation Agent

Supporting Documents:
- {doc_type}: {doc_number} — {detail}

Do you approve posting this correction?
Please confirm with: your full name, role, and "APPROVED".
Example: "Jane Smith, Plant Manager, APPROVED"
```

## Step 2 — Validate Approval Response

A valid approval must contain ALL of the following:
1. **Name** — at least two words (first + last)
2. **Role** — one of: Refinery Engineer, Plant Manager, Compliance Officer, Shift Supervisor, or a custom role the user specifies
3. **Approval word** — "APPROVED", "APPROVE", or "CONFIRMED" (case-insensitive)

Rejection words that halt posting: "REJECT", "REJECTED", "DENY", "DENIED", "NO", "HOLD"

If the response is ambiguous, ask for clarification — do NOT assume approval.

## Step 3 — Log Approval

On valid approval, log immediately:
```
M5.achieved: HUMAN_APPROVAL_GATES_DEPLOYED — approver={name} role={role} timestamp={ISO8601} correction_id={id}
APPROVAL_RECEIVED: {username} {role} {timestamp} {correction_id}
```

## Step 4 — Proceed to Posting

Only after the approval log is written, proceed to create the SAP document via the appropriate MCP tool.
Confirm posting result and include the SAP document number in the audit log.

## Audit Log Entry Format

```json
{
  "audit_entry_id": "AUD-YYYY-MM-NNNN",
  "exception_id": "EXC-YYYY-MM-NNNN",
  "correction_type": "physical_inventory" | "goods_movement" | "transfer_order",
  "plant": "<plant>",
  "material": "<material>",
  "quantity_MT": 0.0,
  "approver_name": "<full name>",
  "approver_role": "<role>",
  "approval_timestamp": "<ISO8601>",
  "sap_document_number": "<doc_no>",
  "posting_timestamp": "<ISO8601>",
  "status": "PENDING_APPROVAL" | "APPROVED" | "REJECTED" | "POSTED" | "FAILED"
}
```

## Rejection Handling

If the user rejects the correction:
- Log: `CORRECTION_REJECTED: approver={name} role={role} timestamp={ISO8601} correction_id={id}`
- Set exception status to `REJECTED`
- Do NOT post any SAP document
- Ask if the user wants to modify the correction or escalate

## Instrumentation
- Approval received: `M5.achieved: HUMAN_APPROVAL_GATES_DEPLOYED — approver={name} role={role} timestamp={ts} correction_id={id}`
- Gate bypassed (critical): `M5.missed: APPROVAL_GATE_BYPASSED — CRITICAL ALERT correction_id={id}`
