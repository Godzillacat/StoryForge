import pytest

from app.db.models import BatchJob
from app.db.session import SessionLocal


def _create(client, *, body: str | None = None) -> dict:
    project = client.post("/api/projects", json={"name": "批量接口"}).json()
    volume = client.post(
        f"/api/projects/{project['id']}/volumes", json={"name": "第一卷"}
    ).json()
    chapter = client.post(
        f"/api/volumes/{volume['id']}/chapters", json={"title": "第一章"}
    ).json()
    scene = client.post(
        f"/api/chapters/{chapter['id']}/scenes", json={"goal": "第一场"}
    ).json()
    if body is not None:
        client.put(f"/api/scenes/{scene['id']}/body", json={"content": body})
    return {
        "project": project,
        "volume": volume,
        "chapter": chapter,
        "scene": scene,
    }


@pytest.fixture()
def no_spawn(monkeypatch):
    spawned: list[str] = []
    monkeypatch.setattr("app.services.batch_service._spawn", spawned.append)
    return spawned


def test_create_and_get_batch(client, no_spawn):
    data = _create(client)

    response = client.post(
        f"/api/projects/{data['project']['id']}/batches",
        json={"scope_type": "chapter", "scope_id": data["chapter"]["id"]},
    )

    assert response.status_code == 201
    job = response.json()
    assert job["status"] == "paused"
    assert job["total"] == 1
    assert job["cursor"] == 0

    fetched = client.get(f"/api/batches/{job['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == job["id"]

    latest = client.get(
        f"/api/projects/{data['project']['id']}/batches/latest"
    ).json()
    assert latest["id"] == job["id"]


def test_create_without_scenes_is_400(client):
    data = _create(client, body="已经写了")

    response = client.post(
        f"/api/projects/{data['project']['id']}/batches",
        json={"scope_type": "chapter", "scope_id": data["chapter"]["id"]},
    )

    assert response.status_code == 400
    assert "没有需要生成的场景" in response.json()["detail"]


def test_create_missing_scope_is_404(client):
    data = _create(client)

    response = client.post(
        f"/api/projects/{data['project']['id']}/batches",
        json={"scope_type": "chapter", "scope_id": "nope"},
    )

    assert response.status_code == 404


def test_create_conflicts_with_running_job(client):
    data = _create(client)
    with SessionLocal() as session:
        session.add(
            BatchJob(
                project_id=data["project"]["id"],
                scope_type="chapter",
                scope_id=data["chapter"]["id"],
                scene_ids_json=[],
                status="running",
            )
        )
        session.commit()

    response = client.post(
        f"/api/projects/{data['project']['id']}/batches",
        json={"scope_type": "chapter", "scope_id": data["chapter"]["id"]},
    )

    assert response.status_code == 409
    assert "进行中的批量任务" in response.json()["detail"]


def test_control_endpoints(client, no_spawn):
    data = _create(client)
    job = client.post(
        f"/api/projects/{data['project']['id']}/batches",
        json={"scope_type": "chapter", "scope_id": data["chapter"]["id"]},
    ).json()

    resumed = client.post(f"/api/batches/{job['id']}/resume")
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "running"

    paused = client.post(f"/api/batches/{job['id']}/pause")
    assert paused.json()["status"] == "paused"

    cancelled = client.post(f"/api/batches/{job['id']}/cancel")
    assert cancelled.json()["status"] == "cancelled"

    again = client.post(f"/api/batches/{job['id']}/resume")
    assert again.status_code == 400
    assert "任务已结束" in again.json()["detail"]


def test_retry_failed_endpoint(client, no_spawn):
    data = _create(client)
    job = client.post(
        f"/api/projects/{data['project']['id']}/batches",
        json={"scope_type": "chapter", "scope_id": data["chapter"]["id"]},
    ).json()
    with SessionLocal() as session:
        stored = session.get(BatchJob, job["id"])
        stored.status = "failed"
        stored.cursor = 1
        stored.failures_json = [
            {"scene_id": data["scene"]["id"], "message": "超时"}
        ]
        session.commit()

    response = client.post(f"/api/batches/{job['id']}/retry-failed")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "running"
    assert body["total"] == 1
    assert body["cursor"] == 0
    assert body["failures"] == []


def test_missing_job_is_404(client):
    assert client.get("/api/batches/nope").status_code == 404
    assert client.post("/api/batches/nope/pause").status_code == 404
