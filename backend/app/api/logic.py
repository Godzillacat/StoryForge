"""逻辑自检接口。路由层只做参数校验、错误翻译与调用。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import logic_chain as chain_lib
from app.api.schemas import LogicCheckRequest
from app.db.models import Scene
from app.db.session import get_session
from app.services import logic_service

router = APIRouter(prefix="/api", tags=["logic"])


def _value_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    if message.startswith("场景不存在"):
        return HTTPException(status_code=404, detail=message)
    if message.startswith("场景的章节结构已损坏"):
        return HTTPException(status_code=409, detail=message)
    return HTTPException(status_code=400, detail=message)


@router.post("/scenes/{scene_id}/logic-check")
def run_logic_check(
    scene_id: str,
    payload: LogicCheckRequest,
    session: Session = Depends(get_session),
) -> dict:
    try:
        return logic_service.run_logic_check(session, scene_id, payload.stage)
    except ValueError as exc:
        raise _value_error(exc) from exc


@router.get("/scenes/{scene_id}/logic-check")
def get_logic_check(
    scene_id: str,
    stage: str = "text",
    session: Session = Depends(get_session),
) -> dict:
    try:
        return logic_service.list_logic_check(session, scene_id, stage)
    except ValueError as exc:
        raise _value_error(exc) from exc


@router.get("/scenes/{scene_id}/logic-chain")
def logic_chain(scene_id: str, session: Session = Depends(get_session)) -> dict:
    """把正文里已有的因果 / 转折 / 揭示摆出来。**不调用模型、不做判断。**"""
    scene = session.get(Scene, scene_id)
    if scene is None:
        raise HTTPException(status_code=404, detail=f"场景不存在：{scene_id}")
    body = scene.body or ""
    if not body.strip():
        return {
            "chain": [],
            "summary": {"total": 0, "cause": 0, "turn": 0, "reveal": 0},
            "reason": "这一场还没有已采纳正文。",
        }
    chain = chain_lib.extract_chain(body)
    return {
        "chain": chain,
        "summary": chain_lib.summarize(chain),
        "reason": "" if chain else "正文里没有明显的因果连接词。",
    }
