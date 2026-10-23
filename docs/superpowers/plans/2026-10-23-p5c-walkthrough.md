# P5c 走查记录：桌面外壳与打包

> 2026-10-23。分支 `worktree-p5c-shell`。走查全程使用临时数据目录，
> **未调用模型**、**未写入作者真实库**。**Inno 安装包未执行**（本机未装）。

## 1. 自动化测试

| 项 | 结果 |
|---|---|
| 后端 | **997 passed**（基线 969，本段新增 28） |
| 前端 | 71 passed（本段未改前端测试） |
| 前端构建 | `pnpm build` 干净 |

## 2. 接口级走查（`scripts/p5c_walkthrough.py`，17 项全过）

| 组 | 覆盖 |
|---|---|
| API | `/api/health` 200；`/api/projects` 是 JSON |
| 根路径 | 200、`text/html`、`<title>StoryForge</title>`、引用 `/assets/*.js` |
| 静态资源 | `/favicon.svg` 200 |
| SPA 深链 | `/read`、`/chapters`、`/write`、`/world`、任意深层路径 全部回落 index.html |
| 未知 API | `/api/definitely-not-a-route`、`/api` 本身、`/API/projects` 全部 404 且**不是 HTML** |
| 缺失的静态文件 | `/chunks/missing.js` → 404（把缺失的 .js 当 HTML 返回 200，浏览器会报「Unexpected token '<'」） |
| 目录穿越 | `/../backend/app/config.py` 拿不到源码 |

## 3. 桌面窗口（真实启动）

`uv run python -m app.desktop`（临时数据目录）：

| 项 | 结果 |
|---|---|
| 后端启动 | `Uvicorn running on http://127.0.0.1:55159`（**端口 0 由系统分配**） |
| 元数据 | `instance.json` = `{"port": 55159, "pid": 137840}` |
| 健康检查 | `GET /api/health` 200 |
| 页面 | `GET /` 200、`/assets/index-*.js` 200、`/assets/*.css` 200、`/favicon.svg` 200 |
| 前端真的在跑 | 窗口内自动发出 `GET /api/projects` 与 `GET /api/settings`，均 200 |
| 单实例 | 第二次启动打印「StoryForge 已经在运行（端口 55159）」，**退出码 1** |
| 陈旧元数据 | 强杀进程后 `instance.json` 残留；`already_running()` 判定为 None 并**顺手清掉文件**，不挡下次启动 |

## 4. 打包（**已实跑**）

`uv run pyinstaller storyforge.spec` → `backend/dist/StoryForge/`，**31 MB**。

| 项 | 结果 |
|---|---|
| 产物自检 | `StoryForge.exe --selftest` → 「自检通过：项目 0 个」，退出码 0 |
| 产物起服务 | `--port 8799` → `/api/health` 200、`/` 200（真的 index.html）、`/read` 200 |
| 静态资源 | `/assets/index-*.js` 200、`/favicon.svg` 200 |
| 数据位置 | 用 `STORYFORGE_DATA_DIR` 指到临时目录，程序目录里没有产生任何数据 |

**打包过程中抓到并修掉的两个真缺陷：**

1. **`uvicorn.Config("app.main:app")` 打包后必失败。** 字符串形式要按名字导入模块，
   打包后的内嵌环境里找不到 —— 实测报 `ERROR: Error loading ASGI app. Could not import module "app.main"`。
   改为直接传 app 对象。
2. **`storyforge.spec` 里 `SPECPATH` 用法错了**：写成 `Path(SPECPATH).parent`，
   而 `SPECPATH` 已经是 spec 所在目录。症状是打包时误报「找不到 frontend/dist/index.html」。

另外把「后端没就绪」的错误文案改准：原先只说「数据目录可能被占用」，而真实原因常常是
启动期模块导入失败 —— 现在提示去看上面 uvicorn 自己的日志。

## 4.1 整支复查修掉的 5 条 Important

| # | 问题 | 修法 | 复验 |
|---|---|---|---|
| 1 | `build.ps1` 的产物自检**根本没检查到** —— `console=False` 的 GUI 程序用 `& $exe` 调用时 PowerShell 不等它结束，`$LASTEXITCODE` 还是上一条命令的 0 | 改用 `Start-Process -Wait -PassThru` 取真正的 `ExitCode` | 复查实测 `& $exe` 43 ms 就返回且退出码是旧的 |
| 2 | **自检查不出它本该查的东西** —— `seed_tools` 在目录缺失时静默返回 0 | 断言工具库必须 25 份、智能体不能为 0 | **实测把产物里的 `tools_lib` 改名后，自检报「应有 25 份，实际 0 份」、退出码 1**；恢复后回到 0 |
| 3 | **构建会把自检跑在作者真实数据目录上** —— 一次打包就在书稿上跑迁移、写备份、播种 | 自检改用系统临时目录，用完删掉 | 建库后 `dispose_engine()` 再 rmtree（Windows 上不 dispose 删不掉），实测无残留 |
| 4 | **单实例锁加得太晚** —— 启动含建库 / 迁移 / 播种要几秒，这期间第二次双击会起第二个后端、第二个 SQLite 写者 | 起后端**之前**用 `O_CREAT\|O_EXCL` 抢一个「正在启动」标记 | 新用例：标记被占时第二次 `run()` 返回 1；崩溃遗留的标记可被接管 |
| 5 | **打包后错误信息全看不见** —— 所有提示走 stderr，资源管理器双击时没有 stderr | `_report()` 同时 print 与 `MessageBoxW`；`STORYFORGE_NO_DIALOG=1` 时只 print（测试与构建脚本不能被模态框挡住） | 打包版自检失败会弹框；构建脚本设了该变量 |

另外修了几条 Minor：`/api` 本身与 `/API/...` 也会回落成页面；缺失的 `.js` 返回 200 HTML
（浏览器报 `Unexpected token '<'`）；`webview.create_window` 移进 try/finally；
spec 里的 `app/agents` 是代码不是数据（多余）；Inno 的 `x64compatible` 需要 6.3+，README 已更正。

---

## 5. 未覆盖 / 遗留

- **Inno 安装包没有真跑**：本机未装 Inno Setup 6，装它属于改系统（作者决定）。
  `packaging/installer.iss` 与 `packaging/README.md` 已就位，作者装好后一条命令即可。
- **打包产物没有在「干净 Windows」上验过**（产品 §8 的完成标志是「干净 Windows 上双击安装即用」）。
  本机验的是「打得出、起得来、页面能开」。
- **`console=False` 时看不到 stderr**：排障要用 `--port N` 在前台跑一次。
- **WebView2 缺失时**只给可读提示，不自动装运行时。
- **只支持 Windows x64**：DPAPI、WebView2、Inno 都是 Windows 的东西。
