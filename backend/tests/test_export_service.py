import zipfile
from io import BytesIO

import pytest

from app.db.models import (
    AuditIssue,
    Chapter,
    Foreshadow,
    Project,
    Scene,
    Volume,
)
from app.services import export_service
from app.text_stats import count_words


def _seed(session):
    project = Project(name="雾港")
    session.add(project)
    session.commit()
    volume = Volume(project_id=project.id, seq=0, name="第一卷")
    session.add(volume)
    session.commit()
    first = Chapter(volume_id=volume.id, seq=0, title="开端")
    second = Chapter(volume_id=volume.id, seq=1, title="空章")
    session.add_all([first, second])
    session.commit()
    scene = Scene(
        chapter_id=first.id,
        seq=0,
        goal="开场",
        body="# 标题\n\n第一段，**加粗**。\n\n> 引用一句。",
    )
    empty = Scene(chapter_id=first.id, seq=1, goal="未写场景")
    blank_chapter_scene = Scene(chapter_id=second.id, seq=0, goal="空章场景")
    session.add_all([scene, empty, blank_chapter_scene])
    session.commit()

    planted = Foreshadow(
        project_id=project.id, name="失忆的录音带", plant_scene_id=scene.id
    )
    paid = Foreshadow(
        project_id=project.id,
        name="雨夜的灯",
        plant_scene_id=scene.id,
        actual_pay_scene_id=scene.id,
    )
    loose = Foreshadow(project_id=project.id, name="还没安排")
    session.add_all([planted, paid, loose])
    session.add_all(
        [
            AuditIssue(
                project_id=project.id,
                scene_id=scene.id,
                source="rule",
                kind="repetition",
                severity="major",
                fingerprint="rule:1",
                check_type="consistency",
            ),
            AuditIssue(
                project_id=project.id,
                scene_id=scene.id,
                source="llm",
                check_type="logic",
                layer="causality",
                stage="text",
                kind="other",
                severity="major",
                fingerprint="logic:1",
            ),
        ]
    )
    session.commit()
    return project, volume, first, second, scene, empty


def test_report_counts_words_scenes_and_gaps(session):
    project, _volume, _first, _second, scene, empty = _seed(session)

    report = export_service.build_report(session, project.id)

    assert report["project_name"] == "雾港"
    assert report["volumes"] == 1
    assert report["chapters"] == 2
    assert report["scenes"] == 3
    assert report["total_words"] == count_words(scene.body)
    missing_goals = [row["goal"] for row in report["scenes_without_body"]]
    assert "未写场景" in missing_goals
    assert "空章场景" in missing_goals
    assert [row["name"] for row in report["unrecovered_foreshadows"]] == ["失忆的录音带"]
    assert report["open_audit_issues"] == 1
    assert report["open_logic_issues"] == 1
    assert report["exportable"] is True


def test_report_missing_project(session):
    with pytest.raises(ValueError, match="项目不存在"):
        export_service.build_report(session, "nope")


def test_markdown_keeps_order_and_skips_empty_chapters(session):
    project, _volume, _first, _second, _scene, _empty = _seed(session)

    text = export_service.build_markdown(session, project.id)

    assert text.startswith("# 雾港")
    assert "## 第1卷 第一卷" in text
    assert "### 第1章 开端" in text
    assert "第一段，**加粗**。" in text
    assert "第2章 空章" not in text
    assert text.index("第1章 开端") < text.index("第一段")


def test_text_strips_markdown_markers(session):
    project, _volume, _first, _second, _scene, _empty = _seed(session)

    text = export_service.build_text(session, project.id)

    assert text.splitlines()[0] == "雾港"
    assert "第1卷 第一卷" in text
    assert "第1章 开端" in text
    assert "# " not in text
    assert "**" not in text
    assert "> " not in text
    assert "第一段，加粗。" in text
    assert "引用一句。" in text


def test_epub_has_the_required_structure_and_escapes_html(session):
    project, _volume, _first, _second, scene, _empty = _seed(session)
    scene.body = "a < b & c"

    data = export_service.build_epub(session, project.id)

    archive = zipfile.ZipFile(BytesIO(data))
    names = archive.namelist()
    assert names[0] == "mimetype"
    assert archive.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
    assert archive.read("mimetype").decode() == "application/epub+zip"
    assert "META-INF/container.xml" in names
    assert "OEBPS/content.opf" in names
    assert "OEBPS/nav.xhtml" in names
    assert "OEBPS/chapter-1.xhtml" in names

    chapter = archive.read("OEBPS/chapter-1.xhtml").decode("utf-8")
    assert "&lt;" in chapter and "&amp;" in chapter
    assert "<script" not in chapter
    opf = archive.read("OEBPS/content.opf").decode("utf-8")
    assert 'property="dcterms:modified"' in opf


def test_epub_for_empty_project_still_valid(session):
    project = Project(name="空项目")
    session.add(project)
    session.commit()

    data = export_service.build_epub(session, project.id)

    archive = zipfile.ZipFile(BytesIO(data))
    assert "OEBPS/chapter-1.xhtml" in archive.namelist()
    assert "尚无正文" in archive.read("OEBPS/chapter-1.xhtml").decode("utf-8")


def test_build_export_rejects_unknown_format(session):
    project, _volume, _first, _second, _scene, _empty = _seed(session)
    with pytest.raises(ValueError, match="不支持的导出格式"):
        export_service.build_export(session, project.id, "pdf")


def test_build_export_returns_media_types(session):
    project, _volume, _first, _second, _scene, _empty = _seed(session)

    for fmt, media_type, extension in (
        ("md", "text/markdown; charset=utf-8", "md"),
        ("txt", "text/plain; charset=utf-8", "txt"),
        ("epub", "application/epub+zip", "epub"),
    ):
        content, actual_type, actual_ext = export_service.build_export(
            session, project.id, fmt
        )
        assert content
        assert actual_type == media_type
        assert actual_ext == extension


# ---- 锁定与待复核（P4a）----

def test_report_counts_locked_objects(session):
    project, *_rest = _seed(session)
    volume = session.query(Volume).filter_by(project_id=project.id).first()
    chapter = session.query(Chapter).filter_by(volume_id=volume.id, seq=0).first()
    scene = session.query(Scene).filter_by(chapter_id=chapter.id, seq=0).first()
    volume.locked = True
    chapter.locked = True
    scene.locked = True
    session.commit()

    report = export_service.build_report(session, project.id)

    assert report["locked_counts"]["volumes"] == 1
    assert report["locked_counts"]["chapters"] == 1
    assert report["locked_counts"]["scenes"] == 1


def test_report_counts_review_marks(session):
    from app.db.models import ReviewMark

    project, *_rest = _seed(session)
    volume = session.query(Volume).filter_by(project_id=project.id).first()
    session.add(ReviewMark(project_id=project.id, target_type="volume", target_id=volume.id))
    session.commit()

    assert export_service.build_report(session, project.id)["review_marks"] == 1


def test_book_lists_unwritten_chapters_so_the_author_sees_the_shape(session):
    """阅读器要看见「还差哪几章」；只列有正文的章会让半本没写的稿子看起来是完整的。

    与导出**刻意不同** —— 导出是成品，阅读器还要看进度。
    """
    project, _volume, _first, _second, _scene, _empty = _seed(session)

    book = export_service.build_book(session, project.id)
    chapters = book["volumes"][0]["chapters"]

    assert [row["title"] for row in chapters] == ["开端", "空章"]
    blank = chapters[1]
    assert blank["has_body"] is False
    assert blank["content"] == ""
    assert blank["word_count"] == 0
    assert book["written_chapters"] == 1
    assert book["total_chapters"] == 2


def test_book_content_matches_the_markdown_export(session):
    """读到的必须就是导出的那份 —— 两个口径一旦分叉，作者读的就不是成品。"""
    project, _volume, _first, _second, _scene, _empty = _seed(session)

    book = export_service.build_book(session, project.id)
    markdown = export_service.build_markdown(session, project.id)
    written = [row for row in book["volumes"][0]["chapters"] if row["has_body"]]
    content = written[0]["content"]

    assert content in markdown


def test_book_word_count_agrees_with_the_chapter_content(session):
    project, *_ = _seed(session)

    book = export_service.build_book(session, project.id)
    chapters = book["volumes"][0]["chapters"]

    assert book["total_words"] == sum(row["word_count"] for row in chapters)
    assert chapters[0]["word_count"] == count_words(chapters[0]["content"])


def test_book_of_an_empty_project_has_no_volumes(session):
    project = Project(name="空白")
    session.add(project)
    session.commit()

    book = export_service.build_book(session, project.id)

    assert book["volumes"] == []
    assert book["total_words"] == 0


def test_book_of_a_missing_project_raises(session):
    with pytest.raises(ValueError, match="项目不存在"):
        export_service.build_book(session, "nope")
