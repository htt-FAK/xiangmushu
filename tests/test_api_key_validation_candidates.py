from __future__ import annotations

from core import api_key_validation


def test_validation_candidates_include_bailian_samples_and_configured_models():
    models = api_key_validation.validation_candidate_models()

    for model in ["qwen-plus", "qwen3.6-35b-a3b", "qwen-max", "qwen-flash", "qwen3.6-27b"]:
        assert model in models
    assert "qwen3.7-plus" in models
    assert "deepseek-v4-flash" in models
    assert len(models) == len(set(models))


def test_api_key_validation_accepts_first_success_after_failures(monkeypatch):
    monkeypatch.setattr(
        api_key_validation,
        "validation_candidate_models",
        lambda: ["bad-model", "qwen-plus", "never-called"],
    )

    calls: list[str] = []

    def fake_probe(api_key: str, model: str, provider_code: str = "dashscope"):
        calls.append(model)
        if model == "bad-model":
            raise RuntimeError("model unavailable")
        return {"ok": True, "model": model, "code": "ok", "message": "ok", "provider_code": provider_code}

    monkeypatch.setattr(api_key_validation, "probe_api_key_model", fake_probe)

    result = api_key_validation.validate_user_api_key("sk-test")

    assert result["ok"] is True
    assert result["validated_model"] == "qwen-plus"
    assert result["provider_code"] == "dashscope"
    assert calls == ["bad-model", "qwen-plus"]
