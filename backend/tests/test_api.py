import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import Provider
from app.db.session import SessionLocal, init_db
from app.main import app
from app.runtime.llm import HttpxChatClient
from app.services.seed_service import seed_agents, seed_tools


@pytest.fixture()
def client():
    init_db()
    with SessionLocal() as session:
        seed_agents(session)
        seed_tools(session)
        # 跑智能体需要一家启用的服务商，这是产品行为不是测试特例。
        # 这里补上前置条件：真实 HTTP 调用被 _patch_client 替换，密钥留空即可。
        if session.scalars(select(Provider)).first() is None:
            session.add(
                Provider(
                    name="测试服务商",
                    kind="custom",
                    base_url="https://api.example.com/v1",
                    enabled=True,
                )
            )
            session.commit()
    with TestClient(app) as c:
        yield c


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_create_and_list_project(client):
    created = client.post("/api/projects", json={"name": "验尸官", "genre": "悬疑"}).json()
    assert created["name"] == "验尸官"
    listing = client.get("/api/projects").json()
    assert any(p["id"] == created["id"] for p in listing)


def test_idea_raw_text_is_preserved_on_parse(client, monkeypatch):
    project = client.post("/api/projects", json={"name": "p"}).json()
    idea = client.post(
        f"/api/projects/{project['id']}/ideas", json={"raw_text": "能听见死者遗言的验尸官"}
    ).json()

    _patch_client(monkeypatch, '{"genre": "悬疑", "premise": "x", "protagonist_desire": "y", "conflict_source": "z", "open_questions": []}')
    client.post(f"/api/projects/{project['id']}/ideas/{idea['id']}/parse")

    refreshed = client.get(f"/api/projects/{project['id']}/ideas").json()[0]
    assert refreshed["raw_text"] == "能听见死者遗言的验尸官"
    assert refreshed["parsed_json"]["genre"] == "悬疑"


def test_parse_returns_run_for_debug_console(client, monkeypatch):
    project = client.post("/api/projects", json={"name": "p"}).json()
    client.post(f"/api/projects/{project['id']}/ideas", json={"raw_text": "灵感"})
    _patch_client(monkeypatch, '{"genre": "悬疑", "premise": "x", "protagonist_desire": "y", "conflict_source": "z", "open_questions": []}')

    ideas = client.get(f"/api/projects/{project['id']}/ideas").json()
    resp = client.post(f"/api/projects/{project['id']}/ideas/{ideas[0]['id']}/parse")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["run"]["rendered_prompt"]
    assert payload["run"]["raw_output"]


def test_agents_listed_with_current_version(client):
    agents = client.get("/api/agents").json()
    names = {a["name"] for a in agents}
    assert "架构师" in names
    assert "灵感解析师" in names
    architect = next(a for a in agents if a["name"] == "架构师")
    assert architect["current_version"]["system_prompt"]


def test_agent_version_creation_and_rollback(client):
    agents = client.get("/api/agents").json()
    agent = agents[0]
    v1 = agent["current_version"]["id"]

    created = client.post(
        f"/api/agents/{agent['id']}/versions",
        json={"system_prompt": "新提示词", "note": "试一版"},
    ).json()
    assert created["version_no"] == agent["current_version"]["version_no"] + 1

    client.post(f"/api/agents/{agent['id']}/rollback/{v1}")
    refreshed = next(a for a in client.get("/api/agents").json() if a["id"] == agent["id"])
    assert refreshed["current_version"]["id"] == v1


def test_provider_never_returns_plaintext_key(client):
    created = client.post(
        "/api/providers",
        json={"name": "测试", "kind": "custom", "base_url": "https://api.example.com/v1", "api_key": "sk-secret-123456"},
    ).json()
    assert "sk-secret-123456" not in str(created)
    assert created["api_key_masked"].startswith("sk-****")

    listing = client.get("/api/providers").json()
    assert "sk-secret-123456" not in str(listing)


def test_tools_listed(client):
    tools = client.get("/api/tools").json()
    assert any(t["key"] == "three_act" for t in tools)


def test_runs_history_is_filterable(client, monkeypatch):
    project = client.post("/api/projects", json={"name": "p"}).json()
    client.post(f"/api/projects/{project['id']}/ideas", json={"raw_text": "灵感"})
    _patch_client(monkeypatch, '{"genre": "悬疑", "premise": "x", "protagonist_desire": "y", "conflict_source": "z", "open_questions": []}')
    ideas = client.get(f"/api/projects/{project['id']}/ideas").json()
    client.post(f"/api/projects/{project['id']}/ideas/{ideas[0]['id']}/parse")

    runs = client.get("/api/runs", params={"project_id": project["id"]}).json()
    assert len(runs) == 1
    assert runs[0]["status"] == "ok"


def test_debug_run_endpoint_returns_full_trail(client, monkeypatch):
    project = client.post("/api/projects", json={"name": "p"}).json()
    client.post(f"/api/projects/{project['id']}/ideas", json={"raw_text": "灵感"})
    _patch_client(monkeypatch, '{"genre": "悬疑", "premise": "x", "protagonist_desire": "y", "conflict_source": "z", "open_questions": []}')
    agents = client.get("/api/agents").json()
    parser = next(a for a in agents if a["name"] == "灵感解析师")

    resp = client.post("/api/runs", json={"project_id": project["id"], "agent_id": parser["id"]})
    body = resp.json()
    assert body["run"]["rendered_prompt"]
    assert body["run"]["raw_output"]
    assert "prompt_tokens" in body["run"]


def _patch_client(monkeypatch, content: str) -> None:
    """把运行时用的 HTTP 客户端换成固定响应的假实现。

    替换的是 RuntimeService._resolve_client 而不是 HttpxChatClient：
    后者在模块 import 时已被绑定，patch 模块属性不会影响已绑定的名字。
    """
    from app.services.runtime_service import RuntimeService

    def handler(request):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 30, "completion_tokens": 15},
            },
        )

    fake = HttpxChatClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(RuntimeService, "_resolve_client", lambda self: fake)
