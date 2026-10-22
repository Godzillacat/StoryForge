import json


def test_tree_and_volume_chapter_crud_over_http(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()

    volume = client.post(
        f"/api/projects/{project['id']}/volumes", json={"name": "第一卷"}
    ).json()
    chapter = client.post(
        f"/api/volumes/{volume['id']}/chapters", json={"title": "第一章"}
    ).json()

    tree = client.get(f"/api/projects/{project['id']}/chapters/tree").json()["volumes"]
    assert tree[0]["name"] == "第一卷"
    assert tree[0]["chapters"][0]["title"] == "第一章"
    assert tree[0]["chapters"][0]["scenes"] == []

    updated = client.patch(
        f"/api/chapters/{chapter['id']}",
        json={"hook": "门后有人", "conflict_level": 4, "dialogue_ratio": 0.3},
    ).json()
    assert updated["hook"] == "门后有人"
    assert updated["conflict_level"] == 4

    moved = client.post(
        f"/api/volumes/{volume['id']}/move", json={"direction": "down"}
    )
    assert moved.status_code == 200

    assert client.delete(f"/api/chapters/{chapter['id']}").status_code == 204
    assert client.delete(f"/api/volumes/{volume['id']}").status_code == 204


def test_chapter_types_lists_the_status_vocabulary(client):
    payload = client.get("/api/chapter-types").json()
    assert payload["statuses"] == [
        {"key": "planned", "label": "规划中"},
        {"key": "confirmed", "label": "已确认"},
    ]


def test_volume_validation_is_a_readable_400(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    response = client.post(
        f"/api/projects/{project['id']}/volumes", json={"name": "   "}
    )
    assert response.status_code == 400
    assert "卷名" in response.json()["detail"]


def test_chapter_bad_rhythm_is_a_readable_400(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    volume = client.post(
        f"/api/projects/{project['id']}/volumes", json={"name": "卷"}
    ).json()

    response = client.post(
        f"/api/volumes/{volume['id']}/chapters",
        json={"title": "章", "conflict_level": 9},
    )
    assert response.status_code == 400
    assert "冲突强度" in response.json()["detail"]


def test_missing_volume_is_404(client):
    assert client.patch("/api/volumes/nope", json={"name": "X"}).status_code == 404
    assert client.post("/api/volumes/nope/move", json={"direction": "up"}).status_code == 404


def test_scene_crud_and_name_resolution_over_http(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    chen = client.post(
        f"/api/projects/{project['id']}/entries", json={"type": "人物", "name": "陈默"}
    ).json()
    place = client.post(
        f"/api/projects/{project['id']}/entries", json={"type": "地理", "name": "南滨"}
    ).json()
    volume = client.post(
        f"/api/projects/{project['id']}/volumes", json={"name": "第一卷"}
    ).json()
    chapter = client.post(
        f"/api/volumes/{volume['id']}/chapters", json={"title": "第一章"}
    ).json()

    scene = client.post(
        f"/api/chapters/{chapter['id']}/scenes",
        json={
            "goal": "找到录音带",
            "characters": ["陈默"],
            "location": "南滨",
            "foreshadow_plants": ["失忆的录音带"],
        },
    ).json()
    assert scene["characters"] == [chen["id"]]
    assert scene["location_id"] == place["id"]
    assert scene["foreshadows"]["plants"][0]["name"] == "失忆的录音带"

    tree = client.get(f"/api/projects/{project['id']}/chapters/tree").json()["volumes"]
    assert tree[0]["chapters"][0]["scenes"][0]["goal"] == "找到录音带"


def test_unknown_character_name_is_a_readable_400(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    volume = client.post(
        f"/api/projects/{project['id']}/volumes", json={"name": "卷"}
    ).json()
    chapter = client.post(
        f"/api/volumes/{volume['id']}/chapters", json={"title": "章"}
    ).json()

    response = client.post(
        f"/api/chapters/{chapter['id']}/scenes",
        json={"goal": "目标", "characters": ["不存在"]},
    )
    assert response.status_code == 400
    assert "找不到" in response.json()["detail"]


def test_scene_bulk_write_replace_and_append(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    client.post(
        f"/api/projects/{project['id']}/entries", json={"type": "人物", "name": "陈默"}
    )
    volume = client.post(
        f"/api/projects/{project['id']}/volumes", json={"name": "卷"}
    ).json()
    chapter = client.post(
        f"/api/volumes/{volume['id']}/chapters", json={"title": "章"}
    ).json()

    first = client.put(
        f"/api/chapters/{chapter['id']}/scenes",
        json={
            "mode": "replace",
            "scenes": [{"goal": "开场", "characters": ["陈默"]}],
        },
    )
    assert first.status_code == 200

    second = client.put(
        f"/api/chapters/{chapter['id']}/scenes",
        json={"mode": "append", "scenes": [{"goal": "追加"}]},
    )
    assert second.status_code == 200
    scenes = second.json()["volumes"][0]["chapters"][0]["scenes"]
    assert [scene["goal"] for scene in scenes] == ["开场", "追加"]


CHAPTER_PLAN = json.dumps(
    {
        "volumes": [
            {
                "name": "候选卷",
                "purpose": "立目标",
                "chapters": [
                    {
                        "title": "候选章",
                        "pov": "陈默",
                        "target_words": 3000,
                        "conflict_level": 3,
                        "dialogue_ratio": 0.4,
                        "hook_strength": 4,
                        "lines": ["主线"],
                    }
                ],
            }
        ],
        "open_questions": ["第二卷要不要换视角？"],
    },
    ensure_ascii=False,
)

SCENE_PLAN = json.dumps(
    {
        "scenes": [
            {
                "goal": "找到录音带",
                "conflict": "档案室有人",
                "turn": "录音带里是自己的声音",
                "characters": ["陈默"],
                "location": "南滨旧城",
                "target_words_min": 800,
                "target_words_max": 1500,
                "foreshadow_plants": ["失忆的录音带"],
            }
        ],
        "open_questions": [],
    },
    ensure_ascii=False,
)


def _plan_slots(project_id: str) -> None:
    from app.db.models import (
        Act,
        Architecture,
        Chapter,
        Idea,
        SettingEntry,
        TimelineEvent,
        Volume,
    )
    from app.db.session import SessionLocal

    with SessionLocal() as session:
        idea = Idea(project_id=project_id, raw_text="能听见死者遗言的验尸官")
        idea.parsed_json = {"genre": "悬疑", "premise": "记忆可交易", "open_questions": []}
        session.add(idea)
        arch = Architecture(project_id=project_id, logline="记忆清洁工")
        session.add(arch)
        session.flush()
        session.add(Act(architecture_id=arch.id, seq=1, name="第一幕"))
        session.add(
            SettingEntry(project_id=project_id, type="character", name="陈默")
        )
        session.add(
            SettingEntry(project_id=project_id, type="place", name="南滨旧城")
        )
        session.add(
            TimelineEvent(project_id=project_id, title="初遇", story_time="第三年·春")
        )
        volume = Volume(project_id=project_id, seq=0, name="第一卷")
        session.add(volume)
        session.flush()
        session.add(Chapter(volume_id=volume.id, seq=0, title="第一章", pov="陈默"))
        session.commit()


def _patch_runtime(monkeypatch, content: str) -> None:
    import httpx

    from app.runtime.llm import HttpxChatClient
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


def test_chapter_plan_returns_candidates_without_writing(client, monkeypatch):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    _plan_slots(project["id"])
    _patch_runtime(monkeypatch, CHAPTER_PLAN)

    body = client.post(f"/api/projects/{project['id']}/chapters/plan").json()

    assert body["structured"] is True
    assert body["volumes"][0]["chapters"][0]["title"] == "候选章"
    assert body["open_questions"] == ["第二卷要不要换视角？"]
    assert body["warnings"] == []
    # 候选只在运行记录里：树仍是 _plan_slots 建的「第一卷 / 第一章」
    tree = client.get(f"/api/projects/{project['id']}/chapters/tree").json()["volumes"]
    assert tree[0]["name"] == "第一卷"
    assert tree[0]["chapters"][0]["title"] == "第一章"


def test_chapter_plan_write_replace_and_append(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()

    first = client.put(
        f"/api/projects/{project['id']}/chapters",
        json={
            "mode": "replace",
            "source_run_id": "run-1",
            "volumes": [
                {"name": "第一卷", "chapters": [{"title": "第一章"}]}
            ],
        },
    )
    assert first.status_code == 200
    volume = first.json()["volumes"][0]
    assert volume["source_run_id"] == "run-1"
    assert volume["chapters"][0]["source_run_id"] == "run-1"

    second = client.put(
        f"/api/projects/{project['id']}/chapters",
        json={
            "mode": "append",
            "volumes": [{"name": "第二卷", "chapters": [{"title": "第二章"}]}],
        },
    )
    assert [v["name"] for v in second.json()["volumes"]] == ["第一卷", "第二卷"]


def test_scene_plan_returns_candidates_without_writing(client, monkeypatch):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    _plan_slots(project["id"])
    chapter = client.get(f"/api/projects/{project['id']}/chapters/tree").json()["volumes"][0]["chapters"][0]
    _patch_runtime(monkeypatch, SCENE_PLAN)

    body = client.post(f"/api/chapters/{chapter['id']}/scenes/plan").json()

    assert body["structured"] is True
    assert body["scenes"][0]["goal"] == "找到录音带"
    assert body["warnings"] == []
    tree = client.get(f"/api/projects/{project['id']}/chapters/tree").json()["volumes"]
    assert tree[0]["chapters"][0]["scenes"] == []


def _writing_scene(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    volume = client.post(
        f"/api/projects/{project['id']}/volumes", json={"name": "第一卷"}
    ).json()
    chapter = client.post(
        f"/api/volumes/{volume['id']}/chapters", json={"title": "第一章"}
    ).json()
    scene = client.post(
        f"/api/chapters/{chapter['id']}/scenes", json={"goal": "找到录音带"}
    ).json()
    return project, scene


def test_tree_exposes_has_body_without_the_full_text(client):
    project, scene = _writing_scene(client)
    client.put(
        f"/api/scenes/{scene['id']}/body", json={"content": "灯塔下的密信。"}
    )

    tree = client.get(f"/api/projects/{project['id']}/chapters/tree").json()
    node = tree["volumes"][0]["chapters"][0]["scenes"][0]
    assert node["has_body"] is True
    assert "body" not in node


def test_the_entry_list_exposes_locked(client):
    """界面靠这个字段显示与解除锁定；不返回它等于无法解锁设定条目。"""
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    entry = client.post(
        f"/api/projects/{project['id']}/entries",
        json={"type": "character", "name": "沈砚"},
    ).json()

    assert entry["locked"] is False

    client.patch(f"/api/locks/entry/{entry['id']}", json={"locked": True})

    listed = client.get(f"/api/projects/{project['id']}/entries").json()
    assert listed[0]["locked"] is True
