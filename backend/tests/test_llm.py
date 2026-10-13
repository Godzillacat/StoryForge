import httpx
import pytest

from app.runtime.llm import ChatConfig, ChatFailure, HttpxChatClient

CONFIG = ChatConfig(base_url="https://api.example.com/v1", api_key="sk-test", model="m1")
MESSAGES = [{"role": "user", "content": "你好"}]


def _client(handler):
    return HttpxChatClient(transport=httpx.MockTransport(handler))


async def test_complete_returns_text_and_usage():
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        captured["body"] = request.read().decode()
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "结果"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 7, "completion_tokens": 11},
            },
        )

    result = await _client(handler).complete(CONFIG, MESSAGES, {"temperature": 0.3})
    assert result.text == "结果"
    assert result.prompt_tokens == 7 and result.completion_tokens == 11
    assert result.partial is False and result.error is None
    assert captured["url"] == "https://api.example.com/v1/chat/completions"
    assert captured["auth"] == "Bearer sk-test"
    assert '"model":"m1"' in captured["body"]


async def test_complete_missing_usage_falls_back_to_estimate():
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": "一二三四"}}]})

    result = await _client(handler).complete(CONFIG, MESSAGES, {})
    assert result.text == "一二三四"
    assert result.completion_tokens == 4  # CJK 估算


@pytest.mark.parametrize(
    ("status", "expected_kind"),
    [(401, "auth"), (403, "auth"), (429, "rate_limit"), (500, "server"), (503, "server")],
)
async def test_error_classification_by_status(status, expected_kind):
    def handler(request):
        return httpx.Response(status, json={"error": {"message": "boom"}})

    with pytest.raises(ChatFailure) as exc:
        await _client(handler).complete(CONFIG, MESSAGES, {})
    assert exc.value.error.kind == expected_kind
    assert str(status) in exc.value.error.message or "boom" in exc.value.error.message


async def test_network_error_is_classified():
    def handler(request):
        raise httpx.ConnectError("connection refused")

    with pytest.raises(ChatFailure) as exc:
        await _client(handler).complete(CONFIG, MESSAGES, {})
    assert exc.value.error.kind == "network"


async def test_timeout_is_classified():
    def handler(request):
        raise httpx.ReadTimeout("timed out")

    with pytest.raises(ChatFailure) as exc:
        await _client(handler).complete(CONFIG, MESSAGES, {})
    assert exc.value.error.kind == "timeout"


async def test_stream_yields_content_chunks():
    body = (
        'data: {"choices":[{"delta":{"content":"你"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"好"}}]}\n\n'
        "data: [DONE]\n\n"
    )

    def handler(request):
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    chunks = [c async for c in _client(handler).stream(CONFIG, MESSAGES, {})]
    assert chunks == ["你", "好"]
