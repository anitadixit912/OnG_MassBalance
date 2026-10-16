---
name: root-cause-investigation
description: Root cause drill-down via MSEG/MKPF material document items. Confirms or revises the provisional root cause category (MC/TX/MD/TF/PL/SY) for each exception.
---

# Root Cause Investigation Skill

## When to Use
Load this skill for each exception (severity > INFO) after variance classification, to confirm the root cause category via document-level evidence.

## Root Cause Categories

| Code | Name | Description |
|------|------|-------------|
| MC   | Meter calibration error | Systematic measurement bias — consistent variance across periods, no matching documents |
| TX   | Transaction/data entry error | A movement document was posted with an incorrect quantity or date |
| MD   | Missing or delayed document | A goods movement occurred but no SAP document was posted yet |
| TF   | Transfer in transit | Inter-plant transfer dispatched but not yet received |
| PL   | Process loss | Evaporation, sampling, line fill — small consistent variance within industry norms |
| SY   | System/interface error | Data inconsistency caused by interface failure, batch job failure, or OData issue |

## Investigation Steps

### Step 1 — Fetch Material Document History
Call `s4_list_material_documents` for the material, plant, and period:
- Filter by `Material`, `Plant`, `PostingDate` range
- Page size: max 100 items
- Look for: reversals (movement type 102, 202, 262), corrections, or large single movements

### Step 2 — Fetch Physical Inventory Document Items
Call `s4_list_physical_inventory_document_items` for the plant and period:
- Check `CountedQuantityInBaseUnit` vs `BookQtyBfrCountInMatlBaseUnit`
- Large discrepancies suggest TX or MD

### Step 3 — Check Open Transfer Orders
Call `s4_list_stock_transport_orders` for the material:
- Filter `DeliveryStatus` ≠ FULLY_DELIVERED
- If open orders exist for the period, classify as TF

### Step 4 — Pattern Analysis
- If variance is < 0.5% and consistent across 3+ periods → PL
- If a single movement reversal accounts for > 80% of the variance → TX
- If no movements found in period but stock changed → MD
- If multiple domains show conflicting data simultaneously → SY
- If variance is > 1% with no document explanation → MC (provisional, flag for engineer review)

### Step 5 — Assign Confirmed Root Cause
Select the single best-fit category. If ambiguous, assign the category with the highest evidence weight and note alternatives in the `investigation_notes` field.

## Output Format

```json
{
  "exception_id": "EXC-YYYY-MM-NNNN",
  "material": "<mat>",
  "plant": "<plant>",
  "period": "<period>",
  "confirmed_root_cause": "MC" | "TX" | "MD" | "TF" | "PL" | "SY",
  "confidence": "HIGH" | "MEDIUM" | "LOW",
  "evidence": [
    {"source": "MSEG", "document": "<doc_no>", "detail": "..."},
    {"source": "PHYS", "document": "<doc_no>", "detail": "..."}
  ],
  "investigation_notes": "<free text>",
  "recommended_correction": "<action to resolve>"
}
```

## Instrumentation
Log evidence fetched:
`ROOT_CAUSE_CONFIRMED: exception={id} cause={code} confidence={level} evidence_count={n}`
