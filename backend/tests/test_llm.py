import json

import httpx
import pytest

from app.runtime.llm import (
    ChatConfig,
    ChatFailure,
    HttpxChatClient,
    StreamDelta,
    StreamUsage,
)

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

    events = [c async for c in _client(handler).stream(CONFIG, MESSAGES, {})]
    assert events == [StreamDelta("你"), StreamDelta("好")]


async def test_stream_failure_preserves_content_already_received():
    # 先吐两个 data 块，然后传输层中断
    def handler(request):
        async def body():
            for text in ("你", "好"):
                payload = json.dumps(
                    {"choices": [{"delta": {"content": text}}]}, ensure_ascii=False
                )
                yield f"data: {payload}\n\n".encode()
            raise httpx.ReadError("connection dropped")

        return httpx.Response(200, content=body(), headers={"content-type": "text/event-stream"})

    events = []
    with pytest.raises(ChatFailure) as exc:
        async for event in _client(handler).stream(CONFIG, MESSAGES, {}):
            events.append(event)
    assert events == [StreamDelta("你"), StreamDelta("好")]
    assert exc.value.partial_text == "你好"


import httpx
import pytest

from app.runtime.llm import ChatConfig, ChatFailure, HttpxChatClient


async def test_timeout_message_carries_the_limit():
    """httpx 超时异常的 str() 常为空串，文案必须自己带上限值，
    否则界面上显示的是「请求超时：」后面什么都没有。"""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("", request=request)

    client = HttpxChatClient(transport=httpx.MockTransport(handler), timeout=275.0)
    with pytest.raises(ChatFailure) as excinfo:
        await client.complete(
            ChatConfig(base_url="http://x/v1", api_key="k", model="m"), [], {}
        )

    assert excinfo.value.error.kind == "timeout"
    assert "275" in excinfo.value.error.message
    assert not excinfo.value.error.message.endswith("：")


async def test_stream_requests_usage_and_emits_it():
    seen: list[dict] = []
    body = (
        'data: {"choices":[{"delta":{"content":"你"}}]}\n\n'
        'data: {"choices":[],"usage":{"prompt_tokens":11,"completion_tokens":7}}\n\n'
        "data: [DONE]\n\n"
    )

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    events = [e async for e in _client(handler).stream(CONFIG, MESSAGES, {})]

    assert seen[0]["stream_options"] == {"include_usage": True}
    assert events == [StreamDelta("你"), StreamUsage(11, 7)]


async def test_stream_retries_once_without_stream_options_on_400():
    calls: list[dict] = []
    body = 'data: {"choices":[{"delta":{"content":"好"}}]}\n\ndata: [DONE]\n\n'

    def handler(request):
        payload = json.loads(request.content)
        calls.append(payload)
        if "stream_options" in payload:
            return httpx.Response(400, json={"error": {"message": "unknown field"}})
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    events = [e async for e in _client(handler).stream(CONFIG, MESSAGES, {})]

    assert len(calls) == 2
    assert "stream_options" not in calls[1]
    assert events == [StreamDelta("好")]


async def test_stream_400_twice_is_reported_as_failure():
    calls: list[dict] = []

    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(400, json={"error": {"message": "bad"}})

    with pytest.raises(ChatFailure) as exc:
        async for _event in _client(handler).stream(CONFIG, MESSAGES, {}):
            pass

    assert len(calls) == 2
    assert exc.value.error.kind == "bad_request"


async def test_stream_without_usage_emits_no_usage_event():
    body = (
        'data: {"choices":[{"delta":{"content":"你"}}]}\n\n'
        "data: [DONE]\n\n"
    )

    def handler(request):
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    events = [e async for e in _client(handler).stream(CONFIG, MESSAGES, {})]

    assert events == [StreamDelta("你")]


async def test_non_stream_reports_whether_usage_came_from_provider():
    def with_usage(request):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "x"}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 4},
            },
        )

    def without_usage(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": "x"}}]})

    assert (await _client(with_usage).complete(CONFIG, MESSAGES, {})).usage_available is True
    assert (await _client(without_usage).complete(CONFIG, MESSAGES, {})).usage_available is False
