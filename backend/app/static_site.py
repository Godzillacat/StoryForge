"""同源托管前端产物。

产品 §7.1：后端与界面同源部署，不需要 CORS。这里负责找到前端构建产物并挂上去。

**产物目录用显式候选列表，不靠 `__file__` 往上猜**：打包后 `__file__` 在
PyInstaller 的临时解包目录里，猜层数必然猜错，猜错的症状是「页面 404 但 API 正常」。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

_MISSING_PAGE = """<!doctype html>
<html lang="zh"><head><meta charset="utf-8"><title>StoryForge</title></head>
<body style="font-family: system-ui, sans-serif; max-width: 40rem; margin: 4rem auto; line-height: 1.7">
<h1>还没有前端产物</h1>
<p>后端已经起来了（<code>/api/health</code> 可用），但没找到前端的构建结果。</p>
<p>开发时先在 <code>frontend/</code> 里跑一次 <code>pnpm build</code>，或者用
<code>STORYFORGE_FRONTEND_DIST</code> 指向产物目录。</p>
<p>开发期也可以继续用 <code>pnpm dev</code>（Vite 会把 <code>/api</code> 代理过来）。</p>
</body></html>
"""


def _candidates() -> list[Path]:
    """候选顺序：环境变量 → 打包目录 → 仓库里的开发产物。"""
    found: list[Path] = []
    override = os.environ.get("STORYFORGE_FRONTEND_DIST")
    if override:
        found.append(Path(override))
    # PyInstaller 解包目录：spec 里把 frontend/dist 放成 frontend_dist。
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        found.append(Path(bundle) / "frontend_dist")
    # 开发：backend/app/static_site.py → 仓库根 → frontend/dist
    found.append(Path(__file__).resolve().parents[2] / "frontend" / "dist")
    return found


def dist_dir() -> Path | None:
    """第一个真的含 `index.html` 的候选；都没有返回 None。"""
    for candidate in _candidates():
        if (candidate / "index.html").is_file():
            return candidate
    return None


def mount_site(app: FastAPI) -> bool:
    """把前端产物挂到 app 上；挂上了返回 True。

    **必须在所有 API 路由注册之后调用** —— catch-all 会把后注册的路由盖掉
    （包括 `/api`）。这里的 catch-all 已经排除了 `/api` 前缀，但顺序仍要守住。
    """
    root = dist_dir()
    if root is None:
        @app.get("/", include_in_schema=False)
        def _missing_site() -> HTMLResponse:
            return HTMLResponse(_MISSING_PAGE)

        return False

    assets = root / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/", include_in_schema=False)
    @app.get("/{full_path:path}", include_in_schema=False)
    def _spa(full_path: str = "") -> FileResponse:
        # API 不该走到这里；真走到了就当不存在，免得把 JSON 请求喂成 HTML。
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="接口不存在")
        target = (root / full_path).resolve()
        # 防目录穿越：解析后的路径必须仍在产物目录内。
        if (
            full_path
            and target.is_file()
            and root.resolve() in target.parents
        ):
            return FileResponse(target)
        # 其余一律回落 index.html —— 单页应用的深链（/read、/chapters）靠这条。
        return FileResponse(root / "index.html")

    return True
