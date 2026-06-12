from __future__ import annotations

from core.evidence_pack import WebFact, build_task_evidence_pack
from core.fill_task import FillTask


class DummyVectorStore:
    def __init__(self, results: list[dict], count: int = 1):
        self._results = results
        self._count = count

    def get_collection_count(self) -> int:
        return self._count

    def search(self, query: str, top_k: int = 3, max_distance: float | None = None) -> list[dict]:
        return list(self._results[:top_k])

    def get_all_documents(self, max_chars: int = 0) -> list[dict]:
        return list(self._results)


def _task() -> FillTask:
    return FillTask(
        task_id="task-1",
        target_chapter="项目背景",
        task_type="paragraph",
        description="围绕数字化转型和政策支持撰写背景",
        location_hint={},
        word_limit=300,
    )


def test_evidence_pack_compresses_and_deduplicates(monkeypatch):
    monkeypatch.setattr("config.FULL_RECALL_MODE", False)
    results = [
        {
            "text": "数字化转型政策支持企业升级。数字化转型政策支持企业升级。无关内容很长很长。",
            "metadata": {"source": "a.txt"},
            "distance": 0.1,
        }
    ]

    pack = build_task_evidence_pack(DummyVectorStore(results), _task(), budget_chars=80)

    assert pack.kb_hits == 1
    assert pack.best_similarity == 0.9
    assert pack.kb_facts == ["数字化转型政策支持企业升级。"]
    assert pack.summary()["kb_fact_count"] == 1


def test_evidence_pack_marks_gap_when_kb_empty(monkeypatch):
    monkeypatch.setattr("config.FULL_RECALL_MODE", False)

    pack = build_task_evidence_pack(DummyVectorStore([], count=0), _task())

    assert pack.weak_kb is True
    assert pack.gaps == ["知识库未提供足够证据"]
    assert "无有效知识库片段" in pack.facts_text()


def test_evidence_pack_includes_web_fact_summary(monkeypatch):
    monkeypatch.setattr("config.FULL_RECALL_MODE", False)
    web_fact = WebFact(claim="公开信息显示政策鼓励智能化升级。", source="https://example.test", confidence="high")

    pack = build_task_evidence_pack(DummyVectorStore([], count=0), _task(), web_facts=[web_fact])

    trace = pack.to_trace_dict()
    assert trace["web_fact_count"] == 1
    assert trace["web_facts"][0]["claim"] == web_fact.claim
    assert "联网证据" in pack.facts_text()
