"""成品报告与导出。纯读：不写库、不碰 HTTP、不调用模型。"""

from __future__ import annotations

import re
import zipfile
from html import escape
from io import BytesIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditIssue, Chapter, Foreshadow, Project, Scene, Volume
from app.text_stats import count_words

_MEDIA_TYPES = {
    "md": "text/markdown; charset=utf-8",
    "txt": "text/plain; charset=utf-8",
    "epub": "application/epub+zip",
}
_EXTENSIONS = {"md": "md", "txt": "txt", "epub": "epub"}


def _project(session: Session, project_id: str) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise ValueError(f"项目不存在：{project_id}")
    return project


def _ordered_volumes(session: Session, project_id: str) -> list[Volume]:
    return list(
        session.scalars(
            select(Volume)
            .where(Volume.project_id == project_id)
            .order_by(Volume.seq, Volume.created_at)
        )
    )


def _ordered_chapters(session: Session, volume_id: str) -> list[Chapter]:
    return list(
        session.scalars(
            select(Chapter)
            .where(Chapter.volume_id == volume_id)
            .order_by(Chapter.seq, Chapter.created_at)
        )
    )


def _ordered_scenes(session: Session, chapter_id: str) -> list[Scene]:
    return list(
        session.scalars(
            select(Scene)
            .where(Scene.chapter_id == chapter_id)
            .order_by(Scene.seq, Scene.created_at)
        )
    )


def _scene_labels(session: Session, project_id: str) -> dict[str, str]:
    labels: dict[str, str] = {}
    for volume in _ordered_volumes(session, project_id):
        for chapter in _ordered_chapters(session, volume.id):
            for scene in _ordered_scenes(session, chapter.id):
                labels[scene.id] = (
                    f"第{volume.seq + 1}卷 第{chapter.seq + 1}章 场景{scene.seq + 1}"
                )
    return labels


def build_report(session: Session, project_id: str) -> dict:
    project = _project(session, project_id)
    volumes = _ordered_volumes(session, project_id)
    chapters = 0
    scenes = 0
    total_words = 0
    missing: list[dict] = []
    for volume in volumes:
        for chapter in _ordered_chapters(session, volume.id):
            chapters += 1
            for scene in _ordered_scenes(session, chapter.id):
                scenes += 1
                body = (scene.body or "").strip()
                total_words += count_words(scene.body)
                if not body:
                    missing.append(
                        {
                            "volume": volume.name,
                            "chapter": chapter.title,
                            "scene": scene.seq + 1,
                            "goal": scene.goal,
                        }
                    )

    labels = _scene_labels(session, project_id)
    unrecovered: list[dict] = []
    for row in session.scalars(
        select(Foreshadow).where(Foreshadow.project_id == project_id)
    ).all():
        if row.actual_pay_scene_id:
            continue
        if not row.plant_scene_id and not row.plan_pay_scene_id:
            continue
        unrecovered.append(
            {
                "name": row.name,
                "planted": bool(row.plant_scene_id),
                "planted_at": labels.get(row.plant_scene_id or "", ""),
                "planned_pay_at": labels.get(row.plan_pay_scene_id or "", ""),
            }
        )

    open_issues = session.scalars(
        select(AuditIssue).where(
            AuditIssue.project_id == project_id, AuditIssue.status == "open"
        )
    ).all()
    return {
        "project_id": project.id,
        "project_name": project.name,
        "total_words": total_words,
        "volumes": len(volumes),
        "chapters": chapters,
        "scenes": scenes,
        "scenes_without_body": missing,
        "unrecovered_foreshadows": unrecovered,
        "open_audit_issues": sum(1 for row in open_issues if row.check_type == "consistency"),
        "open_logic_issues": sum(1 for row in open_issues if row.check_type == "logic"),
        "exportable": True,
    }


def _book_chapters(session: Session, project_id: str) -> list[tuple[str, str]]:
    """(标题, 正文) 列表；只收有正文的章。"""
    result: list[tuple[str, str]] = []
    for volume in _ordered_volumes(session, project_id):
        for chapter in _ordered_chapters(session, volume.id):
            chunks = [
                (scene.body or "").strip()
                for scene in _ordered_scenes(session, chapter.id)
                if (scene.body or "").strip()
            ]
            if not chunks:
                continue
            title = f"第{volume.seq + 1}卷 {volume.name} · 第{chapter.seq + 1}章 {chapter.title}"
            result.append((title, "\n\n".join(chunks)))
    return result


def build_markdown(session: Session, project_id: str) -> str:
    project = _project(session, project_id)
    parts = [f"# {project.name}"]
    for volume in _ordered_volumes(session, project_id):
        chapters = []
        for chapter in _ordered_chapters(session, volume.id):
            chunks = [
                (scene.body or "").strip()
                for scene in _ordered_scenes(session, chapter.id)
                if (scene.body or "").strip()
            ]
            if not chunks:
                continue
            chapters.append(
                f"### 第{chapter.seq + 1}章 {chapter.title}\n\n" + "\n\n".join(chunks)
            )
        if chapters:
            parts.append(f"## 第{volume.seq + 1}卷 {volume.name}")
            parts.extend(chapters)
    return "\n\n".join(parts).rstrip() + "\n"


_MD_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+")
_MD_QUOTE = re.compile(r"^\s{0,3}>\s?")
_MD_EMPHASIS = re.compile(r"(\*\*|__|\*|_|`)")
_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")


def _strip_markdown(text: str) -> str:
    lines = []
    for line in text.splitlines():
        line = _MD_HEADING.sub("", line)
        line = _MD_QUOTE.sub("", line)
        line = _MD_LINK.sub(r"\1", line)
        line = _MD_EMPHASIS.sub("", line)
        lines.append(line.rstrip())
    return "\n".join(lines)


def build_text(session: Session, project_id: str) -> str:
    project = _project(session, project_id)
    parts = [project.name]
    for volume in _ordered_volumes(session, project_id):
        chapters = []
        for chapter in _ordered_chapters(session, volume.id):
            chunks = [
                (scene.body or "").strip()
                for scene in _ordered_scenes(session, chapter.id)
                if (scene.body or "").strip()
            ]
            if not chunks:
                continue
            chapters.append(
                f"第{chapter.seq + 1}章 {chapter.title}\n\n"
                + "\n\n".join(chunks)
            )
        if chapters:
            parts.append(f"第{volume.seq + 1}卷 {volume.name}")
            parts.extend(chapters)
    return _strip_markdown("\n\n".join(parts)).rstrip() + "\n"


def _paragraphs(text: str) -> list[str]:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    return [
        "<p>" + escape(block).replace("\n", "<br/>") + "</p>" for block in blocks
    ]


def _chapter_xhtml(title: str, text: str) -> str:
    body = "\n".join(_paragraphs(text)) if text.strip() else "<p>（尚无正文）</p>"
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh">\n'
        f"<head><title>{escape(title)}</title></head>\n"
        f"<body><h2>{escape(title)}</h2>\n{body}\n</body>\n</html>"
    )


def build_epub(session: Session, project_id: str) -> bytes:
    project = _project(session, project_id)
    chapters = _book_chapters(session, project_id)
    if not chapters:
        chapters = [(project.name, "")]

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED
        )
        archive.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
            "<rootfiles><rootfile full-path=\"OEBPS/content.opf\" "
            'media-type="application/oebps-package+xml"/></rootfiles>\n'
            "</container>",
        )

        manifest = [
            '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
        ]
        spine = []
        nav_items = []
        for index, (title, text) in enumerate(chapters, start=1):
            name = f"chapter-{index}.xhtml"
            archive.writestr(f"OEBPS/{name}", _chapter_xhtml(title, text))
            manifest.append(
                f'<item id="chapter-{index}" href="{name}" media-type="application/xhtml+xml"/>'
            )
            spine.append(f'<itemref idref="chapter-{index}"/>')
            nav_items.append(f'<li><a href="{name}">{escape(title)}</a></li>')

        archive.writestr(
            "OEBPS/nav.xhtml",
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<!DOCTYPE html>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml" '
            'xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="zh">\n'
            "<head><title>目录</title></head>\n"
            '<body><nav epub:type="toc"><h1>目录</h1><ol>'
            + "".join(nav_items)
            + "</ol></nav></body></html>",
        )
        archive.writestr(
            "OEBPS/content.opf",
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
            'unique-identifier="bookid">\n'
            '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
            f'<dc:identifier id="bookid">{escape(project.id)}</dc:identifier>\n'
            f"<dc:title>{escape(project.name)}</dc:title>\n"
            "<dc:language>zh</dc:language>\n"
            "</metadata>\n"
            "<manifest>\n" + "\n".join(manifest) + "\n</manifest>\n"
            "<spine>\n" + "\n".join(spine) + "\n</spine>\n"
            "</package>",
        )
    return buffer.getvalue()


def build_export(session: Session, project_id: str, fmt: str) -> tuple[bytes, str, str]:
    """返回 (内容, media_type, 扩展名)。"""
    if fmt not in _MEDIA_TYPES:
        raise ValueError(f"不支持的导出格式：{fmt}")
    if fmt == "md":
        return build_markdown(session, project_id).encode("utf-8"), _MEDIA_TYPES[fmt], _EXTENSIONS[fmt]
    if fmt == "txt":
        return build_text(session, project_id).encode("utf-8"), _MEDIA_TYPES[fmt], _EXTENSIONS[fmt]
    return build_epub(session, project_id), _MEDIA_TYPES[fmt], _EXTENSIONS[fmt]
