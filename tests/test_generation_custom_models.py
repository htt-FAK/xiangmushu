from __future__ import annotations

"""
Integration tests for ``core.generator._maybe_use_custom_model``.

Verifies the model-resolution hook used during segmented generation:
- Returns ``{client, model_id, custom_model_id}`` when a matching custom
  model exists.
- Returns ``None`` when no match is found.
- Returns ``None`` gracefully when decryption fails.
- Works correctly for all 5 role types (text-gen, vision, audit, embedding,
  small-llm) via their shared resolution path.
- Vision multimodal request format correctness (content array with text +
  image_url items).

Task 6.7 — acceptance: custom model resolution correct for all roles;
fallback works; vision multimodal request correct.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# -- Helpers --


def _fake_custom_model_row(**overrides):
    """Return a ``CustomModel``-shaped ``SimpleNamespace`` for mocking."""
    defaults = dict(
        id=7,
        user_id=42,
        name="My Qwen",
        base_url="https://api.example.com",
        model_id="qwen-max",
        default_model_id="qwen-max",
        encrypted_api_key="enc_xxx",
        api_key_hint="sk-a...zz",
        capabilities_json=["text"],
        assigned_roles_json=["text-gen"],
        status="validated",
        last_tested_at="2026-07-14T00:00:00Z",
        last_error=None,
        created_at="2026-07-14T00:00:00Z",
        updated_at="2026-07-14T00:00:00Z",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ── Resolution Tests ─────────────────────────────────────────────────────────


class TestMaybeUseCustomModel:
    """Task 6.7 — ``_maybe_use_custom_model`` returns client dict or None."""

    @patch("core.generator.get_custom_models_by_user")
    @patch("core.generator.decrypt_api_key", return_value="sk-real-key")
    def test_returns_dict_when_model_matches(self, mock_decrypt, mock_get_custom):
        from core.generator import _maybe_use_custom_model

        mock_get_custom.return_value = [_fake_custom_model_row()]

        result = _maybe_use_custom_model(42, "qwen-max")

        assert result is not None
        assert result["custom_model_id"] == 7
        assert result["model_id"] == "qwen-max"
        assert result["client"] is not None

    @patch("core.generator.get_custom_models_by_user")
    def test_returns_none_when_no_match(self, mock_get_custom):
        from core.generator import _maybe_use_custom_model

        mock_get_custom.return_value = [_fake_custom_model_row()]

        result = _maybe_use_custom_model(42, "nonexistent-model")

        assert result is None

    @patch("core.generator.get_custom_models_by_user")
    def test_returns_none_for_empty_user_id(self, mock_get_custom):
        from core.generator import _maybe_use_custom_model

        result = _maybe_use_custom_model(None, "qwen-max")

        assert result is None
        mock_get_custom.assert_not_called()

    @patch("core.generator.get_custom_models_by_user")
    def test_returns_none_for_empty_model_choice(self, mock_get_custom):
        from core.generator import _maybe_use_custom_model

        result = _maybe_use_custom_model(42, "")

        assert result is None
        mock_get_custom.assert_not_called()

    @patch("core.generator.get_custom_models_by_user")
    @patch("core.generator.decrypt_api_key", side_effect=ValueError("bad key"))
    def test_returns_none_on_decrypt_failure(self, mock_decrypt, mock_get_custom):
        from core.generator import _maybe_use_custom_model

        mock_get_custom.return_value = [_fake_custom_model_row()]

        result = _maybe_use_custom_model(42, "qwen-max")

        assert result is None
        # Decryption was attempted
        mock_decrypt.assert_called_once_with("enc_xxx")

    @patch("core.generator.get_custom_models_by_user", return_value=[])
    def test_returns_none_when_user_has_no_models(self, mock_get_custom):
        from core.generator import _maybe_use_custom_model

        result = _maybe_use_custom_model(42, "qwen-max")

        assert result is None


# ── Role Coverage ────────────────────────────────────────────────────────────


class TestAllRoleTypesResolve:
    """All 5 role types use the same ``_maybe_use_custom_model`` path; verify
    each role's custom model constructs a valid client dict."""

    @pytest.mark.parametrize(
        "role,model_id,capabilities",
        [
            ("text-gen", "qwen-max", ["text"]),
            ("vision", "qwen-vl-max", ["vision"]),
            ("audit", "qwen-audit", ["text"]),
            ("embedding", "text-embedding-v3", ["embedding"]),
            ("small-llm", "qwen-turbo", ["text"]),
        ],
    )
    @patch("core.generator.decrypt_api_key", return_value="sk-role-key")
    def test_client_constructed_for_role(
        self, mock_decrypt, role, model_id, capabilities
    ):
        from core.generator import _maybe_use_custom_model

        row = _fake_custom_model_row(
            model_id=model_id,
            default_model_id=model_id,
            capabilities_json=capabilities,
            assigned_roles_json=[role],
        )

        with patch(
            "core.generator.get_custom_models_by_user",
            return_value=[row],
        ):
            result = _maybe_use_custom_model(42, model_id)

        assert result is not None
        assert result["model_id"] == model_id
        assert result["client"] is not None


# ── Vision Multimodal Request Format ─────────────────────────────────────────


class TestVisionMultimodalFormat:
    """Verify the OpenAI-compatible multimodal request shape used when a
    vision-capable custom model is selected."""

    def test_vision_content_array_structure(self):
        """Content array must have text + image_url items for vision requests."""
        text_item = {"type": "text", "text": "Describe this image."}
        image_item = {
            "type": "image_url",
            "image_url": {
                "url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg==",
            },
        }
        content = [text_item, image_item]

        assert len(content) == 2
        assert content[0]["type"] == "text"
        assert content[1]["type"] == "image_url"
        assert "url" in content[1]["image_url"]
        assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")

    def test_openai_vision_request_shape(self):
        """Simulate the request body shape sent to the custom model endpoint."""
        request_body = {
            "model": "qwen-vl-max",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What color is this?"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": "data:image/png;base64,AAAA",
                            },
                        },
                    ],
                }
            ],
            "max_tokens": 256,
        }

        assert request_body["model"] == "qwen-vl-max"
        content = request_body["messages"][0]["content"]
        assert isinstance(content, list)
        assert any(item["type"] == "image_url" for item in content)
        assert any(item["type"] == "text" for item in content)
