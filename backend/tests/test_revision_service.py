"""修订建议：槽位、预置与任务类型（Task 1）。

这些用例先跑红、再实现：新槽位没注册时上下文组装会整段跳过，
新任务类型没登记时 `find_by_task_type` 找不到智能体。
"""

import pytest

from app.db.models import Architecture, Project


@pytest.fixture()
def project(session):
    """一个带故事圣经的项目，并预置默认阵容。

    `seed_agents` 不随 `session` fixture 自动执行，而本文件的用例都要找
    「修订建议师」；故事圣经则是因为提示词引用了 `{{ story_bible }}`，
    结构化预置缺变量会让渲染整段失败（`allow_missing` 默认关）。
    """
    from app.services.seed_service import seed_agents

    seed_agents(session)
    project = Project(name="雾港", genre="悬疑")
    session.add(project)
    session.flush()
    session.add(
        Architecture(
            project_id=project.id,
            logline="一个替妹妹赎罪的兄长在雾港寻找失踪的船主。",
        )
    )
    session.commit()
    return project


def test_impact_slots_render_from_extra(session, project):
    """两个新槽位只在该次运行里由调用方显式传值，不进通用项目态投影。"""
    from app.services.runtime_service import RuntimeService
    from app.services import agent_service

    agent = agent_service.find_by_task_type(session, "revision_suggest")
    assert agent is not None
    _agent, _version, prepared = RuntimeService(session).prepare_context(
        project.id,
        agent.id,
        {
            "impact_target": "主角动机改为替妹妹赎罪",
            "impact_candidates": "1. 第1卷 第1章 场景2 · 目标：旧值",
        },
    )
    assert prepared.error is None
    assert "主角动机" in prepared.rendered_prompt
    assert "场景2" in prepared.rendered_prompt


def test_revision_agent_has_contract_and_slots(session, project):
    """预置卡的身份、槽位与输出契约。"""
    from app.db.models.agent import AgentVersion
    from app.services import agent_service

    agent = agent_service.find_by_task_type(session, "revision_suggest")
    assert agent is not None
    assert agent.task_type == "revision_suggest"
    assert agent.preset_key == "revision-advisor"

    version = session.get(AgentVersion, agent.current_version_id)
    assert version is not None
    assert version.context_slots_json == [
        "project_core",
        "story_bible",
        "impact_target",
        "impact_candidates",
    ]

    schema = version.output_schema_json
    assert set(schema["properties"]) == {"suggestions", "open_questions"}
    assert schema["required"] == ["suggestions"]
    item = schema["properties"]["suggestions"]["items"]
    assert set(item["required"]) == {"target_label", "field", "after", "reason"}
    assert schema["properties"]["open_questions"]["type"] == "array"


def test_revision_prompt_asks_for_reasons_in_chinese(session, project):
    """提示词护栏：条数上限、四个可改字段、不编造对象名，且不手写英文键。"""
    from app.db.models.agent import AgentVersion
    from app.services import agent_service

    agent = agent_service.find_by_task_type(session, "revision_suggest")
    version = session.get(AgentVersion, agent.current_version_id)
    prompt = version.system_prompt

    assert "12" in prompt
    for word in ("目标", "冲突", "转折", "摘要"):
        assert word in prompt
    assert "编造" in prompt
    assert "{{ impact_target }}" in prompt
    assert "{{ impact_candidates }}" in prompt


def test_db_slot_source_forwards_only_non_private_names(session, project):
    """`__getattr__` 通用转发：空值给 None，下划线开头照旧报 AttributeError。"""
    from app.services.slot_source import DbSlotSource

    source = DbSlotSource(
        session,
        project.id,
        extra_slots={"impact_target": "主角动机改为替妹妹赎罪"},
    )
    assert source.impact_target() == "主角动机改为替妹妹赎罪"
    # 没传的槽位返回 None，而不是抛错：上下文组装据此当空槽位跳过。
    assert source.impact_candidates() is None
    with pytest.raises(AttributeError):
        source._no_such_internal_attribute
