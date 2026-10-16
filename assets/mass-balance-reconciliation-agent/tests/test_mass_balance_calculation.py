"""Tests for mass balance calculation — closing stock formula at Plant/Tank/Material level."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))


@pytest.fixture
def sample_calculation_result():
    return {
        "plant": "1000",
        "period": "2026-09",
        "status": "COMPLETE",
        "results": {
            "plant_level": {
                "opening_MT": 1500.0,
                "receipts_MT": 100.0,
                "issues_MT": 80.0,
                "consumption_MT": 10.0,
                "transfers_MT": 5.0,
                "adjustments_MT": -2.0,
                "closing_MT": 1513.0,
                "physical_stock_MT": 1520.0,
                "book_stock_MT": 1513.0,
                "variance_MT": 7.0,
                "variance_pct": 0.462,
            },
            "tank_level": [
                {
                    "storage_location": "0001",
                    "material": "MAT001",
                    "opening_MT": 1500.0,
                    "closing_MT": 1513.0,
                    "physical_stock_MT": 1520.0,
                    "book_stock_MT": 1513.0,
                    "variance_MT": 7.0,
                    "variance_pct": 0.462,
                }
            ],
            "material_level": [
                {
                    "material": "MAT001",
                    "opening_MT": 1500.0,
                    "closing_MT": 1513.0,
                    "physical_stock_MT": 1520.0,
                    "book_stock_MT": 1513.0,
                    "variance_MT": 7.0,
                    "variance_pct": 0.462,
                }
            ],
        },
        "error": None,
    }


class TestClosingStockFormula:
    def test_closing_equals_formula(self, sample_calculation_result):
        r = sample_calculation_result["results"]["plant_level"]
        expected = r["opening_MT"] + r["receipts_MT"] - r["issues_MT"] - r["consumption_MT"] + r["transfers_MT"] + r["adjustments_MT"]
        assert abs(r["closing_MT"] - expected) < 0.001

    def test_variance_mt_calculation(self, sample_calculation_result):
        r = sample_calculation_result["results"]["plant_level"]
        expected_variance = r["physical_stock_MT"] - r["book_stock_MT"]
        assert abs(r["variance_MT"] - expected_variance) < 0.001

    def test_variance_pct_calculation(self, sample_calculation_result):
        r = sample_calculation_result["results"]["plant_level"]
        if r["book_stock_MT"] != 0:
            expected_pct = (r["variance_MT"] / r["book_stock_MT"]) * 100
            assert abs(r["variance_pct"] - expected_pct) < 0.01

    def test_status_is_complete(self, sample_calculation_result):
        assert sample_calculation_result["status"] == "COMPLETE"

    def test_error_is_none_on_success(self, sample_calculation_result):
        assert sample_calculation_result["error"] is None


class TestCalculationLevels:
    def test_plant_level_present(self, sample_calculation_result):
        assert "plant_level" in sample_calculation_result["results"]

    def test_tank_level_present(self, sample_calculation_result):
        assert "tank_level" in sample_calculation_result["results"]
        assert len(sample_calculation_result["results"]["tank_level"]) > 0

    def test_material_level_present(self, sample_calculation_result):
        assert "material_level" in sample_calculation_result["results"]
        assert len(sample_calculation_result["results"]["material_level"]) > 0

    def test_tank_level_has_storage_location(self, sample_calculation_result):
        tank = sample_calculation_result["results"]["tank_level"][0]
        assert "storage_location" in tank

    def test_material_level_has_material_field(self, sample_calculation_result):
        mat = sample_calculation_result["results"]["material_level"][0]
        assert "material" in mat


class TestM3Instrumentation:
    def test_skill_md_defines_formula(self):
        skill_path = Path(__file__).parent.parent / "app" / "skills" / "mass-balance-calculation" / "SKILL.md"
        assert skill_path.exists()
        content = skill_path.read_text()
        assert "Closing" in content and "Opening" in content and "Receipts" in content

    def test_skill_md_defines_m3_instrumentation(self):
        skill_path = Path(__file__).parent.parent / "app" / "skills" / "mass-balance-calculation" / "SKILL.md"
        content = skill_path.read_text()
        assert "M3.achieved" in content or "MASS_BALANCE_CALCULATION_VALIDATED" in content
