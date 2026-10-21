import time

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
        # 运行的前置条件：没有绑定模型的智能体在解析阶段就会被拦下，
        # 不再回落到服务商的显示名。
        model_binding_json={"model": "test-model"},
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
    assert stored.rendered_prompt.startswith("解析这段灵感：能听见死者遗言的验尸官")
    assert "【输出契约】" in stored.rendered_prompt
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


def test_execute_persists_parse_error_reason(session):
    project, provider, agent, version = _seed(session)
    # 返回合法 JSON，但缺少必填的 genre，触发契约校验失败
    service = RuntimeService(
        session,
        client=HttpxChatClient(
            transport=httpx.MockTransport(_ok_handler('{"not_genre": 1}'))
        ),
    )

    run, result = service.execute(project.id, agent.id)

    assert result.structured is False
    assert result.parse_error is not None
    stored = session.get(GenerationRun, run.id)
    assert stored.structured is False
    assert stored.parse_error == result.parse_error
    assert "genre" in stored.parse_error


def test_timeout_falls_back_to_global_setting(session, monkeypatch):
    from app import config
    from app.services.runtime_service import RuntimeService

    config.save_settings({"request_timeout_seconds": 456})
    service = RuntimeService(session)
    assert service._resolve_timeout({}) == 456.0


def test_agent_level_timeout_wins(session):
    from app.services.runtime_service import RuntimeService

    service = RuntimeService(session)
    assert service._resolve_timeout({"timeout_seconds": 90}) == 90.0


def test_unbound_model_fails_with_a_readable_reason(session):
    """没绑模型时必须报错，不能把服务商显示名当模型 ID 发出去。

    这条路径不联网：模型解析在调用客户端之前完成。
    """
    project, _provider, agent, version = _seed(session)
    version.model_binding_json = {}
    session.commit()

    service = RuntimeService(session)

    with pytest.raises(ValueError) as excinfo:
        service.execute(project.id, agent.id)

    assert "绑定模型" in str(excinfo.value)


def test_prepare_returns_rendered_prompt_and_trimmed(session):
    project, _provider, agent, _version = _seed(session)
    prepared = RuntimeService(session).prepare(project.id, agent.id)

    assert "能听见死者遗言的验尸官" in prepared.prompt.rendered_prompt
    assert prepared.model == "test-model"
    assert prepared.prompt.messages == [
        {"role": "user", "content": prepared.prompt.rendered_prompt}
    ]
    assert prepared.prompt.trimmed == {}


def test_prepare_records_missing_variable_without_raising(session):
    project, _provider, agent, version = _seed(session)
    version.system_prompt = "缺少：{{ world_context }}"
    version.context_slots_json = ["raw_idea"]
    session.commit()

    prepared = RuntimeService(session).prepare(project.id, agent.id)

    assert prepared.prompt.error["kind"] == "template"
    assert "world_context" in prepared.prompt.error["message"]
    assert prepared.prompt.rendered_prompt == ""


def test_prepare_allows_missing_slots_only_when_requested(session):
    """审校预置显式放开空槽位；其它结构化预置仍保持严格，拼错变量照样报错。"""
    project, _provider, agent, version = _seed(session)
    version.system_prompt = "缺少：{{ world_context }}"
    version.context_slots_json = ["raw_idea"]
    session.commit()

    prepared = RuntimeService(session).prepare(
        project.id, agent.id, allow_missing=True
    )
    assert prepared.prompt.error is None
    assert prepared.prompt.rendered_prompt.startswith("缺少：")

    strict = RuntimeService(session).prepare(project.id, agent.id)
    assert strict.prompt.error is not None
    assert "world_context" in strict.prompt.error["message"]


def test_missing_optional_slot_renders_empty_for_plain_text():
    from app.runtime.execute import prepare_prompt

    class EmptySource:
        def scene_characters(self):
            return None

        def summarize(self, key, text):
            return text

    prepared = prepare_prompt(
        system_prompt="人物：{{ scene_characters }}",
        context_slots=["scene_characters"],
        output_schema=None,
        token_budget=8000,
        source=EmptySource(),
        allow_missing=True,
    )

    assert prepared.error is None
    assert prepared.rendered_prompt == "人物："


def test_execute_duration_covers_preparation_time(session, monkeypatch):
    """耗时口径与重构前一致：从准备阶段开始计时，而不是只算模型调用。

    调试台的「耗时」此前包含上下文组装与渲染；若计时起点落在 prepare()
    之后，模板错误这类不发起模型调用的运行会落库成接近 0 毫秒。
    """
    project, _provider, agent, _version = _seed(session)
    service = RuntimeService(
        session, client=HttpxChatClient(transport=httpx.MockTransport(_ok_handler()))
    )
    real_prepare = service.prepare

    def slow_prepare(*args, **kwargs):
        time.sleep(0.06)
        return real_prepare(*args, **kwargs)

    monkeypatch.setattr(service, "prepare", slow_prepare)

    run, _result = service.execute(project.id, agent.id)

    assert run.duration_ms >= 50

