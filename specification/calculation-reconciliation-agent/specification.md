# Specification: calculation-reconciliation-agent

> **Guidelines**: Read [guidelines.md](../guidelines.md), [guidelines-agent.md](../guidelines-agent.md), [guidelines-agent-python.md](../guidelines-agent-python.md), [guidelines-agent-mcp.md](../guidelines-agent-mcp.md) before executing.

---

## Role
Applies the mass balance formula at Plant, Tank, and Material level.
Performs temperature/density/meter factor/water bottom corrections.
Compares Physical stock vs. Book stock and returns variance figures to the Orchestrator.

**Formula:** Closing = Opening + Receipts − Issues − Consumption ± Transfers ± Adjustments

---

## Basic Setup

- [ ] Bootstrap agent in `assets/calculation-reconciliation-agent/` using `sap-agent-bootstrap`
- [ ] Write `app/main.py` — A2A server, agent card: "Calculation & Reconciliation Agent"
- [ ] Write `app/agent.py` — system prompt focused on calculation logic; 9 decorators
- [ ] Write supporting files, `requirements.txt`, `Dockerfile`

## System Prompt Requirements

- [ ] Apply closing stock formula at **3 levels**: Plant level, Tank/Storage Location level, Material level
- [ ] **Receipts** = goods movements with GoodsMovementType inbound (101, 501)
- [ ] **Issues** = goods movements with GoodsMovementType outbound (201, 261, 601)
- [ ] **Consumption** = process order confirmation yield quantities from BOOK domain
- [ ] **Transfers** = stock transport order quantities (in-transit adjustment)
- [ ] **Adjustments** = physical inventory adjustment postings from PHYS domain
- [ ] Apply corrections before Physical vs. Book comparison: temperature correction, density correction, meter factor correction, water bottom deduction
- [ ] Return structured result: closing stock per level, physical stock, book stock, variance (MT and %)
- [ ] Never invent or estimate quantities — all figures come from validated data package

## MCP Wiring

- [x] Material Stock MCP, Physical Inventory MCP, Process Order Confirmation MCP declared in `asset.yaml`
- [ ] Verify all 3 MCP servers load at runtime for calculation data access

## Runtime Skills

- [ ] Create `app/skills/mass-balance-calculation/SKILL.md` — step-by-step formula application; correction factors; level-by-level calculation procedure; Physical vs. Book comparison method

## Business Instrumentation

- [ ] Log `M3.achieved: MASS_BALANCE_CALCULATION_VALIDATED — plant={plant} period={period} levels=plant,tank,material` on success
- [ ] Log `M3.missed: CALCULATION_ERROR — plant={plant} period={period} error={description}` on failure

## Testing

- [ ] `tests/test_formula_plant_level.py` — verify plant-level closing stock formula
- [ ] `tests/test_formula_tank_level.py` — verify tank/storage location level calculation
- [ ] `tests/test_formula_material_level.py` — verify material level calculation
- [ ] `tests/test_corrections.py` — verify temperature, density, meter factor corrections applied
- [ ] `tests/test_physical_vs_book.py` — verify variance = Physical − Book computed correctly
- [ ] `tests/test_zero_variance.py` — verify balanced scenario returns zero variance
- [ ] `tests/test_integration.py` — end-to-end: receive validated data → apply formula → return variance results
- [ ] Run `pytest` from `assets/calculation-reconciliation-agent/`; coverage ≥ 70%; `test_report.json` produced
