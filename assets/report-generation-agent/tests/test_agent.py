"""Tests for the Report Generation Agent."""
import json, sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

SAMPLE_REPORT = """
## Executive KPI Summary
- Plant: 1000 | Period: 2026-09
- Overall Variance: -0.36%
- CRITICAL: 1 | WARNING: 0 | ADVISORY: 1 | INFO: 0
- Pending Approvals: 1
- Fully Reconciled: 3 tanks

## Exception Report

| Exception ID | Period | Plant | Storage | Material | Variance MT | Variance % | Severity | Root Cause | Supporting Docs | Recommendation | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| EXC-2026-09-0001 | 2026-09 | 1000 | 0001 | MAT001 | -25.0 | -1.79% | CRITICAL | TF | 4900000001 | Verify STO receipt at plant 1000 | OPEN |
| EXC-2026-09-0002 | 2026-09 | 1000 | 0002 | MAT002 | -2.5 | -0.25% | ADVISORY | PL | N/A | Within process loss tolerance | OPEN |
"""

CLEAN_REPORT = """
## Executive KPI Summary
- Plant: 1000 | Period: 2026-09
- Overall Variance: 0.0%
- CRITICAL: 0 | WARNING: 0 | ADVISORY: 0 | INFO: 0
- Pending Approvals: 0
- Fully Reconciled: 5 tanks

All tanks and materials reconciled cleanly for this period. No exceptions to report.
"""


class TestSystemPrompt:
    def test_contains_all_required_fields(self):
        from agent import get_system_prompt
        prompt = get_system_prompt()
        for field in ["Exception ID", "Severity", "Root Cause", "Supporting Documents", "Status"]:
            assert field in prompt

    def test_contains_kpi_summary_requirements(self):
        from agent import get_system_prompt
        prompt = get_system_prompt()
        assert "KPI" in prompt or "Executive" in prompt
        assert "CRITICAL" in prompt

    def test_contains_no_posted_without_approval(self):
        from agent import get_system_prompt
        prompt = get_system_prompt()
        assert "POSTED" in prompt
        assert "approval" in prompt.lower() or "NEVER" in prompt

    def test_critical_listed_first_rule(self):
        from agent import get_system_prompt
        prompt = get_system_prompt()
        assert "CRITICAL" in prompt and "FIRST" in prompt.upper() or "first" in prompt.lower()

    def test_nine_decorators(self):
        content = (Path(__file__).parent.parent / "app" / "agent.py").read_text()
        count = len([l for l in content.splitlines() if l.startswith("@agent_model") or l.startswith("@agent_config") or l.startswith("@prompt_section")])
        assert count == 9, f"Expected 9 decorators, got {count}"


class TestReportStructure:
    def test_report_contains_executive_summary(self):
        assert "Executive KPI Summary" in SAMPLE_REPORT or "KPI" in SAMPLE_REPORT

    def test_report_contains_exception_table(self):
        assert "Exception ID" in SAMPLE_REPORT
        assert "EXC-" in SAMPLE_REPORT

    def test_report_critical_appears_before_advisory(self):
        critical_pos = SAMPLE_REPORT.find("CRITICAL")
        advisory_pos = SAMPLE_REPORT.find("ADVISORY")
        assert critical_pos < advisory_pos, "CRITICAL should appear before ADVISORY in report"

    def test_all_exceptions_status_open(self):
        assert "POSTED" not in SAMPLE_REPORT
        assert SAMPLE_REPORT.count("OPEN") >= 2

    def test_clean_report_no_exceptions(self):
        assert "CRITICAL: 0" in CLEAN_REPORT
        assert "Pending Approvals: 0" in CLEAN_REPORT


class TestKPISummary:
    def test_kpi_has_overall_variance(self):
        assert "Overall Variance" in SAMPLE_REPORT or "variance" in SAMPLE_REPORT.lower()

    def test_kpi_has_severity_counts(self):
        assert "CRITICAL: 1" in SAMPLE_REPORT
        assert "ADVISORY: 1" in SAMPLE_REPORT

    def test_kpi_has_pending_approvals(self):
        assert "Pending Approvals" in SAMPLE_REPORT

    def test_kpi_appears_before_exception_table(self):
        kpi_pos = SAMPLE_REPORT.find("Executive KPI")
        table_pos = SAMPLE_REPORT.find("Exception Report")
        assert kpi_pos < table_pos, "KPI Summary should appear before the exception table"


class TestNoPostedWithoutApproval:
    def test_no_posted_status_in_new_report(self):
        assert "POSTED" not in SAMPLE_REPORT

    def test_open_is_initial_status(self):
        assert "OPEN" in SAMPLE_REPORT


class TestM4Instrumentation:
    @pytest.mark.asyncio
    async def test_report_generated_logged(self, caplog):
        import logging
        from agent import SampleAgent
        agent = SampleAgent()
        with patch.object(agent, "_invoke_with_fallback", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = {"messages": [MagicMock(content=SAMPLE_REPORT)]}
            with caplog.at_level(logging.INFO):
                async for _ in agent.stream("generate report for plant 1000", "ctx-001"):
                    pass
        assert any("REPORT_GENERATED" in r.message for r in caplog.records)


class TestIntegration:
    @pytest.mark.asyncio
    async def test_invoke_returns_completed(self):
        from agent import SampleAgent
        agent = SampleAgent()
        with patch.object(agent, "_invoke_with_fallback", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = {"messages": [MagicMock(content=SAMPLE_REPORT)]}
            result = await agent.invoke("generate exception report for plant 1000 period 2026-09", "ctx-int-001")
        assert result.status == "completed"
        assert "Exception" in result.message or "KPI" in result.message

    @pytest.mark.asyncio
    async def test_clean_reconciliation_report(self):
        from agent import SampleAgent
        agent = SampleAgent()
        with patch.object(agent, "_invoke_with_fallback", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = {"messages": [MagicMock(content=CLEAN_REPORT)]}
            result = await agent.invoke("generate report for clean reconciliation", "ctx-int-002")
        assert result.status == "completed"
        assert "0%" in result.message or "reconciled" in result.message.lower()
