import httpx
import pytest

from app.db.models import Agent, AgentVersion, GenerationRun, Idea, Project, Provider
from app.runtime.llm import HttpxChatClient
from app.services.runtime_service import RuntimeService

ANALYSIS_SCHEMA = {
    "type": "object",
    "required": ["genre"],
    "properties": {"genre": {"type": "string"}},
}


def _ok_handler(content='{"genre": "悬疑"}'):
    def handler(request):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 40, "completion_tokens": 20},
            },
        )

    return handler


def _seed(session, client_handler=None):
    project = Project(name="验尸官")
    session.add(project)
    provider = Provider(name="测试服务商", base_url="https://api.example.com/v1", api_key_ref="")
    session.add(provider)
    session.commit()
    agent = Agent(name="灵感解析", task_type="idea_parse")
    session.add(agent)
    session.commit()
    version = AgentVersion(
        agent_id=agent.id,
        version_no=1,
        system_prompt="解析这段灵感：{{ raw_idea }}",
        context_slots_json=["raw_idea"],
        output_schema_json=ANALYSIS_SCHEMA,
    )
    session.add(version)
    session.commit()
    agent.current_version_id = version.id
    session.add(Idea(project_id=project.id, raw_text="能听见死者遗言的验尸官"))
    session.commit()
    return project, provider, agent, version


def test_execute_writes_generation_run(session):
    project, provider, agent, version = _seed(session)
    service = RuntimeService(session, client=HttpxChatClient(transport=httpx.MockTransport(_ok_handler())))

    run, result = service.execute(project.id, agent.id)

    assert result.status == "ok"
    stored = session.get(GenerationRun, run.id)
    assert stored.rendered_prompt == "解析这段灵感：能听见死者遗言的验尸官"
    assert stored.raw_output == '{"genre": "悬疑"}'
    assert stored.parsed_json == {"genre": "悬疑"}
    assert stored.structured is True
    assert stored.prompt_tokens == 40
    assert stored.agent_version_id == version.id
    assert stored.model  # 落库时记下实际模型


def test_execute_uses_agent_current_version(session):
    project, provider, agent, version = _seed(session)
    service = RuntimeService(session, client=HttpxChatClient(transport=httpx.MockTransport(_ok_handler())))
    run, _ = service.execute(project.id, agent.id)
    assert session.get(GenerationRun, run.id).agent_version_id == agent.current_version_id


def test_execute_records_provider_error_without_raising(session):
    project, provider, agent, version = _seed(session)

    def handler(request):
        return httpx.Response(500, json={"error": {"message": "内部错误"}})

    service = RuntimeService(session, client=HttpxChatClient(transport=httpx.MockTransport(handler)))
    run, result = service.execute(project.id, agent.id)

    assert result.status == "error"
    assert session.get(GenerationRun, run.id).status == "error"


def test_execute_raises_when_agent_has_no_version(session):
    project, provider, agent, version = _seed(session)
    agent.current_version_id = None
    session.commit()
    service = RuntimeService(session, client=HttpxChatClient(transport=httpx.MockTransport(_ok_handler())))
    with pytest.raises(ValueError, match="没有可用版本"):
        service.execute(project.id, agent.id)


def test_execute_raises_when_no_provider_configured(session):
    project, provider, agent, version = _seed(session)
    session.query(Provider).delete()
    session.commit()
    service = RuntimeService(session, client=HttpxChatClient(transport=httpx.MockTransport(_ok_handler())))
    with pytest.raises(ValueError, match="没有可用的服务商"):
        service.execute(project.id, agent.id)
