from app.db.models import Act, Architecture, Idea, Project, ToolTemplate
from app.services.slot_source import DbSlotSource


def _seed(session):
    project = Project(name="验尸官", genre="悬疑", tone="冷峻")
    session.add(project)
    session.commit()
    session.add(Idea(project_id=project.id, raw_text="能听见死者遗言的验尸官"))
    arch = Architecture(
        project_id=project.id, tool_ref="three_act", logline="一个验尸官听见了母亲的话"
    )
    session.add(arch)
    session.commit()
    session.add(Act(architecture_id=arch.id, seq=1, name="第一幕", purpose="建立禁令世界"))
    session.add(ToolTemplate(key="three_act", category="通用结构", name="三幕剧"))
    session.commit()
    return project


def test_raw_idea_returns_author_original(session):
    project = _seed(session)
    source = DbSlotSource(session, project.id)
    assert source.raw_idea() == "能听见死者遗言的验尸官"


def test_project_core_includes_name_and_genre(session):
    project = _seed(session)
    source = DbSlotSource(session, project.id)
    core = source.project_core()
    assert "验尸官" in core and "悬疑" in core


def test_architecture_renders_act_skeleton(session):
    project = _seed(session)
    source = DbSlotSource(session, project.id)
    text = source.architecture()
    assert "three_act" in text
    assert "第一幕" in text


def test_story_bible_includes_logline(session):
    project = _seed(session)
    source = DbSlotSource(session, project.id)
    assert "听见了母亲的话" in source.story_bible()


def test_parsed_idea_is_none_before_parsing(session):
    project = _seed(session)
    source = DbSlotSource(session, project.id)
    assert source.parsed_idea() is None


def test_parsed_idea_returns_json_text_after_parsing(session):
    project = _seed(session)
    idea = session.query(Idea).filter_by(project_id=project.id).one()
    idea.parsed_json = {"genre": "悬疑", "open_questions": ["对手是谁"]}
    session.commit()
    text = DbSlotSource(session, project.id).parsed_idea()
    assert "悬疑" in text and "对手是谁" in text


def test_tool_library_empty_when_no_tools(session):
    project = _seed(session)
    source = DbSlotSource(session, project.id)
    assert "三幕剧" in source.tool_library()


def test_summarize_truncates_long_text(session):
    project = _seed(session)
    source = DbSlotSource(session, project.id)
    summarized = source.summarize("raw_idea", "字" * 300)
    assert len(summarized) < 300
    assert summarized.endswith("……")


def test_raw_idea_returns_the_requested_idea_not_the_oldest(session):
    project = _seed(session)
    first = session.query(Idea).filter_by(project_id=project.id).one()
    second = Idea(project_id=project.id, raw_text="第二个灵感：海边的灯塔看守人")
    session.add(second)
    session.commit()

    from app.services.slot_source import DbSlotSource

    source = DbSlotSource(session, project.id, extra_slots={"raw_idea_id": second.id})
    assert source.raw_idea() == "第二个灵感：海边的灯塔看守人"
    # 不传 extra_slots 时保持原行为（取最早一条），供其它槽位调用方使用
    assert DbSlotSource(session, project.id).raw_idea() == first.raw_text


def test_world_context_lists_entries_with_character_fields(session):
    project = _seed(session)
    from app.db.models import SettingEntry

    session.add(SettingEntry(project_id=project.id, type="character", name="陈默",
                             aliases_json=["阿默"], summary="主角",
                             desire="找回记忆", fear="想起自己做过的事",
                             current_state="暂居南滨"))
    session.add(SettingEntry(project_id=project.id, type="rule", name="死者不能复活",
                             hardness="hard", summary="体系根基"))
    session.commit()

    text = DbSlotSource(session, project.id).world_context()

    assert "陈默" in text and "阿默" in text
    assert "欲望" in text and "找回记忆" in text
    assert "硬规则" in text
    assert "死者不能复活" in text


def test_timeline_renders_events(session):
    project = _seed(session)
    from app.db.models import SettingEntry, TimelineEvent

    character = SettingEntry(project_id=project.id, type="character", name="陈默")
    session.add(character)
    session.commit()
    session.add(TimelineEvent(project_id=project.id, title="初遇", story_time="第三年·春",
                              participants_json=[character.id], description="录音带"))
    session.commit()

    text = DbSlotSource(session, project.id).timeline()

    assert "初遇" in text and "第三年·春" in text and "陈默" in text


def test_volume_and_chapter_outline_are_scoped(session):
    project = _seed(session)
    from app.services import chapter_service, scene_service

    volume = chapter_service.create_volume(session, project.id, name="第一卷", purpose="立目标")
    chapter = chapter_service.create_chapter(session, volume.id, title="第一章", pov="陈默")
    scene_service.create_scene(session, chapter.id, goal="找到录音带")

    volume_text = DbSlotSource(session, project.id, extra_slots={"volume_id": volume.id}).volume_outline()
    chapter_text = DbSlotSource(
        session, project.id, extra_slots={"chapter_id": chapter.id, "volume_id": volume.id}
    ).chapter_outline()

    assert "第一卷" in volume_text and "第一章" in volume_text
    assert "第一章" in chapter_text and "找到录音带" in chapter_text
    assert DbSlotSource(session, project.id).volume_outline() is None
    assert DbSlotSource(session, project.id).chapter_outline() is None
