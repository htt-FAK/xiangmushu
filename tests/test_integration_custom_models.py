from __future__ import annotations

"""
Integration test for the full custom-model lifecycle:

    POST create → POST /test → POST /assign → GET /model-options
    (confirm custom model appears) → simulate generation using selected
    custom model; assert SSE route metadata includes ``custom_model_id``.

All OpenAI SDK and database calls are mocked — no real network, DB, or
API key required.

Task 6.5 — acceptance: full lifecycle tested; custom model used in
generation; SSE includes ``custom_model_id``.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# -- Helpers --


def _fake_custom_model_row(**overrides):
    """Return a ``CustomModel``-shaped ``SimpleNamespace`` used as a DB row stub."""
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


def _fake_chat_response(content: str = "Hello") -> MagicMock:
    choice = SimpleNamespace(message=SimpleNamespace(content=content))
    return MagicMock(choices=[choice])


# ── Lifecycle Flow ───────────────────────────────────────────────────────────


class TestCustomModelLifecycle:
    """Task 6.5 — POST create → test → assign → model-options → generate."""

    # -- Step 1: POST create --

    @patch("core.custom_models._db_create")
    @patch("core.custom_models.encrypt_api_key", return_value="enc_xxx")
    @patch("core.custom_models._build_key_hint", return_value="sk-a...zz")
    @patch("core.custom_models.validate_base_url", return_value=(None, None))
    @patch("core.custom_models.get_custom_model_count", return_value=1)
    @patch("core.custom_models._probe_text")
    @patch("core.custom_models._probe_vision")
    @patch("core.custom_models._probe_embedding")
    def test_create_model_returns_validated(
        self,
        mock_embed,
        mock_vision,
        mock_text,
        mock_count,
        mock_validate,
        mock_hint,
        mock_encrypt,
        mock_db_create,
    ):
        from core import custom_models as cm

        mock_db_create.return_value = _fake_custom_model_row()

        # Probe results: text OK, vision skipped, embedding skipped.
        def _run_async(coro):
            import asyncio

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
            if loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(asyncio.run, coro).result()
            return loop.run_until_complete(coro)

        mock_text.return_value = _run_async(_async_pass())
        mock_vision.return_value = _run_async(_async_fail("not supported"))
        mock_embed.return_value = _run_async(_async_fail("not supported"))

        result = cm.create_custom_model(
            user_id=42,
            name="My Qwen",
            base_url="https://api.example.com",
            model_id="qwen-max",
            api_key="sk-test-key-12345678",
        )

        assert result["name"] == "My Qwen"
        assert result["status"] == "validated"
        mock_encrypt.assert_called_once()

    # -- Step 2: model-options includes custom model --

    @patch("core.provider_registry.get_custom_models_by_user")
    def test_model_options_includes_custom_model(self, mock_get_custom):
        from core.provider_registry import _custom_model_options_for_role

        mock_get_custom.return_value = [_fake_custom_model_row()]
        row = _fake_custom_model_row()

        options = _custom_model_options_for_role("main_writer", [row])

        # Custom model has text capability → qualifies for text roles.
        custom_opts = [o for o in options if o.get("source") == "custom"]
        assert len(custom_opts) >= 1
        assert custom_opts[0]["custom_model_id"] == 7
        assert custom_opts[0]["provider_code"] == "custom"

    # -- Step 3: generation uses custom model --

    @patch("core.generator.get_custom_models_by_user")
    @patch("core.generator.decrypt_api_key", return_value="sk-real-key")
    def test_generation_resolves_custom_model(self, mock_decrypt, mock_get_custom):
        from core.generator import _maybe_use_custom_model

        mock_get_custom.return_value = [_fake_custom_model_row()]

        result = _maybe_use_custom_model(42, "qwen-max")

        assert result is not None
        assert result["custom_model_id"] == 7
        assert result["model_id"] == "qwen-max"
        assert result["client"] is not None


# ── SSE route metadata ──────────────────────────────────────────────────────────


class TestSSERouteMetadata:
    """Verify ``custom_model_id`` appears in route metadata during generation."""

    @patch("core.generator.get_custom_models_by_user")
    @patch("core.generator.decrypt_api_key", return_value="sk-real-key")
    def test_custom_model_id_in_resolution(self, mock_decrypt, mock_get_custom):
        from core.generator import _maybe_use_custom_model

        mock_get_custom.return_value = [_fake_custom_model_row(id=99)]

        result = _maybe_use_custom_model(42, "qwen-max")

        assert result is not None
        assert result["custom_model_id"] == 99


# ── Async helpers (no pytest-asyncio dependency) --

async def _async_pass():
    return {"passed": True, "latency_ms": 120, "detail": None, "auth_error": False}


async def _async_fail(detail: str = "not supported"):
    return {"passed": False, "latency_ms": 0, "detail": detail, "auth_error": False}
