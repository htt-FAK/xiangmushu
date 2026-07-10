from __future__ import annotations

from types import SimpleNamespace

from core.dashscope_chat import prepare_chat_request


def _client(base_url: str):
    return SimpleNamespace(base_url=base_url)


def test_prepare_chat_request_keeps_mimo_thinking_payload():
    client, kwargs = prepare_chat_request(
        _client("https://api.xiaomimimo.com/v1"),
        force_client=True,
        model="mimo-v2.5-pro",
        extra_body={"thinking": {"type": "disabled"}},
    )

    assert str(client.base_url) == "https://api.xiaomimimo.com/v1"
    assert kwargs["extra_body"] == {"thinking": {"type": "disabled"}}


def test_prepare_chat_request_adds_dashscope_enable_thinking_flag():
    _, kwargs = prepare_chat_request(
        _client("https://dashscope.aliyuncs.com/compatible-mode/v1"),
        force_client=True,
        model="qwen3.7-plus",
        extra_body={"custom_hint": True},
    )

    assert kwargs["extra_body"]["custom_hint"] is True
    assert kwargs["extra_body"]["enable_thinking"] is False


def test_prepare_chat_request_forces_deepseek_thinking_disabled():
    _, kwargs = prepare_chat_request(
        _client("https://api.deepseek.com"),
        force_client=True,
        model="deepseek-v4-pro",
        extra_body={"thinking": {"type": "enabled"}},
    )

    assert kwargs["extra_body"] == {"thinking": {"type": "disabled"}}
