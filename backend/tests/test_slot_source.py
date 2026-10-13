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
