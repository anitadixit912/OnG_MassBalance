"""Tests for exception report generation — structure, EXC ID, severity, root cause, status."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))


@pytest.fixture
def sample_exception():
    return {
        "exception_id": "EXC-2026-09-0001",
        "period": "2026-09",
        "plant": "1000",
        "material": "MAT001",
        "storage_location": "0001",
        "variance_MT": 7.0,
        "variance_pct": 0.462,
        "severity": "ADVISORY",
        "root_cause": "TX",
        "supporting_docs": ["4900000001"],
        "recommendation": "Verify and re-post reversed goods receipt.",
        "status": "OPEN",
    }


@pytest.fixture
def sample_exception_report():
    return {
        "report_id": "RPT-2026-09-0001",
        "plant": "1000",
        "period": "2026-09",
        "generated_at": "2026-09-16T10:00:00Z",
        "exceptions": [
            {
                "exception_id": "EXC-2026-09-0001",
                "period": "2026-09",
                "plant": "1000",
                "material": "MAT001",
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
            "info_count": 0,
        },
    }


class TestExceptionIdFormat:
    def test_exception_id_starts_with_exc(self, sample_exception):
        assert sample_exception["exception_id"].startswith("EXC-")

    def test_exception_id_has_year_month_seq(self, sample_exception):
        parts = sample_exception["exception_id"].split("-")
        assert len(parts) == 4, f"Expected EXC-YYYY-MM-NNNN format, got {sample_exception['exception_id']}"

    def test_exception_has_severity(self, sample_exception):
        assert sample_exception["severity"] in ["INFO", "ADVISORY", "WARNING", "CRITICAL"]

    def test_exception_has_root_cause(self, sample_exception):
        assert sample_exception["root_cause"] in ["MC", "TX", "MD", "TF", "PL", "SY"]

    def test_exception_has_status(self, sample_exception):
        assert sample_exception["status"] in ["OPEN", "PENDING_APPROVAL", "APPROVED", "POSTED", "REJECTED"]

    def test_exception_has_recommendation(self, sample_exception):
        assert "recommendation" in sample_exception
        assert len(sample_exception["recommendation"]) > 0


class TestExceptionReportStructure:
    def test_report_has_exception_list(self, sample_exception_report):
        assert "exceptions" in sample_exception_report
        assert isinstance(sample_exception_report["exceptions"], list)

    def test_report_has_kpi_section(self, sample_exception_report):
        assert "kpi" in sample_exception_report

    def test_kpi_has_all_counts(self, sample_exception_report):
        kpi = sample_exception_report["kpi"]
        for field in ["total_exceptions", "critical_count", "warning_count", "advisory_count", "info_count"]:
            assert field in kpi

    def test_kpi_total_matches_sum(self, sample_exception_report):
        kpi = sample_exception_report["kpi"]
        total = kpi["critical_count"] + kpi["warning_count"] + kpi["advisory_count"] + kpi["info_count"]
        assert total == kpi["total_exceptions"]


class TestExceptionReportSkill:
    def test_skill_md_exists(self):
        path = Path(__file__).parent.parent / "app" / "skills" / "exception-report" / "SKILL.md"
        assert path.exists()

    def test_skill_md_defines_exception_table(self):
        path = Path(__file__).parent.parent / "app" / "skills" / "exception-report" / "SKILL.md"
        content = path.read_text()
        assert "Exception ID" in content or "EXC-" in content

    def test_skill_md_defines_executive_summary(self):
        path = Path(__file__).parent.parent / "app" / "skills" / "exception-report" / "SKILL.md"
        content = path.read_text()
        assert "Executive" in content or "KPI" in content or "Summary" in content

    def test_system_prompt_defines_exception_format(self):
        from agent import get_system_prompt
        prompt = get_system_prompt()
        assert "Exception ID" in prompt or "EXC-" in prompt
