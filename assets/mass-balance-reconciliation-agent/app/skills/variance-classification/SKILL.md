---
name: variance-classification
description: Tolerance matrix and severity classification for mass balance variances. Maps variance MT and % to INFO/ADVISORY/WARNING/CRITICAL. Applies after mass balance calculation.
---

# Variance Classification Skill

## When to Use
Load this skill after the mass balance calculation to classify each variance by severity and apply the tolerance matrix.

## Tolerance Matrix

| Severity  | Variance % threshold | Variance MT threshold | Action |
|-----------|---------------------|-----------------------|--------|
| INFO      | < 0.1%              | < 1 MT                | Record only — no investigation required |
| ADVISORY  | 0.1% – 0.5%         | 1 MT – 5 MT           | Investigate, no immediate action |
| WARNING   | 0.5% – 2.0%         | 5 MT – 20 MT          | Investigate urgently, recommend correction |
| CRITICAL  | > 2.0%              | > 20 MT               | Escalate immediately, halt pipeline if needed |

**Classification rule**: Apply BOTH thresholds and use the HIGHER severity. For example, a variance of 0.08% but 3 MT classifies as ADVISORY (MT threshold wins).

## Step 1 — Calculate Severity Per Material

For each material result from the calculation step:
1. Determine severity by % threshold
2. Determine severity by MT threshold
3. Assign the higher of the two as the final severity

Severity rank: CRITICAL > WARNING > ADVISORY > INFO

## Step 2 — Aggregate Plant-Level Severity

The plant severity = highest individual material severity.

## Step 3 — Assign Root Cause Category (Initial)

For each exception (severity > INFO), assign an initial root cause category based on available evidence:
- **MC** (Meter calibration): Flag if variance pattern is consistent across periods
- **TX** (Transaction error): Flag if a movement document was recently revised
- **MD** (Missing document): Flag if PHYS or BOOK data is sparse for the period
- **TF** (Transfer in transit): Flag if open stock transport orders exist for the material
- **PL** (Process loss): Flag if variance is small and consistent with evaporation rates
- **SY** (System error): Flag if multiple domains show inconsistent data simultaneously

Root cause is provisional at this stage — confirmed via root-cause-investigation skill.

## Output Format Per Material

```json
{
  "material": "<mat>",
  "storage_location": "<loc>",
  "variance_MT": 0.0,
  "variance_pct": 0.0,
  "severity": "INFO" | "ADVISORY" | "WARNING" | "CRITICAL",
  "severity_driver": "pct" | "MT",
  "provisional_root_cause": "MC" | "TX" | "MD" | "TF" | "PL" | "SY" | null,
  "exception_id": "EXC-YYYY-MM-NNNN" | null
}
```

Exception IDs are assigned only for severity > INFO.
Format: `EXC-{YYYY}-{MM}-{seq:04d}` where seq is a sequence number within the period.

## Plant Summary

```json
{
  "plant": "<plant>",
  "period": "<period>",
  "plant_severity": "INFO" | "ADVISORY" | "WARNING" | "CRITICAL",
  "exception_count": 0,
  "critical_count": 0,
  "warning_count": 0,
  "advisory_count": 0,
  "info_count": 0
}
```

## Instrumentation
- On classification complete: `M4.achieved: VARIANCE_EXCEPTION_PIPELINE_ACTIVE — plant={plant} period={period} exceptions={n} critical={n} warning={n} advisory={n}`
- On failure: `M4.missed: CLASSIFICATION_FAILED — plant={plant} period={period} error={description}`
