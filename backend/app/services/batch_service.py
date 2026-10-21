"""批量生成的持久化任务与进程内 worker。

单机单人，不引入外部队列：任务状态与 cursor 落库，worker 是守护线程，
每个场景一个独立 session。任何失败都记录到任务里，作者可暂停、继续、
取消或只重试失败场景。
"""

from __future__ import annotations

import threading

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import BatchJob, Chapter, Scene, SceneDraft, Volume
from app.db.session import SessionLocal
from app.services import agent_service, chapter_service, text_service
from app.services.runtime_service import RuntimeService

_SCOPE_TYPES = {"chapter", "volume"}
_ACTIVE: set[str] = set()
_ACTIVE_LOCK = threading.Lock()


def _job(session: Session, job_id: str) -> BatchJob:
    job = session.get(BatchJob, job_id)
    if job is None:
        raise ValueError(f"批量任务不存在：{job_id}")
    return job


def get_job(session: Session, job_id: str) -> dict:
    return serialize_job(_job(session, job_id))


def _scope_scene_ids(session: Session, project_id: str, scope_type: str, scope_id: str) -> list[str]:
    if scope_type == "chapter":
        chapter = session.get(Chapter, scope_id)
        if chapter is None:
            raise ValueError(f"章不存在：{scope_id}")
        volume = session.get(Volume, chapter.volume_id)
        if volume is None or volume.project_id != project_id:
            raise ValueError(f"章不属于这个项目：{scope_id}")
        scenes = session.scalars(
            select(Scene).where(Scene.chapter_id == chapter.id).order_by(Scene.seq, Scene.created_at)
        ).all()
        return [scene.id for scene in scenes]

    volume = session.get(Volume, scope_id)
    if volume is None:
        raise ValueError(f"卷不存在：{scope_id}")
    if volume.project_id != project_id:
        raise ValueError(f"卷不属于这个项目：{scope_id}")
    chapters = session.scalars(
        select(Chapter).where(Chapter.volume_id == volume.id).order_by(Chapter.seq, Chapter.created_at)
    ).all()
    ids: list[str] = []
    for chapter in chapters:
        scenes = session.scalars(
            select(Scene).where(Scene.chapter_id == chapter.id).order_by(Scene.seq, Scene.created_at)
        ).all()
        ids.extend(scene.id for scene in scenes)
    return ids


def _available(session: Session, scene_ids: list[str]) -> list[str]:
    if not scene_ids:
        return []
    scenes = {
        row.id: row
        for row in session.scalars(select(Scene).where(Scene.id.in_(scene_ids))).all()
    }
    drafted = set(
        session.scalars(
            select(SceneDraft.scene_id).where(SceneDraft.scene_id.in_(scene_ids))
        ).all()
    )
    return [
        scene_id
        for scene_id in scene_ids
        if scene_id in scenes
        and not (scenes[scene_id].body or "").strip()
        and scene_id not in drafted
    ]


def serialize_job(job: BatchJob) -> dict:
    scene_ids = list(job.scene_ids_json or [])
    total = len(scene_ids)
    cursor = min(job.cursor, total)
    return {
        "id": job.id,
        "project_id": job.project_id,
        "scope_type": job.scope_type,
        "scope_id": job.scope_id,
        "status": job.status,
        "cursor": cursor,
        "total": total,
        "current_scene_id": scene_ids[cursor] if cursor < total else None,
        "failures": list(job.failures_json or []),
        "created_at": job.created_at.isoformat() if job.created_at else "",
        "updated_at": job.updated_at.isoformat() if job.updated_at else "",
    }


def create_job(
    session: Session, project_id: str, scope_type: str, scope_id: str
) -> BatchJob:
    if scope_type not in _SCOPE_TYPES:
        raise ValueError(f"未知的批量范围：{scope_type}")
    if scope_type == "chapter":
        chapter_service.get_project_for_chapter(session, scope_id)
    else:
        chapter_service.get_project_for_volume(session, scope_id)

    running = session.scalars(
        select(BatchJob).where(
            BatchJob.project_id == project_id, BatchJob.status == "running"
        )
    ).first()
    if running is not None:
        raise ValueError("这个项目已有进行中的批量任务")

    scene_ids = _scope_scene_ids(session, project_id, scope_type, scope_id)
    available = _available(session, scene_ids)
    if not available:
        raise ValueError("没有需要生成的场景（已有正文或草稿的场景会跳过）")

    job = BatchJob(
        project_id=project_id,
        scope_type=scope_type,
        scope_id=scope_id,
        scene_ids_json=available,
        cursor=0,
        status="paused",
        failures_json=[],
    )
    session.add(job)
    session.commit()
    return job


def _failure(job: BatchJob, scene_id: str, message: str) -> None:
    job.failures_json = [*(job.failures_json or []), {"scene_id": scene_id, "message": message}]


def advance_job(session: Session, job_id: str) -> str:
    """处理一个场景。返回 ok / skipped / failed / completed / not_running / failed_job。

    单独成函数是为了让测试不必启动线程，也能精确断言每一步的状态。
    """
    job = _job(session, job_id)
    if job.status != "running":
        return "not_running"

    scene_ids = list(job.scene_ids_json or [])
    if job.cursor >= len(scene_ids):
        job.status = "completed"
        session.commit()
        return "completed"

    scene_id = scene_ids[job.cursor]
    scene = session.get(Scene, scene_id)
    if scene is None:
        _failure(job, scene_id, "场景不存在")
        job.cursor += 1
        session.commit()
        return "failed"

    if (scene.body or "").strip() or session.scalars(
        select(SceneDraft).where(SceneDraft.scene_id == scene_id)
    ).first() is not None:
        job.cursor += 1
        session.commit()
        return "skipped"

    agent = agent_service.find_by_task_type(session, "write")
    if agent is None:
        _failure(job, scene_id, "找不到执笔智能体，请检查智能体工作室")
        job.status = "failed"
        session.commit()
        return "failed_job"

    try:
        project, extra = text_service.scene_extra(session, scene)
        run, result = RuntimeService(session).execute(project.id, agent.id, extra)
    except ValueError as exc:
        _failure(job, scene_id, str(exc))
        job.status = "failed"
        session.commit()
        return "failed_job"
    except Exception as exc:  # noqa: BLE001
        _failure(job, scene_id, str(exc).strip() or exc.__class__.__name__)
        job.cursor += 1
        session.commit()
        return "failed"

    if result.status != "ok":
        message = (result.error or {}).get("message") or "模型调用失败"
        _failure(job, scene_id, message)
        job.cursor += 1
        session.commit()
        return "failed"
    if not (result.raw_output or "").strip():
        _failure(job, scene_id, "模型返回空内容")
        job.cursor += 1
        session.commit()
        return "failed"
    if not text_service.save_generated_draft(
        session, scene_id, result.raw_output, run.id
    ):
        job.cursor += 1
        session.commit()
        return "skipped"

    job.cursor += 1
    session.commit()
    return "ok"


def _worker(job_id: str) -> None:
    try:
        while True:
            with SessionLocal() as session:
                job = session.get(BatchJob, job_id)
                if job is None or job.status != "running":
                    return
                outcome = advance_job(session, job_id)
            if outcome in {"completed", "not_running", "failed_job"}:
                return
    finally:
        with _ACTIVE_LOCK:
            _ACTIVE.discard(job_id)


def _spawn(job_id: str) -> None:
    with _ACTIVE_LOCK:
        if job_id in _ACTIVE:
            return
        _ACTIVE.add(job_id)
        threading.Thread(target=_worker, args=(job_id,), daemon=True).start()


def _ensure_no_other_running(session: Session, job: BatchJob) -> None:
    other = session.scalars(
        select(BatchJob).where(
            BatchJob.project_id == job.project_id,
            BatchJob.status == "running",
            BatchJob.id != job.id,
        )
    ).first()
    if other is not None:
        raise ValueError("这个项目已有进行中的批量任务")


def _finish_if_at_end(job: BatchJob) -> bool:
    if job.cursor >= len(job.scene_ids_json or []):
        job.status = "completed"
        return True
    return False


def start_job(job_id: str) -> dict:
    with SessionLocal() as session:
        job = _job(session, job_id)
        if job.status in ("completed", "cancelled"):
            raise ValueError("任务已结束")
        _ensure_no_other_running(session, job)
        job.status = "running"
        done = _finish_if_at_end(job)
        session.commit()
        result = serialize_job(job)
    if not done:
        _spawn(job_id)
    return result


def pause_job(job_id: str) -> dict:
    with SessionLocal() as session:
        job = _job(session, job_id)
        if job.status in ("completed", "cancelled"):
            raise ValueError("任务已结束")
        job.status = "paused"
        session.commit()
        return serialize_job(job)


def resume_job(job_id: str) -> dict:
    with SessionLocal() as session:
        job = _job(session, job_id)
        if job.status in ("completed", "cancelled"):
            raise ValueError("任务已结束")
        _ensure_no_other_running(session, job)
        job.status = "running"
        done = _finish_if_at_end(job)
        session.commit()
        result = serialize_job(job)
    if not done:
        _spawn(job_id)
    return result


def cancel_job(job_id: str) -> dict:
    with SessionLocal() as session:
        job = _job(session, job_id)
        if job.status == "completed":
            raise ValueError("任务已结束")
        job.status = "cancelled"
        session.commit()
        return serialize_job(job)


def retry_failed(job_id: str) -> dict:
    with SessionLocal() as session:
        job = _job(session, job_id)
        if job.status == "running":
            raise ValueError("任务仍在运行，请先暂停")
        _ensure_no_other_running(session, job)
        failures = list(job.failures_json or [])
        if not failures:
            raise ValueError("没有失败场景")
        failed_ids = [
            item["scene_id"]
            for item in failures
            if isinstance(item, dict) and item.get("scene_id")
        ]
        # 失败任务可能停在 cursor 处没往前走（例如没有服务商）：重试必须
        # 把「失败场景 + 尚未处理的后半段」一起放回去，不能只重跑失败项。
        remaining = list(job.scene_ids_json or [])[job.cursor :]
        combined = list(dict.fromkeys([*failed_ids, *remaining]))
        if not combined:
            raise ValueError("没有失败场景")
        job.scene_ids_json = combined
        job.cursor = 0
        job.failures_json = []
        job.status = "running"
        session.commit()
        result = serialize_job(job)
    _spawn(job_id)
    return result


def latest_job(session: Session, project_id: str) -> dict | None:
    job = session.scalars(
        select(BatchJob)
        .where(BatchJob.project_id == project_id)
        .order_by(BatchJob.created_at.desc())
    ).first()
    return serialize_job(job) if job else None


def recover_jobs() -> int:
    """应用启动时把未完成的 running 任务改为 paused —— 线程不跨重启。"""
    with SessionLocal() as session:
        jobs = session.scalars(
            select(BatchJob).where(BatchJob.status == "running")
        ).all()
        for job in jobs:
            job.status = "paused"
        session.commit()
        return len(jobs)
