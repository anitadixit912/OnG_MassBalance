---
name: variance-classification
description: Configurable tolerance matrix for classifying variance severity as INFO/ADVISORY/WARNING/CRITICAL. Assigns Exception IDs and builds structured exception records.
---

# Variance Classification Skill

## When to Use
Load this skill when applying the tolerance matrix to calculated variance results.

## Tolerance Matrix

| Severity  | Variance % Threshold | Variance MT Threshold | Action |
|-----------|---------------------|----------------------|--------|
| INFO      | < 0.1%              | < 1 MT               | Record only; no action required |
| ADVISORY  | 0.1% – 0.5%         | 1 – 5 MT             | Log for review; recommend re-check |
| WARNING   | 0.5% – 2.0%         | 5 – 20 MT            | Investigate urgently; recommend correction |
| CRITICAL  | > 2.0%              | > 20 MT              | Escalate immediately; mandatory correction |

**Rule**: If either threshold is met, apply the higher severity.
**Example**: variance_pct = 0.3% and variance_MT = 8 MT → ADVISORY by %, WARNING by MT → classify as **WARNING**.

## Exception ID Format
`EXC-{YYYY-MM}-{NNNN}` — e.g. `EXC-2026-09-0001`
- YYYY-MM from the reconciliation period
- NNNN is a sequential counter within the period, zero-padded to 4 digits

## Exception Record Template
```json
{
  "exception_id": "EXC-2026-09-0001",
  "period": "2026-09",
  "plant": "1000",
  "storage_location": "TK01",
  "material": "100000001",
  "variance_MT": 12.5,
  "variance_pct": 0.8,
  "severity": "WARNING",
  "root_cause": "TF",
  "root_cause_description": "Transfer in transit — STO issued but not yet received",
  "supporting_documents": ["4900001234", "4900001235"],
  "recommended_correction": "Await GR posting; re-run balance after goods receipt confirmation",
  "status": "OPEN"
}
```

## Zero-Variance Records
Do NOT generate exceptions for variance_MT = 0.0 and variance_pct = 0.0.
These represent fully reconciled tanks/materials — count them in the KPI summary.

## Output Format
```json
{
  "plant": "<plant>",
  "period": "<period>",
  "status": "COMPLETE",
  "summary": {
    "total_exceptions": 0,
    "by_severity": {"CRITICAL": 0, "WARNING": 0, "ADVISORY": 0, "INFO": 0},
    "fully_reconciled_count": 0
  },
  "exceptions": []
}
```

## Instrumentation
- On success: `M4.achieved: VARIANCE_EXCEPTION_PIPELINE_ACTIVE — plant={plant} period={period} exceptions={count} critical={count}`
- On error: `M4.missed: CLASSIFICATION_FAILED — plant={plant} period={period} error={description}`
