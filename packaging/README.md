# StoryForge 打包说明

> 一期只做 **Windows 10/11 x64**。DPAPI 密钥、WebView2、Inno 都是 Windows 的东西。

## 它是什么

```
StoryForge.exe（启动器）
   ├─ 单实例检查（%LOCALAPPDATA%\StoryForge\instance.json）
   ├─ 后台起 Uvicorn（127.0.0.1，端口由系统分配）
   └─ pywebview 开一个 WebView2 窗口，加载 http://127.0.0.1:<port>/
```

后端**同源托管**前端产物（`app/static_site.py`），所以不需要 CORS，也不需要第二个进程。

## 构建

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build.ps1
```

它做三件事：

1. `frontend/` 里 `pnpm build`
2. `backend/` 里 `uv run pyinstaller storyforge.spec`
3. 跑一次 `StoryForge.exe --selftest` 验产物完整

产物：`backend/dist/StoryForge/StoryForge.exe`（整个 `StoryForge\` 目录要一起分发）。

> `--selftest` 会建库、建表、读一次项目列表。它抓的是「数据文件没打进去」这类问题 ——
> 例如 `app/agents` / `app/tools_lib` 漏了，自检会当场失败，而不是等作者双击才发现首页空白。

## 安装包（需要先装 Inno Setup 6）

**本仓库不自动跑这一步** —— 装 Inno Setup 属于改系统，由你决定。

1. 装 Inno Setup 6：<https://jrsoftware.org/isdl.php>
2. 先跑一次上面的 `build.ps1`
3. 在仓库根执行：

```powershell
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\installer.iss
```

产物：`packaging/Output/StoryForge-Setup-0.1.0.exe`。

## 数据在哪

**永远不在程序目录里。**

| 东西 | 位置 |
|---|---|
| 数据库 | `%LOCALAPPDATA%\StoryForge\storyforge.db` |
| 密钥 | `%LOCALAPPDATA%\StoryForge\secrets.bin`（DPAPI 加密） |
| 设置 | `%LOCALAPPDATA%\StoryForge\settings.json` |
| 项目资产（封面等） | `%LOCALAPPDATA%\StoryForge\projects\<项目 id>\` |

所以：

- 程序可以装在只读目录（`Program Files`）里。
- **卸载不会删掉你的书稿** —— 安装器只清程序目录。
- 开发期可以用 `STORYFORGE_DATA_DIR` 指到别处。

## 排障

| 现象 | 原因与处理 |
|---|---|
| 双击没反应 | 多半是已有实例在跑。看 `%LOCALAPPDATA%\StoryForge\instance.json`；关掉旧进程再试 |
| 窗口空白 | 前端产物没打进去。跑 `StoryForge.exe --selftest` 看不出这个（它只验后端）；用 `--port 8756` 起一次，浏览器开 `http://127.0.0.1:8756/` 看是否报「还没有前端产物」 |
| 提示 WebView2 缺失 | 装 Microsoft Edge WebView2 Runtime（Win10/11 一般自带） |
| 后端 30 秒没就绪 | 数据目录被占用或损坏。看控制台日志；必要时备份并重命名 `%LOCALAPPDATA%\StoryForge\` |

## 调试

```powershell
# 固定端口起一次（能看到后端日志，不开窗口的镜像环境也适用）
backend\dist\StoryForge\StoryForge.exe --port 8756

# 开发期直接用 Python
cd backend
uv run python -m app.desktop
```
