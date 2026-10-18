from app.agents.roster import DEFAULT_ROSTER
from app.db.models import Agent, AgentVersion, ToolTemplate
from app.services import preset_service
from app.services.seed_service import seed_agents, seed_tools


def test_seed_agents_creates_roster_with_versions(session):
    count = seed_agents(session)
    assert count >= 2
    agent = session.query(Agent).filter_by(name="架构师").one()
    assert agent.current_version_id is not None
    version = session.get(AgentVersion, agent.current_version_id)
    assert "不替作者决定" in version.system_prompt


def test_seed_agents_is_idempotent(session):
    first = seed_agents(session)
    second = seed_agents(session)
    assert second == 0
    assert session.query(Agent).filter_by(name="架构师").count() == 1


def _legacy_agent(session, preset, prompt: str | None = None):
    agent = Agent(
        name=preset["name"],
        role_label=preset["role_label"],
        color=preset["color"],
        task_type=preset["task_type"],
        builtin=True,
    )
    session.add(agent)
    session.flush()
    version = AgentVersion(
        agent_id=agent.id,
        version_no=1,
        system_prompt=prompt if prompt is not None else preset["system_prompt"],
        context_slots_json=preset["context_slots"],
        output_schema_json=preset["output_schema"],
        param_profile=preset["param_profile"],
        trigger_mode=preset.get("trigger_mode", "manual"),
        note=preset.get("note", ""),
    )
    session.add(version)
    session.flush()
    agent.current_version_id = version.id
    session.commit()
    return agent, version


def test_seed_claims_legacy_agents_and_backfills_fingerprints(session):
    preset = DEFAULT_ROSTER[0]
    agent, version = _legacy_agent(session, preset)

    seed_agents(session)

    session.refresh(agent)
    session.refresh(version)
    assert agent.preset_key == preset["key"]
    assert version.preset_fingerprint == preset_service.fingerprint_for_preset(preset)
    assert session.query(AgentVersion).filter_by(agent_id=agent.id).count() == 1


def test_seed_does_not_backfill_an_edited_version(session):
    preset = DEFAULT_ROSTER[0]
    agent, version = _legacy_agent(session, preset, prompt="作者改过的提示词")

    seed_agents(session)

    session.refresh(version)
    assert agent.preset_key == preset["key"]
    assert version.preset_fingerprint is None


def test_seed_claims_a_renamed_agent_by_task_type(session):
    preset = DEFAULT_ROSTER[0]
    agent, _version = _legacy_agent(session, preset)
    agent.name = "我的解析师"
    session.commit()

    seed_agents(session)

    same_task = session.query(Agent).filter_by(task_type=preset["task_type"]).all()
    assert len(same_task) == 1
    assert same_task[0].preset_key == preset["key"]


def test_seed_does_not_create_when_claiming_is_ambiguous(session):
    preset = DEFAULT_ROSTER[0]
    for name in ("甲", "乙"):
        session.add(Agent(name=name, task_type=preset["task_type"], builtin=True))
    session.commit()

    seed_agents(session)

    assert session.query(Agent).filter_by(task_type=preset["task_type"]).count() == 2


def test_seed_creates_the_writer_agent(session):
    seed_agents(session)
    writer = session.query(Agent).filter_by(task_type="write").one()
    assert writer.name == "执笔"
    version = session.get(AgentVersion, writer.current_version_id)
    assert version.output_schema_json is None
    assert "scene_card" in version.context_slots_json


def test_seed_tools_loads_builtin_library(session):
    count = seed_tools(session)
    assert count > 0
    keys = {t.key for t in session.query(ToolTemplate).all()}
    assert "three_act" in keys
    assert "save_the_cat" in keys


def test_seed_tools_is_idempotent(session):
    seed_tools(session)
    assert seed_tools(session) == 0


def test_every_seeded_tool_has_a_checklist(session):
    seed_tools(session)
    for tool in session.query(ToolTemplate).all():
        assert tool.checklist_json, f"{tool.key} 缺少校验问题清单"
