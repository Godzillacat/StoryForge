import pytest

from app.db.models import PipelineRun, PipelineRunNode, Project
from app.db.session import SessionLocal
from app.pipeline_types import DEFAULT_PIPELINE
from app.services import pipeline_service


@pytest.fixture(autouse=True)
def _no_threads(monkeypatch):
    """接口测试不起后台线程：线程会与断言抢状态。"""
    monkeypatch.setattr(pipeline_service, "spawn_run", lambda run_id: None)


def _project(client, name="雾港"):
    return client.post("/api/projects", json={"name": name}).json()


def test_get_pipeline_lazily_creates_the_default(client):
    project = _project(client)

    response = client.get(f"/api/projects/{project['id']}/pipeline")

    assert response.status_code == 200
    body = response.json()
    assert [n["task_type"] for n in body["nodes"]] == [
        n["task_type"] for n in DEFAULT_PIPELINE
    ]
    assert body["policy"] == "key_only"


def test_get_pipeline_unknown_project_is_404(client):
    assert client.get("/api/projects/nope/pipeline").status_code == 404


def test_put_replaces_nodes_and_policy(client):
    project = _project(client)

    response = client.put(
        f"/api/projects/{project['id']}/pipeline",
        json={
            "policy": "auto",
            "nodes": [
                {"name": "解析", "task_type": "idea_parse"},
                {"name": "架构", "task_type": "architecture", "checkpoint": True},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["policy"] == "auto"
    assert [n["name"] for n in body["nodes"]] == ["解析", "架构"]
    assert body["nodes"][1]["checkpoint"] is True


def test_put_with_empty_nodes_is_400(client):
    project = _project(client)

    response = client.put(
        f"/api/projects/{project['id']}/pipeline", json={"nodes": []}
    )

    assert response.status_code == 400


def test_put_without_task_type_is_422(client):
    project = _project(client)

    response = client.put(
        f"/api/projects/{project['id']}/pipeline", json={"nodes": [{"name": "空"}]}
    )

    assert response.status_code == 422


def test_reset_restores_the_template(client):
    project = _project(client)
    client.put(
        f"/api/projects/{project['id']}/pipeline",
        json={"nodes": [{"name": "只剩一个", "task_type": "idea_parse"}]},
    )

    response = client.post(f"/api/projects/{project['id']}/pipeline/reset")

    assert response.status_code == 200
    assert [n["task_type"] for n in response.json()["nodes"]] == [
        n["task_type"] for n in DEFAULT_PIPELINE
    ]


def test_start_run_returns_the_run(client):
    project = _project(client)

    response = client.post(f"/api/projects/{project['id']}/pipeline/runs")

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "running"
    assert len(body["nodes"]) == len(DEFAULT_PIPELINE)
    assert all(n["status"] == "pending" for n in body["nodes"])

    latest = client.get(f"/api/projects/{project['id']}/pipeline/runs/latest").json()
    assert latest["id"] == body["id"]


def test_second_run_is_409(client):
    project = _project(client)
    client.post(f"/api/projects/{project['id']}/pipeline/runs")

    response = client.post(f"/api/projects/{project['id']}/pipeline/runs")

    assert response.status_code == 409


def test_get_unknown_run_is_404(client):
    assert client.get("/api/pipeline-runs/nope").status_code == 404


def test_control_endpoints(client):
    project = _project(client)
    run = client.post(f"/api/projects/{project['id']}/pipeline/runs").json()

    paused = client.post(f"/api/pipeline-runs/{run['id']}/pause")
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"

    resumed = client.post(f"/api/pipeline-runs/{run['id']}/resume")
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "running"

    cancelled = client.post(f"/api/pipeline-runs/{run['id']}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_cancel_a_finished_run_is_400(client):
    project = _project(client)
    run = client.post(f"/api/projects/{project['id']}/pipeline/runs").json()
    client.post(f"/api/pipeline-runs/{run['id']}/cancel")

    response = client.post(f"/api/pipeline-runs/{run['id']}/cancel")

    assert response.status_code == 400


def test_latest_run_is_null_before_any_run(client):
    project = _project(client)

    assert client.get(f"/api/projects/{project['id']}/pipeline/runs/latest").json() is None


def test_recover_runs_marks_running_as_paused(client):
    project = _project(client)
    run = client.post(f"/api/projects/{project['id']}/pipeline/runs").json()

    pipeline_service.recover_runs()

    with SessionLocal() as session:
        stored = session.get(PipelineRun, run["id"])
        assert stored.status == "paused"
        assert "重启" in stored.message
        assert session.get(Project, project["id"]) is not None
