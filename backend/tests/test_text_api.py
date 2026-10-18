import httpx
import pytest

from app.db.models import GenerationRun, Scene, SceneDraft, SettingEntry
from app.db.session import SessionLocal
from app.runtime.llm import ChatError, ChatFailure
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
    def __init__(self, chunks, fail_at=None):
        self._chunks = chunks
        self._fail_at = fail_at

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
            yield chunk
        if self._fail_at is not None:
            raise ChatFailure(
                ChatError("network", "网络中断"), partial_text="".join(parts)
            )

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
    with SessionLocal() as session:
        from app.db.models import Agent, AgentVersion

        writer = session.query(Agent).filter_by(task_type="write").one()
        version = session.get(AgentVersion, writer.current_version_id)
        version.model_binding_json = {}
        session.commit()

    response = client.post(f"/api/scenes/{scene_id}/generate")
    assert response.status_code == 400
    assert "绑定模型" in response.json()["detail"]


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
