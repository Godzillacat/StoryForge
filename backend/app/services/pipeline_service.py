"""管线运行：状态机、控制与序列化。

**`advance_run` 是同步单步函数**，线程只是循环调用它 —— 状态机的每条分支
都能被 pytest 直接覆盖，不需要起线程。

落库边界：每一步推进前后各提交一次。模型调用可能几十秒，不能一直占着
一个事务；节点粒度落库也让重启后进度不丢。
"""

from __future__ import annotations

import threading

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Pipeline, PipelineNode, PipelineRun, PipelineRunNode, Project
from app.db.session import SessionLocal
from app.pipeline_executors import get_executor
from app.pipeline_types import default_nodes, normalize_policy

_ACTIVE: set[str] = set()
_ACTIVE_LOCK = threading.Lock()

_FINISHED = {"completed", "cancelled", "failed"}


# ---- 管线本体 ----

def ensure_pipeline(session: Session, project_id: str) -> Pipeline:
    """懒创建：一个项目一条管线，首次访问时按默认模板建出来。"""
    project = session.get(Project, project_id)
    if project is None:
        raise ValueError(f"项目不存在：{project_id}")
    pipeline = session.scalars(
        select(Pipeline).where(Pipeline.project_id == project_id)
    ).first()
    if pipeline is not None:
        return pipeline
    pipeline = Pipeline(project_id=project_id)
    session.add(pipeline)
    session.flush()
    for seq, node in enumerate(default_nodes()):
        session.add(
            PipelineNode(
                pipeline_id=pipeline.id,
                seq=seq,
                name=node["name"],
                task_type=node["task_type"],
                checkpoint=node["checkpoint"],
            )
        )
    session.commit()
    return pipeline


def list_nodes(session: Session, pipeline_id: str) -> list[PipelineNode]:
    return list(
        session.scalars(
            select(PipelineNode)
            .where(PipelineNode.pipeline_id == pipeline_id)
            .order_by(PipelineNode.seq)
        )
    )


def update_pipeline(
    session: Session, project_id: str, *, policy: str | None, nodes: list[dict] | None
) -> Pipeline:
    pipeline = ensure_pipeline(session, project_id)
    if policy is not None:
        pipeline.policy = normalize_policy(policy)
    if nodes is not None:
        if not nodes:
            raise ValueError("管线至少要有一个节点")
        for existing in list_nodes(session, pipeline.id):
            session.delete(existing)
        session.flush()
        for seq, node in enumerate(nodes):
            task_type = (node.get("task_type") or "").strip()
            if not task_type:
                raise ValueError("每个节点都要有任务类型")
            session.add(
                PipelineNode(
                    pipeline_id=pipeline.id,
                    seq=seq,
                    name=(node.get("name") or task_type).strip(),
                    task_type=task_type,
                    agent_id=node.get("agent_id") or None,
                    checkpoint=bool(node.get("checkpoint")),
                    enabled=bool(node.get("enabled", True)),
                    target_json=node.get("target_json") or {},
                )
            )
    session.commit()
    return pipeline


def reset_pipeline(session: Session, project_id: str) -> Pipeline:
    return update_pipeline(
        session,
        project_id,
        policy=None,
        nodes=[
            {
                "name": n["name"],
                "task_type": n["task_type"],
                "checkpoint": n["checkpoint"],
                "enabled": True,
            }
            for n in default_nodes()
        ],
    )


# ---- 运行 ----

def _run(session: Session, run_id: str) -> PipelineRun:
    run = session.get(PipelineRun, run_id)
    if run is None:
        raise ValueError(f"管线运行不存在：{run_id}")
    return run


def run_nodes(session: Session, run_id: str) -> list[PipelineRunNode]:
    return list(
        session.scalars(
            select(PipelineRunNode)
            .where(PipelineRunNode.run_id == run_id)
            .order_by(PipelineRunNode.seq)
        )
    )


def _active_run(session: Session, project_id: str) -> PipelineRun | None:
    return session.scalars(
        select(PipelineRun)
        .where(
            PipelineRun.project_id == project_id,
            PipelineRun.status.in_(("running", "awaiting", "paused")),
        )
        .order_by(PipelineRun.created_at.desc())
    ).first()


def start_run(session: Session, project_id: str) -> PipelineRun:
    pipeline = ensure_pipeline(session, project_id)
    if _active_run(session, project_id) is not None:
        raise ValueError("这个项目已有进行中的管线运行，请先完成或取消它")

    # 快照：运行开始后作者可能去改管线，若每步都读当前管线，
    # 改一次顺序就会让进行中的运行错位。
    nodes = list_nodes(session, pipeline.id)
    if not nodes:
        raise ValueError("管线里还没有节点")

    run = PipelineRun(
        project_id=project_id,
        pipeline_id=pipeline.id,
        policy=pipeline.policy,
        status="running",
        cursor=0,
    )
    session.add(run)
    session.flush()
    for node in nodes:
        session.add(
            PipelineRunNode(
                run_id=run.id,
                seq=node.seq,
                name=node.name,
                task_type=node.task_type,
                agent_id=node.agent_id,
            )
        )
    session.commit()
    return run


def _node_at(session: Session, run_id: str, seq: int) -> PipelineRunNode | None:
    return session.scalars(
        select(PipelineRunNode).where(
            PipelineRunNode.run_id == run_id, PipelineRunNode.seq == seq
        )
    ).first()


def advance_run(session: Session, run_id: str) -> None:
    """执行一步。返回时 run 可能推进、暂停、等待确认、完成或失败。"""
    run = _run(session, run_id)
    if run.status != "running":
        return

    node = _node_at(session, run_id, run.cursor)
    if node is None:
        run.status = "completed"
        run.message = ""
        session.commit()
        return

    # 节点级开关与未知类型都不值得停：跳过并说明，继续往后走。
    pipeline_node = session.scalars(
        select(PipelineNode).where(
            PipelineNode.pipeline_id == run.pipeline_id, PipelineNode.seq == node.seq
        )
    ).first()
    if pipeline_node is not None and not pipeline_node.enabled:
        node.status = "skipped"
        node.message = "节点已停用"
        run.cursor += 1
        session.commit()
        return

    executor = get_executor(node.task_type)
    if executor is None:
        node.status = "skipped"
        node.message = f"暂不支持的任务类型：{node.task_type}"
        run.cursor += 1
        session.commit()
        return

    project = session.get(Project, run.project_id)
    blocked = executor.check(session, project, node)
    if blocked:
        # 后续节点一并停下：拿空上下文继续跑只会花钱生成垃圾。
        node.status = "blocked"
        node.message = blocked
        run.status = "paused"
        run.message = f"「{node.name}」缺前置：{blocked}"
        session.commit()
        return

    node.status = "running"
    session.commit()

    try:
        outcome = executor.run(session, project, node)
    except ValueError as exc:
        node.status = "failed"
        node.message = str(exc)
        run.status = "paused"
        run.message = f"「{node.name}」失败：{exc}"
        session.commit()
        return

    node.status = "ok"
    node.generation_run_id = outcome.generation_run_id
    node.summary_json = outcome.summary
    node.message = outcome.message
    run.cursor += 1

    checkpoint = pipeline_node is not None and pipeline_node.checkpoint
    if run.policy == "every" or (run.policy == "key_only" and checkpoint):
        node.status = "awaiting"
        run.status = "awaiting"
        run.message = f"「{node.name}」完成，等你确认后继续"
        session.commit()
        return

    if run.cursor >= len(run_nodes(session, run_id)):
        run.status = "completed"
        run.message = ""
    session.commit()


def _loop(run_id: str) -> None:
    """守护线程：反复推进直到 run 不再 running。每个节点一个独立 session。"""
    try:
        while True:
            with SessionLocal() as session:
                run = session.get(PipelineRun, run_id)
                if run is None or run.status != "running":
                    return
                advance_run(session, run_id)
    finally:
        with _ACTIVE_LOCK:
            _ACTIVE.discard(run_id)


def spawn_run(run_id: str) -> None:
    """启动守护线程推进这次运行。`start_run` 只落库，由调用方决定何时开跑。"""
    with _ACTIVE_LOCK:
        if run_id in _ACTIVE:
            return
        _ACTIVE.add(run_id)
    threading.Thread(target=_loop, args=(run_id,), daemon=True).start()


def resume_run(session: Session, run_id: str) -> PipelineRun:
    """从 awaiting / paused 继续。

    停在一个 blocked / failed 的节点上时，继续就是**重试该节点** ——
    作者补完前置后不该需要新建一次运行。
    """
    run = _run(session, run_id)
    if run.status not in ("awaiting", "paused"):
        raise ValueError("这次运行已经结束，不能继续")
    node = _node_at(session, run_id, run.cursor)
    if node is not None and node.status in ("blocked", "failed"):
        node.status = "pending"
        node.message = ""
    run.status = "running"
    run.message = ""
    session.commit()
    spawn_run(run_id)
    return run


def pause_run(session: Session, run_id: str) -> PipelineRun:
    run = _run(session, run_id)
    if run.status != "running":
        raise ValueError("只有运行中的管线可以暂停")
    # 停在节点边界：正在跑的节点会跑完，线程看到状态变了就不再推进。
    run.status = "paused"
    run.message = "已暂停，当前节点跑完后停下"
    session.commit()
    return run


def cancel_run(session: Session, run_id: str) -> PipelineRun:
    run = _run(session, run_id)
    if run.status in _FINISHED:
        raise ValueError("这次运行已经结束")
    run.status = "cancelled"
    run.message = "已取消"
    # 只取消没跑过的。`awaiting` 的节点已经跑完并留下产出，
    # 把它标成「已取消」会抹掉「这一步其实成功了」这个事实。
    for node in run_nodes(session, run_id):
        if node.status == "pending":
            node.status = "cancelled"
    session.commit()
    return run


def recover_runs() -> int:
    """启动时把进程内线程没跑完的运行收敛为已暂停。"""
    count = 0
    with SessionLocal() as session:
        runs = session.scalars(
            select(PipelineRun).where(PipelineRun.status == "running")
        ).all()
        for run in runs:
            run.status = "paused"
            run.message = "应用重启，已暂停。继续即可从这里接着跑。"
            for node in run_nodes(session, run.id):
                if node.status == "running":
                    node.status = "pending"
            count += 1
        session.commit()
    return count


# ---- 序列化 ----

def _node_out(node: PipelineNode) -> dict:
    return {
        "id": node.id,
        "seq": node.seq,
        "name": node.name,
        "task_type": node.task_type,
        "agent_id": node.agent_id,
        "checkpoint": node.checkpoint,
        "enabled": node.enabled,
    }


def serialize_pipeline(session: Session, pipeline: Pipeline) -> dict:
    from app.pipeline_executors import available_node_types
    from app.pipeline_types import POLICY_LABELS

    return {
        "id": pipeline.id,
        "project_id": pipeline.project_id,
        "policy": pipeline.policy,
        "nodes": [_node_out(n) for n in list_nodes(session, pipeline.id)],
        "node_types": available_node_types(),
        "policies": [
            {"value": value, "label": POLICY_LABELS[value]}
            for value in POLICY_LABELS
        ],
    }


def _run_node_out(node: PipelineRunNode) -> dict:
    return {
        "id": node.id,
        "seq": node.seq,
        "name": node.name,
        "task_type": node.task_type,
        "agent_id": node.agent_id,
        "status": node.status,
        "generation_run_id": node.generation_run_id,
        "summary": node.summary_json,
        "message": node.message,
    }


def serialize_run(session: Session, run: PipelineRun) -> dict:
    nodes = run_nodes(session, run.id)
    return {
        "id": run.id,
        "project_id": run.project_id,
        "policy": run.policy,
        "status": run.status,
        "cursor": run.cursor,
        "message": run.message,
        "nodes": [_run_node_out(n) for n in nodes],
        "created_at": run.created_at.isoformat(),
    }


def get_run(session: Session, run_id: str) -> dict:
    return serialize_run(session, _run(session, run_id))


def latest_run(session: Session, project_id: str) -> dict | None:
    run = session.scalars(
        select(PipelineRun)
        .where(PipelineRun.project_id == project_id)
        .order_by(PipelineRun.created_at.desc())
    ).first()
    return serialize_run(session, run) if run is not None else None
