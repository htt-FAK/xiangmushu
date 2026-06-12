from __future__ import annotations

import server


def test_template_planner_resolves_independently_from_vision(monkeypatch):
    def fake_user_model(user_id: int, module: str) -> str:
        return {
            "vision_layout": "qwen3.7-plus",
            "template_planner": "planner-model",
        }.get(module, "")

    monkeypatch.setattr("config.get_user_model_for_user", fake_user_model)

    vision_model = server._resolve_vision_model("qwen3.7-plus", user_id=7)
    planner_model = server._resolve_template_planner_model("", user_id=7)

    assert vision_model == "qwen3.7-plus"
    assert planner_model == "planner-model"
