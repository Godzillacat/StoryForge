# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：onedir，把前端产物与内置数据一起带上。

**onedir 不是 onefile**：onefile 每次启动都要解压到临时目录，几秒白屏；
onedir 首启快，且这里能把数据目录一条条写清楚。

构建：在 backend/ 里 `uv run pyinstaller storyforge.spec`
产物：`dist/StoryForge/StoryForge.exe`
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

# `SPECPATH` 是 PyInstaller 注入的 spec 所在目录。用绝对路径，别依赖 cwd。
ROOT = Path(SPECPATH).resolve()  # backend/
REPO = ROOT.parent  # 仓库根

# 前端产物。**必须先在前端跑 pnpm build**；没跑就打包会得到一个只有 API 的空壳。
frontend_dist = REPO / "frontend" / "dist"
if not (frontend_dist / "index.html").is_file():
    raise SystemExit(
        "找不到 frontend/dist/index.html —— 先在 frontend/ 里跑一次 pnpm build 再打包。"
    )

datas = [
    (str(frontend_dist), "frontend_dist"),
    (str(ROOT / "app" / "agents"), "app/agents"),
    (str(ROOT / "app" / "tools_lib"), "app/tools_lib"),
]

# pywebview 的各平台后端是运行时按名字导入的，静态分析看不到。
# 只收 Windows 的 EdgeChromium；把 GTK/Qt 那些一起收进来会白胖几十 MB 且缺 DLL。
hiddenimports = [
    "webview.platforms.edgechromium",
    "webview.platforms.winforms",
    *collect_submodules("uvicorn"),
]

block_cipher = None

a = Analysis(
    [str(ROOT / "app" / "desktop.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # 测试与开发期依赖不进产物。
        "pytest",
        "pytest_asyncio",
        "tkinter",
    ],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="StoryForge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # 双击不弹黑框；--selftest 的输出仍然写得到 stderr
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="StoryForge",
)
