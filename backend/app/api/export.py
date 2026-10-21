"""成品报告与导出文件。路由层只做错误翻译与响应头。"""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.services import export_service

router = APIRouter(prefix="/api", tags=["export"])


def _missing(exc: ValueError) -> HTTPException:
    message = str(exc)
    if message.startswith("项目不存在"):
        return HTTPException(status_code=404, detail=message)
    return HTTPException(status_code=400, detail=message)


@router.get("/projects/{project_id}/export/report")
def export_report(project_id: str, session: Session = Depends(get_session)) -> dict:
    try:
        return export_service.build_report(session, project_id)
    except ValueError as exc:
        raise _missing(exc) from exc


@router.get("/projects/{project_id}/export")
def export_project(
    project_id: str,
    format: str = "md",
    session: Session = Depends(get_session),
) -> Response:
    try:
        content, media_type, extension = export_service.build_export(
            session, project_id, format
        )
        filename = export_service.export_filename(session, project_id, format)
    except ValueError as exc:
        raise _missing(exc) from exc
    disposition = (
        f"attachment; filename=storyforge.{extension}; "
        f"filename*=UTF-8''{quote(filename)}"
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": disposition},
    )
