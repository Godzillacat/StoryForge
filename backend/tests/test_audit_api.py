import pytest

REPEATED = (
    "雨落在旧城的铁皮屋顶上，声音像有人在数硬币。"
    "雨落在旧城的铁皮屋顶上，声音像有人在数硬币。"
)


def _create_scene(client, *, body: str | None = REPEATED) -> tuple[str, str]:
    project = client.post("/api/projects", json={"name": "审计接口"}).json()
    volume = client.post(
        f"/api/projects/{project['id']}/volumes", json={"name": "第一卷"}
    ).json()
    chapter = client.post(
        f"/api/volumes/{volume['id']}/chapters", json={"title": "第一章"}
    ).json()
    scene = client.post(
        f"/api/chapters/{chapter['id']}/scenes", json={"goal": "找到录音带"}
    ).json()
    if body is not None:
        response = client.put(f"/api/scenes/{scene['id']}/body", json={"content": body})
        assert response.status_code == 200
    return project["id"], scene["id"]


@pytest.fixture()
def no_llm(monkeypatch):
    """没有可用模型：规则层照跑，LLM 层降级为 skipped。"""

    def fake_execute(self, project_id, agent_id, extra=None):
        raise ValueError("没有可用的服务商，请先配置一家")

    monkeypatch.setattr(
        "app.services.audit_service.RuntimeService.execute", fake_execute
    )


def test_run_audit_returns_rule_issues_without_model(client, no_llm):
    project_id, scene_id = _create_scene(client)

    response = client.post(f"/api/scenes/{scene_id}/audit")

    assert response.status_code == 200
    data = response.json()
    assert data["llm_status"] == "skipped"
    assert "没有可用的服务商" in data["warning"]
    assert data["run_id"] is None
    assert [issue["kind"] for issue in data["issues"]] == ["repetition"]


def test_run_audit_requires_body(client, no_llm):
    project_id, scene_id = _create_scene(client, body=None)

    response = client.post(f"/api/scenes/{scene_id}/audit")

    assert response.status_code == 400
    assert "还没有已采纳正文" in response.json()["detail"]


def test_run_audit_missing_scene(client):
    response = client.post("/api/scenes/nope/audit")
    assert response.status_code == 404
    assert "场景不存在" in response.json()["detail"]


def test_get_audit_before_and_after(client, no_llm):
    project_id, scene_id = _create_scene(client)

    empty = client.get(f"/api/scenes/{scene_id}/audit")
    assert empty.status_code == 200
    assert empty.json() == {"issues": [], "last_audited_at": None}

    client.post(f"/api/scenes/{scene_id}/audit")
    view = client.get(f"/api/scenes/{scene_id}/audit").json()

    assert len(view["issues"]) == 1
    assert view["issues"][0]["source_label"] == "规则"
    assert view["last_audited_at"]


def test_get_audit_missing_scene(client):
    response = client.get("/api/scenes/nope/audit")
    assert response.status_code == 404


def test_resolve_issue_endpoint(client, no_llm):
    project_id, scene_id = _create_scene(client)
    issue = client.post(f"/api/scenes/{scene_id}/audit").json()["issues"][0]

    response = client.patch(
        f"/api/audit/issues/{issue['id']}", json={"resolution": "exception"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "exception"
    assert data["resolution"] == "exception"
    assert client.get(f"/api/scenes/{scene_id}/audit").json()["issues"] == []


def test_resolve_issue_rejects_invalid_resolution(client, no_llm):
    project_id, scene_id = _create_scene(client)
    issue = client.post(f"/api/scenes/{scene_id}/audit").json()["issues"][0]

    response = client.patch(
        f"/api/audit/issues/{issue['id']}", json={"resolution": "ignore"}
    )

    assert response.status_code == 400
    assert "不支持的处理方式" in response.json()["detail"]


def test_resolve_missing_issue(client):
    response = client.patch("/api/audit/issues/nope", json={"resolution": "story"})
    assert response.status_code == 404
    assert "审计问题不存在" in response.json()["detail"]
