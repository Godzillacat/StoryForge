"""同源托管：找到产物、挂上去、深链回落、没有产物时给可读说明。"""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import static_site


def _make_dist(root: Path) -> Path:
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<!doctype html><title>app</title>", encoding="utf-8")
    (root / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (root / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    return root


@pytest.fixture()
def dist(tmp_path, monkeypatch) -> Path:
    root = _make_dist(tmp_path / "dist")
    monkeypatch.setenv("STORYFORGE_FRONTEND_DIST", str(root))
    # 固定候选：否则有 frontend/dist 的机器与没有的机器会走不同分支。
    monkeypatch.setattr(static_site, "_candidates", lambda: [root])
    return root


def _app() -> FastAPI:
    app = FastAPI()

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    static_site.mount_site(app)
    return app


def test_env_override_wins(tmp_path, monkeypatch):
    root = _make_dist(tmp_path / "dist")
    monkeypatch.setenv("STORYFORGE_FRONTEND_DIST", str(root))

    assert static_site.dist_dir() == root


def test_a_dir_without_index_html_is_not_a_build(tmp_path, monkeypatch):
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setattr(static_site, "_candidates", lambda: [empty])

    assert static_site.dist_dir() is None


def test_root_serves_the_built_index(dist):
    client = TestClient(_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "<title>app</title>" in response.text


def test_api_routes_are_not_swallowed(dist):
    client = TestClient(_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_an_unknown_api_path_is_404_json_not_html(dist):
    client = TestClient(_app())

    response = client.get("/api/nope")

    assert response.status_code == 404


def test_deep_links_fall_back_to_index(dist):
    """单页应用的深链（/read、/chapters）直接打开要能用。"""
    client = TestClient(_app())

    response = client.get("/read")

    assert response.status_code == 200
    assert "<title>app</title>" in response.text


def test_real_files_are_served_as_themselves(dist):
    client = TestClient(_app())

    assert client.get("/favicon.svg").text == "<svg/>"


def test_assets_are_served_from_the_assets_mount(dist):
    client = TestClient(_app())

    response = client.get("/assets/app.js")

    assert response.status_code == 200
    assert "console.log" in response.text


def test_path_traversal_cannot_escape_the_dist(tmp_path, dist):
    secret = tmp_path / "secret.txt"
    secret.write_text("do not serve", encoding="utf-8")
    client = TestClient(_app())

    response = client.get("/../secret.txt")

    # 要么 404、要么回落 index —— 绝不能把产物目录外的文件吐出来。
    assert "do not serve" not in response.text


def test_without_a_build_the_api_still_works_and_root_explains(tmp_path, monkeypatch):
    """候选里只有那个不存在的目录 —— 否则会落到仓库里真实存在的 frontend/dist。"""
    monkeypatch.setenv("STORYFORGE_FRONTEND_DIST", str(tmp_path / "missing"))
    monkeypatch.setattr(static_site, "_candidates", lambda: [tmp_path / "missing"])
    app = FastAPI()

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    assert static_site.mount_site(app) is False
    client = TestClient(app)

    assert client.get("/api/health").status_code == 200
    page = client.get("/")
    assert page.status_code == 200
    assert "pnpm build" in page.text
