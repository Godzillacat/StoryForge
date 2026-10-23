def _create(client) -> dict:
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    volume = client.post(
        f"/api/projects/{project['id']}/volumes", json={"name": "第一卷"}
    ).json()
    chapter = client.post(
        f"/api/volumes/{volume['id']}/chapters", json={"title": "第一章"}
    ).json()
    scene = client.post(
        f"/api/chapters/{chapter['id']}/scenes", json={"goal": "开场"}
    ).json()
    client.put(
        f"/api/scenes/{scene['id']}/body", json={"content": "雨落在旧城。\n\n灯亮着。"}
    )
    return {"project": project, "chapter": chapter, "scene": scene}


def test_export_report(client):
    data = _create(client)

    response = client.get(f"/api/projects/{data['project']['id']}/export/report")

    assert response.status_code == 200
    body = response.json()
    assert body["project_name"] == "雾港"
    assert body["chapters"] == 1
    assert body["scenes"] == 1
    assert body["total_words"] > 0


def test_export_report_missing_project(client):
    assert client.get("/api/projects/nope/export/report").status_code == 404


def test_export_all_formats(client):
    data = _create(client)

    for fmt, media_type, extension in (
        ("md", "text/markdown; charset=utf-8", "md"),
        ("txt", "text/plain; charset=utf-8", "txt"),
        ("epub", "application/epub+zip", "epub"),
    ):
        response = client.get(
            f"/api/projects/{data['project']['id']}/export?format={fmt}"
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == media_type
        disposition = response.headers["content-disposition"]
        assert "attachment" in disposition
        assert f"filename*=UTF-8''" in disposition
        assert extension in disposition
        assert response.content
        if fmt == "md":
            assert response.text.startswith("# 雾港")
        if fmt == "epub":
            assert response.content[:2] == b"PK"


def test_export_rejects_unknown_format(client):
    data = _create(client)

    response = client.get(f"/api/projects/{data['project']['id']}/export?format=pdf")

    assert response.status_code == 400
    assert "不支持的导出格式" in response.json()["detail"]


def test_export_missing_project(client):
    assert client.get("/api/projects/nope/export?format=md").status_code == 404


def test_book_returns_the_whole_text_in_one_request(client):
    data = _create(client)

    response = client.get(f"/api/projects/{data['project']['id']}/book")

    assert response.status_code == 200
    body = response.json()
    assert body["project_name"] == "雾港"
    assert len(body["volumes"]) == 1
    chapters = body["volumes"][0]["chapters"]
    assert [row["title"] for row in chapters] == ["第一章"]
    assert "雨落在旧城。" in chapters[0]["content"]
    assert chapters[0]["word_count"] == body["total_words"]


def test_book_missing_project_is_404(client):
    assert client.get("/api/projects/nope/book").status_code == 404
