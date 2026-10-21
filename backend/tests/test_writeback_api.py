import pytest

from app.db.models import GenerationRun
from app.db.session import SessionLocal
from app.runtime.execute import RunResult


def _create(client, *, body: str | None = "陈默把录音带收进怀里。") -> dict:
    project = client.post("/api/projects", json={"name": "回写接口"}).json()
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
    character = client.post(
        f"/api/projects/{project['id']}/entries",
        json={"type": "character", "name": "陈默", "aliases": ["阿默"]},
    ).json()
    foreshadow = client.post(
        f"/api/projects/{project['id']}/foreshadows", json={"name": "失忆的录音带"}
    ).json()
    return {
        "project": project,
        "chapter": chapter,
        "scene": scene,
        "character": character,
        "foreshadow": foreshadow,
    }


@pytest.fixture()
def no_llm(monkeypatch):
    def fake_execute(self, project_id, agent_id, extra=None, allow_missing=None):
        raise ValueError("没有可用的服务商")

    monkeypatch.setattr(
        "app.services.writeback_service.RuntimeService.execute", fake_execute
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
        "app.services.writeback_service.RuntimeService.execute", fake_execute
    )
    return run_id


def test_suggest_without_model_returns_warning(client, no_llm):
    data = _create(client)

    response = client.post(f"/api/scenes/{data['scene']['id']}/writeback")

    assert response.status_code == 200
    body = response.json()
    assert body["llm_status"] == "skipped"
    assert "没有可用的服务商" in body["warning"]
    assert body["character_updates"] == []


def test_suggest_requires_body(client, no_llm):
    data = _create(client, body=None)

    response = client.post(f"/api/scenes/{data['scene']['id']}/writeback")

    assert response.status_code == 400
    assert "还没有已采纳正文" in response.json()["detail"]


def test_suggest_missing_scene(client):
    response = client.post("/api/scenes/nope/writeback")
    assert response.status_code == 404


def test_suggest_success_returns_resolved_candidates(client, monkeypatch):
    data = _create(client)
    run_id = _patch_success(
        monkeypatch,
        data["project"]["id"],
        {
            "chapter_summary": "陈默拿到了录音带。",
            "character_updates": [
                {
                    "character": "阿默",
                    "current_state": "拿到了录音带",
                    "evidence": "陈默把录音带收进怀里。",
                }
            ],
            "foreshadow_pays": [{"name": "失忆的录音带"}],
            "open_questions": ["录音带里是谁的声音？"],
        },
    )

    response = client.post(f"/api/scenes/{data['scene']['id']}/writeback")

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == run_id
    assert body["character_updates"][0]["entry_id"] == data["character"]["id"]
    assert body["foreshadow_pays"][0]["foreshadow_id"] == data["foreshadow"]["id"]
    assert body["open_questions"] == ["录音带里是谁的声音？"]


def test_apply_updates_the_selected_targets(client, no_llm):
    data = _create(client)

    response = client.post(
        f"/api/scenes/{data['scene']['id']}/writeback/apply",
        json={
            "chapter_summary": "陈默拿到了录音带。",
            "character_updates": [
                {
                    "entry_id": data["character"]["id"],
                    "current_state": "拿到了录音带",
                }
            ],
            "foreshadow_pays": [{"foreshadow_id": data["foreshadow"]["id"]}],
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["chapter_summary"] == "陈默拿到了录音带。"
    assert result["character_updates"][0]["current_state"] == "拿到了录音带"

    entries = client.get(
        f"/api/projects/{data['project']['id']}/entries"
    ).json()
    character = next(row for row in entries if row["id"] == data["character"]["id"])
    assert character["current_state"] == "拿到了录音带"

    foreshadows = client.get(
        f"/api/projects/{data['project']['id']}/foreshadows"
    ).json()
    row = next(item for item in foreshadows if item["id"] == data["foreshadow"]["id"])
    assert row["actual_pay_scene_id"] == data["scene"]["id"]


def test_apply_rejects_invalid_ids(client, no_llm):
    data = _create(client)

    response = client.post(
        f"/api/scenes/{data['scene']['id']}/writeback/apply",
        json={"character_updates": [{"entry_id": "nope", "current_state": "在场"}]},
    )

    assert response.status_code == 400
    assert "人物不存在" in response.json()["detail"]
