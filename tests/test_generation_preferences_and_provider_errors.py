from __future__ import annotations

from core.fill_task import FillTask
from core.generator import ContentGenerator, QuotaExceededError
from core.provider_errors import classify_provider_error


class DummyVectorStore:
    def __init__(self, results: list[dict], count: int = 1):
        self._results = results
        self._count = count

    def get_collection_count(self) -> int:
        return self._count

    def search(self, query: str, top_k: int, max_distance: float) -> list[dict]:
        return list(self._results)

    def get_all_documents(self, max_chars: int) -> list[dict]:
        return list(self._results)


def _task(task_type: str = "paragraph") -> FillTask:
    return FillTask(
        task_id="t1",
        target_chapter="项目概述",
        task_type=task_type,
        description="根据资料生成内容",
        location_hint={},
        word_limit=200,
    )


def test_generation_bundle_uses_user_generation_model(monkeypatch):
    monkeypatch.setattr("config.FULL_RECALL_MODE", False)
    monkeypatch.setattr(
        "config.get_user_model_for_user",
        lambda user_id, module: {
            "generation": "user-gen-model",
            "lightweight": "user-light-model",
            "search": "user-search-model",
            "vision": "user-vision-model",
        }[module],
    )
    vs = DummyVectorStore(
        [{"distance": 0.9, "text": "evidence", "metadata": {"source": "a.txt"}}],
        count=1,
    )
    generator = ContentGenerator(vs, user_id=7)

    bundle = generator.prepare_generation_bundle(_task(), top_k=4, enable_web=False, retrieval_max_distance=1.0)

    assert bundle.model == "user-gen-model"


def test_generation_bundle_uses_user_search_model_for_web_route(monkeypatch):
    monkeypatch.setattr("config.FULL_RECALL_MODE", False)
    monkeypatch.setattr(
        "config.get_user_model_for_user",
        lambda user_id, module: {
            "generation": "user-gen-model",
            "lightweight": "user-light-model",
            "search": "user-search-model",
            "vision": "user-vision-model",
        }[module],
    )
    vs = DummyVectorStore([], count=1)
    generator = ContentGenerator(vs, user_id=7)

    bundle = generator.prepare_generation_bundle(_task(), top_k=4, enable_web=True, retrieval_max_distance=1.0)

    assert bundle.model == "user-search-model"


def test_generation_bundle_uses_user_lightweight_model_for_strong_rag(monkeypatch):
    monkeypatch.setattr("config.FULL_RECALL_MODE", False)
    monkeypatch.setattr(
        "config.get_user_model_for_user",
        lambda user_id, module: {
            "generation": "user-gen-model",
            "lightweight": "user-light-model",
            "search": "user-search-model",
            "vision": "user-vision-model",
        }[module],
    )
    vs = DummyVectorStore(
        [{"distance": 0.1, "text": "strong evidence", "metadata": {"source": "a.txt"}}],
        count=1,
    )
    generator = ContentGenerator(vs, user_id=7)

    bundle = generator.prepare_generation_bundle(_task(), top_k=4, enable_web=False, retrieval_max_distance=1.0)

    assert bundle.model == "user-light-model"


def test_provider_error_classifies_402_as_quota():
    class PaymentRequiredError(Exception):
        status_code = 402

    result = classify_provider_error(PaymentRequiredError("Payment Required"))

    assert result["code"] == "quota_exceeded"
    assert result["retryable"] is False


def test_provider_error_classifies_429_quota_message_as_quota():
    class RateLimitedQuotaError(Exception):
        status_code = 429

    result = classify_provider_error(RateLimitedQuotaError("429 insufficient_quota: balance exhausted"))

    assert result["code"] == "quota_exceeded"
    assert result["retryable"] is False


def test_generate_from_bundle_raises_quota_error_without_fallback(monkeypatch):
    monkeypatch.setattr("config.FULL_RECALL_MODE", False)
    monkeypatch.setattr("config.get_user_model_for_user", lambda user_id, module: "quota-model")
    vs = DummyVectorStore(
        [{"distance": 0.9, "text": "evidence", "metadata": {"source": "a.txt"}}],
        count=1,
    )
    generator = ContentGenerator(vs, user_id=7)
    bundle = generator.prepare_generation_bundle(_task(), top_k=4, enable_web=False, retrieval_max_distance=1.0)

    calls: list[str] = []

    class QuotaError(Exception):
        status_code = 429

    def fake_chat(*args, **kwargs):
        calls.append(kwargs["model"])
        raise QuotaError("429 insufficient_quota: balance exhausted")

    monkeypatch.setattr("core.generator.chat_completions_create", fake_chat)

    try:
        generator.generate_from_bundle(bundle)
        assert False, "QuotaExceededError was not raised"
    except QuotaExceededError as exc:
        assert exc.model == "quota-model"
        assert exc.module == "generation"

    assert calls == ["quota-model"]


def test_generate_from_bundle_keeps_non_quota_fallback(monkeypatch):
    monkeypatch.setattr("config.FULL_RECALL_MODE", False)
    monkeypatch.setattr("config.get_user_model_for_user", lambda user_id, module: "primary-model")
    monkeypatch.setattr("config.FALLBACK_LLM_MODEL_1", "fallback-model")
    monkeypatch.setattr("config.FALLBACK_LLM_MODEL_2", "")
    monkeypatch.setattr("config.FALLBACK_LLM_MODEL_3", "")
    vs = DummyVectorStore(
        [{"distance": 0.9, "text": "evidence", "metadata": {"source": "a.txt"}}],
        count=1,
    )
    generator = ContentGenerator(vs, user_id=7)
    bundle = generator.prepare_generation_bundle(_task(), top_k=4, enable_web=False, retrieval_max_distance=1.0)

    calls: list[str] = []

    class TemporaryProviderError(Exception):
        status_code = 503

    class _Message:
        def __init__(self, content: str):
            self.content = content

    class _Choice:
        def __init__(self, content: str):
            self.message = _Message(content)

    class _Response:
        def __init__(self, model: str, content: str):
            self.model = model
            self.choices = [_Choice(content)]
            self.usage = None

    def fake_chat(*args, **kwargs):
        calls.append(kwargs["model"])
        if kwargs["model"] == "primary-model":
            raise TemporaryProviderError("provider temporarily unavailable")
        return _Response(kwargs["model"], "fallback success")

    monkeypatch.setattr("core.generator.chat_completions_create", fake_chat)

    result = generator.generate_from_bundle(bundle)

    assert result == "fallback success"
    assert calls == ["primary-model", "fallback-model"]
