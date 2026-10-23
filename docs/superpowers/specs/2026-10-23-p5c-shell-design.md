# StoryForge P5c 设计：桌面外壳与打包

> 2026-10-23。P5 的最后一段（P5a 阅读器与朗读、P5b EPUB 精修已完成）。
> 产品 §7.1 / §7.5 / D-15：单实例启动器 → 本机后端 → pywebview 窗口（WebView2）→ 同源加载。

## 1. 阶段定义

### 1.1 这一段要解决什么

到现在为止，StoryForge **只能靠两条开发命令跑起来**：一个终端跑 `uvicorn`，另一个跑
`pnpm dev`，浏览器开 `localhost:5173`。作者画像里写着「有耐心维护设定，没耐心当程序员」——
这不叫能用。

这一段把它变成**双击就开**：

1. **同源托管**：后端直接伺服前端构建产物。今天 `main.py` 里根本没有 `StaticFiles`，
   生产形态下打开后端地址只会看到 404。
2. **桌面外壳**：pywebview 开一个 WebView2 窗口，加载本机后端。
3. **单实例锁**：双击两次不该起两个进程、两份 SQLite 写同一份文件。
4. **动态端口**：不跟别的程序抢 8756。
5. **打包脚本**：PyInstaller onedir + Inno 安装包脚本。

### 1.2 验收标准

1. **同源托管**
   - 后端在能找到前端产物时，把 `/` 与静态资源伺服出去；`/api/*` 仍走 API。
   - 前端产物目录可配置（打包时是 `_MEIPASS`，开发时是 `frontend/dist`）。
   - **找不到产物时**：API 照常工作，`/` 返回一段可读的说明（不是 500，也不是空白）。
   - 单页应用的深链（`/read`、`/chapters` 直接打开）回落到 `index.html`。
2. **启动器**
   - `python -m app.desktop`（或打包后的 EXE）→ 起后端 → 开窗口 → 关闭窗口即退出。
   - **单实例**：第二个实例发现已有实例在跑时，**直接退出**并提示。
   - **动态端口**：从一组空闲端口里挑一个，写进单实例的元数据，窗口用实际端口。
   - 后端起不来时，窗口不打开，给出可读原因（不是静默退出）。
3. **打包**
   - `scripts/build.ps1`：构建前端 → PyInstaller onedir → （可选）Inno 安装包。
   - PyInstaller spec 把 `frontend/dist`、`app/agents`、`app/tools_lib` 一起打进去。
   - **`--selftest` 参数**：打包产物不开窗口跑一次自检（建库、建表、读一次），
     用来在没有 GUI 的环境里验证产物是否完整。
4. **数据位置不变**：打进去的程序本体只读，数据全部在 `%LOCALAPPDATA%\StoryForge\`。
5. **基线**：后端 969 条全绿；前端 71 条全绿、`pnpm build` 干净。
6. **本段不调用模型。**

### 1.3 明确不做

- **真跑 Inno 安装包**：本机没装 Inno Setup 6，装它要改系统。**脚本写好、文档写清，
  不执行**（作者决定）。
- **自动更新、代码签名、崩溃上报** —— 都有各自的生态与成本，一期不做。
- **系统托盘、开机自启、深链协议** —— 不是「双击即用」的必要条件。
- **macOS / Linux** —— 产品定位是 Windows（DPAPI 密钥、WebView2、Inno 都是 Windows）。

## 2. 已定决策

| 决策 | 结论 | 理由 |
|---|---|---|
| 前端产物怎么给 | **后端挂 `StaticFiles`，SPA 回落 `index.html`** | 产品 §7.1 明写「同源托管，不需要 CORS」。今天缺这一环，生产形态根本打不开 |
| 产物目录怎么定位 | **显式候选列表**：环境变量 → `_MEIPASS`（打包）→ `frontend/dist`（开发） | 不要靠 `__file__` 往上猜若干层 —— 打包后那是临时解包目录，猜错就是莫名其妙的 404 |
| 找不到产物时 | **API 正常，`/` 返回说明** | 开发时只跑后端是常态；不该因此让整个应用起不来 |
| 单实例怎么做 | **本机回环端口上的锁文件 + TCP 探测** | 不需要额外的锁库；Windows 上没有好用的跨进程文件锁，而「能否连上元数据端口」是确定的事实 |
| 端口怎么选 | **绑定 0 让系统分配**，再把实际端口写进锁文件 | 硬编码 8756 迟早撞车；让 OS 挑是唯一不会错的做法 |
| 窗口与后端的关系 | **后端跑在独立线程，pywebview 占主线程** | pywebview 必须在主线程；uvicorn 的 `Server` 可以 `run` 在后台线程 |
| 后端起不来的表现 | **捕获异常，打日志，不静默退出** | 「双击没反应」是最难排查的故障 |
| PyInstaller 形态 | **onedir，不用 onefile** | onefile 每次启动要解压到临时目录，几秒的启动白屏；onedir 首启快，且 spec 里能明确列出数据目录 |
| 自检入口 | **`--selftest`** | 打包产物在没有 GUI 的环环境里也要能验；跑一次建库 + 读一次，退出码即结论 |
| Inno 脚本 | **写 `installer.iss` 与文档，不执行** | 本机没装 Inno；装它属于改系统。作者自己跑一次即可 |

## 3. 结构

```
backend/app/desktop.py     启动器：单实例、动态端口、后台线程起 uvicorn、pywebview 窗口
backend/app/static_site.py 前端产物目录定位 + SPA 回落
backend/app/main.py        挂 StaticFiles（在 API 路由之后，避免吞掉 /api）
scripts/build.ps1          前端构建 → PyInstaller
backend/storyforge.spec    PyInstaller spec
packaging/installer.iss    Inno Setup 脚本
packaging/README.md        打包说明（作者怎么跑、产物在哪、装 Inno 的步骤）
```

## 4. 服务设计

### 4.1 静态托管（`app/static_site.py`）

```
dist_dir() -> Path | None          # 候选列表里第一个存在且含 index.html 的
mount_site(app: FastAPI) -> bool   # 挂上了返回 True
```

候选顺序：
1. `STORYFORGE_FRONTEND_DIST` 环境变量
2. `sys._MEIPASS/frontend_dist`（PyInstaller）
3. 仓库内 `frontend/dist`（开发）

挂载方式：
- `/assets` 与其它静态文件走 `StaticFiles`。
- **其余非 `/api` 路径回落 `index.html`** —— 直接用 `StaticFiles(html=True)` 做整目录会
  在深链上 404；`html=True` 只处理目录索引，不处理「任意路径 → index.html」。

### 4.2 启动器（`app/desktop.py`）

```
main() -> int
  --selftest   只跑自检，不开窗口
  --port N     指定端口（调试用）
```

流程：
1. 单实例：读 `%LOCALAPPDATA%\StoryForge\instance.json`（端口 + pid）；能连上就退出。
2. 起 `uvicorn.Server`（端口 0 或指定），在后台线程。
3. 等端口就绪（探测 `/api/health`）。
4. `webview.create_window(..., url=http://127.0.0.1:<port>/)`；`webview.start()`。
5. 退出时停 uvicorn、删元数据。

### 4.3 打包

- `storyforge.spec`：入口 `backend/app/desktop.py`；datas = `frontend/dist` + `app/agents` + `app/tools_lib`。
- `scripts/build.ps1`：`pnpm build` → `uv run pyinstaller storyforge.spec` → 提示 Inno 命令。
- onedir 产物在 `dist/StoryForge/`。

## 5. 测试策略

| 层 | 内容 |
|---|---|
| 静态托管 | 有产物时 `/` 返回 index.html、`/read` 回落、`/api/health` 仍是 JSON；无产物时 `/` 给说明且 API 正常 |
| 产物定位 | 环境变量优先；候选都不存在时返回 None |
| 单实例 | 元数据端口被占用时判定「已在运行」；释放后可再次启动 |
| 自检 | `--selftest` 在临时数据目录里建库、建表、退出码 0 |
| 打包 | **不在本机执行**（Inno 未装）；PyInstaller 能否跑通由实测定 |

## 6. 风险

- **pywebview 在无 WebView2 的机器上起不来** —— 目标系统是 Win10/11，WebView2 随 Edge 预装；
  真缺失时给可读原因（`webview` 会抛，捕获后提示装 WebView2 Runtime）。
- **PyInstaller 打 pywebview** 需要 `pywebview` 的 hidden imports（`webview.platforms.edgechromium` 等）；
  spec 里要显式列出，否则运行时 `ImportError`。
- **端口 0 与 firewal** —— 只绑 127.0.0.1，不触发防火墙提示。
- **打包产物体积** —— onedir 约 60–100 MB（Python + 依赖），可接受。
