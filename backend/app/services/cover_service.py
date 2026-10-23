"""项目封面：保存、移除、取路径。

封面是作品资产，落 `project_assets_dir(project_id)/cover.<ext>`，路径记进
`project.cover_path` —— 那一列从 P1a 就在、一直没人读写，与 `architecture.locked`
当初一样是个摆设，这里把它接上。

**按魔数判断格式，不信扩展名**：`cover.exe` 改个名不该被当成图片存进去。
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy.orm import Session

from app import config
from app.db.models import Project

MAX_COVER_BYTES = 4 * 1024 * 1024

# 只收 EPUB 3 的 cover-image 最稳妥的两种；WebP 在部分阅读器上不显示。
_SIGNATURES: tuple[tuple[bytes, str, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "png", "image/png"),
    (b"\xff\xd8\xff", "jpg", "image/jpeg"),
)


def _project(session: Session, project_id: str) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise ValueError(f"项目不存在：{project_id}")
    return project


def detect(data: bytes) -> tuple[str, str] | None:
    """返回 (扩展名, media type)；不认识返回 None。"""
    for signature, extension, media_type in _SIGNATURES:
        if data.startswith(signature):
            return extension, media_type
    return None


def _cover_file(project_id: str, extension: str) -> Path:
    return config.project_assets_dir(project_id) / f"cover.{extension}"


def _existing(session: Session, project_id: str) -> Path | None:
    """`cover_path` 指向的文件真的在才认；用户手工删过就当没有。"""
    project = _project(session, project_id)
    if not project.cover_path:
        return None
    path = Path(project.cover_path)
    return path if path.is_file() else None


def has_cover(session: Session, project_id: str) -> bool:
    return _existing(session, project_id) is not None


def save_cover(session: Session, project_id: str, data: bytes) -> dict:
    project = _project(session, project_id)
    if not data:
        raise ValueError("封面文件是空的")
    if len(data) > MAX_COVER_BYTES:
        raise ValueError(
            f"封面不能超过 {MAX_COVER_BYTES // (1024 * 1024)} MB，这个文件是 "
            f"{len(data) / 1024 / 1024:.1f} MB"
        )
    detected = detect(data)
    if detected is None:
        raise ValueError("封面只支持 PNG 或 JPEG")
    extension, media_type = detected

    target = _cover_file(project_id, extension)
    # 临时文件 + 替换：写到一半断电不会留下半截封面。
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, target)

    # 换成另一种格式时把旧文件删掉，免得两份并存、`cover_path` 指向哪个看运气。
    if project.cover_path:
        previous = Path(project.cover_path)
        if previous != target and previous.is_file():
            previous.unlink(missing_ok=True)

    project.cover_path = str(target)
    session.commit()
    return {"has_cover": True, "size": len(data), "content_type": media_type}


def clear_cover(session: Session, project_id: str) -> None:
    project = _project(session, project_id)
    if project.cover_path:
        path = Path(project.cover_path)
        if path.is_file():
            path.unlink(missing_ok=True)
        project.cover_path = None
        session.commit()


def cover_files(session: Session, project_id: str) -> tuple[bytes, str, str] | None:
    """给 EPUB 用：(图片内容, media type, 包内文件名)；没有封面返回 None。"""
    path = _existing(session, project_id)
    if path is None:
        return None
    data = path.read_bytes()
    detected = detect(data)
    if detected is None:
        return None
    extension, media_type = detected
    return data, media_type, f"cover-image.{extension}"
