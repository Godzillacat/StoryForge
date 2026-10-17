import pytest

from app.db.models import Project, SettingEntry, TimelineEvent
from app.db.session import SessionLocal
from app.services import timeline_service, world_service


def _project(session) -> Project:
    project = Project(name="雾港")
    session.add(project)
    session.commit()
    return project


def _entry(session, project, type_: str, name: str) -> SettingEntry:
    return world_service.create_entry(session, project.id, type=type_, name=name)


def test_create_appends_in_order(session):
    project = _project(session)
    timeline_service.create_event(session, project.id, title="第一")
    timeline_service.create_event(session, project.id, title="第二")
    timeline_service.create_event(session, project.id, title="第三")

    events = timeline_service.list_events(session, project.id)

    assert [e.title for e in events] == ["第一", "第二", "第三"]
    assert [e.order_index for e in events] == [0, 1, 2]


def test_move_up_and_down_reorders(session):
    project = _project(session)
    first = timeline_service.create_event(session, project.id, title="第一")
    second = timeline_service.create_event(session, project.id, title="第二")
    third = timeline_service.create_event(session, project.id, title="第三")

    timeline_service.move_event(session, third.id, "up")
    assert [e.title for e in timeline_service.list_events(session, project.id)] == [
        "第一",
        "第三",
        "第二",
    ]

    timeline_service.move_event(session, first.id, "down")
    assert [e.title for e in timeline_service.list_events(session, project.id)] == [
        "第三",
        "第一",
        "第二",
    ]
    assert [e.order_index for e in timeline_service.list_events(session, project.id)] == [0, 1, 2]


def test_move_at_boundary_is_a_no_op(session):
    project = _project(session)
    first = timeline_service.create_event(session, project.id, title="第一")
    timeline_service.create_event(session, project.id, title="第二")

    timeline_service.move_event(session, first.id, "up")

    assert [e.title for e in timeline_service.list_events(session, project.id)] == ["第一", "第二"]


def test_participants_must_be_characters_in_the_same_project(session):
    project = _project(session)
    other = Project(name="另一本")
    session.add(other)
    session.commit()
    place = _entry(session, project, "place", "南滨")
    outsider = _entry(session, other, "character", "外人")

    with pytest.raises(ValueError, match="不是人物"):
        timeline_service.create_event(
            session, project.id, title="事件", participants=[place.id]
        )
    with pytest.raises(ValueError, match="不属于这个项目"):
        timeline_service.create_event(
            session, project.id, title="事件", participants=[outsider.id]
        )
    with pytest.raises(ValueError, match="不存在"):
        timeline_service.create_event(
            session, project.id, title="事件", participants=["nope"]
        )


def test_participants_are_deduped(session):
    project = _project(session)
    character = _entry(session, project, "character", "陈默")

    event = timeline_service.create_event(
        session, project.id, title="事件", participants=[character.id, character.id]
    )

    assert event.participants_json == [character.id]


def test_location_must_exist_in_the_same_project(session):
    project = _project(session)
    other = Project(name="另一本")
    session.add(other)
    session.commit()
    outsider = _entry(session, other, "place", "境外")

    with pytest.raises(ValueError, match="不属于这个项目"):
        timeline_service.create_event(
            session, project.id, title="事件", location_id=outsider.id
        )
    with pytest.raises(ValueError, match="不存在"):
        timeline_service.create_event(session, project.id, title="事件", location_id="nope")


def test_update_fields_and_clear_location(session):
    project = _project(session)
    place = _entry(session, project, "place", "南滨")
    character = _entry(session, project, "character", "陈默")
    event = timeline_service.create_event(
        session,
        project.id,
        title="初遇",
        story_time="第三年·春",
        location_id=place.id,
        participants=[character.id],
    )

    updated = timeline_service.update_event(
        session,
        event.id,
        title="初遇（改）",
        story_time="第三年·夏",
        description="改了",
        location_id=None,
        participants=[],
    )

    assert updated.title == "初遇（改）"
    assert updated.story_time == "第三年·夏"
    assert updated.description == "改了"
    assert updated.location_id is None
    assert updated.participants_json == []


def test_failed_update_leaves_the_event_untouched(session):
    """校验失败时对象必须原样不动 —— 先验完所有值，再落到对象上。

    若边验边改，`title` 已经写进内存里的那条，接着参与者校验失败抛错。
    HTTP 路径靠请求结束时 `session.close()` 的回滚躲过一劫，但服务层是被
    直接调用的公共面：调用方捕获异常后若继续用这个 session，下一次提交就会
    把半截改动落库 —— 这里显式补一次 `session.commit()` 来模拟那个调用方。
    """
    project = _project(session)
    place = _entry(session, project, "place", "南滨")
    event = timeline_service.create_event(
        session, project.id, title="初遇", story_time="第三年·春"
    )

    with pytest.raises(ValueError, match="不是人物"):
        timeline_service.update_event(
            session, event.id, title="改", participants=[place.id]
        )

    # 内存里的对象在失败时也必须保持原样
    assert event.title == "初遇"

    # 模拟「调用方捕获异常后继续使用同一个 session」：提交一次再换 session 回库读
    session.commit()
    with SessionLocal() as fresh:
        again = fresh.get(TimelineEvent, event.id)
        assert again.title == "初遇"
        assert again.story_time == "第三年·春"


def test_delete_entry_removes_it_from_participants_and_clears_location(session):
    project = _project(session)
    character = _entry(session, project, "character", "陈默")
    place = _entry(session, project, "place", "南滨")
    event = timeline_service.create_event(
        session,
        project.id,
        title="初遇",
        participants=[character.id],
        location_id=place.id,
    )

    world_service.delete_entry(session, character.id)
    with SessionLocal() as fresh:
        assert fresh.get(TimelineEvent, event.id).participants_json == []

    world_service.delete_entry(session, place.id)
    with SessionLocal() as fresh:
        assert fresh.get(TimelineEvent, event.id).location_id is None


def test_events_do_not_leak_across_projects(session):
    a = _project(session)
    b = Project(name="另一本")
    session.add(b)
    session.commit()
    timeline_service.create_event(session, b.id, title="别处")

    assert timeline_service.list_events(session, a.id) == []


def test_delete_event(session):
    project = _project(session)
    event = timeline_service.create_event(session, project.id, title="甲")

    timeline_service.delete_event(session, event.id)

    assert timeline_service.list_events(session, project.id) == []
    with pytest.raises(ValueError):
        timeline_service.delete_event(session, event.id)
