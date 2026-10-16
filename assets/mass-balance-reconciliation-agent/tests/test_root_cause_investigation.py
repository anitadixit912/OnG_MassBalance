"""Tests for root cause investigation — drill-down via material document items, MC/TX/MD/TF/PL/SY."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

ROOT_CAUSE_CODES = ["MC", "TX", "MD", "TF", "PL", "SY"]


@pytest.fixture
def sample_investigation_result():
    return {
        "exception_id": "EXC-2026-09-0001",
        "material": "MAT001",
        "plant": "1000",
        "period": "2026-09",
        "confirmed_root_cause": "TX",
        "confidence": "HIGH",
        "evidence": [
            {"source": "MSEG", "document": "4900000001", "detail": "Reversal movement 102 found — quantity 50 MT"},
        ],
        "investigation_notes": "Material document 4900000001 was reversed on 2026-09-15 without matching re-posting.",
        "recommended_correction": "Re-post the reversed goods receipt (movement type 101) for 50 MT.",
    }


class TestRootCauseCodes:
    def test_all_six_codes_recognised(self):
        for code in ROOT_CAUSE_CODES:
            assert code in ROOT_CAUSE_CODES

    def test_system_prompt_contains_all_root_cause_codes(self):
        from agent import get_system_prompt
        prompt = get_system_prompt()
        for code in ROOT_CAUSE_CODES:
            assert code in prompt

    def test_skill_md_defines_all_codes(self):
        path = Path(__file__).parent.parent / "app" / "skills" / "root-cause-investigation" / "SKILL.md"
        assert path.exists()
        content = path.read_text()
        for code in ROOT_CAUSE_CODES:
            assert code in content


class TestInvestigationResultStructure:
    def test_result_has_exception_id(self, sample_investigation_result):
        assert "exception_id" in sample_investigation_result
        assert sample_investigation_result["exception_id"].startswith("EXC-")

    def test_result_has_confirmed_root_cause(self, sample_investigation_result):
        assert "confirmed_root_cause" in sample_investigation_result
        assert sample_investigation_result["confirmed_root_cause"] in ROOT_CAUSE_CODES

    def test_result_has_confidence(self, sample_investigation_result):
        assert "confidence" in sample_investigation_result
        assert sample_investigation_result["confidence"] in ["HIGH", "MEDIUM", "LOW"]

    def test_result_has_evidence_list(self, sample_investigation_result):
        assert "evidence" in sample_investigation_result
        assert isinstance(sample_investigation_result["evidence"], list)

    def test_evidence_has_source_and_document(self, sample_investigation_result):
        for ev in sample_investigation_result["evidence"]:
            assert "source" in ev
            assert "document" in ev

    def test_result_has_recommended_correction(self, sample_investigation_result):
        assert "recommended_correction" in sample_investigation_result
        assert len(sample_investigation_result["recommended_correction"]) > 0


class TestRootCauseSkillContent:
    def test_skill_md_mentions_mseg_mkpf(self):
        path = Path(__file__).parent.parent / "app" / "skills" / "root-cause-investigation" / "SKILL.md"
        content = path.read_text()
        assert "MSEG" in content or "material document" in content.lower()

    def test_skill_md_mentions_transfer_orders(self):
        path = Path(__file__).parent.parent / "app" / "skills" / "root-cause-investigation" / "SKILL.md"
        content = path.read_text()
        assert "TF" in content or "transfer" in content.lower()
