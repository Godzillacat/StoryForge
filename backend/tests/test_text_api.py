import asyncio

import httpx
import pytest

from app.db.models import GenerationRun, Scene, SceneDraft, SettingEntry
from app.db.session import SessionLocal
from app.runtime.llm import ChatError, ChatFailure, StreamDelta, StreamUsage
from app.services import search_service
from app.services.runtime_service import RuntimeService


def _create_scene(client) -> tuple[str, str]:
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    volume = client.post(
        f"/api/projects/{project['id']}/volumes", json={"name": "第一卷"}
    ).json()
    chapter = client.post(
        f"/api/volumes/{volume['id']}/chapters", json={"title": "第一章"}
    ).json()
    scene = client.post(
        f"/api/chapters/{chapter['id']}/scenes",
        json={"goal": "找到录音带", "conflict": "档案室有人", "turn": "录音带里是自己的声音"},
    ).json()
    return project["id"], scene["id"]


class FakeStreamClient:
    def __init__(self, chunks, fail_at=None, usage=None):
        self._chunks = chunks
        self._fail_at = fail_at
        self._usage = usage

    async def stream(self, config, messages, params):
        # fail_at 表示「先吐出这么多块，再失败」：简报里的写法按索引判断，
        # 单块数据配 fail_at=1 时循环永远到不了那个索引，失败分支根本不会执行。
        parts: list[str] = []
        for index, chunk in enumerate(self._chunks):
            if self._fail_at is not None and index >= self._fail_at:
                raise ChatFailure(
                    ChatError("network", "网络中断"), partial_text="".join(parts)
                )
            parts.append(chunk)
            yield StreamDelta(chunk)
        if self._fail_at is not None:
            raise ChatFailure(
                ChatError("network", "网络中断"), partial_text="".join(parts)
            )
        if self._usage is not None:
            yield StreamUsage(*self._usage)

    async def complete(self, config, messages, params):
        raise AssertionError("流式生成不允许走非流式接口")


def _patch_stream(monkeypatch, fake: FakeStreamClient) -> None:
    monkeypatch.setattr(
        RuntimeService, "_resolve_client", lambda self, timeout: fake
    )


def _stream_body(client, scene_id: str) -> str:
    with client.stream("POST", f"/api/scenes/{scene_id}/generate") as response:
        assert response.status_code == 200
        return "".join(response.iter_lines())


def test_generate_streams_and_saves_a_draft(client, monkeypatch):
    project_id, scene_id = _create_scene(client)
    _patch_stream(monkeypatch, FakeStreamClient(["第一段。", "第二段。"]))

    body = _stream_body(client, scene_id)

    assert "event: run" in body
    assert "event: delta" in body
    assert "event: done" in body

    # client 夹具的库在用例之间不清空，所以按本项目过滤 —— 断言意图不变，
    # 只是不把前一个用例留下的运行记录也算进来。
    with SessionLocal() as session:
        draft = session.query(SceneDraft).filter_by(scene_id=scene_id).one()
        assert draft.content == "第一段。第二段。"
        assert not (session.get(Scene, scene_id).body or "").strip()
        run = session.query(GenerationRun).filter_by(project_id=project_id).one()
        assert run.status == "ok"
        assert run.raw_output == "第一段。第二段。"
        assert run.completion_tokens > 0


def test_generate_failure_keeps_partial_content(client, monkeypatch):
    project_id, scene_id = _create_scene(client)
    _patch_stream(monkeypatch, FakeStreamClient(["第一段。"], fail_at=1))

    body = _stream_body(client, scene_id)

    assert "event: error" in body
    assert "网络中断" in body
    with SessionLocal() as session:
        draft = session.query(SceneDraft).filter_by(scene_id=scene_id).one()
        assert draft.content == "第一段。"
        run = session.query(GenerationRun).filter_by(project_id=project_id).one()
        assert run.status == "partial"
        assert run.raw_output == "第一段。"


def test_failed_regeneration_does_not_overwrite_existing_draft(client, monkeypatch):
    _project_id, scene_id = _create_scene(client)
    _patch_stream(monkeypatch, FakeStreamClient(["第一版。"]))
    _stream_body(client, scene_id)
    _patch_stream(monkeypatch, FakeStreamClient(["第二版。"], fail_at=1))
    _stream_body(client, scene_id)

    with SessionLocal() as session:
        draft = session.query(SceneDraft).filter_by(scene_id=scene_id).one()
        assert draft.content == "第一版。"


def test_generate_without_writer_model_is_400_before_streaming(client):
    _project_id, scene_id = _create_scene(client)
    from app import config

    # 分路或全局默认模型也会提供模型名，这条用例要验的是「哪都没有」。
    config.save_settings({"model_routing": {}, "default_model": None})
    with SessionLocal() as session:
        from app.db.models import Agent, AgentVersion

        writer = session.query(Agent).filter_by(task_type="write").one()
        version = session.get(AgentVersion, writer.current_version_id)
        version.model_binding_json = {}
        session.commit()
        version_id, original_binding = version.id, {}

    try:
        response = client.post(f"/api/scenes/{scene_id}/generate")
        assert response.status_code == 400
        assert "绑定模型" in response.json()["detail"]
    finally:
        # client 夹具共享一个库；不还原会让后面所有生成类用例一起 400。
        with SessionLocal() as session:
            from app.db.models import AgentVersion

            restored = session.get(AgentVersion, version_id)
            restored.model_binding_json = {**original_binding, "model": "test-model"}
            session.commit()


def test_finalize_run_is_idempotent_and_keeps_cancelled_content(client):
    _project_id, scene_id = _create_scene(client)
    with SessionLocal() as session:
        run = GenerationRun(project_id=None, status="running")
        session.add(run)
        session.commit()
        run_id = run.id

    from app.services import text_service

    text_service.finalize_run(
        run_id,
        scene_id,
        content="半截正文。",
        status="cancelled",
        prompt_tokens=10,
        completion_tokens=5,
        cost_estimate=0.0,
        duration_ms=100,
        error=None,
    )
    text_service.finalize_run(
        run_id,
        scene_id,
        content="不应覆盖",
        status="ok",
        prompt_tokens=10,
        completion_tokens=99,
        cost_estimate=0.0,
        duration_ms=200,
        error=None,
    )

    with SessionLocal() as session:
        stored = session.get(GenerationRun, run_id)
        assert stored.status == "cancelled"
        assert stored.raw_output == "半截正文。"
        draft = session.query(SceneDraft).filter_by(scene_id=scene_id).one()
        assert draft.content == "半截正文。"


class _FakeRequest:
    async def is_disconnected(self) -> bool:
        return False


def test_disconnect_right_after_run_event_marks_run_cancelled(client, monkeypatch):
    """客户端在收到 `run` 事件后立刻断开，运行记录不能永远停在 running。

    Starlette 在断开/取消失败时不一定替我们 aclose 响应体迭代器；生成器最终被
    finalizer 关闭时，GeneratorExit 会落在 `run` 的 yield 上。因此 `run` 事件
    本身也必须在 try/finally 之内，否则 finalize_run 永远不会执行。
    """
    project_id, scene_id = _create_scene(client)
    _patch_stream(monkeypatch, FakeStreamClient(["不应开始的正文。"]))

    from app.api import text as text_api

    async def scenario() -> str:
        with SessionLocal() as session:
            response = await text_api.generate_scene(scene_id, _FakeRequest(), session)
        iterator = response.body_iterator
        first = await iterator.__anext__()
        await iterator.aclose()
        return first

    first = asyncio.run(scenario())
    assert "event: run" in first

    with SessionLocal() as session:
        run = session.query(GenerationRun).filter_by(project_id=project_id).one()
        assert run.status == "cancelled"
        assert run.raw_output == ""
        assert session.query(SceneDraft).filter_by(scene_id=scene_id).count() == 0


def test_generate_survives_dirty_search_index_rebuild(client, monkeypatch):
    """生成前的上下文组装会触发惰性 FTS 重建并提交请求会话。

    那条路径必须在流生成器（新会话）里照样跑通：运行记录与草稿都要落库。
    """
    project_id, scene_id = _create_scene(client)
    with SessionLocal() as session:
        session.add(
            SettingEntry(
                project_id=project_id,
                name="南滨旧城",
                type="place",
                description="录音带与档案室所在",
            )
        )
        search_service.mark_dirty(session, project_id)
        session.commit()

    _patch_stream(monkeypatch, FakeStreamClient(["重建索引后的正文。"]))

    body = _stream_body(client, scene_id)

    assert "event: done" in body
    with SessionLocal() as session:
        draft = session.query(SceneDraft).filter_by(scene_id=scene_id).one()
        assert draft.content == "重建索引后的正文。"
        run = session.query(GenerationRun).filter_by(project_id=project_id).one()
        assert run.status == "ok"
        assert run.raw_output == "重建索引后的正文。"
        assert run.rendered_prompt


def test_create_run_survives_request_session_teardown(client):
    """运行落库不得依赖请求会话：prepare 之后对象过期/脱离，create_run 仍要成立。

    这是「准备阶段可能提交并关闭请求会话」的直接回归 —— 旧设计会在
    ``prepared.agent.id`` 上抛 DetachedInstanceError。
    """
    project_id, scene_id = _create_scene(client)
    from app.services import text_service

    with SessionLocal() as session:
        session.add(SettingEntry(project_id=project_id, name="档案室", type="place"))
        search_service.mark_dirty(session, project_id)
        session.commit()

    session = SessionLocal()
    spec = text_service.prepare_generation(session, scene_id)
    # 模拟请求会话 teardown 的最严苛形态：属性过期后再脱离会话。
    session.expire_all()
    session.close()

    run_id = text_service.create_run(spec)

    with SessionLocal() as session:
        run = session.get(GenerationRun, run_id)
        assert run is not None
        assert run.status == "running"
        assert run.project_id == project_id
        assert run.agent_id == spec.agent_id
        assert run.agent_version_id == spec.version_id
        assert run.provider_id == spec.provider_id
        assert run.model == spec.model
        assert run.rendered_prompt == spec.rendered_prompt


def _add_draft(scene_id: str, content: str) -> None:
    with SessionLocal() as session:
        session.add(SceneDraft(scene_id=scene_id, content=content))
        session.commit()


def test_text_endpoints_roundtrip_body_and_revisions(client):
    _project_id, scene_id = _create_scene(client)

    empty = client.get(f"/api/scenes/{scene_id}/text").json()
    assert empty["body"] is None and empty["draft"] is None

    saved = client.put(
        f"/api/scenes/{scene_id}/body", json={"content": "第一段。"}
    ).json()
    assert saved["body"] == "第一段。"
    assert saved["has_body"] is True
    assert saved["revisions"][0]["source"] == "author"

    same = client.put(
        f"/api/scenes/{scene_id}/body", json={"content": "第一段。"}
    ).json()
    assert len(same["revisions"]) == 1

    changed = client.put(
        f"/api/scenes/{scene_id}/body", json={"content": "第二段。"}
    ).json()
    assert len(changed["revisions"]) == 2

    old = next(
        row for row in changed["revisions"] if row["preview"].startswith("第一段")
    )
    detail = client.get(f"/api/scenes/{scene_id}/revisions/{old['id']}").json()
    assert detail["content"] == "第一段。"

    restored = client.post(
        f"/api/scenes/{scene_id}/revisions/{old['id']}/restore"
    ).json()
    assert restored["body"] == "第一段。"
    assert restored["revisions"][0]["source"] == "restore"


def test_draft_endpoints(client):
    _project_id, scene_id = _create_scene(client)
    _add_draft(scene_id, "AI 草稿")

    state = client.get(f"/api/scenes/{scene_id}/text").json()
    assert state["draft"]["content"] == "AI 草稿"

    edited = client.put(
        f"/api/scenes/{scene_id}/draft", json={"content": "改过的草稿"}
    ).json()
    assert edited["content"] == "改过的草稿"

    adopted = client.post(f"/api/scenes/{scene_id}/adopt").json()
    assert adopted["body"] == "改过的草稿"
    assert adopted["draft"] is None
    assert adopted["revisions"][0]["source"] == "ai"


def test_discard_draft(client):
    _project_id, scene_id = _create_scene(client)
    _add_draft(scene_id, "待丢弃")

    assert client.delete(f"/api/scenes/{scene_id}/draft").status_code == 200
    assert client.get(f"/api/scenes/{scene_id}/text").json()["draft"] is None


def test_adopt_without_draft_is_409(client):
    _project_id, scene_id = _create_scene(client)
    assert client.post(f"/api/scenes/{scene_id}/adopt").status_code == 409


def test_missing_scene_and_revision_are_404(client):
    assert client.get("/api/scenes/nope/text").status_code == 404
    _project_id, scene_id = _create_scene(client)
    assert (
        client.get(f"/api/scenes/{scene_id}/revisions/nope").status_code == 404
    )


def test_context_preview_lists_slots_without_calling_the_model(client, monkeypatch):
    _project_id, scene_id = _create_scene(client)

    def boom(*_args, **_kwargs):
        raise AssertionError("预览不允许调用模型")

    monkeypatch.setattr(
        RuntimeService, "_resolve_client", lambda self, timeout: boom()
    )

    payload = client.get(f"/api/scenes/{scene_id}/context-preview").json()

    assert payload["agent"]["name"] == "执笔"
    assert payload["token_budget"] > 0
    keys = {slot["key"] for slot in payload["slots"]}
    assert {"scene_card", "scene_characters", "recent_text"} <= keys
    card = next(slot for slot in payload["slots"] if slot["key"] == "scene_card")
    assert "找到录音带" in card["text"]


def test_context_preview_without_writer_is_400(client):
    _project_id, _scene_id = _create_scene(client)
    with SessionLocal() as session:
        from app.db.models import Agent

        writer = session.query(Agent).filter_by(task_type="write").one()
        writer_id = writer.id
        writer.enabled = False
        session.commit()

    try:
        _project_id, scene_id = _create_scene(client)
        assert (
            client.get(f"/api/scenes/{scene_id}/context-preview").status_code == 400
        )
    finally:
        # client 夹具共享一个库；停用不还原会让后面所有生成类用例一起 400。
        with SessionLocal() as session:
            from app.db.models import Agent

            session.get(Agent, writer_id).enabled = True
            session.commit()


def test_stream_usage_from_provider_is_recorded(client, monkeypatch):
    project_id, scene_id = _create_scene(client)
    _patch_stream(
        monkeypatch, FakeStreamClient(["第一段。"], usage=(123, 45))
    )

    body = _stream_body(client, scene_id)

    assert '"usage_source": "provider"' in body
    with SessionLocal() as session:
        run = session.query(GenerationRun).filter_by(project_id=project_id).one()
        assert run.usage_source == "provider"
        assert run.prompt_tokens == 123
        assert run.completion_tokens == 45


def test_stream_without_usage_is_marked_estimated(client, monkeypatch):
    project_id, scene_id = _create_scene(client)
    _patch_stream(monkeypatch, FakeStreamClient(["第一段。"]))

    body = _stream_body(client, scene_id)

    assert '"usage_source": "estimated"' in body
    with SessionLocal() as session:
        run = session.query(GenerationRun).filter_by(project_id=project_id).one()
        assert run.usage_source == "estimated"
