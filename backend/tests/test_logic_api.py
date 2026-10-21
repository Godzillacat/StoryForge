import pytest

from app.db.models import GenerationRun
from app.db.session import SessionLocal
from app.runtime.execute import RunResult


def _create_scene(client, *, body: str | None = "档案室的门在身后合上。") -> tuple[str, str]:
    project = client.post("/api/projects", json={"name": "逻辑接口"}).json()
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
        assert (
            client.put(f"/api/scenes/{scene['id']}/body", json={"content": body}).status_code
            == 200
        )
    return project["id"], scene["id"]


@pytest.fixture()
def no_llm(monkeypatch):
    def fake_execute(self, project_id, agent_id, extra=None, allow_missing=None):
        raise ValueError("没有可用的服务商，请先配置一家")

    monkeypatch.setattr(
        "app.services.logic_service.RuntimeService.execute", fake_execute
    )


def _patch_success(monkeypatch, project_id: str, parsed: dict):
    with SessionLocal() as session:
        run = GenerationRun(project_id=project_id, status="ok")
        session.add(run)
        session.commit()
        run_id = run.id
    result = RunResult(
        rendered_prompt="",
        raw_output="",
        parsed=parsed,
        structured=True,
        parse_error=None,
        prompt_tokens=1,
        completion_tokens=1,
        cost_estimate=0.0,
        duration_ms=1,
        status="ok",
        error=None,
        trimmed={},
    )

    def fake_execute(self, project_id, agent_id, extra=None, allow_missing=None):
        with SessionLocal() as session:
            return session.get(GenerationRun, run_id), result

    monkeypatch.setattr(
        "app.services.logic_service.RuntimeService.execute", fake_execute
    )
    return run_id


def test_text_stage_without_model_returns_warning(client, no_llm):
    project_id, scene_id = _create_scene(client)

    response = client.post(
        f"/api/scenes/{scene_id}/logic-check", json={"stage": "text"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["llm_status"] == "skipped"
    assert "没有可用的服务商" in data["warning"]
    assert data["issues"] == []
    assert data["stage"] == "text"


def test_plan_stage_runs_without_body(client, no_llm):
    project_id, scene_id = _create_scene(client, body=None)

    response = client.post(
        f"/api/scenes/{scene_id}/logic-check", json={"stage": "plan"}
    )

    assert response.status_code == 200
    assert response.json()["stage"] == "plan"
    assert response.json()["llm_status"] == "skipped"


def test_text_stage_requires_body(client, no_llm):
    project_id, scene_id = _create_scene(client, body=None)

    response = client.post(
        f"/api/scenes/{scene_id}/logic-check", json={"stage": "text"}
    )

    assert response.status_code == 400
    assert "还没有已采纳正文" in response.json()["detail"]


def test_invalid_stage_is_400(client, no_llm):
    project_id, scene_id = _create_scene(client)

    response = client.post(
        f"/api/scenes/{scene_id}/logic-check", json={"stage": "draft"}
    )

    assert response.status_code == 400
    assert "未知的逻辑自检时机" in response.json()["detail"]


def test_missing_scene_is_404(client):
    response = client.post("/api/scenes/nope/logic-check", json={"stage": "text"})
    assert response.status_code == 404


def test_get_returns_issues_and_last_checked(client, monkeypatch):
    project_id, scene_id = _create_scene(client)
    run_id = _patch_success(
        monkeypatch,
        project_id,
        {
            "issues": [
                {
                    "layer": "因果链",
                    "severity": "严重",
                    "quote": "他忽然到了城北。",
                    "rule_ref": "时间线",
                    "explanation": "没有交代移动。",
                    "reader_impact": "读者会跳戏。",
                    "options": ["补移动", "改地点"],
                }
            ]
        },
    )

    run = client.post(f"/api/scenes/{scene_id}/logic-check", json={"stage": "text"})
    assert run.status_code == 200
    assert run.json()["run_id"] == run_id

    view = client.get(f"/api/scenes/{scene_id}/logic-check?stage=text")
    assert view.status_code == 200
    data = view.json()
    assert len(data["issues"]) == 1
    assert data["issues"][0]["layer_label"] == "因果链"
    assert data["issues"][0]["check_type"] == "logic"
    assert data["last_checked_at"]


def test_get_empty_and_invalid_stage(client):
    project_id, scene_id = _create_scene(client)

    empty = client.get(f"/api/scenes/{scene_id}/logic-check?stage=plan")
    assert empty.status_code == 200
    assert empty.json() == {
        "stage": "plan",
        "issues": [],
        "last_checked_at": None,
    }

    invalid = client.get(f"/api/scenes/{scene_id}/logic-check?stage=draft")
    assert invalid.status_code == 400
