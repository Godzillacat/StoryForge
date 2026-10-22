"""影响面与待复核的接口。"""


def _tree(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    volume = client.post(
        f"/api/projects/{project['id']}/volumes", json={"name": "第一卷"}
    ).json()
    chapter = client.post(
        f"/api/volumes/{volume['id']}/chapters", json={"title": "第一章"}
    ).json()
    scene = client.post(
        f"/api/chapters/{chapter['id']}/scenes", json={"goal": "开场"}
    ).json()
    return project, volume, chapter, scene


def test_impact_returns_groups_and_totals(client):
    project, volume, _chapter, _scene = _tree(client)

    body = client.get(
        f"/api/projects/{project['id']}/impact",
        params={"target_type": "volume", "target_id": volume["id"]},
    ).json()

    assert body["target"]["type"] == "volume"
    assert body["target"]["label"] == "第1卷（第一卷）"
    assert {group["key"] for group in body["groups"]} >= {"chapters", "scenes"}
    assert body["totals"]["all"] == sum(g["total"] for g in body["groups"])


def test_impact_for_an_unknown_target_is_404(client):
    project, _volume, _chapter, _scene = _tree(client)

    response = client.get(
        f"/api/projects/{project['id']}/impact",
        params={"target_type": "scene", "target_id": "nope"},
    )

    assert response.status_code == 404


def test_impact_without_an_architecture_is_404(client):
    project, _volume, _chapter, _scene = _tree(client)

    response = client.get(
        f"/api/projects/{project['id']}/impact",
        params={"target_type": "architecture", "target_id": "anything"},
    )

    assert response.status_code == 404
    assert "故事圣经" in response.json()["detail"]


def test_impact_with_an_unknown_type_is_400(client):
    project, _volume, _chapter, _scene = _tree(client)

    response = client.get(
        f"/api/projects/{project['id']}/impact",
        params={"target_type": "chapterr", "target_id": "x"},
    )

    assert response.status_code == 400


def test_marks_round_trip_through_the_api(client):
    project, _volume, _chapter, scene = _tree(client)

    created = client.post(
        f"/api/projects/{project['id']}/review-marks",
        json={
            "items": [
                {
                    "target_type": "scene",
                    "target_id": scene["id"],
                    "reason": "架构已改",
                }
            ]
        },
    )

    assert created.status_code == 200
    assert created.json()["added"] == 1
    assert created.json()["marks"][0]["reason"] == "架构已改"

    again = client.post(
        f"/api/projects/{project['id']}/review-marks",
        json={"items": [{"target_type": "scene", "target_id": scene["id"]}]},
    )
    assert again.json()["added"] == 0

    listed = client.get(f"/api/projects/{project['id']}/review-marks").json()
    assert len(listed) == 1


def test_marks_can_be_cleared_one_by_one(client):
    project, _volume, _chapter, scene = _tree(client)
    mark = client.post(
        f"/api/projects/{project['id']}/review-marks",
        json={"items": [{"target_type": "scene", "target_id": scene["id"]}]},
    ).json()["marks"][0]

    response = client.delete(f"/api/review-marks/{mark['id']}")

    assert response.status_code == 204
    assert client.get(f"/api/projects/{project['id']}/review-marks").json() == []


def test_marks_can_be_cleared_in_bulk(client):
    project, volume, _chapter, scene = _tree(client)
    client.post(
        f"/api/projects/{project['id']}/review-marks",
        json={
            "items": [
                {"target_type": "scene", "target_id": scene["id"]},
                {"target_type": "volume", "target_id": volume["id"]},
            ]
        },
    )

    cleared = client.post(
        f"/api/projects/{project['id']}/review-marks/clear",
        json={
            "items": [
                {"target_type": "scene", "target_id": scene["id"]},
                {"target_type": "volume", "target_id": volume["id"]},
            ]
        },
    )

    assert cleared.json()["removed"] == 2
    assert cleared.json()["marks"] == []


def test_clearing_a_missing_mark_is_404(client):
    assert client.delete("/api/review-marks/nope").status_code == 404


def test_marks_of_an_unknown_project_is_404(client):
    assert client.get("/api/projects/nope/review-marks").status_code == 404


def test_adding_a_mark_with_an_unknown_type_is_400(client):
    project, _volume, _chapter, scene = _tree(client)

    response = client.post(
        f"/api/projects/{project['id']}/review-marks",
        json={"items": [{"target_type": "chapterr", "target_id": scene["id"]}]},
    )

    assert response.status_code == 400
