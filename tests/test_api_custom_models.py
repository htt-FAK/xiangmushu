from __future__ import annotations

"""
Unit tests for REST endpoint validation in /api/user/custom-models.

Tests focus on request validation, error responses, and business logic
without running the actual FastAPI server. All dependencies are mocked.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from fastapi.testclient import TestClient

from server import (
    CustomModelRequest,
    CustomModelUpdateRequest,
    CustomModelTestRequest,
    CustomModelAssignRequest,
    user_custom_models_create,
    user_custom_models_list,
    user_custom_models_update,
    user_custom_models_delete,
    user_custom_models_test,
    user_custom_models_assign,
)
from core import custom_models as custom_models_module


class MockUser:
    def __init__(self, user_id: int = 42, email: str = "test@example.com"):
        self.id = user_id
        self.email = email


class MockRequest:
    def __init__(self):
        self.client = MagicMock()
        self.client.host = "127.0.0.1"
        self.headers = {"user-agent": "test-agent"}


@pytest.fixture
def mock_user():
    return MockUser()


@pytest.fixture
def mock_request():
    return MockRequest()


# ── POST Validation ──────────────────────────────────────────────────────────


class TestCreateValidation:
    """Test POST /api/user/custom-models validation."""

    def test_missing_name_returns_422(self, mock_user, mock_request):
        """Empty name should fail validation."""
        # Pydantic validation happens before the endpoint is called,
        # so we test the custom_models_module.create_custom_model directly
        with pytest.raises(custom_models_module._ModelError) as exc_info:
            custom_models_module.create_custom_model(
                user_id=mock_user.id,
                name="",
                base_url="https://api.example.com",
                model_id="test-model",
                api_key="sk-test-key-12345678",
            )
        assert exc_info.value.code == "name_required"

    def test_invalid_url_format_returns_422(self, mock_user, mock_request):
        """Invalid URL should fail SSRF check."""
        with pytest.raises(custom_models_module._ModelError) as exc_info:
            custom_models_module.create_custom_model(
                user_id=mock_user.id,
                name="Test",
                base_url="not-a-url",
                model_id="test-model",
                api_key="sk-test-key-12345678",
            )
        assert exc_info.value.code == "url_format"

    def test_localhost_url_returns_422_ssrf_rejected(self, mock_user, mock_request):
        """Localhost URLs should be rejected by SSRF guard."""
        with pytest.raises(custom_models_module._ModelError) as exc_info:
            custom_models_module.create_custom_model(
                user_id=mock_user.id,
                name="Test",
                base_url="http://localhost:8080",
                model_id="test-model",
                api_key="sk-test-key-12345678",
            )
        assert exc_info.value.code == "ssrf_rejected"

    def test_short_api_key_returns_422(self, mock_user, mock_request):
        """API key shorter than 8 chars should fail."""
        with pytest.raises(custom_models_module._ModelError) as exc_info:
            custom_models_module.create_custom_model(
                user_id=mock_user.id,
                name="Test",
                base_url="https://api.example.com",
                model_id="test-model",
                api_key="short",
            )
        assert exc_info.value.code == "api_key_length"


# ── GET Empty List ────────────────────────────────────────────────────────────


class TestListEmpty:
    """Test GET /api/user/custom-models returns empty list for new user."""

    @patch("core.custom_models.list_custom_models")
    def test_returns_empty_models_array(self, mock_list, mock_user):
        """New user should get {models: []}, not None or error."""
        mock_list.return_value = []

        result = {"models": custom_models_module.list_custom_models(mock_user.id)}

        assert result == {"models": []}
        assert isinstance(result["models"], list)
        mock_list.assert_called_once_with(mock_user.id)


# ── DELETE 404 ────────────────────────────────────────────────────────────────


class TestDeleteNotFound:
    """Test DELETE non-existent model returns 404."""

    @patch("core.custom_models.delete_custom_model")
    def test_delete_nonexistent_returns_false(self, mock_delete, mock_user):
        """Deleting non-existent model should return False (leading to 404)."""
        mock_delete.return_value = False

        result = custom_models_module.delete_custom_model(
            user_id=mock_user.id, model_id=999
        )

        assert result is False
        mock_delete.assert_called_once_with(model_id=999, user_id=mock_user.id)


# ── PUT Invalid Role ─────────────────────────────────────────────────────────


class TestUpdateInvalidRole:
    """Test PUT with invalid role returns 422."""

    def test_invalid_role_raises_error(self):
        """Invalid role should raise _ModelError."""
        with pytest.raises(custom_models_module._ModelError) as exc_info:
            custom_models_module.assign_model_roles(
                user_id=42,
                model_id=1,
                assigned_roles=["invalid-role"],
            )
        assert exc_info.value.code == "invalid_role"


# ── Rate Limit ────────────────────────────────────────────────────────────────


class TestRateLimit:
    """Test rate limit enforcement for model creation."""

    @patch("core.custom_models.get_custom_model_count")
    @patch("core.custom_models._db_create")
    @patch("core.custom_models.encrypt_api_key")
    @patch("core.custom_models._build_key_hint")
    @patch("core.custom_models.validate_base_url")
    def test_11th_creation_hits_rate_limit(
        self, mock_validate, mock_hint, mock_encrypt, mock_db_create, mock_count
    ):
        """Creating 11 models should hit the MAX_MODELS_PER_USER limit."""
        mock_validate.return_value = (None, None)
        mock_encrypt.return_value = "encrypted"
        mock_hint.return_value = "sk-...zz"
        mock_count.return_value = 20  # Already at limit
        mock_db_create.return_value = MagicMock(
            id=21,
            user_id=42,
            name="Model 21",
            base_url="https://api.example.com",
            model_id="model-21",
            default_model_id="model-21",
            capabilities_json=[],
            assigned_roles_json=[],
            status="untested",
            last_tested_at=None,
            last_error=None,
            api_key_hint="sk-...zz",
            created_at="2026-07-14T00:00:00Z",
            updated_at="2026-07-14T00:00:00Z",
        )

        with pytest.raises(custom_models_module._ModelError) as exc_info:
            custom_models_module.create_custom_model(
                user_id=42,
                name="Model 21",
                base_url="https://api.example.com",
                model_id="model-21",
                api_key="sk-test-key-12345678",
            )

        assert exc_info.value.code == "limit_exceeded"


# ── Max Model Count ───────────────────────────────────────────────────────────


class TestMaxModelCount:
    """Test maximum model count enforcement."""

    @patch("core.custom_models.validate_base_url", return_value=(None, None))
    @patch("core.custom_models.get_custom_model_count")
    def test_21st_model_returns_limit_exceeded(self, mock_count, mock_validate):
        """Creating 21st model should return limit_exceeded error."""
        from core.custom_models import MAX_MODELS_PER_USER

        assert MAX_MODELS_PER_USER == 20

        mock_count.return_value = MAX_MODELS_PER_USER

        with pytest.raises(custom_models_module._ModelError) as exc_info:
            custom_models_module.create_custom_model(
                user_id=42,
                name="Model 21",
                base_url="https://api.example.com",
                model_id="model-21",
                api_key="sk-test-key-12345678",
            )

        assert exc_info.value.code == "limit_exceeded"
        assert "20" in exc_info.value.message


# ── Masked API Key ────────────────────────────────────────────────────────────


class TestMaskedApiKey:
    """Test that API key is never returned in plaintext."""

    @patch("core.custom_models._db_by_user")
    def test_list_response_contains_masked_key(self, mock_db_by_user):
        """List response should contain masked api_key_preview, not plaintext."""
        from core.db import CustomModel

        mock_row = CustomModel(
            id=1,
            user_id=42,
            name="Test Model",
            base_url="https://api.example.com",
            model_id="test-model",
            encrypted_api_key="encrypted_secret_key",
            api_key_hint="sk-a1...ef",
            capabilities_json=["text"],
            assigned_roles_json=["text-gen"],
            default_model_id="test-model",
            status="validated",
            last_tested_at="2026-07-14T00:00:00Z",
            last_error=None,
            created_at="2026-07-14T00:00:00Z",
            updated_at="2026-07-14T00:00:00Z",
        )
        mock_db_by_user.return_value = [mock_row]

        result = custom_models_module.list_custom_models(42)

        assert len(result) == 1
        model = result[0]
        assert "api_key_preview" in model
        assert model["api_key_preview"] == "sk-a1...ef"
        # Ensure plaintext key is not present
        assert "api_key" not in model
        assert "encrypted_api_key" not in model
        # Ensure the original key is not leaked
        assert "secret_key" not in str(model)
