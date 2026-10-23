"""EPUB 的结构：样式、卷层级、两级目录。"""

import zipfile
from io import BytesIO

from app.db.models import Chapter, Project, Scene, Volume
from app.services import export_service


def _two_volumes(session) -> Project:
    project = Project(name="雾港")
    session.add(project)
    session.commit()

    first = Volume(project_id=project.id, seq=0, name="起雾")
    second = Volume(project_id=project.id, seq=1, name="退潮")
    session.add_all([first, second])
    session.commit()

    c1 = Chapter(volume_id=first.id, seq=0, title="开端")
    c2 = Chapter(volume_id=first.id, seq=1, title="空章")
    c3 = Chapter(volume_id=second.id, seq=0, title="转折")
    session.add_all([c1, c2, c3])
    session.commit()

    session.add_all(
        [
            Scene(chapter_id=c1.id, seq=0, body="雨落在旧城。"),
            Scene(chapter_id=c2.id, seq=0),  # 没有正文
            Scene(chapter_id=c3.id, seq=0, body="他推开门。"),
        ]
    )
    session.commit()
    return project


def test_style_lives_in_one_css_file(session):
    project = _two_volumes(session)

    archive = zipfile.ZipFile(BytesIO(export_service.build_epub(session, project.id)))

    assert "OEBPS/style.css" in archive.namelist()
    chapter = archive.read("OEBPS/chapter-1.xhtml").decode("utf-8")
    assert 'href="style.css"' in chapter
    # 样式不能内联到章里。
    assert "<style" not in chapter


def test_template_changes_the_css_only(session):
    project = _two_volumes(session)

    plain = zipfile.ZipFile(
        BytesIO(export_service.build_epub(session, project.id, template="plain"))
    )
    classic = zipfile.ZipFile(
        BytesIO(export_service.build_epub(session, project.id, template="classic"))
    )

    assert plain.read("OEBPS/style.css") != classic.read("OEBPS/style.css")
    # 正文内容不随模板变。
    assert plain.read("OEBPS/chapter-1.xhtml") == classic.read("OEBPS/chapter-1.xhtml")


def test_volume_pages_and_spine_order(session):
    project = _two_volumes(session)

    archive = zipfile.ZipFile(BytesIO(export_service.build_epub(session, project.id)))
    names = archive.namelist()

    assert "OEBPS/volume-1.xhtml" in names
    assert "OEBPS/volume-2.xhtml" in names
    opf = archive.read("OEBPS/content.opf").decode("utf-8")
    spine = opf.split("<spine", 1)[1]
    # 卷扉页在它自己的章之前。
    assert spine.index('idref="volume-1"') < spine.index('idref="chapter-1"')
    assert spine.index('idref="chapter-1"') < spine.index('idref="volume-2"')
    assert spine.index('idref="volume-2"') < spine.index('idref="chapter-2"')


def test_nav_is_two_levels(session):
    project = _two_volumes(session)

    archive = zipfile.ZipFile(BytesIO(export_service.build_epub(session, project.id)))
    nav = archive.read("OEBPS/nav.xhtml").decode("utf-8")

    assert "第1卷 起雾" in nav
    assert "第2卷 退潮" in nav
    # 卷是父节点：卷的 <li> 里嵌一层 <ol>。
    assert nav.count("<ol>") == 3  # 外层 + 两个卷各一层
    assert "第1章 开端" in nav


def test_ncx_lists_chapters_for_old_readers(session):
    project = _two_volumes(session)

    archive = zipfile.ZipFile(BytesIO(export_service.build_epub(session, project.id)))
    ncx = archive.read("OEBPS/toc.ncx").decode("utf-8")

    assert "<navMap>" in ncx
    assert "第1章 开端" in ncx
    assert "第1章 转折" in ncx
    opf = archive.read("OEBPS/content.opf").decode("utf-8")
    assert '<spine toc="ncx">' in opf


def test_ncx_is_two_levels_like_the_nav(session):
    """老阅读器只看 ncx —— 它若平铺，两卷里的「第1章」会一模一样地排在一起。"""
    project = _two_volumes(session)

    archive = zipfile.ZipFile(BytesIO(export_service.build_epub(session, project.id)))
    ncx = archive.read("OEBPS/toc.ncx").decode("utf-8")

    assert ncx.count("<navPoint ") == 4  # 两卷 + 两章
    assert ncx.index("第1卷 起雾") < ncx.index("第1章 开端")
    # 章点嵌在卷点里面：卷点关闭标签之前出现章点。
    volume_one = ncx.split('id="np-volume-1"', 1)[1]
    assert 'id="np-1"' in volume_one
    assert volume_one.index('id="np-1"') < volume_one.index("</navPoint>")


def test_ncx_play_order_is_contiguous(session):
    project = _two_volumes(session)

    archive = zipfile.ZipFile(BytesIO(export_service.build_epub(session, project.id)))
    ncx = archive.read("OEBPS/toc.ncx").decode("utf-8")

    orders = [
        int(part.split('"')[0])
        for part in ncx.split('playOrder="')[1:]
    ]
    assert orders == sorted(orders)
    assert orders == list(range(1, len(orders) + 1))


def test_unwritten_chapters_are_skipped(session):
    project = _two_volumes(session)

    archive = zipfile.ZipFile(BytesIO(export_service.build_epub(session, project.id)))
    names = archive.namelist()

    assert "OEBPS/chapter-1.xhtml" in names
    assert "OEBPS/chapter-2.xhtml" in names
    assert "OEBPS/chapter-3.xhtml" not in names
    assert "空章" not in archive.read("OEBPS/nav.xhtml").decode("utf-8")


def test_html_in_the_body_is_escaped(session):
    project = Project(name="雾港")
    session.add(project)
    session.commit()
    volume = Volume(project_id=project.id, seq=0, name="一卷")
    session.add(volume)
    session.commit()
    chapter = Chapter(volume_id=volume.id, seq=0, title="开端")
    session.add(chapter)
    session.commit()
    session.add(Scene(chapter_id=chapter.id, seq=0, body="<script>alert(1)</script>"))
    session.commit()

    archive = zipfile.ZipFile(BytesIO(export_service.build_epub(session, project.id)))
    page = archive.read("OEBPS/chapter-1.xhtml").decode("utf-8")

    assert "&lt;script&gt;" in page
    assert "<script>alert(1)</script>" not in page
