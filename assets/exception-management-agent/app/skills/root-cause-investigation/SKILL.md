---
name: root-cause-investigation
description: Evidence-gathering playbook for each root cause category (MC/TX/MD/TF/PL/SY). Maps root cause to MCP tool queries and document drilldown patterns.
---

# Root Cause Investigation Skill

## When to Use
Load this skill when you need to assign and justify a root cause category for a classified exception.

## Root Cause Categories

### MC — Meter Calibration Error
**Indicators**: Systematic positive or negative variance across all materials in a storage location; variance pattern correlated with tank size.
**Evidence query**: Check TANK domain for calibration remarks; look for `CalibrationFactor` deviations.
**Recommended correction**: Re-calibrate meter; post adjustment document.

### TX — Transaction / Data Entry Error
**Indicators**: Single large variance spike; movement document quantity inconsistent with surrounding transactions.
**Evidence query**: Use `list_a_materialdocumentitem_for_api_material_document_srv` filtered by Material, StorageLocation, PostingDate. Look for duplicate postings or reversed movements without corresponding originals.
**Recommended correction**: Reverse erroneous material document; re-post correct quantity.

### MD — Missing or Delayed Document
**Indicators**: Receipts expected (STO confirmed at sending plant) but not yet posted at receiving plant.
**Evidence query**: Use `list_stocktransportorder_for_sap_self` with SupplyingPlant filter; check DeliveryDocumentItem for GoodsReceiptStatus = blank.
**Recommended correction**: Post pending goods receipt; rerun balance.

### TF — Transfer In Transit
**Indicators**: Variance amount matches one or more open STO quantities; sending plant shows issue, receiving plant has not received.
**Evidence query**: Use `list_stocktransportorder_for_sap_self` filtered by CreationDate and plant. Check `ScheduleLineDeliveryDate` vs. period end date.
**Recommended correction**: No immediate correction; await GR posting. Flag in report as "in-transit".

### PL — Process Loss
**Indicators**: Small consistent variance (< 0.5%) across multiple periods; variance correlates with throughput volume (higher throughput → higher absolute loss).
**Evidence query**: Compare current period variance_pct with prior 3 periods. No document evidence available — inherent to process.
**Recommended correction**: Accept if within operational tolerance; otherwise investigate pipeline integrity.

### SY — System / Interface Error
**Indicators**: Zero quantities in domains that should have data; duplicate records; data truncation artifacts.
**Evidence query**: Check domain record counts vs. expected (e.g., PHYS count for period should match tank count). Look for null field values in key quantity fields.
**Recommended correction**: Re-extract data from SAP; escalate to Basis/interface team if persistent.

## Evidence Package Fields
Always populate `supporting_documents` with relevant material document numbers, STO numbers, or physical inventory document numbers found during investigation.

If no documents are found, set `supporting_documents: []` and note "No supporting documents found — root cause assigned by pattern analysis" in `recommended_correction`.
