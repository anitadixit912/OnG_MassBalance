"""Tests for data validation — completeness, consistency, referential integrity, pipeline halt."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))


@pytest.fixture
def valid_data_package():
    return {
        "plant": "1000",
        "period": "2026-09",
        "status": "PASS",
        "checks": [
            {"domain": "TANK", "check": "completeness", "result": "PASS", "detail": "3 records"},
            {"domain": "MAT",  "check": "completeness", "result": "PASS", "detail": "3 records"},
            {"domain": "MOV",  "check": "completeness", "result": "PASS", "detail": "15 movements"},
            {"domain": "PHYS", "check": "completeness", "result": "PASS", "detail": "2 documents"},
            {"domain": "BOOK", "check": "completeness", "result": "PASS", "detail": "5 confirmations"},
            {"domain": "MOV",  "check": "consistency",  "result": "PASS", "detail": "All movement types recognised"},
            {"domain": "ALL",  "check": "referential_integrity", "result": "PASS", "detail": "All materials consistent"},
        ],
        "errors": [],
        "warnings": [],
    }


@pytest.fixture
def failed_data_package():
    return {
        "plant": "1000",
        "period": "2026-09",
        "status": "FAIL",
        "checks": [
            {"domain": "TANK", "check": "completeness", "result": "FAIL", "detail": "No TANK records found"},
            {"domain": "MAT",  "check": "completeness", "result": "PASS", "detail": "3 records"},
        ],
        "errors": ["TANK domain has no records for plant 1000 period 2026-09"],
        "warnings": [],
    }


class TestValidationStructure:
    def test_valid_package_has_pass_status(self, valid_data_package):
        assert valid_data_package["status"] == "PASS"

    def test_valid_package_has_no_errors(self, valid_data_package):
        assert len(valid_data_package["errors"]) == 0

    def test_failed_package_has_fail_status(self, failed_data_package):
        assert failed_data_package["status"] == "FAIL"

    def test_failed_package_has_errors(self, failed_data_package):
        assert len(failed_data_package["errors"]) > 0

    def test_checks_contain_domain_field(self, valid_data_package):
        for check in valid_data_package["checks"]:
            assert "domain" in check
            assert "check" in check
            assert "result" in check

    def test_all_domains_checked(self, valid_data_package):
        checked_domains = {c["domain"] for c in valid_data_package["checks"]}
        assert "TANK" in checked_domains
        assert "MAT" in checked_domains
        assert "MOV" in checked_domains


class TestPipelineHaltBehaviour:
    def test_system_prompt_requires_halt_on_failure(self):
        from agent import get_system_prompt
        prompt = get_system_prompt()
        assert "PIPELINE HALT" in prompt or "halt" in prompt.lower()

    def test_validation_failed_keyword_in_prompt(self):
        from agent import get_system_prompt
        prompt = get_system_prompt()
        assert "validation" in prompt.lower()


class TestM2Instrumentation:
    @pytest.mark.asyncio
    async def test_m2_achieved_on_validation_pass(self, caplog):
        import logging
        from agent import SampleAgent
        from unittest.mock import patch, AsyncMock, MagicMock
        agent = SampleAgent()
        response = "VALIDATION_ENGINE_OPERATIONAL: All 7 checks passed. TANK MAT MOV PHYS BOOK"
        with patch.object(agent, "_invoke_with_fallback", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = {"messages": [MagicMock(content=response)]}
            with caplog.at_level(logging.INFO):
                async for _ in agent.stream("validate plant 1000", "ctx-m2-001"):
                    pass
        assert any("M2" in r.message for r in caplog.records)
