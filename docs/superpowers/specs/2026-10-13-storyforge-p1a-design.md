# StoryForge P1a「故事内核」设计文档

> 版本 1.0 · 2026-10-13
>
> 上位依据：`StoryForge-产品设计文档.md` v1.0。本文档只定义 **P1a 垂直切片**的实现设计，不改变上位文档的任何已定决策（§9.1）。冲突时以上位文档为准。

---

## 1. 阶段定义

### 1.1 P1a 在路线图中的位置

上位文档 §8 的 P1 为「架构层闭环」，体量过大、一次做完无法验证。因此拆为三个垂直切片：

| 切片 | 内容 | 状态 |
|---|---|---|
| **P1a 故事内核** | 项目骨架 + 灵感/解析 + 智能体运行时 + 架构推荐并排对比 + 故事圣经 + 调试台 + 模型与费用 | 本文档 |
| P1b 世界观 | 设定条目、人物、关系网、时间线、术语表、规则硬度 | 后续 |
| P1c 章节设计 | 卷 → 章 → 场景卡、节奏曲线、伏笔账本、pywebview 外壳与打包 | 后续 |

每个切片独立 spec → 独立实施计划 → 独立验收。

### 1.2 P1a 验收标准

作者能够完成以下全流程，且全程可编辑、可回退、原始灵感不被覆盖：

1. 新建项目；
2. 在灵感栏输入一段原话，界面明确标注「这段文字 AI 不会改」；
3. 运行灵感解析，得到结构化解析卡（题材、子类型、一句话前提、主角欲望、核心冲突源、情感内核、调性、篇幅预期、可能参考坐标、**它没把握的问题**）；
4. 得到 2–3 套架构推荐，**并排比较**，每套引用解析卡中的具体要素说明适配理由，并给出适配度、风险、篇幅分配；
5. 选定一套，生成「故事圣经 v0」（logline、主题句、幕/卷骨架、主角与对手、结局方向、调性）；
6. 编辑故事圣经并确认，写入项目结构（architecture + act）；
7. 在调试台看到上述每一次运行的**渲染后完整提示词、原始返回、解析结果、token、耗时、花费**。

### 1.3 P1a 明确不做

世界观页、人物卡、关系网、时间线、术语表、卷/章/场景卡、正文生成、润色、一致性审计、逻辑自检、影响面分析、分支、快照、伏笔账本、导出、阅读器、朗读、批量队列、pywebview 外壳、PyInstaller 打包。

这些不是「暂缓实现」，而是**不建表、不建接口、不建页面**，避免空转结构。

---

## 2. 目录结构

```
StoryForge/
├── CLAUDE.md                     # 项目工作指引（由产品设计文档转化）
├── StoryForge-产品设计文档.md      # 上位设计依据
├── docs/superpowers/
│   ├── specs/                    # 设计文档
│   └── plans/                    # 实施计划
├── scripts/
│   ├── dev.ps1                   # 同时起后端与前端
│   └── dev-backend.ps1
├── backend/
│   ├── pyproject.toml            # uv 管理
│   ├── uv.lock
│   └── app/
│       ├── main.py               # FastAPI 装配、路由挂载、静态托管
│       ├── config.py             # 数据目录解析、全局设置读取
│       ├── db/
│       │   ├── base.py           # DeclarativeBase、通用 Mixin
│       │   ├── session.py        # engine、session factory、WAL 设置
│       │   └── models/           # 每个聚合一个文件
│       ├── api/                  # 路由层，只做参数校验与调用 service
│       ├── services/             # 业务编排层
│       ├── runtime/              # ★ 智能体运行时
│       │   ├── context.py        # 槽位收集 + 预算裁剪
│       │   ├── render.py         # 提示词模板渲染
│       │   ├── llm.py            # LLM 适配器（OpenAI 兼容）
│       │   ├── schema.py         # 输出契约校验 / 重试 / 降级
│       │   ├── pricing.py        # token 估算与费用计算
│       │   └── execute.py        # 运行时编排
│       ├── crypto/dpapi.py       # Windows DPAPI 密钥加密
│       ├── agents/               # 默认智能体阵容预置（角色卡 + 提示词）
│       ├── tools_lib/            # 创作工具库内置模板（JSON）
│       └── tests/                # pytest
└── frontend/
    ├── package.json              # pnpm
    ├── vite.config.ts
    ├── tailwind.config.js
    └── src/
        ├── main.tsx / App.tsx
        ├── api/                  # 后端接口封装
        ├── components/           # 通用组件
        ├── pages/                # 五个页面
        └── lib/                  # 纯函数工具（有 vitest 覆盖）
```

**分层约束**：`api` 不写业务逻辑，`services` 不碰 HTTP，`runtime` 不依赖 FastAPI（可被独立测试）。这条约束让运行时能用纯 pytest 覆盖，不需要起服务器。

---

## 3. 运行形态（P1a）

### 3.1 开发期

```
uvicorn app.main:app --port 8756 --reload      (backend/)
pnpm dev                                        (frontend/, 5173, /api 代理到 8756)
```

浏览器访问 `http://127.0.0.1:5173`。

### 3.2 生产形态（P1a 预留，P1c 启用）

后端 `main.py` 已具备托管前端构建产物的能力（同源，无 CORS）。P1c 加入 pywebview 窗口与 PyInstaller 打包时，只需：

- 前端 `pnpm build` → `frontend/dist`；
- 启动器决定动态端口，注入环境变量；
- pywebview 加载 `http://127.0.0.1:<port>`。

因此 **P1a 不引入任何在 P1c 需要推翻的结构**。

### 3.3 数据目录

一律在程序目录之外，按上位文档 §7.5：

```
%LOCALAPPDATA%\StoryForge\
├── storyforge.db          # SQLite（WAL）
├── settings.json          # 全局设置（不含密钥明文）
├── secrets.bin            # DPAPI 加密后的密钥
└── projects/<project_id>/ # 项目资产：封面、导入稿、导出成品
```

开发期可用环境变量 `STORYFORGE_DATA_DIR` 覆盖，便于测试隔离。

---

## 4. 数据模型（P1a 子集）

只建本阶段真正写入的表。所有表带 `id`（UUID 字符串）、`created_at`、`updated_at`。

### 4.1 创作内容

| 表 | 关键字段 |
|---|---|
| `project` | `name`, `genre`, `sub_genre`, `tone`, `target_length`, `writing_lang`, `cover_path`, `logic_check_level` |
| `idea` | `project_id`, `raw_text`（**作者原话，永不覆盖**）, `tags_json`, `parsed_json`, `status` |
| `architecture` | `project_id`, `tool_ref`, `logline`, `theme`, `premise`, `ending_direction`, `locked` |
| `act` | `architecture_id`, `seq`, `name`, `purpose`, `target_word_ratio`, `summary` |
| `tool_template` | `category`, `name`, `definition_json`（骨架表）, `checklist_json`（校验问题清单）, `builtin`, `project_id`（自建时非空） |

### 4.2 智能体

| 表 | 关键字段 |
|---|---|
| `agent` | `name`, `role_label`, `color`, `task_type`, `enabled`, `builtin`, `current_version_id` |
| `agent_version` | `agent_id`, `version_no`, `system_prompt`, `model_binding_json`, `param_profile`, `context_slots_json`, `output_schema_json`, `skills_json`, `trigger_mode`, `note` |
| `generation_run` | `project_id`, `agent_id`, `agent_version_id`, `provider_id`, `model`, `params_json`, `rendered_prompt`, `input_digest`, `raw_output`, `parsed_json`, `structured`（bool）, `prompt_tokens`, `completion_tokens`, `cost_estimate`, `duration_ms`, `status`, `error_json`, `trimmed_json` |

**版本机制**：改提示词不修改 `agent_version` 行，而是插入新版本并把 `agent.current_version_id` 指向它。旧版本保留，可回滚。`generation_run` 永远引用具体的 `agent_version_id`，所以历史运行永远可复现（上位文档 D-03 可追溯、D-06 版本化）。

**关键设计：调试台不建自己的数据。** 调试台是 `generation_run` 的一个只读视图。这兑现上位文档「改完立刻看到效果与代价」，且不需要维护第二套记录。

### 4.3 配置

| 表 | 关键字段 |
|---|---|
| `provider` | `name`, `kind`（预设名或 `custom`）, `base_url`, `api_key_ref`, `enabled`, `priority` |
| `setting` | `key`, `value_json`（全局设置、模型分路、参数档、预算） |

`provider` 表**不存密钥明文**，只存 `api_key_ref`（指向 `secrets.bin` 中的条目名）。密钥读写在 `crypto/dpapi.py` 里统一处理，任何 API 响应只回显屏蔽态（如 `sk-****abcd`）。

### 4.4 不做但预留的字段

`project.logic_check_level` 本阶段只存不用，因为上位文档把它定义在 project 表上、且界面迟早要显示。这是**唯一**一处预留。

---

## 5. 智能体运行时

这是 P1a 的核心，也是整个产品的地基。

### 5.1 编排流程

```
execute(agent_version, project, extra_input) -> generation_run
  ① 槽位收集  按 context_slots_json 从项目态取内容
  ② 预算裁剪  按优先级表裁剪，记录被裁掉了什么
  ③ 提示词渲染  Jinja2 渲染 system_prompt
  ④ 模型调用   LLM 适配器（流式或非流式）
  ⑤ 契约校验   按 output_schema_json 校验 → 失败重试 1 次 → 再失败降级
  ⑥ 落库       generation_run 全量入库
```

### 5.2 槽位与预算（对应上位文档 §5.4）

槽位是一个注册表，每个槽位知道如何从项目态取内容：

| 槽位 key | 内容 | 优先级 | 超预算时 |
|---|---|---|---|
| `project_core` | 项目基本信息、logline、主题句 | 最高 | 永不裁剪 |
| `scene_card` | 当前场景卡（P1a 暂无，槽位保留） | 最高 | 永不裁剪 |
| `full_characters` | 出场人物完整卡（P1a 暂无） | 最高 | 永不裁剪 |
| `story_bible` | 故事圣经摘要 | 高 | 压缩为要点 |
| `architecture` | 幕/卷骨架 | 高 | 压缩为要点 |
| `parsed_idea` | 灵感解析卡 | 高 | 压缩为要点 |
| `raw_idea` | 灵感原话 | 中 | 缩短 |
| `tool_library` | 创作工具库摘要 | 中 | 先减条数再减长度 |
| `style_samples` | 风格样本（P1a 暂无） | 低 | 减到一段 |

**token 预算**：默认值存在 `setting` 里（默认 8000 tokens 用于上下文）。裁剪算法按优先级从低到高依次削减，直到落进预算。裁剪结果写入 `generation_run.trimmed_json`，界面必须明示「这次砍掉了什么」（上位文档 D-09）。

**token 估算**：中英混排按 `ceil(len(text) / 3)` 估算。真实 usage 由模型返回并覆盖估算值。

### 5.3 提示词渲染

用 Jinja2，变量名用英文，形如：

```jinja
你是长篇小说结构顾问。灵感解析卡：{{ parsed_idea }}。可用结构：{{ tool_library }}。
```

槽位内容渲染为文本块注入。渲染后的完整提示词存入 `generation_run.rendered_prompt`，调试台直接展示。**渲染失败不静默**：抛错并让作者看到是哪个变量缺失。

### 5.4 LLM 适配器

只实现 **OpenAI 兼容协议**一套。理由：DeepSeek、Moonshot、智谱、Ollama、LM Studio、自建代理均提供 OpenAI 兼容端点，接入新服务商 = 加一行预设。这直接兑现上位文档 §4.10「内置常见服务商预设 + 支持自定义 OpenAI 兼容地址」。

```
POST {base_url}/chat/completions
  body: { model, messages, temperature, max_tokens, stream }
```

- **非流式**：读 `choices[0].message.content` 与 `usage`。
- **流式**：逐 chunk 推 SSE，累积文本，结束后读取 usage（若服务商在流中不返回 usage，则用估算）。
- **错误分类**：网络错误 / 认证失败 / 限流 / 服务端错误 / 超时，各自映射为可读中文原因。P1a 不做自动换家重试（上位文档 §4.10 的容错在 P3 与模型分路一起做），失败时**保留已收到的片段**，`status = partial`，作者可重试。

### 5.5 输出契约

结构化输出是「AI 产出即可编辑物件」成立的前提（上位文档 §5.5）。

- **校验器**：实现 JSON Schema 的一个实用子集 —— `type`、`properties`、`required`、`items`、`enum`、`array` 长度。不引入重型依赖。
- **容错**：模型返回常带 ` ```json ` 包裹或前后废话，先做提取再解析。
- **重试**：解析或校验失败，把失败原因追加进提示词重试一次。
- **降级**：仍失败则标记 `structured = false`，原始文本存入 `raw_output`，UI 显示为纯文本块并提示「未结构化」，**不阻塞作者**（上位文档 §5.5 与 D-13 的容错精神）。

---

## 6. 前端（P1a 五页）

React + TypeScript + Vite + Tailwind + TipTap。TipTap 用于正文编辑场景，P1a 中用于故事圣经等长文本字段的所见即所得编辑。

| 页面 | 内容 |
|---|---|
| **故事仪表盘** | 项目列表与新建；选中项目后显示体检单雏形：字数（P1a 为 0）、结构完整度（幕是否填满）、最近改动。告警数与节奏曲线留占位。 |
| **灵感与解析** | 灵感栏（作者原话，界面明确标注「这段文字 AI 不会改」）；解析卡字段可逐项编辑；「它没把握的问题」单列成一栏等待作者补充。 |
| **架构推荐** | 2–3 套方案**并排**展示：工具名、引用解析卡要素的理由、适配度、风险、篇幅分配。允许标注杂交方案。选定后生成故事圣经 v0，作者编辑确认后写入 `architecture` 与 `act`。 |
| **智能体工作室** | 角色卡全字段编辑（名称、定位、颜色、任务类型、系统提示、绑定模型、参数档、上下文槽位勾选与排序、输出契约、可调用技能、触发方式、启停）；版本列表与回滚；**调试台**：选智能体 + 输入 → 渲染后提示词 / 原始返回 / 解析结果 / token / 耗时 / 花费。 |
| **模型与费用** | 服务商增删改 + 一键连通性测试 + 自定义 OpenAI 兼容地址；模型分路（架构/章节/正文/润色/审校/逻辑/对话各指定模型）；参数档（严谨/平衡/发散）；费用汇总（按项目、智能体、任务）。 |

**界面密度**：P1a 只做「协作模式」（左树 + 右控制面板），沉浸模式属正文写作，留到 P2。

---

## 7. 测试策略

纯逻辑必须测，UI 不写自动化测试。

**pytest（后端）**：
- 槽位裁剪：优先级顺序正确、预算边界、裁剪记录准确；
- token 估算：中英混排；
- JSON Schema 校验：合法/非法/包裹提取/降级路径；
- 费用计算：usage × 单价，边界与缺失单价；
- DPAPI：加密→解密往返一致；
- 提示词渲染：变量注入、缺失变量报错；
- LLM 适配器：用假 HTTP 传输层测请求构造与错误分类，不打真实网络。

**vitest（前端）**：仅测 `src/lib/` 下的纯整形函数。

**验收**：§1.2 的七步端到端手工走一遍。

---

## 8. 任务拆分

每步可独立验证，按依赖顺序：

| # | 任务 | 验证方式 |
|---|---|---|
| 1 | 仓库骨架 + uv/pnpm 初始化 + 配置与数据目录 | 后端能起、`/api/health` 返回 200；前端 dev 起得来 |
| 2 | 数据库层：engine + WAL + 模型 + 建表 | pytest 建表与 CRUD 通过 |
| 3 | DPAPI 加密模块 | 加解密往返 pytest 通过 |
| 4 | LLM 适配器（OpenAI 兼容，流式 + 非流式 + usage + 错误分类） | 假传输层 pytest 通过 |
| 5 | 上下文组装器（槽位注册表 + 预算 + 裁剪记录） | 裁剪算法 pytest 通过 |
| 6 | 输出契约校验器（Schema 子集 + 提取 + 重试 + 降级） | 校验 pytest 通过 |
| 7 | 运行时编排 + `generation_run` 落库 + SSE 接口 | 用一个假模型跑通一次 run 并落库 |
| 8 | 默认智能体阵容预置（灵感解析、架构师 + 提示词骨架） | 预置数据可在接口中列出 |
| 9 | 创作工具库内置模板（§4.3 表格内容） | 模板可在接口中列出与实例化 |
| 10 | 前端骨架 + 五页 + 接通真实接口 | 手工走查五页 |
| 11 | 端到端验收 | §1.2 七步全部通过 |

---

## 9. 风险与对策（P1a 范围）

| 风险 | 对策 |
|---|---|
| 运行时抽象过早，被后续切片推翻 | 运行时只依赖「槽位注册表 + 项目态只读接口」，P1b/P1c 新增槽位即可，不改编排 |
| 前端五页同时铺开导致进度不可见 | 任务 10 之前，后端全部可用 curl/Swagger 独立验证 |
| 无真实 API Key 时无法验证 | 适配器与编排用假传输层测试；真实调用作为手工验收项，缺失密钥时明确提示 |
| Schema 校验引入重型依赖 | 只实现子集，不引入 jsonschema 库 |
| SQLite 并发写 | 启用 WAL；单进程单用户场景足够，上位文档 D-16 已定 |

---

## 10. 与上位文档的一致性核对

| 上位决策 | P1a 是否遵守 |
|---|---|
| D-01 本机优先 | 是。数据目录在本机，密钥 DPAPI 加密，除模型调用不联网 |
| D-03 可编辑/可追溯/可回退/可锁定 | 可编辑（解析卡、故事圣经）、可追溯（`generation_run`）、可回退（`agent_version` 回滚）；锁定的落点（架构 `locked` 字段）已建，界面在 P1c |
| D-04 内容三级分离 | 是。`idea.raw_text` 永不覆盖，AI 产出存于 `parsed_json` 与 run 的 `raw_output` |
| D-05 故事优先于设定 | P1a 未涉设定，架构推荐页只呈现选项与风险，不替作者裁决 |
| D-06 智能体 = 角色卡 + 管线 | 角色卡全字段已建；管线编排属 P3，P1a 只做单次运行 |
| D-09 上下文 = 槽位 + 预算 + 裁剪并明示 | 是，§5.2 |
| D-14 正文格式 Markdown | 是，故事圣经存 Markdown |
| D-15 桌面外壳 pywebview | 延后到 P1c，但 §3.2 已预留零改动路径 |
| D-16 检索一期只用 SQLite FTS5 | P1a 未涉检索，不引入向量库 |
| D-18 一期只做单版生成 | 是，调试台只做单版生成 + 手动重生成 |
| D-20 智能体与工具库 JSON 导入导出 | 工具库模板已按 JSON 定义；导入导出界面属 P3 |
