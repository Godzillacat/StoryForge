"""OpenAI 兼容的 LLM 适配器。

只实现一套协议：DeepSeek、Moonshot、智谱、Ollama、LM Studio、自建代理
都提供 OpenAI 兼容端点，接入新服务商 = 加一行预设（上位文档 §4.10）。
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx

from app.runtime.pricing import estimate_tokens

_ERROR_KINDS = {
    400: "bad_request",
    401: "auth",
    403: "auth",
    404: "bad_request",
    429: "rate_limit",
}


@dataclass(frozen=True)
class ChatError:
    kind: str  # network | auth | rate_limit | server | timeout | bad_request
    message: str
    status: int | None = None


class ChatFailure(Exception):
    """带已分类原因与已收内容的调用失败。已收内容不丢。"""

    def __init__(self, error: ChatError, partial_text: str = "") -> None:
        super().__init__(error.message)
        self.error = error
        self.partial_text = partial_text


@dataclass(frozen=True)
class ChatConfig:
    base_url: str
    api_key: str
    model: str


@dataclass(frozen=True)
class ChatResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    finish_reason: str | None = None
    partial: bool = False
    error: ChatError | None = None


class ChatClient:
    """适配器接口。测试用假实现替换，编排代码不感知 HTTP。"""

    async def complete(self, config: ChatConfig, messages: list[dict], params: dict) -> ChatResult:
        raise NotImplementedError

    def stream(self, config: ChatConfig, messages: list[dict], params: dict) -> AsyncIterator[str]:
        raise NotImplementedError


def _classify(status: int) -> str:
    return _ERROR_KINDS.get(status, "server" if status >= 500 else "bad_request")


def _read_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except (json.JSONDecodeError, ValueError):
        return response.text[:200] or "服务商未返回可读原因"
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])
        if error:
            return str(error)
    return response.text[:200] or "服务商未返回可读原因"


class HttpxChatClient(ChatClient):
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None, timeout: float = 120.0):
        self._transport = transport
        self._timeout = timeout

    def _endpoint(self, config: ChatConfig) -> str:
        return config.base_url.rstrip("/") + "/chat/completions"

    def _headers(self, config: ChatConfig) -> dict[str, str]:
        headers = {"content-type": "application/json"}
        if config.api_key:
            headers["authorization"] = f"Bearer {config.api_key}"
        return headers

    def _body(self, config: ChatConfig, messages: list[dict], params: dict, stream: bool) -> dict:
        body = {"model": config.model, "messages": messages, "stream": stream}
        body.update(params or {})
        return body

    def _wrap_transport_error(self, exc: Exception) -> ChatFailure:
        if isinstance(exc, httpx.TimeoutException):
            return ChatFailure(ChatError("timeout", f"请求超时：{exc}"))
        if isinstance(exc, httpx.TransportError):
            return ChatFailure(ChatError("network", f"网络错误：{exc}"))
        return ChatFailure(ChatError("network", f"调用失败：{exc}"))

    async def complete(self, config: ChatConfig, messages: list[dict], params: dict) -> ChatResult:
        async with httpx.AsyncClient(transport=self._transport, timeout=self._timeout) as client:
            try:
                response = await client.post(
                    self._endpoint(config),
                    headers=self._headers(config),
                    json=self._body(config, messages, params, stream=False),
                )
            except Exception as exc:  # noqa: BLE001 — 统一转成可读原因
                raise self._wrap_transport_error(exc) from exc

            if response.status_code >= 400:
                raise ChatFailure(
                    ChatError(
                        _classify(response.status_code),
                        _read_error_message(response),
                        response.status_code,
                    )
                )

            payload = response.json()

        choices = payload.get("choices") or [{}]
        message = choices[0].get("message") or {}
        text = message.get("content") or ""
        usage = payload.get("usage") or {}
        return ChatResult(
            text=text,
            prompt_tokens=int(usage.get("prompt_tokens") or estimate_tokens(
                "\n".join(m.get("content", "") for m in messages)
            )),
            completion_tokens=int(usage.get("completion_tokens") or estimate_tokens(text)),
            finish_reason=choices[0].get("finish_reason"),
        )

    async def stream(
        self, config: ChatConfig, messages: list[dict], params: dict
    ) -> AsyncIterator[str]:
        async with httpx.AsyncClient(transport=self._transport, timeout=self._timeout) as client:
            try:
                async with client.stream(
                    "POST",
                    self._endpoint(config),
                    headers=self._headers(config),
                    json=self._body(config, messages, params, stream=True),
                ) as response:
                    if response.status_code >= 400:
                        await response.aread()
                        raise ChatFailure(
                            ChatError(
                                _classify(response.status_code),
                                _read_error_message(response),
                                response.status_code,
                            )
                        )
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[len("data:") :].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        delta = (chunk.get("choices") or [{}])[0].get("delta") or {}
                        content = delta.get("content")
                        if content:
                            yield content
            except ChatFailure:
                raise
            except Exception as exc:  # noqa: BLE001
                raise self._wrap_transport_error(exc) from exc
