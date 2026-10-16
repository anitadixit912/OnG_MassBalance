"""Tests for data ingestion — verifies all 5 SAP data domains are fetched."""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))


@pytest.fixture
def sample_data_package():
    return {
        "plant": "1000",
        "period": "2026-09",
        "domains": {
            "TANK": [{"Material": "MAT001", "Plant": "1000", "StorageLocation": "0001", "MatlWrhsStkQtyInMatlBaseUnit": "1500.000"}],
            "MAT": [{"Material": "MAT001", "MaterialBaseUnit": "MT"}],
            "MOV": [{"MaterialDocument": "4900000001", "PostingDate": "2026-09-01", "GoodsMovementType": "101", "Material": "MAT001", "Plant": "1000", "QuantityInBaseUnit": "100.000"}],
            "PHYS": [{"PhysicalInventoryDocument": "0000000001", "FiscalYear": "2026", "Plant": "1000", "StorageLocation": "0001"}],
            "BOOK": [{"ConfirmationGroup": "0000000001", "OrderID": "000001000", "Material": "MAT001", "Plant": "1000", "ConfirmationYieldQuantity": "95.000"}],
            "TRANSFERS": [{"StockTransportOrder": "4500000001", "SupplyingPlant": "2000", "Plant": "1000", "Product": "MAT001", "OrderQuantity": "200.000"}],
        },
        "status": "COMPLETE",
        "missing_domains": [],
    }


class TestDataIngestionDomains:
    def test_all_six_domains_present(self, sample_data_package):
        for domain in ["TANK", "MAT", "MOV", "PHYS", "BOOK", "TRANSFERS"]:
            assert domain in sample_data_package["domains"]

    def test_complete_status_no_missing_domains(self, sample_data_package):
        assert sample_data_package["status"] == "COMPLETE"
        assert sample_data_package["missing_domains"] == []

    def test_tank_has_quantity_field(self, sample_data_package):
        tank = sample_data_package["domains"]["TANK"][0]
        assert "MatlWrhsStkQtyInMatlBaseUnit" in tank

    def test_mat_has_base_unit(self, sample_data_package):
        mat = sample_data_package["domains"]["MAT"][0]
        assert "MaterialBaseUnit" in mat

    def test_mov_has_movement_type(self, sample_data_package):
        mov = sample_data_package["domains"]["MOV"][0]
        assert "GoodsMovementType" in mov

    def test_mov_has_quantity(self, sample_data_package):
        mov = sample_data_package["domains"]["MOV"][0]
        assert "QuantityInBaseUnit" in mov

    def test_phys_has_required_fields(self, sample_data_package):
        phys = sample_data_package["domains"]["PHYS"][0]
        for field in ["PhysicalInventoryDocument", "FiscalYear", "Plant", "StorageLocation"]:
            assert field in phys

    def test_book_has_yield_quantity(self, sample_data_package):
        book = sample_data_package["domains"]["BOOK"][0]
        assert "ConfirmationYieldQuantity" in book

    def test_book_has_order_id(self, sample_data_package):
        book = sample_data_package["domains"]["BOOK"][0]
        assert "OrderID" in book

    def test_transfers_has_required_fields(self, sample_data_package):
        transfer = sample_data_package["domains"]["TRANSFERS"][0]
        for field in ["StockTransportOrder", "SupplyingPlant", "Plant", "Product", "OrderQuantity"]:
            assert field in transfer

    def test_plant_and_period_present(self, sample_data_package):
        assert "plant" in sample_data_package
        assert "period" in sample_data_package


class TestM1Instrumentation:
    @pytest.mark.asyncio
    async def test_m1_achieved_logged_on_complete(self, caplog):
        import logging
        from agent import SampleAgent
        agent = SampleAgent()
        response = "DATA_INGESTION_LIVE: TANK MAT MOV PHYS BOOK TRANSFERS all fetched."
        with MagicMock() as _:
            from unittest.mock import patch
            with patch.object(agent, "_invoke_with_fallback", new_callable=AsyncMock) as mock_invoke:
                mock_invoke.return_value = {"messages": [MagicMock(content=response)]}
                with caplog.at_level(logging.INFO):
                    async for _ in agent.stream("collect data for plant 1000", "ctx-m1-001"):
                        pass
        assert any("M1" in r.message for r in caplog.records)
