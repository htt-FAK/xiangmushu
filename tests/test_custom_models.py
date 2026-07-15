from __future__ import annotations

"""
Unit tests for core.custom_models capability probes (_probe_text, _probe_vision,
_probe_embedding) and role suggestion (suggest_roles).

All OpenAI SDK calls are mocked — no real network or API key required.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# -- Helpers --

def _fake_chat_response(content: str = "Hello") -> MagicMock:
    """Return a mock that mimics openai ChatCompletion response."""
    choice = SimpleNamespace(message=SimpleNamespace(content=content))
    return MagicMock(choices=[choice])


def _make_auth_error(status: int = 401) -> Exception:
    err = Exception("authentication error")
    err.status_code = status  # type: ignore[attr-defined]
    return err


def _make_timeout_error() -> Exception:
    return Exception("connection timeout: timed out after 30s")


# ── suggest_roles ────────────────────────────────────────────────────────────


class TestSuggestRoles:
    """Task 2.10 — role suggestion from capabilities."""

    def _suggest(self, caps: list, name: str = "", mid: str = ""):
        from core.custom_models import suggest_roles
        return suggest_roles(caps, model_name=name, model_id=mid)

    def test_qwen_text_suggests_text_gen_and_audit(self):
        result = self._suggest(["text"], "qwen-max", "qwen-max")
        assert result == ["text-gen", "audit"]

    def test_deepseek_text_suggests_text_gen_and_audit(self):
        result = self._suggest(["text"], "deepseek-chat", "deepseek-chat")
        assert result == ["text-gen", "audit"]

    def test_turbo_triggers_small_llm(self):
        result = self._suggest(["text"], "gpt-3.5-turbo", "gpt-3.5-turbo")
        assert result == ["text-gen", "audit", "small-llm"]

    def test_vision_only_no_text_roles(self):
        result = self._suggest(["vision"], "qwen-vl-max", "qwen-vl-max")
        assert result == ["vision"]
        assert "text-gen" not in result
        assert "audit" not in result

    def test_empty_capabilities_returns_empty(self):
        result = self._suggest([], "anything", "anything")
        assert result == []

    def test_ordering_preserved_across_full_capability_set(self):
        result = self._suggest(
            ["text", "vision", "embedding"],
            "qwen-max",
            "qwen-max",
        )
        # Expected order: text-gen, vision, embedding, audit, (no small-llm here)
        assert result == ["text-gen", "vision", "embedding", "audit"]

    def test_flash_triggers_small_llm(self):
        result = self._suggest(["text"], "qwen-flash", "qwen-flash")
        assert "small-llm" in result
        assert "text-gen" in result

    def test_embedding_only(self):
        result = self._suggest(["embedding"], "unknown-model", "unknown-model")
        assert result == ["embedding"]


# ── _probe_text ──────────────────────────────────────────────────────────────


def _run_async(coro):
    """Run an async coroutine synchronously (no pytest-asyncio dependency)."""
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


class TestProbeText:
    """Task 2.7 — text probe with mocked OpenAI client."""

    @patch("core.custom_models._openai_client")
    def test_valid_response_adds_text_capability(self, mock_client_factory):
        from core.custom_models import _probe_text

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _fake_chat_response("Hello world")
        mock_client_factory.return_value = mock_client

        result = _run_async(_probe_text("http://example.com", "sk-key-key", "test-model"))

        assert result["passed"] is True
        assert result["latency_ms"] >= 0

    @patch("core.custom_models._openai_client")
    def test_empty_response_fails(self, mock_client_factory):
        from core.custom_models import _probe_text

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _fake_chat_response("")
        mock_client_factory.return_value = mock_client

        result = _run_async(_probe_text("http://example.com", "sk-key-key", "test-model"))

        assert result["passed"] is False
        assert "empty" in (result.get("detail") or "").lower()

    @patch("core.custom_models._openai_client")
    def test_auth_error_401_classified(self, mock_client_factory):
        from core.custom_models import _probe_text

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = _make_auth_error(401)
        mock_client_factory.return_value = mock_client

        result = _run_async(_probe_text("http://example.com", "bad-key", "test-model"))

        assert result["passed"] is False
        assert result.get("auth_error") is True

    @patch("core.custom_models._openai_client")
    def test_timeout_recorded(self, mock_client_factory):
        from core.custom_models import _probe_text

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = _make_timeout_error()
        mock_client_factory.return_value = mock_client

        result = _run_async(_probe_text("http://example.com", "sk-key", "test-model"))

        assert result["passed"] is False
        assert "timeout" in (result.get("detail") or "").lower()


# ── _probe_vision ─────────────────────────────────────────────────────────────


class TestProbeVision:
    """Task 2.8 — vision probe with mocked multimodal response."""

    @patch("core.custom_models._openai_client")
    def test_vision_success(self, mock_client_factory):
        from core.custom_models import _probe_vision

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _fake_chat_response("blue image")
        mock_client_factory.return_value = mock_client

        result = _run_async(_probe_vision("http://example.com", "sk-key", "qwen-vl-max"))

        assert result["passed"] is True

    @patch("core.custom_models._openai_client")
    def test_vision_422_not_supported(self, mock_client_factory):
        from core.custom_models import _probe_vision

        err = Exception("model does not support image input (status 422)")
        err.status_code = 422  # type: ignore
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = err
        mock_client_factory.return_value = mock_client

        result = _run_async(_probe_vision("http://example.com", "sk-key", "qwen-max"))

        assert result["passed"] is False
        detail = (result.get("detail") or "").lower()
        assert "image" in detail or "vision" in detail or "multimodal" in detail


# ── _probe_embedding ──────────────────────────────────────────────────────────


class TestProbeEmbedding:
    """Task 2.9 — embedding probe with fallback variant logic."""

    @patch("core.custom_models._openai_client")
    def test_embedding_success_primary_model(self, mock_client_factory):
        from core.custom_models import _probe_embedding

        mock_client = MagicMock()
        fake_data = SimpleNamespace(embedding=[0.1, 0.2, 0.3, 0.4])
        mock_client.embeddings.create.return_value = SimpleNamespace(data=[fake_data])
        mock_client_factory.return_value = mock_client

        result = _run_async(_probe_embedding("http://example.com", "sk-key", "text-embedding-v3"))

        assert result["passed"] is True

    @patch("core.custom_models._openai_client")
    def test_embedding_primary_fails_variant_succeeds(self, mock_client_factory):
        from core.custom_models import _probe_embedding

        call_count = {"n": 0}
        fake_data = SimpleNamespace(embedding=[0.1, 0.2, 0.3])

        def side_effect(**kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                # Primary model fails
                raise Exception("model not found")
            # Variant succeeds
            return SimpleNamespace(data=[fake_data])

        mock_client = MagicMock()
        mock_client.embeddings.create.side_effect = side_effect
        mock_client_factory.return_value = mock_client

        # model_id that is NOT text-embedding- prefixed → triggers variant attempt
        result = _run_async(_probe_embedding("http://example.com", "sk-key", "qwen-max"))

        assert result["passed"] is True
        assert call_count["n"] == 2

    @patch("core.custom_models._openai_client")
    def test_empty_embedding_array_fails(self, mock_client_factory):
        from core.custom_models import _probe_embedding

        mock_client = MagicMock()
        fake_data = SimpleNamespace(embedding=[])
        mock_client.embeddings.create.return_value = SimpleNamespace(data=[fake_data])
        mock_client_factory.return_value = mock_client

        result = _run_async(_probe_embedding("http://example.com", "sk-key", "text-embedding-v3"))

        assert result["passed"] is False

    @patch("core.custom_models._openai_client")
    def test_auth_error_stops_variant_attempts(self, mock_client_factory):
        from core.custom_models import _probe_embedding

        auth_err = _make_auth_error(401)
        mock_client = MagicMock()
        mock_client.embeddings.create.side_effect = auth_err
        mock_client_factory.return_value = mock_client

        result = _run_async(_probe_embedding("http://example.com", "sk-key", "qwen-max"))

        assert result["passed"] is False
        assert result.get("auth_error") is True
        # Should only be called once (no variant attempt after auth error)
        assert mock_client.embeddings.create.call_count == 1
