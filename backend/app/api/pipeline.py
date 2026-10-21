"""管线接口。路由层只做参数校验、错误翻译与调用。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import PipelineUpdate
from app.db.session import get_session
from app.services import pipeline_service

router = APIRouter(prefix="/api", tags=["pipeline"])


def _value_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    if message.startswith(("项目不存在", "管线运行不存在")):
        return HTTPException(status_code=404, detail=message)
    if message.startswith("这个项目已有进行中的管线运行"):
        return HTTPException(status_code=409, detail=message)
    return HTTPException(status_code=400, detail=message)


@router.get("/projects/{project_id}/pipeline")
def get_pipeline(project_id: str, session: Session = Depends(get_session)) -> dict:
    try:
        pipeline = pipeline_service.ensure_pipeline(session, project_id)
    except ValueError as exc:
        raise _value_error(exc) from exc
    return pipeline_service.serialize_pipeline(session, pipeline)


@router.put("/projects/{project_id}/pipeline")
def update_pipeline(
    project_id: str, payload: PipelineUpdate, session: Session = Depends(get_session)
) -> dict:
    try:
        pipeline = pipeline_service.update_pipeline(
            session,
            project_id,
            policy=payload.policy,
            nodes=[node.model_dump() for node in payload.nodes] if payload.nodes is not None else None,
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    return pipeline_service.serialize_pipeline(session, pipeline)


@router.post("/projects/{project_id}/pipeline/reset")
def reset_pipeline(project_id: str, session: Session = Depends(get_session)) -> dict:
    try:
        pipeline = pipeline_service.reset_pipeline(session, project_id)
    except ValueError as exc:
        raise _value_error(exc) from exc
    return pipeline_service.serialize_pipeline(session, pipeline)


@router.post("/projects/{project_id}/pipeline/runs", status_code=201)
def start_run(project_id: str, session: Session = Depends(get_session)) -> dict:
    try:
        run = pipeline_service.start_run(session, project_id)
    except ValueError as exc:
        raise _value_error(exc) from exc
    pipeline_service.spawn_run(run.id)
    return pipeline_service.get_run(session, run.id)


@router.get("/projects/{project_id}/pipeline/runs/latest")
def latest_run(project_id: str, session: Session = Depends(get_session)) -> dict | None:
    return pipeline_service.latest_run(session, project_id)


@router.get("/pipeline-runs/{run_id}")
def get_run(run_id: str, session: Session = Depends(get_session)) -> dict:
    try:
        return pipeline_service.get_run(session, run_id)
    except ValueError as exc:
        raise _value_error(exc) from exc


def _control(action, run_id: str) -> dict:
    from app.db.session import SessionLocal

    with SessionLocal() as session:
        try:
            action(session, run_id)
        except ValueError as exc:
            raise _value_error(exc) from exc
        return pipeline_service.get_run(session, run_id)


@router.post("/pipeline-runs/{run_id}/pause")
def pause_run(run_id: str) -> dict:
    return _control(pipeline_service.pause_run, run_id)


@router.post("/pipeline-runs/{run_id}/resume")
def resume_run(run_id: str) -> dict:
    return _control(pipeline_service.resume_run, run_id)


@router.post("/pipeline-runs/{run_id}/cancel")
def cancel_run(run_id: str) -> dict:
    return _control(pipeline_service.cancel_run, run_id)
