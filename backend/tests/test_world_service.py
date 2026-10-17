import pytest
from sqlalchemy import select

from app.db.models import Project, SettingEntry
from app.db.session import SessionLocal
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


def test_update_rejects_a_blank_name(session):
    """与 create 对称：纯空白的名字是从 Pydantic 的 min_length=1 漏过来的。"""
    project = _project(session)
    entry = world_service.create_entry(session, project.id, type="place", name="雾港旧城")

    with pytest.raises(ValueError):
        world_service.update_entry(session, entry.id, name="   ")

    assert world_service.get_entry(session, entry.id).name == "雾港旧城"


def test_update_duplicate_name_reports_the_name_the_author_typed(session):
    """报错里的名字必须是作者刚填的那个。

    rollback 会让实例 expire，若在 rollback 之后才读 entry.name，拿到的是
    改动前的旧名字 —— 于是消息会指着正在编辑的那条说「已经有叫它的条目了」。
    """
    project = _project(session)
    world_service.create_entry(session, project.id, type="place", name="甲")
    target = world_service.create_entry(session, project.id, type="place", name="乙")

    with pytest.raises(ValueError) as excinfo:
        world_service.update_entry(session, target.id, name="甲")

    assert "甲" in str(excinfo.value)


def test_create_relation_between_two_entries(session):
    project = _project(session)
    a = world_service.create_entry(session, project.id, type="faction", name="记忆交易局")
    b = world_service.create_entry(session, project.id, type="place", name="雾港旧城")

    relation = world_service.create_relation(
        session, project.id, from_id=a.id, to_id=b.id, kind="位于", note="总部"
    )

    assert relation.kind == "位于"
    assert relation.note == "总部"
    assert [r.id for r in world_service.list_relations(session, project.id)] == [relation.id]


def test_relation_rejects_unknown_or_cross_project_entries(session):
    project = _project(session)
    other = Project(name="另一本")
    session.add(other)
    session.commit()
    a = world_service.create_entry(session, project.id, type="faction", name="甲")
    outside = world_service.create_entry(session, other.id, type="place", name="境外")

    with pytest.raises(ValueError):
        world_service.create_relation(
            session, project.id, from_id=a.id, to_id="nope", kind="位于"
        )
    with pytest.raises(ValueError):
        world_service.create_relation(
            session, project.id, from_id=a.id, to_id=outside.id, kind="位于"
        )


def test_relation_requires_a_kind(session):
    project = _project(session)
    a = world_service.create_entry(session, project.id, type="faction", name="甲")
    b = world_service.create_entry(session, project.id, type="place", name="乙")
    with pytest.raises(ValueError):
        world_service.create_relation(session, project.id, from_id=a.id, to_id=b.id, kind="  ")


def test_relation_ignores_unknown_fields(session):
    """路由用 **model_dump() 展开，下一切片给这张表加列时不能当场崩。"""
    project = _project(session)
    a = world_service.create_entry(session, project.id, type="faction", name="甲")
    b = world_service.create_entry(session, project.id, type="place", name="乙")

    relation = world_service.create_relation(
        session, project.id, from_id=a.id, to_id=b.id, kind="位于", 未来的列="x"
    )

    assert relation.kind == "位于"


def test_delete_relation(session):
    project = _project(session)
    a = world_service.create_entry(session, project.id, type="faction", name="甲")
    b = world_service.create_entry(session, project.id, type="place", name="乙")
    relation = world_service.create_relation(
        session, project.id, from_id=a.id, to_id=b.id, kind="位于"
    )

    world_service.delete_relation(session, relation.id)

    assert world_service.list_relations(session, project.id) == []
    with pytest.raises(ValueError):
        world_service.delete_relation(session, relation.id)


def test_terms_project_every_name_and_alias(session):
    project = _project(session)
    entry = world_service.create_entry(
        session,
        project.id,
        type="faction",
        name="记忆交易局",
        aliases=["交易局", "管理局"],
    )
    world_service.create_entry(session, project.id, type="term", name="一息")

    terms = world_service.list_terms(session, project.id)

    by_form = {t["form"]: t for t in terms}
    assert set(by_form) == {"记忆交易局", "交易局", "管理局", "一息"}
    assert by_form["记忆交易局"]["is_primary"] is True
    assert by_form["交易局"]["is_primary"] is False
    # 每一行都指回它的来源条目，作者才知道该去哪改
    assert by_form["交易局"]["entry_id"] == entry.id
    assert by_form["交易局"]["entry_name"] == "记忆交易局"


def test_terms_are_empty_for_an_empty_project(session):
    project = _project(session)
    assert world_service.list_terms(session, project.id) == []


def test_terms_do_not_leak_across_projects(session):
    a = _project(session)
    other = Project(name="另一本")
    session.add(other)
    session.commit()
    world_service.create_entry(session, other.id, type="place", name="别处")

    assert world_service.list_terms(session, a.id) == []


def test_character_fields_round_trip(session):
    """八项走一趟真数据库、换个 session 再读回来。

    不能只用 `session` 读：`SessionLocal` 是 `expire_on_commit=False`，同一个
    session 里 `get_entry` 返回的就是刚写的那个 identity-mapped 对象，读到的
    仍是内存里的值 —— 此时列名即使拼错（`setattr` 落在一个没有映射的普通属性
    上，不报错也不落库），断言照样能过。这种「什么都不验」的往返测试比没有测试
    更危险：它顶着一个会走库的名字，实际上一次库都没查。
    `expire_all()` 也挡不住 —— 普通属性不在 SQLAlchemy 的映射管理范围内、过期
    不会清掉它（两种写法都实测过）。只有换一个 session，取值才必须回库里拿。
    判别力已实测：把任一被断言的列名改错，这条测试就变红（task-3-report §4）。
    """
    project = _project(session)

    entry = world_service.create_entry(
        session,
        project.id,
        type="人物",  # 中文名，顺便验归一化
        name="陈默",
        aliases=["阿默", "老陈"],
        appearance="瘦高，左眉有疤",
        personality="寡言，认死理",
        desire="找回被抹去的记忆",
        fear="想起自己做过的事",
        arc_type="幻灭",
        abilities="能读取他人记忆，但每读一次忘掉自己一件事",
        speech_style="「你先说。」「不必。」",
        current_state="暂居南滨，身份未暴露",
    )

    assert entry.type == "character"
    with SessionLocal() as fresh:
        again = world_service.get_entry(fresh, entry.id)
        assert again.appearance == "瘦高，左眉有疤"
        assert again.arc_type == "幻灭"
        assert again.speech_style == "「你先说。」「不必。」"
        assert again.current_state == "暂居南滨，身份未暴露"


def test_character_fields_survive_a_type_change_but_hardness_does_not(session):
    """人物八项在类型改变时**保留**（长文本误删太重）；hardness 仍按老规矩清空。"""
    project = _project(session)

    character = world_service.create_entry(
        session, project.id, type="人物", name="陈默", appearance="瘦高"
    )
    updated = world_service.update_entry(session, character.id, type="势力")

    assert updated.type == "faction"
    assert updated.appearance == "瘦高"

    rule = world_service.create_entry(
        session, project.id, type="规则体系", name="记忆不可复活", hardness="硬规则"
    )
    changed = world_service.update_entry(session, rule.id, type="势力")

    assert changed.hardness is None
