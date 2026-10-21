import pytest

from app.db.models import (
    Pipeline,
    PipelineNode,
    PipelineRun,
    Project,
)
from app.pipeline_executors import NodeOutcome
from app.pipeline_types import DEFAULT_PIPELINE
from app.services import pipeline_service


@pytest.fixture()
def project(session):
    project = Project(name="雾港")
    session.add(project)
    session.commit()
    return project


def _stub_executors(monkeypatch, *, blocked=(), fail=()):
    """把执行器换成受控假实现，状态机测试不碰模型。"""
    from app.pipeline_executors import Executor

    def make(task_type):
        def check(session, project, node):
            return f"缺前置：{task_type}" if task_type in blocked else None

        def run(session, project, node):
            if task_type in fail:
                raise ValueError(f"{task_type} 挂了")
            return NodeOutcome(
                generation_run_id=None,
                summary={"task_type": task_type},
            )

        return Executor(task_type, check, run)

    from app.services import pipeline_service as ps

    monkeypatch.setattr(
        ps,
        "get_executor",
        lambda task_type: make(task_type)
        if any(n["task_type"] == task_type for n in DEFAULT_PIPELINE)
        else None,
    )


@pytest.fixture(autouse=True)
def _no_threads(monkeypatch):
    """状态机测试一律手动 `advance_run`，不起后台线程。

    线程会在别的 session 里推进同一个运行，和测试里手动推进的游标抢状态，
    失败信息会指向「结果不确定」而不是真实缺陷。
    """
    monkeypatch.setattr(pipeline_service, "spawn_run", lambda run_id: None)


def _drain(session, run_id):
    """一直推进到 run 不再 running，返回最终状态。"""
    for _ in range(20):
        pipeline_service.advance_run(session, run_id)
        session.expire_all()
        run = session.get(PipelineRun, run_id)
        if run.status != "running":
            return run
    raise AssertionError("运行没有收敛")


def test_ensure_pipeline_is_idempotent(session, project):
    first = pipeline_service.ensure_pipeline(session, project.id)
    second = pipeline_service.ensure_pipeline(session, project.id)

    assert first.id == second.id
    assert session.query(Pipeline).count() == 1
    assert len(pipeline_service.list_nodes(session, first.id)) == len(DEFAULT_PIPELINE)


def test_ensure_pipeline_rejects_unknown_project(session):
    with pytest.raises(ValueError, match="项目不存在"):
        pipeline_service.ensure_pipeline(session, "nope")


def test_update_pipeline_replaces_nodes_and_renumbers(session, project):
    pipeline_service.ensure_pipeline(session, project.id)

    pipeline_service.update_pipeline(
        session,
        project.id,
        policy="auto",
        nodes=[
            {"name": "先解析", "task_type": "idea_parse"},
            {"name": "再架构", "task_type": "architecture", "checkpoint": True},
        ],
    )

    nodes = pipeline_service.list_nodes(session, pipeline_service.ensure_pipeline(session, project.id).id)
    assert [n.seq for n in nodes] == [0, 1]
    assert [n.name for n in nodes] == ["先解析", "再架构"]
    assert nodes[1].checkpoint is True
    assert pipeline_service.ensure_pipeline(session, project.id).policy == "auto"


def test_update_pipeline_rejects_empty_nodes(session, project):
    with pytest.raises(ValueError, match="至少要有一个节点"):
        pipeline_service.update_pipeline(session, project.id, policy=None, nodes=[])


def test_update_pipeline_rejects_missing_task_type(session, project):
    with pytest.raises(ValueError, match="任务类型"):
        pipeline_service.update_pipeline(
            session, project.id, policy=None, nodes=[{"name": "空节点"}]
        )


def test_reset_pipeline_restores_the_template(session, project):
    pipeline_service.update_pipeline(
        session,
        project.id,
        policy="every",
        nodes=[{"name": "只剩一个", "task_type": "idea_parse"}],
    )

    pipeline_service.reset_pipeline(session, project.id)

    nodes = pipeline_service.list_nodes(session, pipeline_service.ensure_pipeline(session, project.id).id)
    assert [n.task_type for n in nodes] == [n["task_type"] for n in DEFAULT_PIPELINE]
    # reset 不动策略：作者对节奏的偏好不该被「恢复默认」抹掉
    assert pipeline_service.ensure_pipeline(session, project.id).policy == "every"


def test_start_run_snapshots_the_nodes(session, project):
    pipeline = pipeline_service.ensure_pipeline(session, project.id)
    run = pipeline_service.start_run(session, project.id)

    nodes = pipeline_service.run_nodes(session, run.id)
    assert len(nodes) == len(pipeline_service.list_nodes(session, pipeline.id))
    assert all(node.status == "pending" for node in nodes)
    assert run.status == "running"
    assert run.cursor == 0


def test_start_run_rejects_a_second_active_run(session, project):
    pipeline_service.start_run(session, project.id)

    with pytest.raises(ValueError, match="已有进行中的管线运行"):
        pipeline_service.start_run(session, project.id)


def test_snapshot_isolates_a_running_run_from_pipeline_edits(session, project, monkeypatch):
    _stub_executors(monkeypatch)
    run = pipeline_service.start_run(session, project.id)
    pipeline_id = pipeline_service.ensure_pipeline(session, project.id).id
    original_types = [n.task_type for n in pipeline_service.run_nodes(session, run.id)]

    # 运行开始后把管线整个换掉
    pipeline_service.update_pipeline(
        session, project.id, policy=None, nodes=[{"name": "x", "task_type": "scene_plan"}]
    )

    nodes = pipeline_service.run_nodes(session, run.id)
    assert [n.task_type for n in nodes] == original_types
    assert session.get(Pipeline, pipeline_id) is not None


def test_disabled_node_is_skipped(session, project, monkeypatch):
    _stub_executors(monkeypatch)
    pipeline_service.update_pipeline(
        session,
        project.id,
        policy="auto",
        nodes=[
            {"name": "停用的", "task_type": "idea_parse", "enabled": False},
            {"name": "要跑的", "task_type": "architecture"},
        ],
    )
    run = pipeline_service.start_run(session, project.id)

    final = _drain(session, run.id)

    nodes = pipeline_service.run_nodes(session, run.id)
    assert final.status == "completed"
    assert nodes[0].status == "skipped"
    assert nodes[0].message == "节点已停用"
    assert nodes[1].status == "ok"


def test_unknown_task_type_is_skipped(session, project, monkeypatch):
    _stub_executors(monkeypatch)
    pipeline_service.update_pipeline(
        session,
        project.id,
        policy="auto",
        nodes=[{"name": "不认识的", "task_type": "polish"}],
    )
    run = pipeline_service.start_run(session, project.id)

    final = _drain(session, run.id)

    node = pipeline_service.run_nodes(session, run.id)[0]
    assert final.status == "completed"
    assert node.status == "skipped"
    assert "暂不支持" in node.message


def test_blocked_node_pauses_the_run_and_leaves_the_rest_pending(session, project, monkeypatch):
    _stub_executors(monkeypatch, blocked={"architecture"})
    pipeline_service.update_pipeline(
        session,
        project.id,
        policy="auto",
        nodes=[
            {"name": "解析", "task_type": "idea_parse"},
            {"name": "架构", "task_type": "architecture"},
            {"name": "世界观", "task_type": "worldbuilding"},
        ],
    )
    run = pipeline_service.start_run(session, project.id)

    final = _drain(session, run.id)

    nodes = pipeline_service.run_nodes(session, run.id)
    assert final.status == "paused"
    assert "缺前置" in final.message
    assert [n.status for n in nodes] == ["ok", "blocked", "pending"]


def test_failed_node_pauses_the_run(session, project, monkeypatch):
    _stub_executors(monkeypatch, fail={"idea_parse"})
    pipeline_service.update_pipeline(
        session,
        project.id,
        policy="auto",
        nodes=[{"name": "解析", "task_type": "idea_parse"}],
    )
    run = pipeline_service.start_run(session, project.id)

    final = _drain(session, run.id)

    node = pipeline_service.run_nodes(session, run.id)[0]
    assert final.status == "paused"
    assert node.status == "failed"
    assert "挂了" in node.message


def test_every_policy_pauses_after_each_node(session, project, monkeypatch):
    _stub_executors(monkeypatch)
    pipeline_service.update_pipeline(
        session,
        project.id,
        policy="every",
        nodes=[
            {"name": "一", "task_type": "idea_parse"},
            {"name": "二", "task_type": "architecture"},
        ],
    )
    run = pipeline_service.start_run(session, project.id)

    pipeline_service.advance_run(session, run.id)
    session.expire_all()
    after_first = session.get(PipelineRun, run.id)

    assert after_first.status == "awaiting"
    assert pipeline_service.run_nodes(session, run.id)[0].status == "awaiting"


def test_key_only_pauses_only_at_checkpoints(session, project, monkeypatch):
    _stub_executors(monkeypatch)
    pipeline_service.update_pipeline(
        session,
        project.id,
        policy="key_only",
        nodes=[
            {"name": "普通", "task_type": "idea_parse"},
            {"name": "检查点", "task_type": "architecture", "checkpoint": True},
        ],
    )
    run = pipeline_service.start_run(session, project.id)

    pipeline_service.advance_run(session, run.id)
    session.expire_all()
    assert session.get(PipelineRun, run.id).status == "running"

    pipeline_service.advance_run(session, run.id)
    session.expire_all()
    after = session.get(PipelineRun, run.id)
    assert after.status == "awaiting"
    assert pipeline_service.run_nodes(session, run.id)[1].status == "awaiting"


def test_auto_policy_runs_to_completion(session, project, monkeypatch):
    _stub_executors(monkeypatch)
    pipeline_service.update_pipeline(
        session,
        project.id,
        policy="auto",
        nodes=[
            {"name": "一", "task_type": "idea_parse"},
            {"name": "二", "task_type": "architecture", "checkpoint": True},
        ],
    )
    run = pipeline_service.start_run(session, project.id)

    final = _drain(session, run.id)

    assert final.status == "completed"
    assert [n.status for n in pipeline_service.run_nodes(session, run.id)] == ["ok", "ok"]


def test_resume_from_awaiting_moves_on(session, project, monkeypatch):
    _stub_executors(monkeypatch)
    # key_only：只在检查点停，第二个节点跑完就收尾 —— 用 every 的话
    # 它会停在自己的检查点后，断言会变成「又停了一次」。
    pipeline_service.update_pipeline(
        session,
        project.id,
        policy="key_only",
        nodes=[
            {"name": "一", "task_type": "idea_parse", "checkpoint": True},
            {"name": "二", "task_type": "architecture"},
        ],
    )
    run = pipeline_service.start_run(session, project.id)
    pipeline_service.advance_run(session, run.id)
    session.expire_all()

    pipeline_service.resume_run(session, run.id)
    final = _drain(session, run.id)

    assert final.status == "completed"


def test_resume_retries_a_blocked_node(session, project, monkeypatch):
    _stub_executors(monkeypatch, blocked={"idea_parse"})
    pipeline_service.update_pipeline(
        session,
        project.id,
        policy="auto",
        nodes=[{"name": "解析", "task_type": "idea_parse"}],
    )
    run = pipeline_service.start_run(session, project.id)
    _drain(session, run.id)
    assert pipeline_service.run_nodes(session, run.id)[0].status == "blocked"

    # 作者补完前置后再继续：应当重试同一节点
    _stub_executors(monkeypatch)
    pipeline_service.resume_run(session, run.id)
    final = _drain(session, run.id)

    assert final.status == "completed"
    assert pipeline_service.run_nodes(session, run.id)[0].status == "ok"


def test_cancel_marks_unrun_nodes(session, project, monkeypatch):
    _stub_executors(monkeypatch)
    pipeline_service.update_pipeline(
        session,
        project.id,
        policy="every",
        nodes=[
            {"name": "一", "task_type": "idea_parse"},
            {"name": "二", "task_type": "architecture"},
        ],
    )
    run = pipeline_service.start_run(session, project.id)
    pipeline_service.advance_run(session, run.id)
    session.expire_all()

    pipeline_service.cancel_run(session, run.id)

    nodes = pipeline_service.run_nodes(session, run.id)
    assert session.get(PipelineRun, run.id).status == "cancelled"
    assert nodes[0].status == "awaiting"  # 已跑完的保持原样
    assert nodes[1].status == "cancelled"


def test_cannot_cancel_a_finished_run(session, project, monkeypatch):
    _stub_executors(monkeypatch)
    pipeline_service.update_pipeline(
        session, project.id, policy="auto", nodes=[{"name": "一", "task_type": "idea_parse"}]
    )
    run = pipeline_service.start_run(session, project.id)
    _drain(session, run.id)

    with pytest.raises(ValueError, match="已经结束"):
        pipeline_service.cancel_run(session, run.id)


def test_recover_runs_pauses_running_ones(session, project, monkeypatch):
    _stub_executors(monkeypatch)
    run = pipeline_service.start_run(session, project.id)
    node = pipeline_service.run_nodes(session, run.id)[0]
    node.status = "running"
    session.commit()

    count = pipeline_service.recover_runs()

    assert count == 1
    session.expire_all()
    assert session.get(PipelineRun, run.id).status == "paused"
    assert pipeline_service.run_nodes(session, run.id)[0].status == "pending"


def test_real_executor_blocked_by_missing_idea(session, project):
    """不 stub 执行器：空项目跑默认管线，第一个节点就该被拦下。"""
    run = pipeline_service.start_run(session, project.id)

    pipeline_service.advance_run(session, run.id)

    node = pipeline_service.run_nodes(session, run.id)[0]
    assert node.status == "blocked"
    assert "灵感与解析" in node.message


def test_completing_clears_awaiting_markers(session, project, monkeypatch):
    """整条管线跑完后，停在检查点的节点不该继续显示「待确认」。"""
    _stub_executors(monkeypatch)
    pipeline_service.update_pipeline(
        session,
        project.id,
        policy="key_only",
        nodes=[
            {"name": "一", "task_type": "idea_parse", "checkpoint": True},
            {"name": "二", "task_type": "architecture"},
        ],
    )
    run = pipeline_service.start_run(session, project.id)
    pipeline_service.advance_run(session, run.id)
    session.expire_all()
    assert pipeline_service.run_nodes(session, run.id)[0].status == "awaiting"

    pipeline_service.resume_run(session, run.id)
    final = _drain(session, run.id)

    assert final.status == "completed"
    assert [n.status for n in pipeline_service.run_nodes(session, run.id)] == ["ok", "ok"]
