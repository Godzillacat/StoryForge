from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.schemas import (
    ReviewMarkClear,
    ReviewMarkCreate,
    RevisionApplyRequest,
    RevisionSuggestRequest,
)
from app.db.session import get_session
from app.services import impact_service, review_service, revision_service

router = APIRouter(prefix="/api", tags=["impact"])

# 「运行记录不存在」也按「缺失」映射 404：它比「参数不合法」更接近
# 「你要的那个东西没有」。与它同前缀的「运行记录不存在于这个项目」一并命中。
_MISSING_PREFIXES = (
    "项目不存在",
    "这个项目还没有故事圣经",
    "设定条目不存在",
    "卷不存在",
    "章不存在",
    "场景不存在",
    "待复核标记不存在",
    "运行记录不存在",
)


def _error(exc: ValueError) -> HTTPException:
    message = str(exc)
    if message.startswith(_MISSING_PREFIXES):
        return HTTPException(status_code=404, detail=message)
    return HTTPException(status_code=400, detail=message)


@router.get("/projects/{project_id}/impact")
def analyze_impact(
    project_id: str,
    target_type: str = Query(...),
    target_id: str = Query(...),
    session: Session = Depends(get_session),
) -> dict:
    try:
        return impact_service.analyze(session, project_id, target_type, target_id)
    except ValueError as exc:
        raise _error(exc) from exc


@router.post("/projects/{project_id}/impact/revisions")
def suggest_revisions(
    project_id: str,
    payload: RevisionSuggestRequest,
    session: Session = Depends(get_session),
) -> dict:
    """针对一次上游改动生成待勾选的修订建议（不写业务表）。

    先跑一次影响面分析做目标校验：预检只校验目标存在；对 entry 目标可能
    触发检索索引的惰性重建并提交，并不是纯读。`revision_service.suggest()`
    会把所有异常（含「目标不存在」）都折成 `llm_status="error"`，那样
    HTTP 层就再也分不清「目标不存在」（客户端错误）与「模型失败」。
    校验通过后原样返回服务结果，不改写、不吞掉 —— 模型失败仍以
    `llm_status="error"` 的形状回到界面，由面板显示中文原因。
    """
    try:
        impact_service.analyze(
            session, project_id, payload.target_type, payload.target_id
        )
    except ValueError as exc:
        raise _error(exc) from exc
    return revision_service.suggest(
        session, project_id, payload.target_type, payload.target_id
    )


@router.post("/projects/{project_id}/impact/revisions/apply")
def apply_revisions(
    project_id: str,
    payload: RevisionApplyRequest,
    session: Session = Depends(get_session),
) -> dict:
    """把作者勾选的建议逐条写库，并逐条给出跳过原因。

    运行记录不存在 / 不属于这个项目 → 404；不是一次可应用的修订建议运行
    → 400。写入内容由服务层从运行记录读回，请求里只有下标。
    """
    try:
        return revision_service.apply(
            session, project_id, payload.run_id, payload.accepted
        )
    except ValueError as exc:
        raise _error(exc) from exc


@router.get("/projects/{project_id}/review-marks")
def list_marks(project_id: str, session: Session = Depends(get_session)) -> list[dict]:
    try:
        return review_service.list_marks(session, project_id)
    except ValueError as exc:
        raise _error(exc) from exc


@router.post("/projects/{project_id}/review-marks")
def add_marks(
    project_id: str, payload: ReviewMarkCreate, session: Session = Depends(get_session)
) -> dict:
    try:
        added = review_service.add_marks(
            session, project_id, [item.model_dump() for item in payload.items]
        )
        rows = review_service.list_marks(session, project_id)
    except ValueError as exc:
        raise _error(exc) from exc
    return {"added": added, "marks": rows}


@router.post("/projects/{project_id}/review-marks/clear")
def clear_marks(
    project_id: str, payload: ReviewMarkClear, session: Session = Depends(get_session)
) -> dict:
    try:
        removed = review_service.clear_marks(
            session, project_id, [item.model_dump() for item in payload.items]
        )
        rows = review_service.list_marks(session, project_id)
    except ValueError as exc:
        raise _error(exc) from exc
    return {"removed": removed, "marks": rows}


@router.delete("/review-marks/{mark_id}", status_code=204)
def clear_mark(mark_id: str, session: Session = Depends(get_session)) -> None:
    try:
        review_service.clear_mark(session, mark_id)
    except ValueError as exc:
        raise _error(exc) from exc
