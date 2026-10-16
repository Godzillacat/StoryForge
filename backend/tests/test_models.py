import pytest

from app.db.base import new_id
from app.db.models import Agent, AgentVersion, GenerationRun, Idea, Project


def test_new_id_is_unique_string():
    a, b = new_id(), new_id()
    assert isinstance(a, str) and len(a) == 36
    assert a != b


def test_project_roundtrip(session):
    project = Project(name="验尸官", genre="悬疑")
    session.add(project)
    session.commit()
    fetched = session.get(Project, project.id)
    assert fetched.name == "验尸官"
    assert fetched.logic_check_level == "loose"
    assert fetched.created_at is not None


def test_raw_idea_is_stored_separately_from_parsed(session):
    project = Project(name="p")
    session.add(project)
    session.commit()
    idea = Idea(project_id=project.id, raw_text="能听见死者遗言的验尸官", tags_json=["悬疑"])
    session.add(idea)
    session.commit()
    assert idea.raw_text == "能听见死者遗言的验尸官"
    assert idea.parsed_json is None
    idea.parsed_json = {"genre": "悬疑"}
    session.commit()
    assert idea.raw_text == "能听见死者遗言的验尸官"  # 解析不回写原文（D-04）


def test_agent_current_version_pointer(session):
    agent = Agent(name="架构师", task_type="architecture")
    session.add(agent)
    session.commit()
    version = AgentVersion(agent_id=agent.id, version_no=1, system_prompt="你是架构师")
    session.add(version)
    session.commit()
    agent.current_version_id = version.id
    session.commit()
    assert session.get(Agent, agent.id).current_version_id == version.id


def test_generation_run_stores_full_audit_trail(session):
    project = Project(name="p")
    session.add(project)
    session.commit()
    run = GenerationRun(
        project_id=project.id,
        model="test-model",
        rendered_prompt="渲染后的提示词",
        raw_output="原始返回",
        prompt_tokens=10,
        completion_tokens=20,
        cost_estimate=0.0014,
        status="ok",
    )
    session.add(run)
    session.commit()
    assert run.rendered_prompt == "渲染后的提示词"
    assert run.structured is False


def test_setting_entry_defaults_and_roundtrip(session):
    from app.db.models import SettingEntry

    project = Project(name="雾港")
    session.add(project)
    session.commit()

    entry = SettingEntry(project_id=project.id, type="faction", name="记忆交易局")
    session.add(entry)
    session.commit()

    stored = session.get(SettingEntry, entry.id)
    assert stored.aliases_json == []
    assert stored.tags_json == []
    assert stored.summary == ""
    assert stored.hardness is None
    assert stored.source_run_id is None


def test_entry_name_is_unique_within_a_project(session):
    from sqlalchemy.exc import IntegrityError

    from app.db.models import SettingEntry

    project = Project(name="雾港")
    other = Project(name="另一本")
    session.add_all([project, other])
    session.commit()

    session.add(SettingEntry(project_id=project.id, type="place", name="雾港旧城"))
    session.add(SettingEntry(project_id=other.id, type="place", name="雾港旧城"))
    session.commit()  # 跨项目同名是合法的

    session.add(SettingEntry(project_id=project.id, type="faction", name="雾港旧城"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_deleting_an_entry_removes_its_relations(session):
    from sqlalchemy import select

    from app.db.models import EntryRelation, SettingEntry

    project = Project(name="雾港")
    session.add(project)
    session.commit()
    a = SettingEntry(project_id=project.id, type="faction", name="甲")
    b = SettingEntry(project_id=project.id, type="place", name="乙")
    session.add_all([a, b])
    session.commit()
    session.add(EntryRelation(project_id=project.id, from_id=a.id, to_id=b.id, kind="位于"))
    session.commit()

    session.delete(a)
    session.commit()

    remaining = session.scalars(select(EntryRelation)).all()
    assert remaining == []


def test_relation_is_directional(session):
    from sqlalchemy import select

    from app.db.models import EntryRelation, SettingEntry

    project = Project(name="雾港")
    session.add(project)
    session.commit()
    a = SettingEntry(project_id=project.id, type="faction", name="甲")
    b = SettingEntry(project_id=project.id, type="place", name="乙")
    session.add_all([a, b])
    session.commit()
    session.add(EntryRelation(project_id=project.id, from_id=a.id, to_id=b.id, kind="位于"))
    session.commit()

    forward = session.scalars(select(EntryRelation).where(EntryRelation.from_id == a.id)).all()
    backward = session.scalars(select(EntryRelation).where(EntryRelation.from_id == b.id)).all()
    assert len(forward) == 1
    assert backward == []
