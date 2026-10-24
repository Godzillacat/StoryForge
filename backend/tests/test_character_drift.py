"""性格漂移：人物在章上的手记状态与只读投影。

状态是作者手记的一行文本，服务只负责存与投影，不判断变化合不合理（那是逻辑
自检的事）。这里钉住 spec §3.1–§3.2 / §4 的边界：`(chapter_id, entry_id)` 唯一、
写入是 upsert、`changed` 与该人物上一条记录比（首条恒 false）、没记录是缺格而
不是 0、章与条目都必须属于该项目、删章 / 删人物条目时状态行跟着走。
"""

from dataclasses import dataclass

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db.models import Chapter, CharacterState, Project, SettingEntry, Volume
from app.db.session import SessionLocal
from app.services import character_drift_service


@dataclass
class DriftSetup:
    project: Project
    volume: Volume
    chapters: list[Chapter]
    hero: SettingEntry
    friend: SettingEntry
    place: SettingEntry


def _project(session, name="雾港"):
    project = Project(name=name)
    session.add(project)
    session.commit()
    return project


def _volume(session, project, seq=0, name="第一卷"):
    volume = Volume(project_id=project.id, seq=seq, name=name)
    session.add(volume)
    session.commit()
    return volume


def _chapter(session, volume, seq, title):
    chapter = Chapter(volume_id=volume.id, seq=seq, title=title)
    session.add(chapter)
    session.commit()
    return chapter


def _entry(session, project, kind, name):
    entry = SettingEntry(project_id=project.id, type=kind, name=name)
    session.add(entry)
    session.commit()
    return entry


@pytest.fixture()
def drift(session):
    """四章、两个人、一个非人物条目 —— 「第几章」的标签与缺格都靠这四章。"""
    project = _project(session)
    volume = _volume(session, project)
    chapters = [
        _chapter(session, volume, seq, title)
        for seq, title in enumerate(("雨夜", "码头", "审讯", "天亮"))
    ]
    return DriftSetup(
        project=project,
        volume=volume,
        chapters=chapters,
        hero=_entry(session, project, "character", "阿明"),
        friend=_entry(session, project, "character", "阿乙"),
        place=_entry(session, project, "place", "灯塔"),
    )


def _put(session, drift, chapter, entry, note):
    return character_drift_service.put_state(session, chapter.id, entry.id, note)


def _row(data, entry):
    return next(row for row in data["characters"] if row["entry_id"] == entry.id)


def _state_count(session):
    return session.scalar(select(func.count()).select_from(CharacterState))


def test_first_record_is_not_a_change(session, drift):
    _put(session, drift, drift.chapters[0], drift.hero, "犹豫")

    data = character_drift_service.get_drift(session, drift.project.id)

    # 只有一条记录的人物也列出来：作者确认过这一条，只是看不出漂移。
    assert [row["name"] for row in data["characters"]] == ["阿明"]
    row = data["characters"][0]
    assert row["cells"] == [
        {
            "chapter_id": drift.chapters[0].id,
            "label": "第1章 雨夜",
            "note": "犹豫",
            "changed": False,
        }
    ]
    assert row["changes"] == 0
    assert row["recorded"] == 1
    assert data["totals"] == {"characters": 1, "changes": 0, "sparse": 1}
    assert data["reason"] == ""


def test_chapters_are_always_the_whole_project_in_reading_order(session, drift):
    """`chapters` 是全项目章列表（前端据此对齐列），与有没有记录无关。"""
    # 第二卷排在后面，阅读顺序必须跟着卷序、章序走。
    second_volume = _volume(session, drift.project, seq=1, name="第二卷")
    _chapter(session, second_volume, 0, "归途")

    data = character_drift_service.get_drift(session, drift.project.id)

    assert data["chapters"] == [
        {"id": chapter.id, "label": f"第{index + 1}章 {chapter.title}"}
        for index, chapter in enumerate(drift.chapters)
    ] + [{"id": data["chapters"][-1]["id"], "label": "第1章 归途"}]
    assert data["characters"] == []
    assert data["totals"] == {"characters": 0, "changes": 0, "sparse": 0}
    assert data["reason"] == "还没有状态记录"


def test_project_without_characters_says_so(session):
    project = _project(session, "空项目")
    _volume(session, project)

    data = character_drift_service.get_drift(session, project.id)

    assert data["characters"] == []
    assert data["totals"] == {"characters": 0, "changes": 0, "sparse": 0}
    assert data["reason"] == "还没有人物"


def test_unknown_project_raises(session):
    with pytest.raises(ValueError, match="项目不存在"):
        character_drift_service.get_drift(session, "nope")


def test_same_note_is_not_a_change(session, drift):
    _put(session, drift, drift.chapters[0], drift.hero, "犹豫")
    _put(session, drift, drift.chapters[1], drift.hero, "犹豫")

    row = _row(character_drift_service.get_drift(session, drift.project.id), drift.hero)

    # 两条都留着（作者确认过两次），只是都没变 —— 不能合并成一条。
    assert row["recorded"] == 2
    assert [cell["changed"] for cell in row["cells"]] == [False, False]
    assert row["changes"] == 0
    assert character_drift_service.get_drift(session, drift.project.id)["totals"] == {
        "characters": 1,
        "changes": 0,
        "sparse": 0,
    }


def test_changed_compares_with_the_characters_previous_record(session, drift):
    notes = ("犹豫", "决意", "决意", "动摇")
    for chapter, note in zip(drift.chapters, notes):
        _put(session, drift, chapter, drift.hero, note)

    row = _row(character_drift_service.get_drift(session, drift.project.id), drift.hero)

    # 与「上一条记录」比，不是与上一章比：第 3 章重复第 2 章的状态不算变化。
    assert [cell["changed"] for cell in row["cells"]] == [False, True, False, True]
    assert row["changes"] == 2
    assert row["recorded"] == 4


def test_cells_only_contain_recorded_chapters(session, drift):
    _put(session, drift, drift.chapters[0], drift.hero, "犹豫")
    _put(session, drift, drift.chapters[2], drift.hero, "决意")

    row = _row(character_drift_service.get_drift(session, drift.project.id), drift.hero)

    # 没记录的章是缺格（前端留白），不是 0、也不是空字符串。
    assert [cell["chapter_id"] for cell in row["cells"]] == [
        drift.chapters[0].id,
        drift.chapters[2].id,
    ]
    assert [cell["label"] for cell in row["cells"]] == ["第1章 雨夜", "第3章 审讯"]


def test_sparse_counts_characters_with_a_single_record(session, drift):
    _put(session, drift, drift.chapters[0], drift.hero, "犹豫")
    _put(session, drift, drift.chapters[1], drift.friend, "沉默")
    _put(session, drift, drift.chapters[2], drift.friend, "开口")

    data = character_drift_service.get_drift(session, drift.project.id)

    assert {row["name"] for row in data["characters"]} == {"阿明", "阿乙"}
    assert _row(data, drift.hero)["changes"] == 0
    assert _row(data, drift.friend)["changes"] == 1
    assert data["totals"] == {"characters": 2, "changes": 1, "sparse": 1}


def test_upsert_keeps_a_single_row(session, drift):
    _put(session, drift, drift.chapters[0], drift.hero, "犹豫")
    _put(session, drift, drift.chapters[0], drift.hero, "决意")

    # 直接查库：唯一约束 + upsert 必须真的只留一行。
    assert _state_count(session) == 1
    row = _row(character_drift_service.get_drift(session, drift.project.id), drift.hero)
    assert row["recorded"] == 1
    assert row["cells"][0]["note"] == "决意"
    assert row["changes"] == 0


def test_database_enforces_one_record_per_chapter_and_character(session, drift):
    """唯一约束要真的建在库里：绕过服务直插第二行必须被数据库拒绝。"""
    _put(session, drift, drift.chapters[0], drift.hero, "犹豫")

    session.add(
        CharacterState(
            chapter_id=drift.chapters[0].id, entry_id=drift.hero.id, note="决意"
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    assert _state_count(session) == 1


def test_non_character_is_rejected(session, drift):
    with pytest.raises(ValueError, match="只能记录人物的状态"):
        _put(session, drift, drift.chapters[0], drift.place, "灯塔亮了")
    assert _state_count(session) == 0


def test_note_is_stored_without_surrounding_whitespace(session, drift):
    _put(session, drift, drift.chapters[0], drift.hero, "  犹豫  ")

    row = _row(character_drift_service.get_drift(session, drift.project.id), drift.hero)

    assert row["cells"][0]["note"] == "犹豫"


def test_blank_note_is_rejected(session, drift):
    with pytest.raises(ValueError, match="状态不能为空"):
        _put(session, drift, drift.chapters[0], drift.hero, "   ")
    assert _state_count(session) == 0


def test_oversized_note_is_rejected(session, drift):
    with pytest.raises(ValueError, match="500"):
        _put(session, drift, drift.chapters[0], drift.hero, "字" * 501)

    _put(session, drift, drift.chapters[0], drift.hero, "字" * 500)
    assert _state_count(session) == 1


def test_deleting_a_missing_record_raises(session, drift):
    with pytest.raises(ValueError, match="没有这条记录"):
        character_drift_service.delete_state(
            session, drift.chapters[0].id, drift.hero.id
        )


def test_deleting_a_middle_record_recomputes_changed(session, drift):
    for index, note in ((0, "犹豫"), (1, "决意"), (2, "犹豫")):
        _put(session, drift, drift.chapters[index], drift.hero, note)
    before = _row(
        character_drift_service.get_drift(session, drift.project.id), drift.hero
    )
    assert [cell["changed"] for cell in before["cells"]] == [False, True, True]

    character_drift_service.delete_state(
        session, drift.chapters[1].id, drift.hero.id
    )

    after = _row(
        character_drift_service.get_drift(session, drift.project.id), drift.hero
    )
    # 删掉中间那条之后，第 3 章与第 1 章相同 —— changed 重算为 false。
    assert [cell["changed"] for cell in after["cells"]] == [False, False]
    assert after["changes"] == 0
    assert after["recorded"] == 2
    assert _state_count(session) == 2


def test_deleting_a_chapter_removes_its_states(session, drift):
    _put(session, drift, drift.chapters[0], drift.hero, "犹豫")
    _put(session, drift, drift.chapters[1], drift.hero, "决意")

    session.delete(drift.chapters[0])
    session.commit()

    remaining = session.scalars(select(CharacterState)).all()
    assert [state.chapter_id for state in remaining] == [drift.chapters[1].id]


def test_deleting_a_character_entry_removes_its_states(session, drift):
    _put(session, drift, drift.chapters[0], drift.hero, "犹豫")
    _put(session, drift, drift.chapters[0], drift.friend, "沉默")

    session.delete(drift.hero)
    session.commit()

    remaining = session.scalars(select(CharacterState)).all()
    assert [state.entry_id for state in remaining] == [drift.friend.id]


def _seed_api(client, name="雾港"):
    """通过接口造项目：API 用例验证的是路由层的状态码与错误映射。"""
    project = client.post("/api/projects", json={"name": name}).json()
    volume = client.post(
        f"/api/projects/{project['id']}/volumes", json={"name": "第一卷"}
    ).json()
    chapter = client.post(
        f"/api/volumes/{volume['id']}/chapters", json={"title": "雨夜"}
    ).json()
    hero = client.post(
        f"/api/projects/{project['id']}/entries",
        json={"type": "character", "name": f"{name}的阿明"},
    ).json()
    place = client.post(
        f"/api/projects/{project['id']}/entries",
        json={"type": "place", "name": f"{name}的灯塔"},
    ).json()
    return project, chapter, hero, place


def _path(chapter, entry):
    return f"/api/chapters/{chapter['id']}/character-states/{entry['id']}"


def test_api_round_trip_put_get_delete(client):
    project, chapter, hero, _place = _seed_api(client)

    written = client.put(_path(chapter, hero), json={"note": "  犹豫  "})
    assert written.status_code == 200
    body = written.json()
    assert body["chapter_id"] == chapter["id"]
    assert body["entry_id"] == hero["id"]
    assert body["note"] == "犹豫"

    drift = client.get(f"/api/projects/{project['id']}/character-drift").json()
    assert drift["characters"] == [
        {
            "entry_id": hero["id"],
            "name": hero["name"],
            "cells": [
                {
                    "chapter_id": chapter["id"],
                    "label": "第1章 雨夜",
                    "note": "犹豫",
                    "changed": False,
                }
            ],
            "changes": 0,
            "recorded": 1,
        }
    ]
    assert drift["chapters"] == [{"id": chapter["id"], "label": "第1章 雨夜"}]
    assert drift["totals"] == {"characters": 1, "changes": 0, "sparse": 1}
    assert drift["reason"] == ""

    assert client.delete(_path(chapter, hero)).status_code == 204
    assert client.get(f"/api/projects/{project['id']}/character-drift").json()[
        "characters"
    ] == []


def test_api_rejects_a_non_character_with_400(client):
    _project, chapter, _hero, place = _seed_api(client)

    response = client.put(_path(chapter, place), json={"note": "灯塔亮了"})

    assert response.status_code == 400
    assert "只能记录人物的状态" in response.json()["detail"]


def test_api_rejects_a_blank_note_with_400(client):
    _project, chapter, hero, _place = _seed_api(client)

    response = client.put(_path(chapter, hero), json={"note": "   "})

    assert response.status_code == 400
    assert "状态不能为空" in response.json()["detail"]


def test_api_rejects_an_oversized_note_with_400(client):
    _project, chapter, hero, _place = _seed_api(client)

    response = client.put(_path(chapter, hero), json={"note": "字" * 501})

    assert response.status_code == 400
    assert "500" in response.json()["detail"]


def test_api_reports_unknown_project_as_404(client):
    response = client.get("/api/projects/nope/character-drift")

    assert response.status_code == 404
    assert "项目不存在" in response.json()["detail"]


def test_api_reports_an_unknown_chapter_as_404(client):
    _project, _chapter, hero, _place = _seed_api(client)

    response = client.put(_path({"id": "nope"}, hero), json={"note": "犹豫"})

    assert response.status_code == 404
    assert "章不存在" in response.json()["detail"]


def test_api_treats_another_projects_character_as_missing(client):
    _own_project, own_chapter, own_hero, _own_place = _seed_api(client, "雾港")
    _other_project, other_chapter, other_hero, _other_place = _seed_api(client, "南滨")

    response = client.put(_path(own_chapter, other_hero), json={"note": "犹豫"})
    assert response.status_code == 404
    assert "人物不存在" in response.json()["detail"]

    # 反过来也不通：章与条目必须属于同一个项目。
    response = client.put(_path(other_chapter, own_hero), json={"note": "犹豫"})
    assert response.status_code == 404
    assert "人物不存在" in response.json()["detail"]


def test_api_reports_an_unknown_entry_as_404(client):
    _project, chapter, _hero, _place = _seed_api(client)

    response = client.put(_path(chapter, {"id": "nope"}), json={"note": "犹豫"})

    assert response.status_code == 404
    assert "人物不存在" in response.json()["detail"]


def test_api_deletes_a_missing_record_as_404(client):
    _project, chapter, hero, _place = _seed_api(client)

    response = client.delete(_path(chapter, hero))

    assert response.status_code == 404
    assert "没有这条记录" in response.json()["detail"]


def test_api_deleting_a_chapter_cascades_to_states(client):
    _project, chapter, hero, _place = _seed_api(client)
    assert client.put(_path(chapter, hero), json={"note": "犹豫"}).status_code == 200

    assert client.delete(f"/api/chapters/{chapter['id']}").status_code == 204

    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(CharacterState)) == 0
