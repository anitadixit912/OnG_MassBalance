---
name: validation
description: Validates completeness, consistency, and referential integrity of collected hydrocarbon data. Blocks pipeline on failure.
---

# Validation Skill

## When to Use
Load this skill after data collection to validate the data package before any calculation.

## Validation Rules

### 1. Completeness Check
All 6 domains must have at least one record for the requested plant and period.
If any domain is empty → FAIL immediately. Do not proceed.

### 2. Consistency Check
- Material numbers in MOV must exist in MAT domain
- Physical inventory items must reference valid plant/storage locations in TANK
- Opening stock + movements must be internally consistent

### 3. Referential Integrity
- All material document items must reference existing materials
- All PHYS items must reference valid plant/storage combinations

### 4. Outlier Detection
- Flag any quantity deviating more than 3 standard deviations from the period average
- Flag any material/tank with no PHYS count in the period

## Output
On PASS: return structured PASS response with record counts per domain.
On FAIL: return structured FAIL response with domain, field, and error description. **HALT pipeline.**

## Instrumentation
On pass: `M2.achieved: VALIDATION_ENGINE_OPERATIONAL — plant={plant} period={period} checks_passed={count}`
On fail: `M2.missed: VALIDATION_FAILED — plant={plant} period={period} error={description}`
