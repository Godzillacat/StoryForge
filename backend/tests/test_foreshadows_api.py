def test_foreshadow_crud_over_http(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()

    created = client.post(
        f"/api/projects/{project['id']}/foreshadows",
        json={"name": "失忆的录音带", "note": "主角的过去"},
    ).json()
    assert created["name"] == "失忆的录音带"
    assert created["actual_pay_scene_id"] is None

    listed = client.get(f"/api/projects/{project['id']}/foreshadows").json()
    assert [row["id"] for row in listed] == [created["id"]]

    updated = client.patch(
        f"/api/foreshadows/{created['id']}",
        json={"name": "录音带", "status": "planted"},
    ).json()
    assert updated["name"] == "录音带"
    assert updated["status"] == "planted"

    assert client.delete(f"/api/foreshadows/{created['id']}").status_code == 204
    assert client.get(f"/api/projects/{project['id']}/foreshadows").json() == []


def _scene(client, project_id: str) -> str:
    volume = client.post(
        f"/api/projects/{project_id}/volumes", json={"name": "第一卷"}
    ).json()
    chapter = client.post(
        f"/api/volumes/{volume['id']}/chapters", json={"title": "第一章"}
    ).json()
    return client.post(
        f"/api/chapters/{chapter['id']}/scenes", json={"goal": "回收"}
    ).json()["id"]


def test_author_can_clear_a_wrongly_matched_actual_pay(client):
    """回写助手匹配错场景时，作者得能撤销那条事实 —— 否则「已收」会一直派生下去。"""
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    scene_id = _scene(client, project["id"])
    created = client.post(
        f"/api/projects/{project['id']}/foreshadows",
        json={"name": "录音带", "status": "planted"},
    ).json()

    paid = client.patch(
        f"/api/foreshadows/{created['id']}", json={"actual_pay_scene_id": scene_id}
    ).json()
    assert paid["effective_status"] == "paid"

    cleared = client.patch(
        f"/api/foreshadows/{created['id']}", json={"actual_pay_scene_id": None}
    ).json()
    assert cleared["actual_pay_scene_id"] is None
    assert cleared["effective_status"] == "planted"


def test_foreshadow_types_are_served_by_the_backend(client):
    """词表由后端下发，前端不硬编第二份。"""
    rows = client.get("/api/foreshadow-types").json()["statuses"]

    assert [row["key"] for row in rows] == ["planned", "planted", "paid", "dropped"]
    assert {row["key"]: row["label"] for row in rows}["dropped"] == "已弃"


def test_summary_reports_rate_without_dropped(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    scene_id = _scene(client, project["id"])
    # 创建接口不接 actual_pay_scene_id（建伏笔时还没回收），走 PATCH。
    paid = client.post(
        f"/api/projects/{project['id']}/foreshadows", json={"name": "已收"}
    ).json()
    client.patch(f"/api/foreshadows/{paid['id']}", json={"actual_pay_scene_id": scene_id})
    for name, body in (("已埋", {"status": "planted"}), ("放弃", {"status": "dropped"}),
                       ("放弃二", {"status": "dropped"})):
        client.post(f"/api/projects/{project['id']}/foreshadows", json={"name": name, **body})

    summary = client.get(f"/api/projects/{project['id']}/foreshadows/summary").json()

    assert summary["total"] == 4
    assert summary["dropped"] == 2
    # 1 / (1 + 1 + 0)
    assert summary["rate"] == 0.5
