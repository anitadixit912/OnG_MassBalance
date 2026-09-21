---
name: data-collection
description: Fetches live hydrocarbon data from SAP IS-Oil & Gas OGS_650 via OGS_S4 BTP destination covering TANK, MAT, MOV, PHYS, BOOK, and TRANSFERS domains
---

# Data Collection Skill

## When to Use
Load this skill when you need to collect hydrocarbon data from SAP for a specific plant and period.

## Instructions

### Step 1 — Collect TANK domain (material stock levels)
Use `list_a_matlstkinacctmod_for_api_material_stock_srv` filtered by Plant and StorageLocation.
Set `$top=100`. Returns MatlWrhsStkQtyInMatlBaseUnit per material/storage location.

### Step 2 — Collect MAT domain (material master)
Use `list_a_materialstock_for_api_material_stock_srv`.
Set `$top=100`. Returns Material and MaterialBaseUnit.

### Step 3 — Collect MOV domain (goods movements)
Use `list_a_materialdocumentheader_for_api_material_document_srv` filtered by PostingDate and Plant.
Expand items via `list_a_materialdocumentitem_for_api_material_document_srv`.
Set `$top=100`. Returns GoodsMovementType, Material, QuantityInBaseUnit.

### Step 4 — Collect PHYS domain (physical inventory)
Use `list_physicalinventorydocument_for_sap_self` filtered by Plant and FiscalYear.
Expand items. Set `$top=100`. Returns BookQtyBfrCountInMatlBaseUnit and Quantity.

### Step 5 — Collect BOOK domain (process order confirmations)
Use `list_procordconf2_for_api_proc_order_confirmation_2_srv` filtered by Plant and PostingDate.
Set `$top=100`. Returns ConfirmationYieldQuantity and ConfirmationScrapQuantity.

### Step 6 — Collect TRANSFERS domain (stock transport orders)
Use `list_stocktransportorder_for_sap_self` filtered by SupplyingPlant and CreationDate.
Expand items. Set `$top=100`. Returns OrderQuantity and receiving Plant.

## Completion
Once all 6 domains are collected, log:
`M1.achieved: DATA_INGESTION_LIVE — plant={plant} period={period} domains=TANK,MAT,MOV,PHYS,BOOK,TRANSFERS`

If any domain fails, log:
`M1.missed: DATA_INGESTION_FAILED — plant={plant} period={period} missing_domains={list}`
