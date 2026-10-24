"""设定投放曲线的后端投影。

只读投影：词表来自 `SettingEntry.name` ∪ `aliases_json`，命中来自场景已采纳正文的字面
扫描。不调用模型、不落库。这里钉住的是 spec §3.1 / §4 的边界：长 form 优先、阅读顺序
取首次、无正文章不参与新/旧判定、重名计入歧义、正则元字符不误匹配。
"""

import pytest

from app.db.models import Chapter, Project, Scene, SettingEntry, Volume
from app.services import setting_load_service


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


def _scene(session, chapter, seq, body=None, **fields):
    scene = Scene(chapter_id=chapter.id, seq=seq, body=body, **fields)
    session.add(scene)
    session.commit()
    return scene


def _entry(session, project, name, aliases=(), **fields):
    entry = SettingEntry(
        project_id=project.id,
        type=fields.pop("type", "concept"),
        name=name,
        aliases_json=list(aliases),
        **fields,
    )
    session.add(entry)
    session.commit()
    return entry


@pytest.fixture()
def project_with_bodies(session):
    """三章：有正文、有正文、没写；三个条目：一个带长别名、一个正常、一个只在无正文章出现。"""
    project = _project(session)
    volume = _volume(session, project)
    first = _chapter(session, volume, 0, "雨夜")
    _scene(session, first, 0, body="阿明哥推门进来。")
    second = _chapter(session, volume, 1, "天亮")
    _scene(session, second, 0, body="雾港的雨停了。")
    third = _chapter(session, volume, 2, "未写")
    # 无正文章：场景卡里提了「潮汐」，但那不是正文，不能算已投放。
    _scene(session, third, 0, goal="潮汐将至")
    _entry(session, project, "阿明", aliases=["阿明哥"])
    _entry(session, project, "雾港")
    _entry(session, project, "潮汐")
    return project


def test_long_form_wins(session, project_with_bodies):
    data = setting_load_service.build_load(session, project_with_bodies.id)
    chapter = data["chapters"][0]

    assert {"阿明哥"} == {term["form"] for term in chapter["new_terms"]}
    assert chapter["mentions"] == 1
    assert chapter["chars"] == 8
    assert chapter["density"] == 125.0


def test_chapter_without_body_is_not_counted(session, project_with_bodies):
    data = setting_load_service.build_load(session, project_with_bodies.id)
    empty = next(chapter for chapter in data["chapters"] if not chapter["has_body"])

    assert empty["new_count"] == 0 and empty["density"] == 0
    assert empty["mentions"] == 0 and empty["chars"] == 0
    assert empty["new_terms"] == []
    # 只在无正文里出现（且只出现在场景卡上）的条目仍算从未出现。
    assert data["totals"]["never_seen"] == 1


def test_first_appearance_is_by_reading_order(session, project_with_bodies):
    data = setting_load_service.build_load(session, project_with_bodies.id)
    firsts = [
        chapter
        for chapter in data["chapters"]
        if any(term["name"] == "雾港" for term in chapter["new_terms"])
    ]

    assert len(firsts) == 1
    assert firsts[0]["label"].startswith("第2章")
    assert data["totals"] == {
        "entries": 3,
        "delivered": 2,
        "never_seen": 1,
        "ambiguities": 0,
    }


def test_repeated_mentions_count_but_the_term_is_listed_once(session):
    project = _project(session)
    chapter = _chapter(session, _volume(session, project), 0, "雨夜")
    _scene(session, chapter, 0, body="雾港。雾港又起雾了。")
    _entry(session, project, "雾港")

    data = setting_load_service.build_load(session, project.id)
    row = data["chapters"][0]

    assert row["mentions"] == 2
    assert row["new_count"] == 1
    assert len(row["new_terms"]) == 1
    assert row["new_terms"][0]["form"] == "雾港"


def test_a_form_in_two_scenes_of_one_chapter_is_listed_once(session):
    project = _project(session)
    chapter = _chapter(session, _volume(session, project), 0, "雨夜")
    _scene(session, chapter, 0, body="雾港的雨。")
    _scene(session, chapter, 1, body="雾港的灯。")
    _entry(session, project, "雾港")

    data = setting_load_service.build_load(session, project.id)
    row = data["chapters"][0]

    assert row["mentions"] == 2
    assert row["new_count"] == 1


def test_duplicate_forms_are_counted_as_ambiguities(session):
    project = _project(session)
    chapter = _chapter(session, _volume(session, project), 0, "雨夜")
    _scene(session, chapter, 0, body="老师来了。")
    earliest = _entry(session, project, "阿明", aliases=["老师"])
    _entry(session, project, "先生", aliases=["老师"])

    data = setting_load_service.build_load(session, project.id)
    term = data["chapters"][0]["new_terms"][0]

    assert data["totals"]["ambiguities"] == 1
    # 两个条目都不叫「老师」时，归最早创建的那个。
    assert term["entry_id"] == earliest.id
    assert term["name"] == "阿明"


def test_form_prefers_the_entry_whose_name_equals_it(session):
    project = _project(session)
    chapter = _chapter(session, _volume(session, project), 0, "雨夜")
    _scene(session, chapter, 0, body="老师来了。")
    _entry(session, project, "阿明", aliases=["老师"])
    named = _entry(session, project, "老师")

    data = setting_load_service.build_load(session, project.id)

    assert data["totals"]["ambiguities"] == 1
    assert data["chapters"][0]["new_terms"][0]["entry_id"] == named.id


def test_regex_metacharacters_do_not_overmatch(session):
    project = _project(session)
    chapter = _chapter(session, _volume(session, project), 0, "雨夜")
    _scene(session, chapter, 0, body="A.B 与 AXB 是两回事。")
    _entry(session, project, "A.B")

    data = setting_load_service.build_load(session, project.id)
    row = data["chapters"][0]

    assert row["mentions"] == 1
    assert {term["form"] for term in row["new_terms"]} == {"A.B"}


def test_parentheses_and_pipes_are_escaped_too(session):
    """未转义的 `A(B|C)` 会把正文里的 AB / AC 当成命中。"""
    project = _project(session)
    chapter = _chapter(session, _volume(session, project), 0, "雨夜")
    _scene(session, chapter, 0, body="A(B|C) 与 AB 与 AC。")
    _entry(session, project, "A(B|C)")

    row = setting_load_service.build_load(session, project.id)["chapters"][0]

    assert row["mentions"] == 1
    assert {term["form"] for term in row["new_terms"]} == {"A(B|C)"}


def test_wordlist_tolerates_broken_alias_json(session):
    project = _project(session)
    chapter = _chapter(session, _volume(session, project), 0, "雨夜")
    _scene(session, chapter, 0, body="阿明来了。")
    broken = _entry(session, project, "阿明")
    # 历史数据或手工改库可能留下非数组、非字符串的别名：跳过，不炸。
    broken.aliases_json = "阿明"
    session.commit()
    mixed = _entry(session, project, "雾港")
    mixed.aliases_json = [None, 3, {"name": "雾港"}, "  ", "  雾港  "]
    session.commit()

    data = setting_load_service.build_load(session, project.id)
    row = data["chapters"][0]

    assert row["mentions"] == 1
    assert {term["form"] for term in row["new_terms"]} == {"阿明"}
    assert data["totals"]["entries"] == 2


def test_entries_without_any_usable_form_are_counted_as_never_seen(session):
    project = _project(session)
    chapter = _chapter(session, _volume(session, project), 0, "雨夜")
    _scene(session, chapter, 0, body="雨。")
    _entry(session, project, "")

    data = setting_load_service.build_load(session, project.id)

    # 没有可用 form 的条目仍是条目：计入总数，也必然「从未出现」。
    assert data["totals"] == {
        "entries": 1,
        "delivered": 0,
        "never_seen": 1,
        "ambiguities": 0,
    }
    assert data["reason"] == ""


def test_project_without_entries_says_so(session):
    project = _project(session)
    chapter = _chapter(session, _volume(session, project), 0, "雨夜")
    _scene(session, chapter, 0, body="雾港的雨停了。")

    data = setting_load_service.build_load(session, project.id)

    assert data["reason"] == "还没有设定条目"
    assert data["chapters"][0]["has_body"] is True
    assert data["chapters"][0]["mentions"] == 0
    assert data["chapters"][0]["new_count"] == 0


def test_project_without_bodies_says_so(session):
    project = _project(session)
    chapter = _chapter(session, _volume(session, project), 0, "雨夜")
    _scene(session, chapter, 0, body="   ")
    _entry(session, project, "雾港")

    data = setting_load_service.build_load(session, project.id)

    assert data["reason"] == "还没有已采纳正文"
    assert data["chapters"][0]["has_body"] is False
    assert data["totals"]["never_seen"] == 1


def test_new_count_dedupes_aliases_of_one_entry_in_a_chapter(session):
    """`new_terms` 按 form 列，但柱子数的是条目：同一角色的两个称呼只算 1。"""
    project = _project(session)
    chapter = _chapter(session, _volume(session, project), 0, "雨夜")
    _scene(session, chapter, 0, body="阿明哥和阿明都来了。")
    _entry(session, project, "阿明", aliases=["阿明哥"])

    row = setting_load_service.build_load(session, project.id)["chapters"][0]

    assert {term["form"] for term in row["new_terms"]} == {"阿明", "阿明哥"}
    assert row["new_count"] == 1


def test_an_alias_of_an_already_delivered_entry_is_not_counted_as_new(session):
    project = _project(session)
    volume = _volume(session, project)
    first = _chapter(session, volume, 0, "雨夜")
    _scene(session, first, 0, body="阿明来了。")
    second = _chapter(session, volume, 1, "天亮")
    _scene(session, second, 0, body="阿明哥来了。")
    _entry(session, project, "阿明", aliases=["阿明哥"])

    data = setting_load_service.build_load(session, project.id)

    assert data["chapters"][0]["new_count"] == 1
    # 第二个称呼仍作为 form 首次出现列出来，但这个条目已经投放过，不再计「新」。
    assert {term["form"] for term in data["chapters"][1]["new_terms"]} == {"阿明哥"}
    assert data["chapters"][1]["new_count"] == 0
    assert sum(chapter["new_count"] for chapter in data["chapters"]) == (
        data["totals"]["delivered"]
    ) == 1


def test_a_form_seen_in_an_earlier_chapter_is_not_listed_again(session):
    project = _project(session)
    volume = _volume(session, project)
    first = _chapter(session, volume, 0, "雨夜")
    _scene(session, first, 0, body="雾港的雨。")
    second = _chapter(session, volume, 1, "天亮")
    _scene(session, second, 0, body="雾港又起雾了。")
    _entry(session, project, "雾港")

    data = setting_load_service.build_load(session, project.id)

    assert data["chapters"][0]["new_count"] == 1
    assert data["chapters"][1]["new_terms"] == []
    assert data["chapters"][1]["new_count"] == 0
    assert data["chapters"][1]["mentions"] == 1


def test_first_appearance_follows_volume_order(session):
    """第二卷第一章的首次出现必须晚于第一卷末章。"""
    project = _project(session)
    first_volume = _volume(session, project, seq=0, name="第一卷")
    opening = _chapter(session, first_volume, 0, "起点")
    _scene(session, opening, 0, body="风。")
    last_of_first = _chapter(session, first_volume, 1, "末章")
    _scene(session, last_of_first, 0, body="阿明来了。")
    second_volume = _volume(session, project, seq=1, name="第二卷")
    first_of_second = _chapter(session, second_volume, 0, "新篇")
    _scene(session, first_of_second, 0, body="雾港。")
    _entry(session, project, "阿明")
    _entry(session, project, "雾港")

    data = setting_load_service.build_load(session, project.id)

    assert [chapter["volume_label"] for chapter in data["chapters"]] == [
        "第一卷",
        "第一卷",
        "第二卷",
    ]
    assert [
        [term["name"] for term in chapter["new_terms"]]
        for chapter in data["chapters"]
    ] == [[], ["阿明"], ["雾港"]]
    assert data["chapters"][2]["id"] == first_of_second.id


def test_another_projects_entries_and_bodies_do_not_leak(session):
    project = _project(session)
    chapter = _chapter(session, _volume(session, project), 0, "雨夜")
    _scene(session, chapter, 0, body="雨。")
    _entry(session, project, "雾港")

    other = _project(session, name="别处")
    other_chapter = _chapter(session, _volume(session, other), 0, "晴")
    _scene(session, other_chapter, 0, body="雾港")
    _entry(session, other, "潮汐")

    data = setting_load_service.build_load(session, project.id)

    assert data["totals"] == {
        "entries": 1,
        "delivered": 0,
        "never_seen": 1,
        "ambiguities": 0,
    }
    assert data["chapters"][0]["mentions"] == 0


def test_unknown_project_raises(session):
    with pytest.raises(ValueError, match="项目不存在"):
        setting_load_service.build_load(session, "nope")


def test_api_reports_an_unknown_project_as_404(client):
    response = client.get("/api/projects/nope/setting-load")

    assert response.status_code == 404
    assert "项目不存在" in response.json()["detail"]


def test_api_returns_empty_chapters_for_a_new_project(client):
    project = client.post("/api/projects", json={"name": "空项目"}).json()

    body = client.get(f"/api/projects/{project['id']}/setting-load").json()

    assert body == {
        "chapters": [],
        "totals": {"entries": 0, "delivered": 0, "never_seen": 0, "ambiguities": 0},
        "reason": "还没有设定条目",
    }
