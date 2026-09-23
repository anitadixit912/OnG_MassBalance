---
name: mass-balance-calculation
description: Step-by-step mass balance formula application at Plant, Tank, and Material level. Includes corrections for temperature, density, meter factor, and water bottom. Reference field mappings from SAP IS-Oil OData domains.
---

# Mass Balance Calculation Skill

## When to Use
Load this skill to apply the mass balance formula against validated data domains.

## Core Formula
**Closing = Opening + Receipts − Issues − Consumption ± Transfers ± Adjustments**

## Field Mappings

| Component | Domain | SAP Field |
|-----------|--------|-----------|
| Opening   | TANK   | `MatlWrhsStkQtyInMatlBaseUnit` (start of period record) |
| Receipts  | MOV    | Sum of `QuantityInBaseUnit` where `GoodsMovementType` ∈ {101, 501} |
| Issues    | MOV    | Sum of `QuantityInBaseUnit` where `GoodsMovementType` ∈ {201, 261, 601} |
| Consumption | BOOK | Sum of `ConfirmationYieldQuantity` |
| Transfers | TRANSFERS | Sum of `OrderQuantity` (outbound negative, inbound positive) |
| Adjustments | PHYS | Sum of (`Quantity` − `BookQtyBfrCountInMatlBaseUnit`) per item |

## Calculation Levels

### Level 1 — Plant
Aggregate all materials and storage locations for the plant.
`closing_plant = opening_plant + receipts_plant − issues_plant − consumption_plant ± transfers_plant ± adjustments_plant`

### Level 2 — Tank / Storage Location
Group by `StorageLocation`. Apply formula per storage location.
`closing_tank = opening_tank + receipts_tank − issues_tank − consumption_tank ± transfers_tank ± adjustments_tank`

### Level 3 — Material
Group by `Material`. Apply formula per material number.
`closing_mat = opening_mat + receipts_mat − issues_mat − consumption_mat ± transfers_mat ± adjustments_mat`

## Corrections (apply before Physical vs. Book comparison)

1. **Temperature correction**: Apply API gravity/temperature factor if `TemperatureDifference` field present
2. **Density correction**: Convert volume to mass using `DensityFactor` if present (default 0.85 t/m³ for crude)
3. **Meter factor correction**: Multiply metered volumes by `MeterFactor` (default 1.0)
4. **Water bottom deduction**: Subtract `WaterBottomQuantity` from opening tank reading if present

## Physical vs. Book Variance
`variance_MT = physical_closing_MT − book_closing_MT`
`variance_pct = (variance_MT / book_closing_MT) × 100`  (return 0.0 if book_closing_MT = 0)

## Output Format
```json
{
  "plant": "<plant>",
  "period": "<period>",
  "status": "COMPLETE",
  "results": {
    "plant_level": {
      "opening_MT": 0.0,
      "receipts_MT": 0.0,
      "issues_MT": 0.0,
      "consumption_MT": 0.0,
      "transfers_MT": 0.0,
      "adjustments_MT": 0.0,
      "closing_MT": 0.0,
      "physical_stock_MT": 0.0,
      "book_stock_MT": 0.0,
      "variance_MT": 0.0,
      "variance_pct": 0.0
    },
    "tank_level": [
      {
        "storage_location": "<loc>",
        "material": "<mat>",
        "opening_MT": 0.0,
        "closing_MT": 0.0,
        "physical_stock_MT": 0.0,
        "book_stock_MT": 0.0,
        "variance_MT": 0.0,
        "variance_pct": 0.0
      }
    ],
    "material_level": [
      {
        "material": "<mat>",
        "opening_MT": 0.0,
        "closing_MT": 0.0,
        "physical_stock_MT": 0.0,
        "book_stock_MT": 0.0,
        "variance_MT": 0.0,
        "variance_pct": 0.0
      }
    ]
  },
  "error": null
}
```

## Instrumentation
- On success: `M3.achieved: MASS_BALANCE_CALCULATION_VALIDATED — plant={plant} period={period} levels=plant,tank,material`
- On error: `M3.missed: CALCULATION_ERROR — plant={plant} period={period} error={description}`
