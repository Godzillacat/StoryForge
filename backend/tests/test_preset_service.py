import pytest

from app.agents.roster import DEFAULT_ROSTER
from app.db.models import Agent, AgentVersion
from app.services import preset_service

PRESET = DEFAULT_ROSTER[0]


def _agent_with_version(session, prompt: str | None = None, fingerprint: str | None = None):
    agent = Agent(
        name=PRESET["name"],
        role_label=PRESET["role_label"],
        color=PRESET["color"],
        task_type=PRESET["task_type"],
        builtin=True,
        preset_key=PRESET["key"],
    )
    session.add(agent)
    session.flush()
    version = AgentVersion(
        agent_id=agent.id,
        version_no=1,
        system_prompt=prompt if prompt is not None else PRESET["system_prompt"],
        context_slots_json=PRESET["context_slots"],
        output_schema_json=PRESET["output_schema"],
        param_profile=PRESET["param_profile"],
        trigger_mode=PRESET.get("trigger_mode", "manual"),
        model_binding_json={"model": "作者的模型"},
        preset_fingerprint=fingerprint,
    )
    session.add(version)
    session.flush()
    agent.current_version_id = version.id
    session.commit()
    return agent, version


def test_fingerprint_ignores_model_binding_and_note(session):
    agent, version = _agent_with_version(session)
    version.model_binding_json = {"model": "另一个"}
    version.note = "注释不同"
    session.commit()

    assert preset_service.fingerprint_for_version(version) == preset_service.fingerprint_for_preset(
        PRESET
    )


def test_status_for_up_to_date(session):
    preset_fp = preset_service.fingerprint_for_preset(PRESET)
    agent, version = _agent_with_version(session, fingerprint=preset_fp)

    status = preset_service.status_for(agent, version)

    assert status == {
        "key": PRESET["key"],
        "update_available": False,
        "can_restore": False,
        "up_to_date": True,
    }


def test_status_for_a_legacy_version_without_fingerprint(session):
    agent, version = _agent_with_version(session, fingerprint=None)

    status = preset_service.status_for(agent, version)

    assert status["update_available"] is False
    assert status["can_restore"] is True
    assert status["up_to_date"] is False


def test_status_for_a_modified_preset_version(session):
    agent, version = _agent_with_version(session, fingerprint="旧指纹")

    status = preset_service.status_for(agent, version)

    assert status["update_available"] is True
    assert status["can_restore"] is True


def test_apply_preset_creates_a_new_version_and_preserves_model_binding(session):
    agent, old = _agent_with_version(session, fingerprint="旧指纹")

    new = preset_service.apply_preset(session, agent)

    assert new.version_no == 2
    assert new.system_prompt == PRESET["system_prompt"]
    assert new.preset_fingerprint == preset_service.fingerprint_for_preset(PRESET)
    assert new.model_binding_json == {"model": "作者的模型"}
    assert agent.current_version_id == new.id
    assert session.get(AgentVersion, old.id) is not None


def test_apply_preset_rejects_when_already_up_to_date(session):
    preset_fp = preset_service.fingerprint_for_preset(PRESET)
    agent, _version = _agent_with_version(session, fingerprint=preset_fp)

    with pytest.raises(ValueError, match="已是最新"):
        preset_service.apply_preset(session, agent)


def test_apply_preset_rejects_an_agent_without_preset(session):
    agent = Agent(name="自定义", task_type="idea_parse")
    session.add(agent)
    session.commit()

    with pytest.raises(ValueError, match="没有可用的预置"):
        preset_service.apply_preset(session, agent)
