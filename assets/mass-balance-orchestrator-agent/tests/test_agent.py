"""Tests for the Mass Balance Orchestrator Agent."""
import json, sys, logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

PIPELINE_COMPLETE_RESPONSE = """
## Executive KPI Summary
- Plant: 1000 | Period: 2026-09
- Overall Variance: -0.36%
- CRITICAL: 1 | WARNING: 0 | ADVISORY: 1 | INFO: 0
- Pending Approvals: 1

## Exception Report
| EXC-2026-09-0001 | CRITICAL | TF | -25.0 MT | OPEN |

Do you approve posting correction EXC-2026-09-0001? Please confirm with your name and role.
"""

PIPELINE_VALIDATION_FAIL = """
Pipeline halted at Step 2 — Validation Failed.

Errors:
- TANK domain: No records found for plant 1000 period 2026-09

Please check OGS_S4 destination connectivity and retry.
"""

PIPELINE_CLEAN = """
## Executive KPI Summary
- Plant: 1000 | Period: 2026-09
- Overall Variance: 0.0%
- CRITICAL: 0 | WARNING: 0 | ADVISORY: 0 | INFO: 0

All tanks and materials reconciled cleanly. No corrections required.
"""


class TestSystemPrompt:
    def test_contains_five_pipeline_steps(self):
        from agent import get_system_prompt
        prompt = get_system_prompt()
        for step in ["Data Collection", "Validation", "Calculation", "Exception", "Report"]:
            assert step in prompt

    def test_contains_no_auto_post_rule(self):
        from agent import get_system_prompt
        prompt = get_system_prompt()
        assert "NEVER auto-post" in prompt or "never auto-post" in prompt.lower()

    def test_contains_validation_halt_rule(self):
        from agent import get_system_prompt
        prompt = get_system_prompt()
        assert "HALT" in prompt or "halt" in prompt.lower()
        assert "FAIL" in prompt

    def test_contains_approval_gate(self):
        from agent import get_system_prompt
        prompt = get_system_prompt()
        assert "approval" in prompt.lower() or "approve" in prompt.lower()

    def test_contains_m5_instrumentation(self):
        from agent import get_system_prompt
        assert "M5" in get_system_prompt()

    def test_nine_decorators(self):
        content = (Path(__file__).parent.parent / "app" / "agent.py").read_text()
        count = len([l for l in content.splitlines() if l.startswith("@agent_model") or l.startswith("@agent_config") or l.startswith("@prompt_section")])
        assert count == 9, f"Expected 9 decorators, got {count}"


class TestPipelineHappyPath:
    @pytest.mark.asyncio
    async def test_pipeline_returns_report(self):
        from agent import SampleAgent
        agent = SampleAgent()
        with patch.object(agent, "_invoke_with_fallback", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = {"messages": [MagicMock(content=PIPELINE_CLEAN)]}
            result = await agent.invoke("run mass balance for plant 1000 period 2026-09", "ctx-001")
        assert result.status == "completed"
        assert "reconciled" in result.message.lower() or "KPI" in result.message

    @pytest.mark.asyncio
    async def test_approval_gate_triggered_on_exceptions(self):
        from agent import SampleAgent
        agent = SampleAgent()
        with patch.object(agent, "_invoke_with_fallback", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = {"messages": [MagicMock(content=PIPELINE_COMPLETE_RESPONSE)]}
            result = await agent.invoke("run mass balance for plant 1000", "ctx-002")
        # When approval is needed, agent should request user input
        assert result.status in ["input_required", "completed"]
        assert "approve" in result.message.lower() or "CRITICAL" in result.message


class TestValidationHalt:
    @pytest.mark.asyncio
    async def test_pipeline_halts_on_validation_fail(self):
        from agent import SampleAgent
        agent = SampleAgent()
        with patch.object(agent, "_invoke_with_fallback", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = {"messages": [MagicMock(content=PIPELINE_VALIDATION_FAIL)]}
            result = await agent.invoke("run mass balance for plant 1000", "ctx-003")
        assert result.status == "completed"
        assert "Validation Failed" in result.message or "halted" in result.message.lower()


class TestApprovalGate:
    @pytest.mark.asyncio
    async def test_approval_accepted(self, caplog):
        from agent import SampleAgent
        agent = SampleAgent()
        approved_response = "Correction EXC-2026-09-0001 approved and posted."
        with patch.object(agent, "_invoke_with_fallback", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = {"messages": [MagicMock(content=approved_response)]}
            with caplog.at_level(logging.INFO):
                chunks = []
                async for chunk in agent.handle_approval("approve — John Smith, Plant Manager", "ctx-004"):
                    chunks.append(chunk)
        assert any("M5.achieved" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_rejection_no_posting(self):
        from agent import SampleAgent
        agent = SampleAgent()
        chunks = []
        async for chunk in agent.handle_approval("reject — variance too small to correct", "ctx-005"):
            chunks.append(chunk)
        last = chunks[-1]
        assert last["is_task_complete"] is True
        assert "rejected" in last["content"].lower()
        assert "No SAP document" in last["content"]

    @pytest.mark.asyncio
    async def test_no_auto_post_without_approval(self):
        """Verify the agent prompts for approval rather than auto-posting."""
        from agent import SampleAgent
        agent = SampleAgent()
        with patch.object(agent, "_invoke_with_fallback", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = {"messages": [MagicMock(content=PIPELINE_COMPLETE_RESPONSE)]}
            chunks = []
            async for chunk in agent.stream("run mass balance for plant 1000", "ctx-006"):
                chunks.append(chunk)
        # Check approval is requested — not auto-posted
        last = chunks[-1]
        assert last.get("require_user_input") is True or "approve" in last["content"].lower()


class TestAuditTrail:
    @pytest.mark.asyncio
    async def test_approval_logged_with_details(self, caplog):
        from agent import SampleAgent
        agent = SampleAgent()
        approved_response = "Correction posted."
        with patch.object(agent, "_invoke_with_fallback", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = {"messages": [MagicMock(content=approved_response)]}
            with caplog.at_level(logging.INFO):
                async for _ in agent.handle_approval("yes, approve — Ahmed Al-Rashid, Senior Engineer", "ctx-007"):
                    pass
        approval_logs = [r for r in caplog.records if "M5.achieved" in r.message]
        assert len(approval_logs) > 0
        assert "Ahmed" in approval_logs[0].message or "approval received" in approval_logs[0].message.lower()


class TestIntegration:
    @pytest.mark.asyncio
    async def test_full_pipeline_clean_reconciliation(self):
        from agent import SampleAgent
        agent = SampleAgent()
        with patch.object(agent, "_invoke_with_fallback", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = {"messages": [MagicMock(content=PIPELINE_CLEAN)]}
            result = await agent.invoke("run daily mass balance for plant 1000 for 2026-09-21", "ctx-int-001")
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_error_handling_returns_completed(self):
        from agent import SampleAgent
        agent = SampleAgent()
        with patch.object(agent, "_invoke_with_fallback", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.side_effect = Exception("Connection timeout")
            result = await agent.invoke("run mass balance", "ctx-int-002")
        assert result.status == "completed"
        assert "error" in result.message.lower()
