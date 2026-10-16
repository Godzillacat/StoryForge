import pytest

from app.db.models import Agent, AgentVersion
from app.services import agent_service


def _make_agent(session, prompt: str = "v1 提示词") -> Agent:
    agent = Agent(name="测试智能体", role_label="测试", task_type="idea_parse")
    session.add(agent)
    session.flush()
    version = AgentVersion(
        agent_id=agent.id,
        version_no=1,
        system_prompt=prompt,
        context_slots_json=["raw_idea"],
        model_binding_json={"model": "m1"},
    )
    session.add(version)
    session.flush()
    agent.current_version_id = version.id
    session.commit()
    return agent


def test_new_version_after_rollback_inherits_the_current_version(session):
    """回滚之后，「当前版本」不再是版本号最大的那个。

    取最大版本号会把作者刚弃用的内容悄悄带回来 —— 而「回滚到好版本，
    基于它改一改再保存」正是作者最自然的操作路径。
    """
    agent = _make_agent(session, prompt="v1 正确提示词")

    v2 = agent_service.create_version(session, agent.id, system_prompt="v2 测试串")
    assert v2.version_no == 2

    agent_service.rollback_to(session, agent.id, agent.current_version_id)  # 无副作用
    v1 = [v for v in agent_service.list_versions(session, agent.id) if v.version_no == 1][0]
    agent_service.rollback_to(session, agent.id, v1.id)

    v3 = agent_service.create_version(session, agent.id, note="只改了备注")

    assert v3.version_no == 3
    assert v3.system_prompt == "v1 正确提示词"
    assert v3.model_binding_json == {"model": "m1"}
    assert v3.context_slots_json == ["raw_idea"]


def test_explicit_fields_still_win_over_inheritance(session):
    agent = _make_agent(session)
    v2 = agent_service.create_version(session, agent.id, system_prompt="全新的")
    assert v2.system_prompt == "全新的"
    assert v2.model_binding_json == {"model": "m1"}  # 未显式给的字段仍继承


def test_first_version_of_an_empty_agent(session):
    agent = Agent(name="空智能体", task_type="idea_parse")
    session.add(agent)
    session.commit()

    v1 = agent_service.create_version(session, agent.id, system_prompt="首版")
    assert v1.version_no == 1
    assert v1.system_prompt == "首版"
    assert v1.param_profile == "balanced"
