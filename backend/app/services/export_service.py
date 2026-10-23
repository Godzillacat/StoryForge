"""成品报告与导出。纯读：不写库、不碰 HTTP、不调用模型。"""

from __future__ import annotations

import re
import zipfile
from html import escape
from io import BytesIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Architecture,
    AuditIssue,
    Chapter,
    Foreshadow,
    Project,
    ReviewMark,
    Scene,
    SettingEntry,
    Volume,
)
from app.services import foreshadow_service
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
        if not foreshadow_service.is_unrecovered(row):
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
    locked = _locked_counts(session, project_id, volumes)
    review_marks = session.query(ReviewMark).filter_by(project_id=project_id).count()
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
        "locked_counts": locked,
        "review_marks": review_marks,
        "exportable": True,
    }


def _locked_counts(session: Session, project_id: str, volumes) -> dict:
    """锁定对象一览。产品 §4.8 要求成品报告含锁定状态 —— 作者在导出前
    该知道哪些部分是自己钉死的、不会再变。"""
    counts = {
        "architecture": 0,
        "entries": 0,
        "volumes": 0,
        "chapters": 0,
        "scenes": 0,
    }
    arch = session.scalars(
        select(Architecture).where(Architecture.project_id == project_id)
    ).first()
    if arch is not None and arch.locked:
        counts["architecture"] = 1
    counts["entries"] = (
        session.query(SettingEntry)
        .filter_by(project_id=project_id, locked=True)
        .count()
    )
    for volume in volumes:
        if volume.locked:
            counts["volumes"] += 1
        for chapter in _ordered_chapters(session, volume.id):
            if chapter.locked:
                counts["chapters"] += 1
            for scene in _ordered_scenes(session, chapter.id):
                if scene.locked:
                    counts["scenes"] += 1
    return counts


def _chapter_text(session: Session, chapter: Chapter) -> str:
    """章内正文：按场景顺序用空行拼接。**导出与阅读器共用这一份口径。**"""
    return "\n\n".join(
        (scene.body or "").strip()
        for scene in _ordered_scenes(session, chapter.id)
        if (scene.body or "").strip()
    )


def build_book(session: Session, project_id: str) -> dict:
    """整本正文，供阅读器一次性取回。

    **空章也返回**（`content` 为空、`has_body` 为 false）：阅读器要让作者看见
    「这本书还差哪几章」，只列有正文的章会让半本没写的稿子看起来是完整的。
    这与导出**刻意不同** —— 导出是成品，读到哪算到哪；阅读器还要看进度。

    `content` 是 Markdown 原文，渲染交给前端：渲染规则属于展示层，后端不该
    知道「段落怎么画」。
    """
    project = _project(session, project_id)
    volumes: list[dict] = []
    total_words = 0
    written_chapters = 0
    for volume in _ordered_volumes(session, project_id):
        chapters: list[dict] = []
        for chapter in _ordered_chapters(session, volume.id):
            content = _chapter_text(session, chapter)
            words = count_words(content)
            if content:
                written_chapters += 1
            total_words += words
            chapters.append(
                {
                    "id": chapter.id,
                    "seq": chapter.seq,
                    "title": chapter.title,
                    "word_count": words,
                    "has_body": bool(content),
                    "content": content,
                }
            )
        if chapters:
            volumes.append(
                {
                    "id": volume.id,
                    "seq": volume.seq,
                    "name": volume.name,
                    "chapters": chapters,
                }
            )
    return {
        "project_id": project.id,
        "project_name": project.name,
        "total_words": total_words,
        "written_chapters": written_chapters,
        "total_chapters": sum(len(vol["chapters"]) for vol in volumes),
        "volumes": volumes,
    }



def build_markdown(session: Session, project_id: str) -> str:
    project = _project(session, project_id)
    parts = [f"# {project.name}"]
    for volume in _ordered_volumes(session, project_id):
        chapters = []
        for chapter in _ordered_chapters(session, volume.id):
            content = _chapter_text(session, chapter)
            if not content:
                continue
            chapters.append(f"### 第{chapter.seq + 1}章 {chapter.title}\n\n" + content)
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
            content = _chapter_text(session, chapter)
            if not content:
                continue
            chapters.append(f"第{chapter.seq + 1}章 {chapter.title}\n\n" + content)
        if chapters:
            parts.append(f"第{volume.seq + 1}卷 {volume.name}")
            parts.extend(chapters)
    return _strip_markdown("\n\n".join(parts)).rstrip() + "\n"


def _paragraphs(text: str) -> list[str]:
    """段落只出语义标记，样式归 CSS —— 服务端不该知道「缩进几字」。"""
    blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    return ["<p>" + escape(block).replace("\n", "<br/>") + "</p>" for block in blocks]


def _xhtml(title: str, body: str, *, css: bool = True) -> str:
    head = f"<head><title>{escape(title)}</title>"
    if css:
        head += '<link rel="stylesheet" type="text/css" href="style.css"/>'
    head += "</head>"
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<!DOCTYPE html>\n"
        '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh">\n'
        f"{head}\n<body>\n{body}\n</body>\n</html>"
    )


def _chapter_xhtml(title: str, text: str) -> str:
    paragraphs = _paragraphs(text) if text.strip() else ["<p>（尚无正文）</p>"]
    body = f'<h2 class="chapter-title">{escape(title)}</h2>\n' + "\n".join(paragraphs)
    return _xhtml(title, body)


def _volume_xhtml(title: str) -> str:
    return _xhtml(title, f'<h1 class="volume-title">{escape(title)}</h1>')


def _cover_xhtml(image_name: str) -> str:
    # 封面页不带样式表：它只有一张图，任何边距都会让图四周出现白边。
    return _xhtml(
        "封面",
        f'<div class="cover"><img src="{image_name}" alt="封面"/></div>',
        css=False,
    )


def _modified_stamp(project: Project) -> str:
    value = project.updated_at or project.created_at
    if value is None:
        return "1970-01-01T00:00:00Z"
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _book_structure(session: Session, project_id: str) -> list[dict]:
    """整本的层级结构：卷 → 章（只收有正文的章）。

    与 `build_book` / `build_markdown` 共用 `_chapter_text` 的口径，但这里要
    保留卷这一层 —— 导出的目录与扉页都需要它。
    """
    volumes: list[dict] = []
    for volume in _ordered_volumes(session, project_id):
        chapters = []
        for chapter in _ordered_chapters(session, volume.id):
            content = _chapter_text(session, chapter)
            if not content:
                continue
            chapters.append(
                {
                    "title": f"第{chapter.seq + 1}章 {chapter.title}",
                    "content": content,
                }
            )
        if chapters:
            volumes.append(
                {
                    "title": f"第{volume.seq + 1}卷 {volume.name}",
                    "name": volume.name,
                    "chapters": chapters,
                }
            )
    return volumes


def build_epub(
    session: Session,
    project_id: str,
    template: str | None = None,
) -> bytes:
    from app import epub_styles
    from app.services import cover_service

    project = _project(session, project_id)
    css = epub_styles.template_css(epub_styles.normalize_template(template))
    structure = _book_structure(session, project_id)
    if not structure:
        # 还没有正文：仍然出一本合法的空书（带一章占位），作者能打开确认
        # 「确实是空的」，而不是拿到一个连章节都没有、阅读器打不开的文件。
        structure = [
            {
                "title": project.name,
                "name": project.name,
                "chapters": [{"title": project.name, "content": ""}],
            }
        ]

    cover = cover_service.cover_files(session, project_id)

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
        archive.writestr("OEBPS/style.css", css)

        manifest = [
            '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
            '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
            '<item id="css" href="style.css" media-type="text/css"/>',
        ]
        spine: list[str] = []
        nav_volumes: list[str] = []
        ncx_points: list[str] = []
        chapter_no = 0

        if cover is not None:
            data, media_type, name = cover
            archive.writestr(f"OEBPS/{name}", data)
            manifest.append(
                f'<item id="cover-image" href="{name}" media-type="{media_type}" '
                'properties="cover-image"/>'
            )
            manifest.append(
                '<item id="cover" href="cover.xhtml" media-type="application/xhtml+xml"/>'
            )
            archive.writestr("OEBPS/cover.xhtml", _cover_xhtml(name))
            # 封面页永远排第一 —— 阅读器打开先看到它。
            spine.append('<itemref idref="cover" linear="yes"/>')

        volume_no = 0
        for volume in structure:
            if volume["chapters"]:
                volume_no += 1
                name = f"volume-{volume_no}.xhtml"
                archive.writestr(f"OEBPS/{name}", _volume_xhtml(volume["title"]))
                manifest.append(
                    f'<item id="volume-{volume_no}" href="{name}" '
                    'media-type="application/xhtml+xml"/>'
                )
                spine.append(f'<itemref idref="volume-{volume_no}"/>')
                nav_volume = (
                    f'<li><a href="{name}">{escape(volume["title"])}</a><ol>'
                )
            else:
                # 空项目兜底出来的那一卷没有扉页，也不该进目录。
                nav_volume = ""
                name = ""

            chapters_nav: list[str] = []
            for chapter in volume["chapters"]:
                chapter_no += 1
                chapter_name = f"chapter-{chapter_no}.xhtml"
                archive.writestr(
                    f"OEBPS/{chapter_name}", _chapter_xhtml(chapter["title"], chapter["content"])
                )
                manifest.append(
                    f'<item id="chapter-{chapter_no}" href="{chapter_name}" '
                    'media-type="application/xhtml+xml"/>'
                )
                spine.append(f'<itemref idref="chapter-{chapter_no}"/>')
                chapters_nav.append(
                    f'<li><a href="{chapter_name}">{escape(chapter["title"])}</a></li>'
                )
                if name:
                    ncx_points.append(
                        f'<navPoint id="np-{chapter_no}" playOrder="{chapter_no}">'
                        f'<navLabel><text>{escape(chapter["title"])}</text></navLabel>'
                        f'<content src="{chapter_name}"/></navPoint>'
                    )

            if name:
                nav_volumes.append(
                    nav_volume + "".join(chapters_nav) + "</ol></li>"
                )

        archive.writestr(
            "OEBPS/nav.xhtml",
            '<?xml version="1.0" encoding="utf-8"?>\n'
            "<!DOCTYPE html>\n"
            '<html xmlns="http://www.w3.org/1999/xhtml" '
            'xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="zh">\n'
            '<head><title>目录</title><link rel="stylesheet" type="text/css" href="style.css"/></head>\n'
            '<body><nav epub:type="toc" id="toc"><h1>目录</h1><ol>'
            + "".join(nav_volumes)
            + "</ol></nav></body>\n</html>",
        )

        archive.writestr(
            "OEBPS/toc.ncx",
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
            f'<head><meta name="dtb:uid" content="{escape(project.id)}"/></head>'
            f"<docTitle><text>{escape(project.name)}</text></docTitle>"
            f"<navMap>{''.join(ncx_points)}</navMap>"
            "</ncx>",
        )

        metadata_extra = ""
        if cover is not None:
            metadata_extra = '<meta name="cover" content="cover-image"/>\n'
        archive.writestr(
            "OEBPS/content.opf",
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
            'unique-identifier="bookid">\n'
            '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
            f'<dc:identifier id="bookid">{escape(project.id)}</dc:identifier>\n'
            f"<dc:title>{escape(project.name)}</dc:title>\n"
            "<dc:language>zh</dc:language>\n"
            f'<meta property="dcterms:modified">{_modified_stamp(project)}</meta>\n'
            f"{metadata_extra}"
            "</metadata>\n"
            "<manifest>\n" + "\n".join(manifest) + "\n</manifest>\n"
            '<spine toc="ncx">\n' + "\n".join(spine) + "\n</spine>\n"
            "</package>",
        )
    return buffer.getvalue()


def export_filename(session: Session, project_id: str, fmt: str) -> str:
    project = _project(session, project_id)
    if fmt not in _EXTENSIONS:
        raise ValueError(f"不支持的导出格式：{fmt}")
    return f"{project.name}.{_EXTENSIONS[fmt]}"


def build_export(
    session: Session,
    project_id: str,
    fmt: str,
    template: str | None = None,
) -> tuple[bytes, str, str]:
    """返回 (内容, media_type, 扩展名)。

    `template` 只对 EPUB 有意义；MD / TXT 没有样式可言，忽略即可 ——
    不因为一个用不上的参数报错。
    """
    if fmt not in _MEDIA_TYPES:
        raise ValueError(f"不支持的导出格式：{fmt}")
    if fmt == "md":
        return build_markdown(session, project_id).encode("utf-8"), _MEDIA_TYPES[fmt], _EXTENSIONS[fmt]
    if fmt == "txt":
        return build_text(session, project_id).encode("utf-8"), _MEDIA_TYPES[fmt], _EXTENSIONS[fmt]
    return build_epub(session, project_id, template=template), _MEDIA_TYPES[fmt], _EXTENSIONS[fmt]
