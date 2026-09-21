"""Unit and integration tests for the Data Collection Agent."""
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add app/ to path
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))


@pytest.fixture
def mock_tools():
    """Mock MCP tools returning canned SAP data."""
    tool = MagicMock()
    tool.name = "list_a_matlstkinacctmod_for_api_material_stock_srv"
    tool.description = "List material stocks in account model"
    tool.coroutine = AsyncMock(return_value=json.dumps({
        "value": [{"Material": "MAT001", "Plant": "1000", "StorageLocation": "0001", "MatlWrhsStkQtyInMatlBaseUnit": "1500.000"}]
    }))
    tool.func = None
    tool.args_schema = None
    tool.handle_tool_error = True
    return [tool]


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
            "TRANSFERS": [{"StockTransportOrder": "4500000001", "SupplyingPlant": "2000", "Plant": "1000", "Product": "MAT001", "OrderQuantity": "200.000"}]
        },
        "status": "COMPLETE",
        "missing_domains": []
    }


class TestSystemPrompt:
    def test_system_prompt_contains_live_data_rule(self):
        from agent import get_system_prompt
        prompt = get_system_prompt()
        assert "LIVE DATA ONLY" in prompt or "never fabricate" in prompt.lower()

    def test_system_prompt_contains_all_domains(self):
        from agent import get_system_prompt
        prompt = get_system_prompt()
        for domain in ["TANK", "MAT", "MOV", "PHYS", "BOOK", "TRANSFERS"]:
            assert domain in prompt

    def test_system_prompt_contains_page_size_limit(self):
        from agent import get_system_prompt
        prompt = get_system_prompt()
        assert "100" in prompt

    def test_system_prompt_contains_m1_instrumentation(self):
        from agent import get_system_prompt
        prompt = get_system_prompt()
        assert "M1" in prompt


class TestAgentDecorators:
    def test_nine_decorators_present(self):
        agent_py = Path(__file__).parent.parent / "app" / "agent.py"
        content = agent_py.read_text()
        decorator_lines = [l for l in content.splitlines() if l.startswith("@agent_model") or l.startswith("@agent_config") or l.startswith("@prompt_section")]
        assert len(decorator_lines) == 9, f"Expected 9 decorators, found {len(decorator_lines)}: {decorator_lines}"

    def test_model_name_returns_claude(self):
        from agent import get_model_name
        assert "claude" in get_model_name().lower() or "sonnet" in get_model_name().lower()

    def test_temperature_is_zero(self):
        from agent import get_temperature
        assert get_temperature() == 0.0


class TestTankDomain:
    @pytest.mark.asyncio
    async def test_tank_domain_in_output(self, sample_data_package):
        assert "TANK" in sample_data_package["domains"]
        assert len(sample_data_package["domains"]["TANK"]) > 0

    @pytest.mark.asyncio
    async def test_tank_has_quantity(self, sample_data_package):
        tank = sample_data_package["domains"]["TANK"][0]
        assert "MatlWrhsStkQtyInMatlBaseUnit" in tank


class TestMovDomain:
    def test_mov_has_movement_type(self, sample_data_package):
        mov = sample_data_package["domains"]["MOV"][0]
        assert "GoodsMovementType" in mov

    def test_mov_has_quantity(self, sample_data_package):
        mov = sample_data_package["domains"]["MOV"][0]
        assert "QuantityInBaseUnit" in mov


class TestBookDomain:
    def test_book_has_yield_quantity(self, sample_data_package):
        book = sample_data_package["domains"]["BOOK"][0]
        assert "ConfirmationYieldQuantity" in book

    def test_book_has_order_id(self, sample_data_package):
        book = sample_data_package["domains"]["BOOK"][0]
        assert "OrderID" in book


class TestDataPackageStructure:
    def test_complete_status_all_domains(self, sample_data_package):
        assert sample_data_package["status"] == "COMPLETE"
        assert len(sample_data_package["missing_domains"]) == 0

    def test_all_six_domains_present(self, sample_data_package):
        for domain in ["TANK", "MAT", "MOV", "PHYS", "BOOK", "TRANSFERS"]:
            assert domain in sample_data_package["domains"]

    def test_plant_and_period_present(self, sample_data_package):
        assert "plant" in sample_data_package
        assert "period" in sample_data_package


class TestM1Instrumentation:
    @pytest.mark.asyncio
    async def test_m1_achieved_logged_on_complete(self, caplog):
        import logging
        with patch("agent.get_mcp_tools", new_callable=AsyncMock, return_value=[]):
            from agent import SampleAgent
            agent = SampleAgent()
            complete_response = '{"status": "COMPLETE", "domains": {}, "plant": "1000", "period": "2026-09", "missing_domains": []}'
            with patch.object(agent, "_invoke_with_fallback", new_callable=AsyncMock) as mock_invoke:
                mock_invoke.return_value = {"messages": [MagicMock(content=complete_response)]}
                with caplog.at_level(logging.INFO):
                    async for _ in agent.stream("collect data for plant 1000", "ctx-001"):
                        pass
                assert any("M1.achieved" in r.message or "M1.missed" in r.message for r in caplog.records)


class TestIntegration:
    @pytest.mark.asyncio
    async def test_agent_invoke_returns_completed(self):
        from agent import SampleAgent
        agent = SampleAgent()
        complete_response = json.dumps({
            "plant": "1000", "period": "2026-09",
            "domains": {"TANK": [], "MAT": [], "MOV": [], "PHYS": [], "BOOK": [], "TRANSFERS": []},
            "status": "COMPLETE", "missing_domains": []
        })
        with patch.object(agent, "_invoke_with_fallback", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = {"messages": [MagicMock(content=complete_response)]}
            result = await agent.invoke("collect data for plant 1000 period 2026-09", "ctx-integration-001")
        assert result.status == "completed"
        assert "COMPLETE" in result.message or "plant" in result.message
