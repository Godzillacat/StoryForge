from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from app.api._serializers import _idea_out
from app.api.schemas import IdeaCreate, ProjectCreate, ProjectUpdate
from app.db.session import get_session
from app.services import cover_service, idea_service, project_service

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _project_out(project, *, has_cover: bool = False) -> dict:
    return {
        "id": project.id,
        "name": project.name,
        "genre": project.genre,
        "sub_genre": project.sub_genre,
        "tone": project.tone,
        "target_length": project.target_length,
        "summary": project.summary,
        "writing_lang": project.writing_lang,
        "logic_check_level": project.logic_check_level,
        "has_cover": has_cover,
        "created_at": project.created_at.isoformat(),
    }


@router.get("")
def list_projects(session: Session = Depends(get_session)) -> list[dict]:
    return [
        _project_out(p, has_cover=cover_service.has_cover(session, p.id))
        for p in project_service.list_projects(session)
    ]


@router.post("", status_code=201)
def create_project(payload: ProjectCreate, session: Session = Depends(get_session)) -> dict:
    return _project_out(project_service.create_project(session, **payload.model_dump()))


@router.get("/{project_id}")
def get_project(project_id: str, session: Session = Depends(get_session)) -> dict:
    project = project_service.get_project(session, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return _project_out(project, has_cover=cover_service.has_cover(session, project_id))


@router.patch("/{project_id}")
def update_project(
    project_id: str, payload: ProjectUpdate, session: Session = Depends(get_session)
) -> dict:
    try:
        project = project_service.update_project(session, project_id, **payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _project_out(project, has_cover=cover_service.has_cover(session, project_id))


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, session: Session = Depends(get_session)) -> None:
    try:
        project_service.delete_project(session, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{project_id}/cover")
async def upload_cover(
    project_id: str,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> dict:
    # 多读 1 字节就能判断「超限」：整个文件读进来再检查，作者误选一个
    # 400 MB 的 PSD 会把内存和事件循环一起拖住。
    data = await file.read(cover_service.MAX_COVER_BYTES + 1)
    try:
        return cover_service.save_cover(session, project_id, data)
    except ValueError as exc:
        message = str(exc)
        if message.startswith("项目不存在"):
            raise HTTPException(status_code=404, detail=message) from exc
        raise HTTPException(status_code=400, detail=message) from exc


@router.delete("/{project_id}/cover", status_code=204)
def remove_cover(project_id: str, session: Session = Depends(get_session)) -> None:
    try:
        cover_service.clear_cover(session, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{project_id}/cover")
def read_cover(project_id: str, session: Session = Depends(get_session)) -> Response:
    """封面原图。仪表盘拿它当缩略图（本机回环，几 MB 以内不必缩）。"""
    try:
        files = cover_service.cover_files(session, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if files is None:
        raise HTTPException(status_code=404, detail="这个项目没有封面")
    data, media_type, _name = files
    # 封面内容不变的话让浏览器缓存，切项目来回时不重复下载。
    return Response(content=data, media_type=media_type)


@router.get("/{project_id}/ideas")
def list_ideas(project_id: str, session: Session = Depends(get_session)) -> list[dict]:
    return [_idea_out(i) for i in idea_service.list_ideas(session, project_id)]


@router.post("/{project_id}/ideas", status_code=201)
def create_idea(project_id: str, payload: IdeaCreate, session: Session = Depends(get_session)) -> dict:
    return _idea_out(idea_service.create_idea(session, project_id, payload.raw_text, payload.tags))
