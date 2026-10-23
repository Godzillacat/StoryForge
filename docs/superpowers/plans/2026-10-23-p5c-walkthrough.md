# P5c 走查记录：桌面外壳与打包

> 2026-10-23。分支 `worktree-p5c-shell`。走查全程使用临时数据目录，
> **未调用模型**、**未写入作者真实库**。**Inno 安装包未执行**（本机未装）。

## 1. 自动化测试

| 项 | 结果 |
|---|---|
| 后端 | **990 passed**（基线 969，本段新增 21） |
| 前端 | 71 passed（本段未改前端测试） |
| 前端构建 | `pnpm build` 干净 |

## 2. 接口级走查（`scripts/p5c_walkthrough.py`，14 项全过）

| 组 | 覆盖 |
|---|---|
| API | `/api/health` 200；`/api/projects` 是 JSON |
| 根路径 | 200、`text/html`、`<title>StoryForge</title>`、引用 `/assets/*.js` |
| 静态资源 | `/favicon.svg` 200 |
| SPA 深链 | `/read`、`/chapters`、`/write`、`/world`、任意深层路径 全部回落 index.html |
| 未知 API | `/api/definitely-not-a-route` → 404 且**不是 HTML**（不会把 JSON 请求喂成页面） |
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

## 5. 未覆盖 / 遗留

- **Inno 安装包没有真跑**：本机未装 Inno Setup 6，装它属于改系统（作者决定）。
  `packaging/installer.iss` 与 `packaging/README.md` 已就位，作者装好后一条命令即可。
- **打包产物没有在「干净 Windows」上验过**（产品 §8 的完成标志是「干净 Windows 上双击安装即用」）。
  本机验的是「打得出、起得来、页面能开」。
- **`console=False` 时看不到 stderr**：排障要用 `--port N` 在前台跑一次。
- **WebView2 缺失时**只给可读提示，不自动装运行时。
- **只支持 Windows x64**：DPAPI、WebView2、Inno 都是 Windows 的东西。
