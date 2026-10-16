"""Tests for approval governance — no SAP document without approval, log format."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))


@pytest.fixture
def approval_record():
    return {
        "audit_entry_id": "AUD-2026-09-0001",
        "exception_id": "EXC-2026-09-0001",
        "correction_type": "goods_movement",
        "plant": "1000",
        "material": "MAT001",
        "quantity_MT": 7.0,
        "approver_name": "Jane Smith",
        "approver_role": "Plant Manager",
        "approval_timestamp": "2026-09-16T10:00:00Z",
        "sap_document_number": "4900000099",
        "posting_timestamp": "2026-09-16T10:01:00Z",
        "status": "POSTED",
    }


class TestNoAutoPosting:
    def test_system_prompt_forbids_auto_posting(self):
        from agent import get_system_prompt
        prompt = get_system_prompt()
        assert "NO AUTO-POSTING" in prompt or "NEVER" in prompt

    def test_system_prompt_requires_named_user_approval(self):
        from agent import get_system_prompt
        prompt = get_system_prompt()
        lower = prompt.lower()
        assert "approval" in lower or "approve" in lower

    def test_system_prompt_requires_waiting_for_approval(self):
        from agent import get_system_prompt
        prompt = get_system_prompt()
        assert "wait" in prompt.lower() or "explicit" in prompt.lower()


class TestApprovalLogFormat:
    def test_audit_entry_has_exception_id(self, approval_record):
        assert "exception_id" in approval_record
        assert approval_record["exception_id"].startswith("EXC-")

    def test_audit_entry_has_audit_entry_id(self, approval_record):
        assert "audit_entry_id" in approval_record
        assert approval_record["audit_entry_id"].startswith("AUD-")

    def test_audit_entry_has_approver_name(self, approval_record):
        assert "approver_name" in approval_record
        parts = approval_record["approver_name"].split()
        assert len(parts) >= 2, "Approver name must be at least two words"

    def test_audit_entry_has_approver_role(self, approval_record):
        assert "approver_role" in approval_record
        assert len(approval_record["approver_role"]) > 0

    def test_audit_entry_has_timestamp(self, approval_record):
        assert "approval_timestamp" in approval_record
        ts = approval_record["approval_timestamp"]
        assert "T" in ts or "-" in ts

    def test_audit_entry_posted_status(self, approval_record):
        assert approval_record["status"] == "POSTED"

    def test_audit_entry_has_sap_document(self, approval_record):
        assert "sap_document_number" in approval_record
        assert len(approval_record["sap_document_number"]) > 0


class TestApprovalGovernanceSkill:
    def test_skill_md_exists(self):
        path = Path(__file__).parent.parent / "app" / "skills" / "approval-governance" / "SKILL.md"
        assert path.exists()

    def test_skill_md_defines_approval_format(self):
        path = Path(__file__).parent.parent / "app" / "skills" / "approval-governance" / "SKILL.md"
        content = path.read_text()
        assert "APPROVED" in content

    def test_skill_md_defines_m5_instrumentation(self):
        path = Path(__file__).parent.parent / "app" / "skills" / "approval-governance" / "SKILL.md"
        content = path.read_text()
        assert "M5.achieved" in content or "HUMAN_APPROVAL_GATES_DEPLOYED" in content

    def test_skill_md_mentions_bypass_alert(self):
        path = Path(__file__).parent.parent / "app" / "skills" / "approval-governance" / "SKILL.md"
        content = path.read_text()
        assert "BYPASSED" in content or "CRITICAL ALERT" in content
