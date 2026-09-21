"""Tests for Validation & Anomaly Agent."""
import json, sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))


@pytest.fixture
def pass_response():
    return json.dumps({"status": "PASS", "plant": "1000", "period": "2026-09", "records_validated": {"TANK": 5, "MAT": 5, "MOV": 20, "PHYS": 5, "BOOK": 10, "TRANSFERS": 3}, "errors": [], "warnings": []})

@pytest.fixture
def fail_response():
    return json.dumps({"status": "FAIL", "plant": "1000", "period": "2026-09", "records_validated": {"TANK": 0, "MAT": 5, "MOV": 20, "PHYS": 5, "BOOK": 10, "TRANSFERS": 3}, "errors": [{"domain": "TANK", "field": "records", "error": "No TANK records found for plant 1000 period 2026-09"}], "warnings": []})


class TestSystemPrompt:
    def test_contains_completeness_rule(self):
        from agent import get_system_prompt
        prompt = get_system_prompt()
        assert "Completeness" in prompt or "completeness" in prompt

    def test_contains_consistency_rule(self):
        from agent import get_system_prompt
        prompt = get_system_prompt()
        assert "Consistency" in prompt or "consistency" in prompt

    def test_contains_fail_halt_rule(self):
        from agent import get_system_prompt
        prompt = get_system_prompt()
        assert "FAIL" in prompt
        assert "halt" in prompt.lower() or "NEVER" in prompt

    def test_contains_m2_instrumentation(self):
        from agent import get_system_prompt
        prompt = get_system_prompt()
        assert "M2" in prompt

    def test_nine_decorators(self):
        agent_py = Path(__file__).parent.parent / "app" / "agent.py"
        content = agent_py.read_text()
        count = len([l for l in content.splitlines() if l.startswith("@agent_model") or l.startswith("@agent_config") or l.startswith("@prompt_section")])
        assert count == 9, f"Expected 9 decorators, got {count}"


class TestPassResponse:
    def test_pass_status_has_no_errors(self, pass_response):
        data = json.loads(pass_response)
        assert data["status"] == "PASS"
        assert len(data["errors"]) == 0

    def test_pass_has_all_domains(self, pass_response):
        data = json.loads(pass_response)
        for domain in ["TANK", "MAT", "MOV", "PHYS", "BOOK", "TRANSFERS"]:
            assert domain in data["records_validated"]

    def test_pass_has_record_counts(self, pass_response):
        data = json.loads(pass_response)
        for count in data["records_validated"].values():
            assert count > 0


class TestFailResponse:
    def test_fail_status_has_errors(self, fail_response):
        data = json.loads(fail_response)
        assert data["status"] == "FAIL"
        assert len(data["errors"]) > 0

    def test_fail_error_has_domain_field_and_message(self, fail_response):
        data = json.loads(fail_response)
        error = data["errors"][0]
        assert "domain" in error
        assert "field" in error
        assert "error" in error

    def test_fail_identifies_empty_domain(self, fail_response):
        data = json.loads(fail_response)
        assert data["records_validated"]["TANK"] == 0
        assert any(e["domain"] == "TANK" for e in data["errors"])


class TestM2Instrumentation:
    @pytest.mark.asyncio
    async def test_m2_achieved_on_pass(self, caplog, pass_response):
        import logging
        from agent import SampleAgent
        agent = SampleAgent()
        with patch.object(agent, "_invoke_with_fallback", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = {"messages": [MagicMock(content=pass_response)]}
            with caplog.at_level(logging.INFO):
                async for _ in agent.stream("validate data package", "ctx-001"):
                    pass
        assert any("M2.achieved" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_m2_missed_on_fail(self, caplog, fail_response):
        import logging
        from agent import SampleAgent
        agent = SampleAgent()
        with patch.object(agent, "_invoke_with_fallback", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = {"messages": [MagicMock(content=fail_response)]}
            with caplog.at_level(logging.WARNING):
                async for _ in agent.stream("validate data package", "ctx-002"):
                    pass
        assert any("M2.missed" in r.message for r in caplog.records)


class TestIntegration:
    @pytest.mark.asyncio
    async def test_invoke_returns_completed_on_pass(self, pass_response):
        from agent import SampleAgent
        agent = SampleAgent()
        with patch.object(agent, "_invoke_with_fallback", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = {"messages": [MagicMock(content=pass_response)]}
            result = await agent.invoke("validate data for plant 1000", "ctx-int-001")
        assert result.status == "completed"
        assert "PASS" in result.message

    @pytest.mark.asyncio
    async def test_invoke_returns_fail_response(self, fail_response):
        from agent import SampleAgent
        agent = SampleAgent()
        with patch.object(agent, "_invoke_with_fallback", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = {"messages": [MagicMock(content=fail_response)]}
            result = await agent.invoke("validate data for plant 1000", "ctx-int-002")
        assert result.status == "completed"
        assert "FAIL" in result.message
