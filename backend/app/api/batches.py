"""批量生成接口。路由层只做参数校验、错误翻译与调用。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import BatchCreate
from app.db.session import get_session
from app.services import batch_service

router = APIRouter(prefix="/api", tags=["batches"])

_MISSING_PREFIXES = ("批量任务不存在", "章不存在", "卷不存在")


def _value_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    if message.startswith(_MISSING_PREFIXES):
        return HTTPException(status_code=404, detail=message)
    if message.startswith("这个项目已有进行中的批量任务"):
        return HTTPException(status_code=409, detail=message)
    return HTTPException(status_code=400, detail=message)


@router.post("/projects/{project_id}/batches", status_code=201)
def create_batch(
    project_id: str,
    payload: BatchCreate,
    session: Session = Depends(get_session),
) -> dict:
    try:
        job = batch_service.create_job(
            session, project_id, payload.scope_type, payload.scope_id
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    return batch_service.serialize_job(job)


@router.get("/projects/{project_id}/batches/latest")
def latest_batch(project_id: str, session: Session = Depends(get_session)) -> dict | None:
    return batch_service.latest_job(session, project_id)


@router.get("/batches/{job_id}")
def get_batch(job_id: str, session: Session = Depends(get_session)) -> dict:
    try:
        return batch_service.get_job(session, job_id)
    except ValueError as exc:
        raise _value_error(exc) from exc


def _control(action, job_id: str) -> dict:
    try:
        return action(job_id)
    except ValueError as exc:
        raise _value_error(exc) from exc


@router.post("/batches/{job_id}/pause")
def pause_batch(job_id: str) -> dict:
    return _control(batch_service.pause_job, job_id)


@router.post("/batches/{job_id}/resume")
def resume_batch(job_id: str) -> dict:
    return _control(batch_service.resume_job, job_id)


@router.post("/batches/{job_id}/cancel")
def cancel_batch(job_id: str) -> dict:
    return _control(batch_service.cancel_job, job_id)


@router.post("/batches/{job_id}/retry-failed")
def retry_failed_batch(job_id: str) -> dict:
    return _control(batch_service.retry_failed, job_id)
