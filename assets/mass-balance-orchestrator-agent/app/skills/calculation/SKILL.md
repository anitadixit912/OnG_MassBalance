---
name: calculation
description: Applies the mass balance formula at Plant, Tank, and Material level with temperature, density, and meter factor corrections
---

# Calculation Skill

## When to Use
Load this skill after validation passes to calculate the mass balance.

## Formula
**Closing = Opening + Receipts − Issues − Consumption ± Transfers ± Adjustments**

- **Opening** = MatlWrhsStkQtyInMatlBaseUnit from TANK (start of period)
- **Receipts** = sum of MOV items with GoodsMovementType in [101, 501]
- **Issues** = sum of MOV items with GoodsMovementType in [201, 261, 601]
- **Consumption** = sum of ConfirmationYieldQuantity from BOOK domain
- **Transfers** = sum of OrderQuantity from TRANSFERS domain
- **Adjustments** = sum of (Quantity − BookQtyBfrCountInMatlBaseUnit) from PHYS domain

## Calculation Levels
1. **Plant level** — aggregate all materials and tanks
2. **Tank/Storage Location level** — per StorageLocation
3. **Material level** — per Material number

## Corrections
Apply before Physical vs. Book comparison:
- Temperature correction
- Density correction
- Meter factor correction
- Water bottom deduction

## Output
Return: closing_stock_MT, physical_stock_MT, book_stock_MT, variance_MT, variance_pct at all 3 levels.

## Instrumentation
On success: `M3.achieved: MASS_BALANCE_CALCULATION_VALIDATED — plant={plant} period={period} levels=plant,tank,material`
On error: `M3.missed: CALCULATION_ERROR — plant={plant} period={period} error={description}`
