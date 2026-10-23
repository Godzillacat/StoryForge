"""封面：魔数判定、大小上限、保存 / 移除、EPUB 集成。"""

import zipfile
from io import BytesIO

import pytest

from app import config
from app.db.models import Chapter, Project, Scene, Volume
from app.services import cover_service, export_service

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


def _project(session, name="雾港") -> Project:
    project = Project(name=name)
    session.add(project)
    session.commit()
    return project


def test_png_and_jpeg_are_detected_by_magic_number():
    assert cover_service.detect(PNG) == ("png", "image/png")
    assert cover_service.detect(JPEG) == ("jpg", "image/jpeg")


def test_a_renamed_executable_is_not_an_image():
    assert cover_service.detect(b"MZ\x90\x00 definitely an exe") is None


def test_save_writes_the_file_and_records_the_path(session):
    project = _project(session)

    result = cover_service.save_cover(session, project.id, PNG)

    assert result["has_cover"] is True
    assert result["content_type"] == "image/png"
    path = config.project_assets_dir(project.id) / "cover.png"
    assert path.is_file()
    assert path.read_bytes() == PNG
    assert cover_service.has_cover(session, project.id) is True


def test_switching_format_removes_the_old_file(session):
    project = _project(session)
    cover_service.save_cover(session, project.id, PNG)

    cover_service.save_cover(session, project.id, JPEG)

    assert (config.project_assets_dir(project.id) / "cover.jpg").is_file()
    assert not (config.project_assets_dir(project.id) / "cover.png").exists()


def test_non_image_is_rejected(session):
    project = _project(session)

    with pytest.raises(ValueError, match="只支持 PNG 或 JPEG"):
        cover_service.save_cover(session, project.id, b"not an image")


def test_oversized_cover_is_rejected(session):
    project = _project(session)
    big = PNG + b"\x00" * cover_service.MAX_COVER_BYTES

    with pytest.raises(ValueError, match="不能超过"):
        cover_service.save_cover(session, project.id, big)


def test_empty_cover_is_rejected(session):
    project = _project(session)

    with pytest.raises(ValueError, match="是空的"):
        cover_service.save_cover(session, project.id, b"")


def test_missing_project_is_rejected(session):
    with pytest.raises(ValueError, match="项目不存在"):
        cover_service.save_cover(session, "nope", PNG)


def test_clear_removes_the_file_and_the_flag(session):
    project = _project(session)
    cover_service.save_cover(session, project.id, PNG)

    cover_service.clear_cover(session, project.id)

    assert cover_service.has_cover(session, project.id) is False
    assert not (config.project_assets_dir(project.id) / "cover.png").exists()


def test_a_hand_deleted_file_counts_as_no_cover(session):
    """用户手工删过封面文件时，界面不该还显示有封面。"""
    project = _project(session)
    cover_service.save_cover(session, project.id, PNG)
    (config.project_assets_dir(project.id) / "cover.png").unlink()

    assert cover_service.has_cover(session, project.id) is False
    assert cover_service.cover_files(session, project.id) is None


def test_a_corrupted_file_also_counts_as_no_cover(session):
    """文件被换成垃圾字节时，界面与 EPUB 必须说法一致 —— 否则作者看到
    「已设置」，导出的书却没有封面页。"""
    project = _project(session)
    cover_service.save_cover(session, project.id, PNG)
    (config.project_assets_dir(project.id) / "cover.png").write_bytes(b"garbage")

    assert cover_service.has_cover(session, project.id) is False
    assert cover_service.cover_files(session, project.id) is None


def test_a_cover_path_pointing_outside_the_assets_dir_is_ignored(session, tmp_path):
    """库里的路径可能被手工改过或被回滚带回来 —— 它不该让删除操作碰到别的文件。"""
    project = _project(session)
    outside = tmp_path / "somebody-elses.png"
    outside.write_bytes(PNG)
    project.cover_path = str(outside)
    session.commit()

    assert cover_service.has_cover(session, project.id) is False

    cover_service.clear_cover(session, project.id)
    assert outside.exists(), "资产目录之外的文件绝不能被删"


def test_no_temp_file_is_left_behind(session):
    project = _project(session)

    cover_service.save_cover(session, project.id, PNG)

    leftovers = list(config.project_assets_dir(project.id).glob("*.tmp"))
    assert leftovers == []


def _book(session, project) -> None:
    volume = Volume(project_id=project.id, seq=0, name="第一卷")
    session.add(volume)
    session.commit()
    chapter = Chapter(volume_id=volume.id, seq=0, title="开端")
    session.add(chapter)
    session.commit()
    session.add(Scene(chapter_id=chapter.id, seq=0, body="雨落在旧城。"))
    session.commit()


def test_epub_without_a_cover_has_no_cover_page(session):
    project = _project(session)
    _book(session, project)

    data = export_service.build_epub(session, project.id)
    archive = zipfile.ZipFile(BytesIO(data))

    assert "OEBPS/cover.xhtml" not in archive.namelist()
    opf = archive.read("OEBPS/content.opf").decode("utf-8")
    assert 'properties="cover-image"' not in opf
    assert '<meta name="cover"' not in opf


def test_epub_with_a_cover_puts_it_first_in_the_spine(session):
    project = _project(session)
    _book(session, project)
    cover_service.save_cover(session, project.id, PNG)

    data = export_service.build_epub(session, project.id)
    archive = zipfile.ZipFile(BytesIO(data))

    assert "OEBPS/cover-image.png" in archive.namelist()
    assert "OEBPS/cover.xhtml" in archive.namelist()
    opf = archive.read("OEBPS/content.opf").decode("utf-8")
    assert 'properties="cover-image"' in opf
    assert '<meta name="cover" content="cover-image"/>' in opf
    # spine 第一项必须是封面页。
    spine = opf.split("<spine", 1)[1]
    assert spine.index('idref="cover"') < spine.index('idref="volume-1"')


def test_cover_xhtml_points_at_the_real_file(session):
    project = _project(session)
    _book(session, project)
    cover_service.save_cover(session, project.id, JPEG)

    data = export_service.build_epub(session, project.id)
    archive = zipfile.ZipFile(BytesIO(data))

    page = archive.read("OEBPS/cover.xhtml").decode("utf-8")
    assert 'src="cover-image.jpg"' in page
    assert "OEBPS/cover-image.jpg" in archive.namelist()
