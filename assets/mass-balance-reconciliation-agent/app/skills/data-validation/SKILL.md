---
name: data-validation
description: Step-by-step data validation rules for the five SAP IS-Oil data domains (TANK, MAT, MOV, PHYS, BOOK). Run before any mass balance calculation — halt pipeline on failure.
---

# Data Validation Skill

## When to Use
Load this skill to validate completeness, consistency, and referential integrity across all five data domains before any calculation proceeds.

## Pipeline Rule
If ANY validation check fails, log `M2.missed: VALIDATION_FAILED` and HALT — do NOT proceed to calculation.

## Step 1 — Completeness Checks

### TANK domain
- At least one stock record must exist for the requested plant
- `MatlWrhsStkQtyInMatlBaseUnit` must not be null or empty
- `Plant` must match the requested plant code

### MAT domain
- At least one material master record must exist for each material found in TANK
- `Material` and `MaterialBaseUnit` fields must be present

### MOV domain
- At least one movement document must exist for the period
- `MaterialDocument`, `PostingDate`, `GoodsMovementType`, `QuantityInBaseUnit` must all be present
- `PostingDate` must fall within the requested period

### PHYS domain
- `PhysicalInventoryDocument`, `FiscalYear`, `Plant`, `StorageLocation` required per item
- If no physical inventory documents exist for the period, log a WARNING and continue (not a hard failure)

### BOOK domain
- `ConfirmationGroup`, `OrderID`, `Material`, `Plant`, `ConfirmationYieldQuantity` required per item
- If no process order confirmations exist for the period, log a WARNING and continue (not a hard failure)

### TRANSFERS domain
- `StockTransportOrder`, `SupplyingPlant`, `Plant`, `Product`, `OrderQuantity` required per item
- If no transfer orders exist, this is acceptable — set `transfers_MT = 0`

## Step 2 — Consistency Checks

- Every material in MOV must appear in TANK or MAT (no orphaned movements)
- Every material in BOOK must appear in TANK (no orphaned confirmations)
- `GoodsMovementType` must be a recognised SAP movement type (101, 201, 261, 501, 601, 701 etc.)
- `QuantityInBaseUnit` must be a non-negative number (negative quantities indicate SAP reversal — flag as advisory)
- `PostingDate` must be a valid ISO date (YYYY-MM-DD)

## Step 3 — Referential Integrity

- Material codes in all domains must be consistent (no trailing spaces, consistent formatting)
- Plant codes must match across all domains
- Storage location codes in PHYS must appear in TANK records

## Validation Result Structure

```json
{
  "plant": "<plant>",
  "period": "<period>",
  "status": "PASS" | "FAIL",
  "checks": [
    {"domain": "TANK", "check": "completeness", "result": "PASS" | "FAIL", "detail": "..."},
    {"domain": "MAT",  "check": "completeness", "result": "PASS" | "FAIL", "detail": "..."},
    {"domain": "MOV",  "check": "completeness", "result": "PASS" | "FAIL", "detail": "..."},
    {"domain": "PHYS", "check": "completeness", "result": "PASS" | "WARN", "detail": "..."},
    {"domain": "BOOK", "check": "completeness", "result": "PASS" | "WARN", "detail": "..."},
    {"domain": "MOV",  "check": "consistency",  "result": "PASS" | "FAIL", "detail": "..."},
    {"domain": "ALL",  "check": "referential_integrity", "result": "PASS" | "FAIL", "detail": "..."}
  ],
  "errors": ["<description of each FAIL>"],
  "warnings": ["<description of each WARN>"]
}
```

## Instrumentation
- On all checks passing: `M2.achieved: VALIDATION_ENGINE_OPERATIONAL — plant={plant} period={period} checks={n} passed`
- On any hard FAIL: `M2.missed: VALIDATION_FAILED — plant={plant} period={period} error={description}`
