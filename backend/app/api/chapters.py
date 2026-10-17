from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import (
    ChapterCreate,
    ChapterUpdate,
    MoveRequest,
    SceneCreate,
    SceneUpdate,
    SceneWrite,
    VolumeCreate,
    VolumeUpdate,
)
from app.db.session import get_session
from app.services import chapter_service, scene_service

router = APIRouter(prefix="/api", tags=["chapters"])


def _volume_out(volume) -> dict:
    return {
        "id": volume.id,
        "project_id": volume.project_id,
        "seq": volume.seq,
        "name": volume.name,
        "purpose": volume.purpose,
        "summary": volume.summary,
        "act_seq": volume.act_seq,
        "target_words": volume.target_words,
        "status": volume.status,
        "source_run_id": volume.source_run_id,
    }


def _chapter_out(chapter) -> dict:
    return {
        "id": chapter.id,
        "volume_id": chapter.volume_id,
        "seq": chapter.seq,
        "title": chapter.title,
        "pov": chapter.pov,
        "target_words": chapter.target_words,
        "emotional_tone": chapter.emotional_tone,
        "lines": chapter.lines_json,
        "hook": chapter.hook,
        "summary": chapter.summary,
        "conflict_level": chapter.conflict_level,
        "dialogue_ratio": chapter.dialogue_ratio,
        "hook_strength": chapter.hook_strength,
        "status": chapter.status,
        "source_run_id": chapter.source_run_id,
    }


def _bad_request(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


# 场景路由的 404 判定必须看消息前缀，不能用「不存在」子串：作者要输入的是
# 人物 / 地点名，名字本身就可能叫「不存在」，而名称解析失败是 400。
_MISSING_PREFIXES = ("章不存在", "场景不存在", "卷不存在", "项目不存在")


def _is_missing(exc: ValueError) -> bool:
    return str(exc).startswith(_MISSING_PREFIXES)


@router.get("/chapter-types")
def list_chapter_types() -> dict:
    """状态词表的唯一真相在 app/chapter_types.py；前端不硬编第二份。"""
    from app.chapter_types import STATUS_LABELS

    return {
        "statuses": [
            {"key": key, "label": label} for key, label in STATUS_LABELS.items()
        ]
    }


@router.get("/projects/{project_id}/chapters/tree")
def get_tree(project_id: str, session: Session = Depends(get_session)) -> dict:
    return {"volumes": chapter_service.build_tree(session, project_id)}


@router.post("/projects/{project_id}/volumes", status_code=201)
def create_volume(
    project_id: str, payload: VolumeCreate, session: Session = Depends(get_session)
) -> dict:
    try:
        volume = chapter_service.create_volume(session, project_id, **payload.model_dump())
    except ValueError as exc:
        raise _bad_request(exc) from exc
    return _volume_out(volume)


@router.patch("/volumes/{volume_id}")
def update_volume(
    volume_id: str, payload: VolumeUpdate, session: Session = Depends(get_session)
) -> dict:
    try:
        volume = chapter_service.update_volume(
            session, volume_id, **payload.model_dump(exclude_unset=True)
        )
    except ValueError as exc:
        if _is_missing(exc):
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise _bad_request(exc) from exc
    return _volume_out(volume)


@router.delete("/volumes/{volume_id}", status_code=204)
def delete_volume(volume_id: str, session: Session = Depends(get_session)) -> None:
    try:
        chapter_service.delete_volume(session, volume_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/volumes/{volume_id}/move")
def move_volume(
    volume_id: str, payload: MoveRequest, session: Session = Depends(get_session)
) -> dict:
    try:
        volume = chapter_service.move_volume(session, volume_id, payload.direction)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _volume_out(volume)


@router.post("/volumes/{volume_id}/chapters", status_code=201)
def create_chapter(
    volume_id: str, payload: ChapterCreate, session: Session = Depends(get_session)
) -> dict:
    try:
        chapter = chapter_service.create_chapter(session, volume_id, **payload.model_dump())
    except ValueError as exc:
        if _is_missing(exc):
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise _bad_request(exc) from exc
    return _chapter_out(chapter)


@router.patch("/chapters/{chapter_id}")
def update_chapter(
    chapter_id: str, payload: ChapterUpdate, session: Session = Depends(get_session)
) -> dict:
    try:
        chapter = chapter_service.update_chapter(
            session, chapter_id, **payload.model_dump(exclude_unset=True)
        )
    except ValueError as exc:
        if _is_missing(exc):
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise _bad_request(exc) from exc
    return _chapter_out(chapter)


@router.delete("/chapters/{chapter_id}", status_code=204)
def delete_chapter(chapter_id: str, session: Session = Depends(get_session)) -> None:
    try:
        chapter_service.delete_chapter(session, chapter_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/chapters/{chapter_id}/move")
def move_chapter(
    chapter_id: str, payload: MoveRequest, session: Session = Depends(get_session)
) -> dict:
    try:
        chapter = chapter_service.move_chapter(session, chapter_id, payload.direction)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _chapter_out(chapter)


@router.post("/chapters/{chapter_id}/scenes", status_code=201)
def create_scene(
    chapter_id: str, payload: SceneCreate, session: Session = Depends(get_session)
) -> dict:
    try:
        scene = scene_service.create_scene(session, chapter_id, **payload.model_dump())
    except ValueError as exc:
        if _is_missing(exc):
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise _bad_request(exc) from exc
    return scene_service.scene_payload(session, scene)


@router.patch("/scenes/{scene_id}")
def update_scene(
    scene_id: str, payload: SceneUpdate, session: Session = Depends(get_session)
) -> dict:
    try:
        scene = scene_service.update_scene(
            session, scene_id, **payload.model_dump(exclude_unset=True)
        )
    except ValueError as exc:
        if _is_missing(exc):
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise _bad_request(exc) from exc
    return scene_service.scene_payload(session, scene)


@router.delete("/scenes/{scene_id}", status_code=204)
def delete_scene(scene_id: str, session: Session = Depends(get_session)) -> None:
    try:
        scene_service.delete_scene(session, scene_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/scenes/{scene_id}/move")
def move_scene(
    scene_id: str, payload: MoveRequest, session: Session = Depends(get_session)
) -> dict:
    try:
        scene = scene_service.move_scene(session, scene_id, payload.direction)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return scene_service.scene_payload(session, scene)


@router.put("/chapters/{chapter_id}/scenes")
def write_scenes(
    chapter_id: str, payload: SceneWrite, session: Session = Depends(get_session)
) -> dict:
    try:
        scene_service.write_scenes(
            session, chapter_id, payload.scenes, payload.mode, payload.source_run_id
        )
    except ValueError as exc:
        if _is_missing(exc):
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise _bad_request(exc) from exc
    project = chapter_service.get_project_for_chapter(session, chapter_id)
    return {"volumes": chapter_service.build_tree(session, project.id)}
