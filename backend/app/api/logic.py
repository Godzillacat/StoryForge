"""逻辑自检接口。路由层只做参数校验、错误翻译与调用。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.schemas import LogicCheckRequest
from app.db.session import get_session
from app.services import (
    causal_service,
    character_drift_service,
    logic_service,
    setting_load_service,
)

router = APIRouter(prefix="/api", tags=["logic"])


class CharacterStateRequest(BaseModel):
    """一行手记状态。缺 `note` 当作空串，由服务统一翻成「状态不能为空」的 400。"""

    note: str = ""


# 404 判定看消息前缀，不用「不存在」子串：名称本身可能就含「不存在」。
_NOT_FOUND_PREFIXES = (
    "场景不存在",
    "项目不存在",
    "章不存在",
    "人物不存在",
    "没有这条记录",
)


def _value_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    if message.startswith(_NOT_FOUND_PREFIXES):
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
    try:
        return logic_service.logic_chain(session, scene_id)
    except ValueError as exc:
        raise _value_error(exc) from exc


@router.get("/projects/{project_id}/causal-map")
def causal_map(project_id: str, session: Session = Depends(get_session)) -> dict:
    """因果链图的只读投影：场景树 + 已报过的因果问题，不改任何数据。"""
    try:
        return causal_service.build_map(session, project_id)
    except ValueError as exc:
        raise _value_error(exc) from exc


@router.get("/projects/{project_id}/setting-load")
def setting_load(project_id: str, session: Session = Depends(get_session)) -> dict:
    """设定投放曲线的只读投影：按章统计新出现 / 总提及 / 密度。不调用模型。"""
    try:
        return setting_load_service.build_load(session, project_id)
    except ValueError as exc:
        raise _value_error(exc) from exc


@router.get("/projects/{project_id}/character-drift")
def character_drift(project_id: str, session: Session = Depends(get_session)) -> dict:
    """性格漂移的只读投影：按人物分组的章节状态序列 + 变化次数。不改任何数据。"""
    try:
        return character_drift_service.get_drift(session, project_id)
    except ValueError as exc:
        raise _value_error(exc) from exc


@router.put("/chapters/{chapter_id}/character-states/{entry_id}")
def put_character_state(
    chapter_id: str,
    entry_id: str,
    payload: CharacterStateRequest,
    session: Session = Depends(get_session),
) -> dict:
    """作者手记的一行状态。同章同人是 upsert —— 重复保存是改它，不是再记一条。"""
    try:
        return character_drift_service.put_state(
            session, chapter_id, entry_id, payload.note
        )
    except ValueError as exc:
        raise _value_error(exc) from exc


@router.delete("/chapters/{chapter_id}/character-states/{entry_id}", status_code=204)
def delete_character_state(
    chapter_id: str, entry_id: str, session: Session = Depends(get_session)
) -> None:
    """删掉一条手记；没有这条记录是 404，不是静默成功。"""
    try:
        character_drift_service.delete_state(session, chapter_id, entry_id)
    except ValueError as exc:
        raise _value_error(exc) from exc


