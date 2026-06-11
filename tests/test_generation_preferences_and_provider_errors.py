from __future__ import annotations

from core.fill_task import FillTask
from core.generator import ContentGenerator
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
