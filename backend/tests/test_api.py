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
        if session.scalars(select(Provider).where(Provider.enabled.is_(True))).first() is None:
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


def test_parse_uses_the_idea_that_was_requested(client, monkeypatch):
    project = client.post("/api/projects", json={"name": "p"}).json()
    client.post(f"/api/projects/{project['id']}/ideas", json={"raw_text": "第一个灵感：验尸官"})
    second = client.post(
        f"/api/projects/{project['id']}/ideas", json={"raw_text": "第二个灵感：灯塔看守人"}
    ).json()
    _patch_client(
        monkeypatch,
        '{"genre": "悬疑", "premise": "x", "protagonist_desire": "y", "conflict_source": "z", "open_questions": []}',
    )

    client.post(f"/api/projects/{project['id']}/ideas/{second['id']}/parse")

    runs = client.get("/api/runs", params={"project_id": project["id"]}).json()
    assert "第二个灵感：灯塔看守人" in runs[0]["rendered_prompt"]
    assert "第一个灵感：验尸官" not in runs[0]["rendered_prompt"]


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
    monkeypatch.setattr(RuntimeService, "_resolve_client", lambda self, timeout: fake)


def test_patch_agent_updates_agent_level_fields(client):
    agent = client.get("/api/agents").json()[0]

    response = client.patch(
        f"/api/agents/{agent['id']}",
        json={"role_label": "解析官", "color": "#ff0000", "enabled": False},
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["role_label"] == "解析官"
    assert updated["color"] == "#ff0000"
    assert updated["enabled"] is False
    assert updated["name"] == agent["name"]  # 没传的字段不动
    assert updated["task_type"] == agent["task_type"]
    # 改 agent 级字段不该产生新版本
    assert updated["current_version"]["version_no"] == agent["current_version"]["version_no"]


def test_patch_unknown_agent_is_404(client):
    assert client.patch("/api/agents/nope", json={"name": "x"}).status_code == 404


def test_slots_endpoint_reflects_the_registry(client):
    from app.runtime.context import SLOT_REGISTRY

    payload = client.get("/api/slots").json()

    assert {s["key"] for s in payload} == set(SLOT_REGISTRY)
    assert payload == sorted(payload, key=lambda s: -s["priority"])
    by_key = {s["key"]: s for s in payload}
    assert by_key["raw_idea"]["label"] == SLOT_REGISTRY["raw_idea"].label
    assert by_key["raw_idea"]["over_budget"] == "drop"


def test_explicit_null_output_schema_clears_it(client):
    """显式传 null 表示「不要契约」，不能被当成「未提供」而继承上一版。

    工作室页留空输出契约文本框时发的就是 null；若后端把它丢掉，作者
    清空契约后新版本仍带着旧契约，而界面写着「留空表示不做结构化校验」。
    """
    agent = client.get("/api/agents").json()[0]
    assert agent["current_version"]["output_schema_json"] is not None

    created = client.post(
        f"/api/agents/{agent['id']}/versions",
        json={"output_schema_json": None, "note": "清空契约"},
    ).json()

    assert created["output_schema_json"] is None


def test_omitted_version_field_still_inherits(client):
    """没传的字段仍要继承 —— 别把「未提供」也一起清空了。"""
    agent = client.get("/api/agents").json()[0]

    created = client.post(
        f"/api/agents/{agent['id']}/versions",
        json={"note": "只改备注"},
    ).json()

    assert created["output_schema_json"] == agent["current_version"]["output_schema_json"]
    assert created["context_slots_json"] == agent["current_version"]["context_slots_json"]
