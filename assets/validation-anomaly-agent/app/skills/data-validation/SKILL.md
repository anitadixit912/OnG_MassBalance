---
name: data-validation
description: Detailed validation rules for hydrocarbon data completeness, consistency, referential integrity, and outlier detection across all 6 SAP IS-Oil & Gas data domains.
---

# Data Validation Skill

## When to Use
Load this skill when you need detailed validation criteria beyond the system prompt summary.

## Domain Coverage
All 6 domains must be present for the requested plant AND period:
- **TANK** — `list_a_matlstkinacctmod_for_api_material_stock_srv` results
- **MAT** — `list_a_materialstock_for_api_material_stock_srv` results
- **MOV** — `list_a_materialdocumentheader_for_api_material_document_srv` results (with items)
- **PHYS** — `list_physicalinventorydocument_for_sap_self` results (with items)
- **BOOK** — `list_procordconf2_for_api_proc_order_confirmation_2_srv` results
- **TRANSFERS** — `list_stocktransportorder_for_sap_self` results

## Rule 1 — Completeness
- Each domain array must contain ≥ 1 record
- Empty array → FAIL immediately; name the domain in the error
- PARTIAL status from data collection (missing_domains not empty) → FAIL

## Rule 2 — Consistency
- Every Material in MOV items must appear in MAT domain
- Every StorageLocation in PHYS items must appear in TANK domain
- BOOK ConfirmationYieldQuantity must be ≥ 0
- MOV GoodsMovementType must be a known IS-Oil code (101, 201, 261, 501, 601 are standard)
- TRANSFERS OrderQuantity must be ≥ 0

## Rule 3 — Referential Integrity
- MOV header DocumentDate must fall within the requested period
- PHYS FiscalYear must match the period year
- BOOK PostingDate must fall within the requested period
- TRANSFERS ScheduleLineDeliveryDate must fall within the requested period ± 30 days (in-transit tolerance)

## Rule 4 — Outlier Detection
For each continuous quantity field (MatlWrhsStkQtyInMatlBaseUnit, QuantityInBaseUnit, ConfirmationYieldQuantity, OrderQuantity):
1. Compute mean and standard deviation across all records in the domain
2. Flag any value > 3 standard deviations from the mean as a WARNING
3. A zero value for stock that was non-zero in the same material last period → WARNING (possible missing reading)
4. Negative stock quantity → ERROR (fail with domain=TANK, field=MatlWrhsStkQtyInMatlBaseUnit)

## FAIL Response Template
```json
{
  "status": "FAIL",
  "plant": "<plant>",
  "period": "<period>",
  "records_validated": {"TANK": 0, "MAT": 0, "MOV": 0, "PHYS": 0, "BOOK": 0, "TRANSFERS": 0},
  "errors": [
    {"domain": "<domain>", "field": "<field or 'count'>", "error": "<description>"}
  ],
  "warnings": []
}
```

## PASS Response Template
```json
{
  "status": "PASS",
  "plant": "<plant>",
  "period": "<period>",
  "records_validated": {"TANK": 12, "MAT": 45, "MOV": 230, "PHYS": 18, "BOOK": 67, "TRANSFERS": 14},
  "errors": [],
  "warnings": [
    {"domain": "<domain>", "field": "<field>", "warning": "<description>"}
  ]
}
```

## Instrumentation
- On PASS: `M2.achieved: VALIDATION_ENGINE_OPERATIONAL — plant={plant} period={period} checks_passed={count}`
- On FAIL: `M2.missed: VALIDATION_FAILED — plant={plant} period={period} error={first_error_description}`
