import pytest
from sqlalchemy import select

from app.db.models import Project, SettingEntry
from app.services import world_service


def _project(session) -> Project:
    project = Project(name="雾港")
    session.add(project)
    session.commit()
    return project


def test_create_normalizes_type_and_hardness(session):
    """模型（或手工输入）写「势力」还是「faction」都落到同一个 key。"""
    project = _project(session)

    entry = world_service.create_entry(
        session,
        project.id,
        type="规则体系",
        name="记忆不可复活",
        hardness="硬规则",
    )

    assert entry.type == "rule"
    assert entry.hardness == "hard"


def test_create_rejects_an_unknown_type(session):
    project = _project(session)
    with pytest.raises(ValueError) as excinfo:
        world_service.create_entry(session, project.id, type="魔法体系", name="X")
    assert "魔法体系" in str(excinfo.value)


def test_non_rule_entries_drop_the_hardness(session):
    project = _project(session)
    entry = world_service.create_entry(
        session, project.id, type="place", name="雾港旧城", hardness="hard"
    )
    assert entry.hardness is None


def test_duplicate_name_returns_a_readable_reason(session):
    """唯一约束在数据库上，但作者要看到中文原因而不是 IntegrityError 堆栈。"""
    project = _project(session)
    world_service.create_entry(session, project.id, type="place", name="雾港旧城")

    with pytest.raises(ValueError) as excinfo:
        world_service.create_entry(session, project.id, type="faction", name="雾港旧城")
    assert "雾港旧城" in str(excinfo.value)


def test_list_filters_by_type_and_keeps_creation_order(session):
    project = _project(session)
    world_service.create_entry(session, project.id, type="place", name="甲")
    world_service.create_entry(session, project.id, type="faction", name="乙")
    world_service.create_entry(session, project.id, type="place", name="丙")

    places = world_service.list_entries(session, project.id, type="place")

    assert [e.name for e in places] == ["甲", "丙"]


def test_update_and_delete(session):
    project = _project(session)
    entry = world_service.create_entry(session, project.id, type="item", name="旧名")

    updated = world_service.update_entry(
        session, entry.id, name="新名", aliases=["别名一"], tags=["道具"]
    )
    assert updated.name == "新名"
    assert updated.aliases_json == ["别名一"]
    assert updated.tags_json == ["道具"]

    world_service.delete_entry(session, entry.id)
    assert session.scalars(select(SettingEntry)).all() == []


def test_update_unknown_entry_raises(session):
    with pytest.raises(ValueError):
        world_service.update_entry(session, "nope", name="X")


def test_type_change_re_normalizes(session):
    """改成规则类时，类型与硬度两个字段都要走归一化。

    注意必须改成 **rule**：硬度只在规则类条目上有意义（spec §2.1），
    拿 faction 去断言 hardness 保留，与那条不变量冲突。
    """
    project = _project(session)
    entry = world_service.create_entry(session, project.id, type="place", name="某地")

    updated = world_service.update_entry(session, entry.id, type="规则体系", hardness="软规则")

    assert updated.type == "rule"
    assert updated.hardness == "soft"


def test_changing_away_from_rule_clears_hardness(session):
    """不变量在 update 路径上同样成立：一条规则改成「势力」就不再带硬度。"""
    project = _project(session)
    entry = world_service.create_entry(
        session, project.id, type="rule", name="死者不能复活", hardness="hard"
    )
    assert entry.hardness == "hard"

    updated = world_service.update_entry(session, entry.id, type="势力")

    assert updated.type == "faction"
    assert updated.hardness is None
