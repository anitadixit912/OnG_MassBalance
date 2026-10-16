---
name: exception-report
description: Exception report generation template and Executive KPI summary format. Produces structured exception reports with evidence packages and an executive dashboard.
---

# Exception Report Skill

## When to Use
Load this skill after variance classification and root cause investigation to generate the final structured exception report and executive KPI summary.

## Exception Report Template

### Header

```
REFINERY MASS BALANCE EXCEPTION REPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Report Date : {ISO date}
Plant       : {plant}
Period      : {YYYY-MM}
SAP System  : OGS/650 (via OGS_S4 destination)
Run By      : Refinery Mass Balance Reconciliation Agent
```

### Exception Table (one row per exception)

| Exception ID | Period | Plant | Material | SLoc | Variance MT | Variance % | Severity | Root Cause | Supporting Docs | Recommendation | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| EXC-YYYY-MM-NNNN | YYYY-MM | {plant} | {mat} | {sloc} | {qty} | {pct}% | CRITICAL/WARNING/ADVISORY | {code} | {doc_nos} | {action} | OPEN |

### Exception Detail Block (one per exception)

```
Exception ID   : EXC-YYYY-MM-NNNN
Status         : OPEN | PENDING_APPROVAL | APPROVED | POSTED | REJECTED
─────────────────────────────────────────────────────────────────
Period         : YYYY-MM
Plant          : {plant}
Material       : {material} — {material_description}
Storage Loc    : {sloc}
─────────────────────────────────────────────────────────────────
Variance (MT)  : {variance_MT}
Variance (%)   : {variance_pct}%
Severity       : {INFO | ADVISORY | WARNING | CRITICAL}
─────────────────────────────────────────────────────────────────
Root Cause     : {code} — {full_name}
Confidence     : HIGH | MEDIUM | LOW
─────────────────────────────────────────────────────────────────
Evidence Package:
  {doc_type} {doc_number}: {detail}
  {doc_type} {doc_number}: {detail}
─────────────────────────────────────────────────────────────────
Recommended Correction:
  {description of proposed SAP correction}
─────────────────────────────────────────────────────────────────
Investigation Notes:
  {free text from root cause investigation}
```

## Executive KPI Summary Dashboard

```
EXECUTIVE SUMMARY — MASS BALANCE KPIs
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Plant    : {plant}
Period   : {YYYY-MM}

Pipeline Status:
  ✓ M1 Data Ingestion      : {LIVE | PARTIAL | FAILED}
  ✓ M2 Validation          : {PASS | FAIL}
  ✓ M3 Calculation         : {VALIDATED | ERROR}
  ✓ M4 Variance Pipeline   : {ACTIVE | FAILED}
  ✓ M5 Approval Gates      : {DEPLOYED | BYPASSED}

Stock Summary (all materials):
  Opening Stock            : {total_MT} MT
  + Receipts               : {total_MT} MT
  − Issues                 : {total_MT} MT
  − Consumption            : {total_MT} MT
  ± Transfers              : {total_MT} MT
  ± Adjustments            : {total_MT} MT
  = Calculated Closing     : {total_MT} MT
  System Closing Stock     : {total_MT} MT
  ──────────────────────────────────────
  Net Variance             : {total_MT} MT ({pct}%)
  Plant Severity           : {severity}

Exception Summary:
  Total Exceptions         : {n}
    CRITICAL               : {n}
    WARNING                : {n}
    ADVISORY               : {n}
    INFO (recorded only)   : {n}
  Pending Approval         : {n}
  Posted to SAP            : {n}
```

## Report Generation Rules

1. Include ALL materials in the plant summary table — even those with zero variance (INFO)
2. Exception detail blocks only for severity > INFO
3. If no exceptions above INFO: state "No exceptions above INFO threshold for this period"
4. Pending approval items must appear in Section 6 of the main output format
5. After generating the report, present the Human Approval Gate section if any CRITICAL or WARNING exceptions require correction

## Instrumentation
On report generated: `EXCEPTION_REPORT_GENERATED: plant={plant} period={period} exceptions={n} report_id={id}`
