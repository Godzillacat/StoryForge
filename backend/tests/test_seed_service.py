from app.db.models import Agent, AgentVersion, ToolTemplate
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
