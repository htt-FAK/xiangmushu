from __future__ import annotations

from core import api_key_validation


def test_validation_candidates_include_bailian_samples_and_configured_models():
    models = api_key_validation.validation_candidate_models()

    for model in ["qwen-plus", "qwen3.6-35b-a3b", "qwen-max", "qwen-flash", "qwen3.6-27b"]:
        assert model in models
    assert "qwen3.7-plus" in models
    # dashscope（百炼）端点只识别 qwen 等百炼模型，不应混入其它 provider 的模型名
    assert not any(m.lower().startswith("deepseek") for m in models)
    assert not any(m.lower().startswith("mimo") for m in models)
    assert len(models) == len(set(models))


def test_validation_candidates_are_provider_scoped():
    deepseek_models = api_key_validation.validation_candidate_models("deepseek")
    assert deepseek_models
    assert all(m.lower().startswith("deepseek") for m in deepseek_models)

    mimo_models = api_key_validation.validation_candidate_models("mimo")
    assert mimo_models
    assert all(m.lower().startswith("mimo") for m in mimo_models)


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


def test_api_key_validation_prioritizes_user_selected_models(monkeypatch):
    monkeypatch.setattr(api_key_validation, "validation_candidate_models", lambda provider_code="dashscope": ["qwen-plus"])
    monkeypatch.setattr(api_key_validation, "_selected_models_for_provider", lambda user_id, provider_code: ["qwen3.7-plus"])

    calls: list[str] = []

    def fake_probe(api_key: str, model: str, provider_code: str = "dashscope"):
        calls.append(model)
        if model == "qwen3.7-plus":
            raise RuntimeError("not allowed")
        return {"ok": True, "model": model, "code": "ok", "message": "ok", "provider_code": provider_code}

    monkeypatch.setattr(api_key_validation, "probe_api_key_model", fake_probe)
    result = api_key_validation.validate_user_api_key("sk-test", "dashscope", user_id=7)

    assert result["ok"] is True
    assert calls == ["qwen3.7-plus", "qwen-plus"]


def test_api_key_validation_returns_selected_model_hint_on_failure(monkeypatch):
    monkeypatch.setattr(api_key_validation, "validation_candidate_models", lambda provider_code="dashscope": ["qwen-plus"])
    monkeypatch.setattr(api_key_validation, "_selected_models_for_provider", lambda user_id, provider_code: ["deepseek-v4-pro"])
    monkeypatch.setattr(api_key_validation, "probe_api_key_model", lambda api_key, model, provider_code="dashscope": (_ for _ in ()).throw(RuntimeError("model unavailable")))

    result = api_key_validation.validate_user_api_key("sk-test", "dashscope", user_id=9)

    assert result["ok"] is False
    assert "deepseek-v4-pro" in result["message"]
    assert result["selected_models"] == ["deepseek-v4-pro"]
