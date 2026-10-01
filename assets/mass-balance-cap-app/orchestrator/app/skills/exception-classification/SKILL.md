---
name: exception-classification
description: Applies tolerance matrix to classify variance severity and root cause. Drills into MSEG/MKPF to build evidence packages.
---

# Exception Classification Skill

## When to Use
Load this skill after calculation to classify variances and build evidence packages.

## Tolerance Matrix
- **INFO**: variance < 0.1% AND < 1 MT — record only
- **ADVISORY**: variance 0.1–0.5% OR 1–5 MT — investigate, recommend review
- **WARNING**: variance 0.5–2.0% OR 5–20 MT — investigate urgently, recommend correction
- **CRITICAL**: variance > 2.0% OR > 20 MT — escalate immediately

## Root Cause Categories
- **MC** — Meter Calibration error
- **TX** — Transaction/data entry error
- **MD** — Missing or delayed document
- **TF** — Transfer in transit (STO issued but not yet received)
- **PL** — Process loss (evaporation, sampling, line fill)
- **SY** — System/interface error

## Evidence Package
For each exception, drill down using:
- `list_a_materialdocumentitem_for_api_material_document_srv` — movement history
- `list_stocktransportorder_for_sap_self` — check for in-transit transfers (TF)
- `list_physicalinventorydocumentitem_for_sap_self` — book vs counted quantities

## Exception ID Format
EXC-{YYYY-MM}-{NNNN} e.g. EXC-2026-09-0001

## Critical Rule
All exceptions must have status **OPEN**. Never auto-post corrections.

## Instrumentation
On success: `M4.achieved: VARIANCE_EXCEPTION_PIPELINE_ACTIVE — plant={plant} period={period} exceptions={count} critical={count}`
On error: `M4.missed: CLASSIFICATION_FAILED — plant={plant} period={period} error={description}`
