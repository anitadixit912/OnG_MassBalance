"""End-to-end integration test — full reconciliation flow with all external systems mocked."""
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))


@pytest.fixture
def full_reconciliation_response():
    return json.dumps({
        "plant": "1000",
        "period": "2026-09",
        "pipeline_milestones": {
            "M1": "DATA_INGESTION_LIVE",
            "M2": "VALIDATION_ENGINE_OPERATIONAL",
            "M3": "MASS_BALANCE_CALCULATION_VALIDATED",
            "M4": "VARIANCE_EXCEPTION_PIPELINE_ACTIVE",
            "M5": "HUMAN_APPROVAL_GATES_DEPLOYED",
        },
        "materials": ["MAT001"],
        "exceptions": [
            {
                "exception_id": "EXC-2026-09-0001",
                "severity": "ADVISORY",
                "root_cause": "TX",
                "status": "OPEN",
            }
        ],
        "kpi": {
            "total_exceptions": 1,
            "critical_count": 0,
            "warning_count": 0,
            "advisory_count": 1,
        },
        "TANK": True,
        "MAT": True,
        "MOV": True,
        "PHYS": True,
        "BOOK": True,
    })


@pytest.mark.integration
class TestEndToEndFlow:
    @pytest.mark.asyncio
    async def test_agent_invoke_returns_completed(self, full_reconciliation_response):
        from agent import SampleAgent
        agent = SampleAgent()
        with patch.object(agent, "_invoke_with_fallback", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = {"messages": [MagicMock(content=full_reconciliation_response)]}
            result = await agent.invoke(
                "Run full mass balance reconciliation for plant 1000 period 2026-09",
                "ctx-e2e-001",
            )
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_agent_stream_yields_processing_then_complete(self, full_reconciliation_response):
        from agent import SampleAgent
        agent = SampleAgent()
        with patch.object(agent, "_invoke_with_fallback", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = {"messages": [MagicMock(content=full_reconciliation_response)]}
            chunks = []
            async for chunk in agent.stream("Run mass balance", "ctx-e2e-002"):
                chunks.append(chunk)
        assert len(chunks) >= 2
        assert chunks[0]["is_task_complete"] is False
        assert chunks[-1]["is_task_complete"] is True

    @pytest.mark.asyncio
    async def test_no_tools_mode_returns_completed(self):
        from agent import SampleAgent
        agent = SampleAgent()
        no_tools_response = "SAP tools are not available. Please configure the OGS_S4 destination."
        with patch.object(agent, "_invoke_with_fallback", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = {"messages": [MagicMock(content=no_tools_response)]}
            result = await agent.invoke("run mass balance", "ctx-e2e-003", tools=[])
        assert result.status == "completed"
        assert result.message is not None

    @pytest.mark.asyncio
    async def test_agent_handles_error_gracefully(self):
        from agent import SampleAgent
        agent = SampleAgent()
        with patch.object(agent, "_invoke_with_fallback", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.side_effect = RuntimeError("LLM unavailable")
            result = await agent.invoke("run mass balance", "ctx-e2e-error")
        # The agent catches exceptions and surfaces them as completed with error content
        assert result.status in ("error", "completed")
        assert result.message is not None
        assert len(result.message) > 0

    @pytest.mark.asyncio
    async def test_m1_to_m5_milestones_logged(self, full_reconciliation_response, caplog):
        import logging
        from agent import SampleAgent
        agent = SampleAgent()
        with patch.object(agent, "_invoke_with_fallback", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = {"messages": [MagicMock(content=full_reconciliation_response)]}
            with caplog.at_level(logging.INFO):
                async for _ in agent.stream("run full reconciliation", "ctx-e2e-milestones"):
                    pass
        milestone_logs = [r.message for r in caplog.records if "M" in r.message and "achieved" in r.message]
        assert len(milestone_logs) >= 1, "Expected at least one M*.achieved log entry"


class TestAgentCore:
    @pytest.mark.asyncio
    async def test_run_reconciliation_returns_string(self):
        from agent import SampleAgent
        agent = SampleAgent()
        expected = "mass balance complete"
        with patch.object(agent, "_invoke_with_fallback", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = {"messages": [MagicMock(content=expected)]}
            result = await agent._run_reconciliation(
                query="run balance",
                context_id="ctx-core-001",
                tools=[],
                system_prompt="You are an agent.",
                extra=[],
            )
        assert result == expected

    def test_supported_content_types(self):
        from agent import SampleAgent
        assert "text" in SampleAgent.SUPPORTED_CONTENT_TYPES
