from __future__ import annotations

"""
Integration tests for ``ContentAuditor._resolve_custom_audit_client``.

Verifies the audit-model resolution precedence chain:
1. New ``user_custom_models`` table (``audit`` role) wins when present.
2. Falls back to old ``user_custom_audit_models`` table when new table empty.
3. Falls back to platform default when both tables empty.
4. If both tables have entries, new table takes precedence.
5. If new-table decryption fails, falls through to old table.

All OpenAI SDK and database calls are mocked — no real network, DB, or
API key required.

Task 6.8 — acceptance: audit resolution precedence verified; backward
compatibility maintained; migration preserves audit data.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# -- Helpers --


def _make_new_table_row(**overrides):
    """Return a ``CustomModel``-shaped ``SimpleNamespace`` for the new table."""
    defaults = dict(
        id=10,
        user_id=42,
        name="New Audit Model",
        base_url="https://api.new.example.com",
        model_id="qwen-audit",
        default_model_id="qwen-audit",
        encrypted_api_key="enc_new_key",
        api_key_hint="sk-n...ew",
        capabilities_json=["text"],
        assigned_roles_json=["audit"],
        status="validated",
        last_tested_at="2026-07-14T00:00:00Z",
        last_error=None,
        created_at="2026-07-14T00:00:00Z",
        updated_at="2026-07-14T00:00:00Z",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_old_table_record(**overrides):
    """Return a legacy ``UserCustomAuditModel``-shaped ``SimpleNamespace``."""
    defaults = dict(
        id=5,
        user_id=42,
        name="Old Audit Model",
        base_url="https://api.old.example.com",
        model_id="qwen-old-audit",
        encrypted_api_key="enc_old_key",
        api_key_hint="sk-o...ld",
        status="validated",
        validated_at="2026-07-01T00:00:00Z",
    )
    defaults.update(overrides)
    record = SimpleNamespace(**defaults)
    # The legacy record exposes ``decrypted_api_key()`` as a method.
    record.decrypted_api_key = lambda: "sk-decrypted-old"
    return record


def _make_auditor(user_id=42):
    """Instantiate ``ContentAuditor`` with minimal kwargs (mocked)."""
    with patch("core.content_auditor.config") as mock_config:
        mock_config.AUDIT_LLM_MODEL = "default-audit-model"
        from core.content_auditor import ContentAuditor

        auditor = ContentAuditor.__new__(ContentAuditor)
        auditor._user_id = user_id
        auditor._custom_audit_client_cache = None
        return auditor


# ── Precedence Tests ─────────────────────────────────────────────────────────


class TestNewTableTakesPrecedence:
    """When new table has audit-assigned model, it is used over old table."""

    @patch("core.content_auditor.decrypt_api_key", return_value="sk-new-decrypted")
    @patch("core.content_auditor.get_custom_models_by_role")
    def test_uses_new_table_when_present(self, mock_get_by_role, mock_decrypt):
        from core.content_auditor import ContentAuditor

        mock_get_by_role.return_value = [_make_new_table_row()]
        auditor = _make_auditor()

        result = auditor._resolve_custom_audit_client()

        assert result["status"] == "used_custom_new"
        assert result["record_id"] == 10
        assert result["model_id"] == "qwen-audit"
        assert result["client"] is not None

    @patch("core.content_auditor.decrypt_api_key", return_value="sk-new-decrypted")
    @patch("core.content_auditor.get_custom_models_by_role")
    @patch("core.content_auditor._custom_audit_module")
    def test_new_table_wins_over_old(
        self, mock_old_module, mock_get_by_role, mock_decrypt
    ):
        mock_get_by_role.return_value = [_make_new_table_row()]
        mock_old_module.get_by_user_id.return_value = _make_old_table_record()
        auditor = _make_auditor()

        result = auditor._resolve_custom_audit_client()

        assert result["status"] == "used_custom_new"
        assert result["record_id"] == 10
        # Old table should not have been consulted
        mock_old_module.get_by_user_id.assert_not_called()


class TestFallbackToOldTable:
    """When new table empty, falls back to old ``user_custom_audit_models``."""

    @patch("core.content_auditor.get_custom_models_by_role", return_value=[])
    @patch("core.content_auditor._custom_audit_module")
    def test_falls_back_when_new_empty(self, mock_old_module, mock_get_by_role):
        mock_old_module.get_by_user_id.return_value = _make_old_table_record()
        auditor = _make_auditor()

        result = auditor._resolve_custom_audit_client()

        assert result["status"] == "used_custom"
        assert result["record_id"] == 5
        assert result["model_id"] == "qwen-old-audit"

    @patch("core.content_auditor.get_custom_models_by_role", return_value=[])
    @patch("core.content_auditor._custom_audit_module")
    def test_old_table_validated_status_required(self, mock_old_module, mock_get):
        record = _make_old_table_record(status="untested")
        mock_old_module.get_by_user_id.return_value = record
        auditor = _make_auditor()

        result = auditor._resolve_custom_audit_client()

        assert result["status"] == "default"
        assert result["client"] is None


class TestFallbackToDefault:
    """When both tables are empty, returns default (no custom audit model)."""

    @patch("core.content_auditor.get_custom_models_by_role", return_value=[])
    @patch("core.content_auditor._custom_audit_module")
    def test_both_empty_returns_default(self, mock_old_module, mock_get_by_role):
        mock_old_module.get_by_user_id.return_value = None
        auditor = _make_auditor()

        result = auditor._resolve_custom_audit_client()

        assert result["status"] == "default"
        assert result["client"] is None
        assert result["model_id"] is None
        assert result["record_id"] is None


class TestGracefulDecryptFailure:
    """If new-table decryption fails, falls through to old table."""

    @patch("core.content_auditor.get_custom_models_by_role")
    @patch("core.content_auditor.decrypt_api_key", side_effect=ValueError("bad key"))
    @patch("core.content_auditor._custom_audit_module")
    def test_decrypt_fail_falls_to_old(
        self, mock_old_module, mock_decrypt, mock_get_by_role
    ):
        mock_get_by_role.return_value = [_make_new_table_row()]
        mock_old_module.get_by_user_id.return_value = _make_old_table_record()
        auditor = _make_auditor()

        result = auditor._resolve_custom_audit_client()

        # Should have fallen through to the old table
        assert result["status"] == "used_custom"
        assert result["record_id"] == 5
        assert result["model_id"] == "qwen-old-audit"


class TestNoUserId:
    """When ``user_id`` is None, returns default immediately."""

    def test_none_user_returns_default(self):
        auditor = _make_auditor(user_id=None)

        result = auditor._resolve_custom_audit_client()

        assert result["status"] == "default"
        assert result["client"] is None


class TestMemoization:
    """Result is cached on instance; second call does not re-query DB."""

    @patch("core.content_auditor.get_custom_models_by_role", return_value=[])
    @patch("core.content_auditor._custom_audit_module")
    def test_second_call_uses_cache(self, mock_old_module, mock_get_by_role):
        mock_old_module.get_by_user_id.return_value = None
        auditor = _make_auditor()

        result1 = auditor._resolve_custom_audit_client()
        result2 = auditor._resolve_custom_audit_client()

        assert result1 is result2
        # DB queried only once
        mock_get_by_role.assert_called_once()
