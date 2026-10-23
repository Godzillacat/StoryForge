"""封面与模板的 HTTP 接口。"""

import pytest

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _project(client, name="雾港") -> dict:
    return client.post("/api/projects", json={"name": name}).json()


def test_upload_and_remove_a_cover(client):
    project = _project(client)

    assert client.get(f"/api/projects/{project['id']}").json()["has_cover"] is False

    response = client.put(
        f"/api/projects/{project['id']}/cover",
        files={"file": ("cover.png", PNG, "image/png")},
    )

    assert response.status_code == 200
    assert response.json()["has_cover"] is True
    assert client.get(f"/api/projects/{project['id']}").json()["has_cover"] is True

    assert client.delete(f"/api/projects/{project['id']}/cover").status_code == 204
    assert client.get(f"/api/projects/{project['id']}").json()["has_cover"] is False


def test_list_projects_reports_has_cover(client):
    project = _project(client)
    client.put(
        f"/api/projects/{project['id']}/cover",
        files={"file": ("cover.png", PNG, "image/png")},
    )

    rows = client.get("/api/projects").json()

    assert rows[0]["has_cover"] is True


def test_a_non_image_is_rejected(client):
    project = _project(client)

    response = client.put(
        f"/api/projects/{project['id']}/cover",
        files={"file": ("cover.png", b"not really a png", "image/png")},
    )

    assert response.status_code == 400
    assert "只支持 PNG 或 JPEG" in response.json()["detail"]


def test_cover_for_a_missing_project_is_404(client):
    response = client.put(
        "/api/projects/nope/cover",
        files={"file": ("cover.png", PNG, "image/png")},
    )

    assert response.status_code == 404


def test_removing_a_cover_that_is_not_there_is_fine(client):
    project = _project(client)

    assert client.delete(f"/api/projects/{project['id']}/cover").status_code == 204


def test_deleting_a_project_removes_its_assets(client):
    from app import config

    project = _project(client)
    client.put(
        f"/api/projects/{project['id']}/cover",
        files={"file": ("cover.png", PNG, "image/png")},
    )
    assets = config.project_assets_dir(project["id"])
    assert assets.is_dir()

    assert client.delete(f"/api/projects/{project['id']}").status_code == 204

    assert not assets.exists()


def test_unknown_template_is_400(client):
    project = _project(client)

    response = client.get(f"/api/projects/{project['id']}/export?format=epub&template=fancy")

    assert response.status_code == 400
    assert "未知的 EPUB 样式模板" in response.json()["detail"]


def test_template_parameter_changes_the_epub(client):
    import zipfile
    from io import BytesIO

    project = _project(client)
    volume = client.post(
        f"/api/projects/{project['id']}/volumes", json={"name": "第一卷"}
    ).json()
    chapter = client.post(
        f"/api/volumes/{volume['id']}/chapters", json={"title": "第一章"}
    ).json()
    scene = client.post(
        f"/api/chapters/{chapter['id']}/scenes", json={"goal": "开场"}
    ).json()
    client.put(f"/api/scenes/{scene['id']}/body", json={"content": "雨落在旧城。"})

    plain = client.get(f"/api/projects/{project['id']}/export?format=epub&template=plain")
    classic = client.get(
        f"/api/projects/{project['id']}/export?format=epub&template=classic"
    )

    assert plain.status_code == 200 and classic.status_code == 200
    plain_css = zipfile.ZipFile(BytesIO(plain.content)).read("OEBPS/style.css")
    classic_css = zipfile.ZipFile(BytesIO(classic.content)).read("OEBPS/style.css")
    assert plain_css != classic_css


@pytest.mark.parametrize("fmt", ["md", "txt"])
def test_template_is_ignored_for_text_formats(client, fmt):
    """MD / TXT 没有样式可言，传了模板也不该报错。"""
    project = _project(client)

    response = client.get(
        f"/api/projects/{project['id']}/export?format={fmt}&template=classic"
    )

    assert response.status_code == 200
