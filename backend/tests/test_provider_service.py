import httpx
import pytest

from app.db.models import Agent, AgentVersion, Provider
from app.runtime.llm import HttpxChatClient
from app.services import provider_service


@pytest.fixture()
def provider(session):
    p = Provider(name="测试商", kind="custom", base_url="http://x/v1", enabled=True)
    session.add(p)
    session.commit()
    return p


def _service_with(monkeypatch, handler) -> None:
    """把 HttpxChatClient 换成假传输层，不打真实网络。"""
    monkeypatch.setattr(
        provider_service,
        "HttpxChatClient",
        lambda **kwargs: HttpxChatClient(transport=httpx.MockTransport(handler), **kwargs),
    )


def _bind_model(session, provider, model: str) -> None:
    agent = Agent(name="某智能体", task_type="idea_parse")
    session.add(agent)
    session.flush()
    version = AgentVersion(
        agent_id=agent.id,
        version_no=1,
        model_binding_json={"provider_id": provider.id, "model": model},
    )
    session.add(version)
    session.flush()
    agent.current_version_id = version.id
    session.commit()


def _ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": "pong"}}], "usage": {}})


def _status(code: int, message: str):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(code, json={"error": {"message": message}})

    return handler


def test_uses_the_model_bound_to_an_agent(session, provider, monkeypatch):
    """空模型名发请求是假阳性的根源：它只证明地址可达，不证明模型可用。"""
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = request.read().decode()
        return _ok(request)

    _bind_model(session, provider, "qwen3.8-flash")
    _service_with(monkeypatch, handler)

    result = provider_service.test_connection(session, provider.id)

    assert result["ok"] is True
    assert "qwen3.8-flash" in seen["body"]
    assert "qwen3.8-flash" in result["message"]


def test_refuses_to_probe_without_a_model(session, provider, monkeypatch):
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return _ok(request)

    _service_with(monkeypatch, handler)
    result = provider_service.test_connection(session, provider.id)

    assert result["ok"] is False
    assert "绑定模型" in result["message"]
    assert called is False  # 不发无意义的请求


def test_explicit_model_wins(session, provider, monkeypatch):
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = request.read().decode()
        return _ok(request)

    _service_with(monkeypatch, handler)
    provider_service.test_connection(session, provider.id, model="手工填的模型")
    assert "手工填的模型" in seen["body"]


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (400, "请求被拒"),
        (401, "密钥无效"),
        (403, "密钥无效"),
        (404, "接口地址或模型名不存在"),
        (429, "额度不足或限流"),
    ],
)
def test_failure_kinds_are_labelled(session, provider, monkeypatch, code, expected):
    _bind_model(session, provider, "m")
    _service_with(monkeypatch, _status(code, f"服务商说的原话 {code}"))

    result = provider_service.test_connection(session, provider.id)

    assert result["ok"] is False
    assert expected in result["message"]
    assert f"服务商说的原话 {code}" in result["message"]  # 原文必须带上


def test_network_failure_is_reported(session, provider, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    _bind_model(session, provider, "m")
    _service_with(monkeypatch, handler)

    result = provider_service.test_connection(session, provider.id)
    assert result["ok"] is False
    assert "网络" in result["message"] or "调用失败" in result["message"]


def test_missing_base_url_is_reported(session, monkeypatch):
    p = Provider(name="没地址", kind="custom", base_url="", enabled=True)
    session.add(p)
    session.commit()
    assert provider_service.test_connection(session, p.id)["ok"] is False
