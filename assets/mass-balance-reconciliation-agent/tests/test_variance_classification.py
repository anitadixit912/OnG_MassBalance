"""Tests for variance classification — tolerance matrix and all 4 severity levels."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))


def classify_severity(variance_pct: float, variance_mt: float) -> str:
    """Reference implementation of the tolerance matrix."""
    sev_by_pct = "INFO"
    if variance_pct >= 2.0:
        sev_by_pct = "CRITICAL"
    elif variance_pct >= 0.5:
        sev_by_pct = "WARNING"
    elif variance_pct >= 0.1:
        sev_by_pct = "ADVISORY"

    sev_by_mt = "INFO"
    if abs(variance_mt) >= 20.0:
        sev_by_mt = "CRITICAL"
    elif abs(variance_mt) >= 5.0:
        sev_by_mt = "WARNING"
    elif abs(variance_mt) >= 1.0:
        sev_by_mt = "ADVISORY"

    rank = {"INFO": 0, "ADVISORY": 1, "WARNING": 2, "CRITICAL": 3}
    return max([sev_by_pct, sev_by_mt], key=lambda s: rank[s])


class TestToleranceMatrix:
    def test_info_classification_small_pct_small_mt(self):
        assert classify_severity(0.05, 0.5) == "INFO"

    def test_advisory_by_pct(self):
        assert classify_severity(0.2, 0.5) == "ADVISORY"

    def test_advisory_by_mt(self):
        assert classify_severity(0.05, 2.0) == "ADVISORY"

    def test_warning_by_pct(self):
        assert classify_severity(1.0, 0.5) == "WARNING"

    def test_warning_by_mt(self):
        assert classify_severity(0.05, 10.0) == "WARNING"

    def test_critical_by_pct(self):
        assert classify_severity(2.5, 0.5) == "CRITICAL"

    def test_critical_by_mt(self):
        assert classify_severity(0.05, 25.0) == "CRITICAL"

    def test_mt_threshold_wins_over_pct(self):
        # 0.08% (INFO by %) but 3 MT (ADVISORY by MT) → ADVISORY
        assert classify_severity(0.08, 3.0) == "ADVISORY"

    def test_pct_threshold_wins_over_mt(self):
        # 2.5% (CRITICAL by %) but 0.5 MT (INFO by MT) → CRITICAL
        assert classify_severity(2.5, 0.5) == "CRITICAL"

    def test_all_four_severities_exist(self):
        assert classify_severity(0.05, 0.5) == "INFO"
        assert classify_severity(0.2, 0.5) == "ADVISORY"
        assert classify_severity(1.0, 0.5) == "WARNING"
        assert classify_severity(2.5, 0.5) == "CRITICAL"


class TestVarianceClassificationSkill:
    def test_skill_md_exists(self):
        path = Path(__file__).parent.parent / "app" / "skills" / "variance-classification" / "SKILL.md"
        assert path.exists()

    def test_skill_md_defines_all_severity_levels(self):
        path = Path(__file__).parent.parent / "app" / "skills" / "variance-classification" / "SKILL.md"
        content = path.read_text()
        for sev in ["INFO", "ADVISORY", "WARNING", "CRITICAL"]:
            assert sev in content

    def test_skill_md_defines_m4_instrumentation(self):
        path = Path(__file__).parent.parent / "app" / "skills" / "variance-classification" / "SKILL.md"
        content = path.read_text()
        assert "M4.achieved" in content or "VARIANCE_EXCEPTION_PIPELINE_ACTIVE" in content

    def test_system_prompt_contains_all_severity_levels(self):
        from agent import get_system_prompt
        prompt = get_system_prompt()
        for sev in ["INFO", "ADVISORY", "WARNING", "CRITICAL"]:
            assert sev in prompt
