# StoryForge P2a 执笔闭环设计文档

> 2026-10-18。P2「生成闭环」的第一段：把「场景卡 → 流式生成正文 → AI 草稿 → diff 采纳 → 已采纳正文与修订快照」打通。
>
> 上位依据：`StoryForge-产品设计文档.md` §3.1（内容三级）、§4.6（写作台）、§5.2（执笔）、§5.3（管线与检查点）、§5.4（上下文组装）、§6（长文工程）、D-03 / D-04 / D-07 / D-09 / D-14 / D-18。
> 本段只做执笔闭环；审校、逻辑自检、状态与伏笔回写、批量生成、导出留给后续切片。

## 1. 阶段定义

### 1.1 为什么先做这一段

P1 已经能把一部作品策划到场景卡，但正文层完全空白：`scene` 没有正文字段，没有草稿、修订、快照表；
`ChatClient.stream()` 在 HTTP 层已写好，却从未接到 API；执笔、审校、逻辑自检三个预置智能体都不存在。
P2 原本一次装下生成、两道检查、状态回写与导出，体量远大于此前任何切片。

按既有教训「切片越大，真实验证越晚」，P2 的第一段只切**最依赖真实模型的执笔链路**：
作者选中一个场景，点「生成正文」，模型分块流式返回，作者可停止、可编辑草稿、可对比旧稿，
采纳后才写入已采纳正文并留下修订快照。两道检查与回写都建立在这条链路之上，等它稳定后再做。

### 1.2 验收标准

1. **迁移**：作者真实库副本启动时，迁移 v4 在存量库上执行一次（自动备份、原数据一条不少），
   再次启动不重复执行；全新库直接是最新结构。
2. **新表**：`scene_draft`、`scene_revision` 由 `create_all` 建出；`scene.body` 列存在。
3. **执笔智能体**：全新库与既有库都能出现「执笔」预置（`task_type=write`）；
   作者可在现有工作室绑定模型、修改提示词与槽位；未绑模型时在发起流式**之前**返回可读中文错误。
4. **上下文预览**：生成前可查看本次将注入的槽位、估算 token 与预算；生成后运行记录里有裁剪说明。
5. **流式生成**：SSE 依次给出 `run` / `delta` / `done`；运行记录落 `status=ok`、完整 `raw_output`、
   token 估算、费用估算与耗时；成功后写入一条 AI 草稿。
6. **中断不丢内容**：作者停止或服务商中途失败时，已生成内容完整保留在运行记录；
   若此前没有草稿，部分内容存为草稿；若已有草稿，不覆盖旧草稿。
7. **采纳**：AI 草稿可编辑、可丢弃；采纳后写入 `scene.body`、生成 `source=ai` 修订、删除草稿；
   采纳后的正文可被 FTS 检索到。
8. **修订**：作者保存正文、恢复旧版都生成新的不可变修订；内容未变化时不产生重复修订；
   修订列表与单条全文可查；恢复本身也留下一条 `source=restore` 修订。
9. **diff**：旧稿与新稿的整场行级 diff 由前端纯函数生成并有单元测试；采纳整份生效。
10. **基线**：后端既有 **381 条测试全绿**并补齐新增测试；前端既有 **18 条**全绿并补齐纯逻辑测试；`pnpm build` 干净。
11. **真实模型复验**：在作者库副本上走通「预览 → 流式生成 → 停止/完成 → 编辑草稿 → diff → 采纳 → 修订 → 检索」；
    不写作者真实库；调用前先确认阿里云百炼免费额度。

### 1.3 明确不做

- **一致性审计、逻辑自检**：两道检查独立切片，本段不建问题表、不调用检查智能体。
- **人物状态推进、伏笔实际回收、章摘要生成**：留给回写切片；本段只落正文与修订。
- **本章剩余场景连续跑、整卷批量、本机队列**：本段只做逐场景手动生成。
- **段落级就地重写与逐块采纳**：本段只做整场 diff + 整份采纳。
- **结果缓存**（场景卡 + 智能体版本 + 模型 + 参数哈希）：留到费用优化切片。
- **风格样本槽位**：`style_samples` 仍返回 `None`，本段用「最近已采纳正文尾部」承担语感。
- **防复读（比喻/句式指纹）**：YAGNI，留后续。
- **锁定、项目快照、场景分支**：属 P4。
- **导出 TXT / EPUB**：不属本段。
- **TipTap**：本段正文用 Markdown 源码编辑；所见即所得留到阅读/精修阶段。
- **模型分路、费用预估、精确 usage**：流式运行用现有估算函数记 token；精确用量留 P3。

## 2. 已定决策

| 决策 | 结论 | 理由 |
|---|---|---|
| P2 切片 | 第一段只做执笔闭环 | 最依赖真实模型，先验证；检查与回写建立在其上 |
| 写作台形态 | 独立 `/write` 页面，三栏 | 与产品文档附录 B 一致；后续检查面板有位置 |
| 正文编辑器 | Markdown 源码 textarea | 无 HTML↔Markdown 往返损失，行级 diff 可靠；TipTap 后置 |
| 生成节奏 | 逐场景手动 | 产品默认节奏；先把流式与采纳跑稳 |
| 采纳粒度 | 整场行级 diff + 整份采纳 | 本段聚焦；逐块采纳后置 |
| 上下文预览 | 生成前只读预览 + 运行后裁剪说明 | 花钱前可见；不做单次手动增删 |
| 修订 | 快照 + 历史列表 + 恢复 | 满足 D-03 可回退，成本可控 |
| 流式用量 | 成功路径用 `estimate_tokens` 估算 | 不改 `ChatClient` 协议，不赌服务商支持 `stream_options` |
| 草稿数量 | 每场景至多一条 | D-18 一期只做单版生成；历史在 `generation_run` 与修订里 |
| 正文状态 | 不扩展 `STATUS_VALUES`；用派生 `has_body` | 状态词表属于规划状态；写没写由正文是否存在判断 |
| 纯文本预置的缺槽位 | 渲染为空串（`allow_missing`） | 执笔的首场可能没有人物、检索结果或前情正文；严格渲染会让它天然跑不起来。结构化预置仍严格报缺变量 |

## 3. 数据模型

### 3.1 `scene.body`（迁移 v4）

```sql
ALTER TABLE scene ADD COLUMN body TEXT
```

- 当前**已采纳正文**，Markdown，可空；空串与 `NULL` 都视为「没有正文」。
- 迁移只加可空列，原地操作，存量数据不受影响。
- 迁移语句**冻结为字面量**，不从模型或常量派生（沿用既有裁定）。

### 3.2 `scene_draft`（新表，`create_all` 建）

```text
id          TEXT PRIMARY KEY
scene_id    TEXT NOT NULL UNIQUE  -- FK scene.id ON DELETE CASCADE
run_id      TEXT                  -- FK generation_run.id ON DELETE SET NULL
content     TEXT NOT NULL DEFAULT ''
created_at  TEXT NOT NULL
updated_at  TEXT NOT NULL
```

- 每个场景至多一条**可编辑 AI 草稿**；`UNIQUE(scene_id)`。
- 重新生成成功时覆盖；作者可编辑草稿内容，`run_id` 仍记录最初来源。
- 草稿是待审材料，不进入正式稿件、不进入 FTS、不影响 `scene.body`（D-04）。

### 3.3 `scene_revision`（新表，`create_all` 建）

```text
id          TEXT PRIMARY KEY
scene_id    TEXT NOT NULL        -- FK scene.id ON DELETE CASCADE
content     TEXT NOT NULL
source      TEXT NOT NULL        -- ai | author | restore
run_id      TEXT                 -- FK generation_run.id ON DELETE SET NULL
note        TEXT DEFAULT ''
created_at  TEXT NOT NULL
```

- 不可变：没有更新接口，只能新增。
- `source=ai`：采纳 AI 草稿；`source=author`：作者保存正文；`source=restore`：恢复旧修订。
- 采纳总是新增一条 `ai` 修订（即使是相同内容，也保留「采纳过」的审计），`run_id` 取自草稿来源；
  作者保存**仅在内容实际变化时**新增，避免历史噪音；恢复**总是**新增一条 `restore` 修订
  （作者显式动作），`note` 记录「恢复自修订 <id>」。

### 3.4 派生规则

- **`has_body`**：`scene.body` 去空白后非空。章节树接口的场景节点加这个派生布尔值，
  写作台据此显示「已写 / 未写」；树里**不返回正文全文**。
- **字数**：后端纯函数 `count_words(text)`，按「非空白字符数」计（中文写作惯例），
  空文本返回 0。用于写作台显示与验收测试，不做章节 / 项目汇总（汇总留给统计切片）。

## 4. 运行时与生成链路

### 4.1 准备阶段（抽取复用，不改既有行为）

现有 `RuntimeService.execute()` 同时做了「解析智能体/版本/服务商/模型/参数」与「组装上下文 + 渲染 + 非流式调用」。
本段把前半段抽成可复用的**准备步骤**，供流式生成共用：

```python
@dataclass(frozen=True)
class PreparedExecution:
    agent: Agent
    version: AgentVersion
    provider: Provider
    model: str
    params: dict
    rendered_prompt: str
    context: ContextBundle
    messages: list[dict]
    client: ChatClient
```

- `RuntimeService.prepare(project_id, agent_id, extra) -> PreparedExecution`：
  读取智能体与当前版本、解析服务商与模型、组装上下文、渲染提示词（按需追加契约说明块）。
- `RuntimeService.execute()` 改为「prepare → 非流式 complete → 落库」，**行为与返回不变**。
- 执笔智能体 `output_schema_json` 为空，因此没有契约说明块，输出按纯文本处理。
- 准备阶段失败（无服务商、无模型、版本丢失）继续抛 `ValueError`，由 API 层译成 400 中文原因。

### 4.2 生成 API 与 SSE 协议

`POST /api/scenes/{scene_id}/generate`

请求体为空（或 `{}`）。成功时返回 `text/event-stream`；准备阶段失败时返回普通 JSON 错误（尚未开始流式）。

事件格式（每个事件 `event:` + 单行 `data:` JSON）：

```text
event: run
data: {"run_id":"...","model":"...","agent":"执笔","estimated_tokens":1234,"trimmed":{"world_context":"压缩为要点"}}

event: delta
data: {"text":"他把伞收起，雨水顺着..."}

event: done
data: {"run_id":"...","status":"ok","prompt_tokens":1200,"completion_tokens":980,"cost_estimate":0.0012,"duration_ms":18400,"chars":980,"draft_id":"..."}

event: error
data: {"run_id":"...","kind":"network","message":"网络中断，已保留 412 字","chars":412}
```

- `run` 事件在流开始前发出，携带运行 id、模型与裁剪信息；它同时充当首字节，避免长时间无响应。
- `delta` 只带正文增量；服务端在发事件前把增量追加到内存缓冲。
- `done` 与 `error` 必须二者其一，且是最后一个事件。
- 流式开始后 HTTP 状态固定为 200，错误通过 `error` 事件表达。

### 4.3 运行记录与生命周期

端点先完成校验与准备（模型解析、上下文组装、提示词渲染），再返回 `StreamingResponse`；
`GenerationRun` 由**流生成器在开头创建并提交**，随后立刻发出 `run` 事件。这样若客户端在
生成器真正开始前就断开，不会留下一条永远停在 `running` 的孤儿记录。

生成开始时创建 `GenerationRun` 并提交：

- `status="running"`（新增状态；既有取值 `ok | partial | error` 不变）；
- 写入 `project_id / agent_id / agent_version_id / provider_id / model / params_json / rendered_prompt / trimmed_json`；
- `raw_output` 初始为空。

流结束时更新同一条记录：

| 结束方式 | `status` | `raw_output` | 草稿处理 |
|---|---|---|---|
| 正常完成 | `ok` | 完整文本 | 覆盖 / 新建草稿 |
| 服务商或网络失败 | 已收文本非空时 `partial`，否则 `error` | 已收文本 | 无草稿则存部分内容；已有草稿不覆盖 |
| 作者停止 / 客户端断开 | `cancelled`（新增状态） | 已收文本 | 同失败路径 |

- 最终写入用**新的数据库会话**（`SessionLocal`），不依赖请求会话在流结束时的生命周期。
- 结束写入封装成幂等的 `finalize_run(run_id, ...)`：若运行已被标记为终态则不再覆盖。
- 客户端断开检测：流循环每收到一块检查 `request.is_disconnected()`；同时在生成器的
  `finally` 中兜底调用 `finalize_run(status="cancelled")`。上游 HTTP 流通过退出
  `async with` 作用域被关闭，避免继续计费。

### 4.4 用量与费用

- 流式路径不请求服务商返回 usage（不改 `ChatClient.stream` 的产物，也不依赖
  `stream_options.include_usage` 的兼容性）。
- `prompt_tokens` 用现有 `estimate_tokens` 对渲染后提示词估算；
  `completion_tokens` 对完整 / 部分文本估算；
  `cost_estimate` 用现有 `pricing` 与角色卡 `prices` 计算。
- 运行记录与界面注明这是**估算值**；精确用量与流式 usage 解析留 P3 费用记账。

### 4.5 执笔预置智能体

在 `DEFAULT_ROSTER` 追加：

| 字段 | 值 |
|---|---|
| `key` | `writer` |
| 名称 / 定位 / 颜色 | 执笔 / 正文 / `#ec4899` |
| `task_type` | `write` |
| 输出契约 | **无**（纯文本 / Markdown 正文） |
| `param_profile` | `balanced` |
| `trigger_mode` | `manual` |
| 上下文槽位 | `project_core`, `story_bible`, `world_context`, `volume_outline`, `chapter_outline`, `timeline`, `scene_card`, `scene_characters`, `related_settings`, `recent_text` |

提示词（写入 `system_prompt`）的要点：

1. 只写当前场景的正文，不写标题、不写章节号、不写解释或创作说明；
2. 严格遵守场景卡的目标、冲突、转折、POV / 人称、故事内时间与目标字数区间；
3. 人物与地点一律使用世界观里的标准名或已有称呼，不新造专有名词；
4. 对话、动作、心理描写按场景卡与章纲的调性展开，写到转折落地即停；
5. 输出 Markdown 正文，段落之间空一行；
6. 不总结、不评论、不返回 JSON。

提示词只使用已注册的槽位变量，不手写英文键；渲染层仍会做槽位一致性护栏。

执笔没有输出契约，且首场可能没有出场人物、检索结果或前情正文。渲染层对**无输出契约的预置**
把缺失槽位当作空串（`allow_missing=True`），避免这类天然可空的内容让准备阶段直接失败；
结构化预置仍严格报缺变量，既有「缺前置材料」的可读错误不受影响。

既有安装：`seed_agents` 在启动时按 `preset_key` / 名称认领，缺失则新建。因此已有库会在下次启动
出现「执笔」；不会改动其他角色卡，也不会自动切换任何版本。

### 4.6 上下文槽位

`SLOT_REGISTRY` 新增三项：

| key | 标签 | 优先级 | 超预算 |
|---|---|---|---|
| `scene_card` | 当前场景卡 | `P_NEVER` | `never` |
| `scene_characters` | 出场人物完整卡 | `P_NEVER` | `never` |
| `recent_text` | 最近已采纳正文 | `P_MID` | `drop` |

`DbSlotSource` 扩展：

- 新增 `_scene()`：从 `extra_slots["scene_id"]` 取场景，并校验其章 / 卷属于当前项目。
- `scene_card()`：输出场景序号、章 / 卷名、目标、冲突、转折、出场人物名、地点名、故事内时间、
  POV、目标字数区间、埋设 / 回收伏笔名、场景状态。人物与地点按 ID 解析名称。
- `scene_characters()`：对 `characters_json` 中属于人物类条目的 ID，输出**完整角色卡**
  （名称、别名与称呼、概述、外貌、性格、欲望、恐惧、弧光类型、能力边界、说话风格、当前状态）。
  非人物 ID、已删除条目忽略。没有任何人物时返回 `None`。
- `recent_text()`：取同一章中 `seq` 小于当前场景、`body` 非空且去空白后非空的场景，
  按 `seq` 倒序取最近 2 场，拼接后**保留尾部**最多 1200 字；没有则返回 `None`。
- `related_settings()` 的检索词：生成场景时用「场景目标 + 冲突 + 转折 + 出场人物名 + 地点名」拼成，
  通过 `extra_slots["search_query"]` 传入；仍取前 8 条条目。
- 生成与上下文预览都会先解析场景 → 章 → 卷，并传入
  `extra_slots = {"scene_id", "chapter_id", "volume_id", "search_query"}`；
  `chapter_outline` / `volume_outline` / `related_settings` 依赖这几个 id。

## 5. 服务与 API

### 5.1 `text_service`

新模块 `backend/app/services/text_service.py`，职责：

- `get_text(session, scene_id) -> TextState`：正文、草稿、字数、修订摘要。
- `save_body(session, scene_id, content, *) -> TextState`：更新 `scene.body`；内容变化时新增 `author` 修订；
  标脏搜索索引。
- `save_draft(session, scene_id, content) -> DraftState`：仅当草稿存在时更新；不存在抛 404 语义错误。
- `discard_draft(session, scene_id) -> None`。
- `adopt_draft(session, scene_id) -> TextState`：要求草稿存在且内容去空白后非空；
  写入 `body`、新增 `source=ai` 修订、删除草稿、标脏索引。
- `list_revisions(session, scene_id)` / `get_revision(...)` / `restore_revision(...)`。
- `start_generation(session, scene_id)`：返回准备结果与已创建的运行记录；供路由使用。
- `finalize_run(run_id, content, status, usage, duration_ms, *, create_draft: bool)`：
  用新会话更新运行并处理草稿；幂等。
- 所有会改 `scene.body` 的路径在提交前调用 `search_service.mark_dirty(session, project_id)`。

### 5.2 正文接口

| 方法与路径 | 请求 | 响应 |
|---|---|---|
| `GET /api/scenes/{id}/text` | — | `TextState` |
| `PUT /api/scenes/{id}/body` | `{"content": "..."}` | `TextState` |
| `PUT /api/scenes/{id}/draft` | `{"content": "..."}` | `DraftState` |
| `DELETE /api/scenes/{id}/draft` | — | `{"ok": true}` |
| `POST /api/scenes/{id}/adopt` | — | `TextState` |
| `GET /api/scenes/{id}/revisions` | — | `[RevisionSummary]` |
| `GET /api/scenes/{id}/revisions/{revision_id}` | — | `RevisionDetail` |
| `POST /api/scenes/{id}/revisions/{revision_id}/restore` | — | `TextState` |
| `GET /api/scenes/{id}/context-preview` | — | `ContextPreview` |

响应形态：

```jsonc
// TextState
{
  "scene_id": "...",
  "body": "……正文……",          // 没有正文时为 null
  "has_body": true,
  "word_count": 1234,
  "draft": {                     // 没有草稿时为 null
    "id": "...",
    "content": "……",
    "run_id": "...",
    "updated_at": "2026-10-18T..."
  },
  "revisions": [RevisionSummary]
}

// RevisionSummary（不含全文）
{
  "id": "...",
  "source": "ai",
  "run_id": "...",
  "note": "",
  "chars": 1234,
  "created_at": "2026-10-18T...",
  "preview": "开头最多 80 字……"
}

// RevisionDetail
{"id":"...","source":"ai","run_id":"...","note":"","content":"……","created_at":"..."}

// ContextPreview
{
  "agent": {"id":"...","name":"执笔","version_no":1},
  "token_budget": 8000,
  "estimated_tokens": 5123,
  "over_budget": false,
  "slots": [
    {"key":"scene_card","label":"当前场景卡","priority":100,"over_budget":"never",
     "text":"……注入内容……","estimated_tokens":420}
  ],
  "trimmed": {"world_context":"压缩为要点"}
}
```

- `slots` 展示的是**裁剪后**实际会注入的内容；被丢弃的槽位 `text` 为 `null` 并出现在 `trimmed` 里。
- 预览不创建运行记录、不调用模型；`related_settings` 可能触发索引重建并按既有文档化行为提交。

### 5.3 错误与状态码

| 情形 | 状态码 | 文案方向 |
|---|---|---|
| 场景不存在 | 404 | 「场景不存在」 |
| 场景所属项目数据损坏（章 / 卷丢失） | 409 | 「场景的章节结构已损坏」 |
| 执笔智能体不存在 / 被停用 / 没有版本 | 400 | 「找不到执笔智能体，请检查智能体工作室」 |
| 未绑定模型 | 400 | 「执笔还没有绑定模型，请先在智能体工作室指定」 |
| 没有可用服务商 | 400 | 「没有可用的服务商……」 |
| 采纳时没有草稿 | 409 | 「当前没有可采纳的草稿」 |
| 草稿内容为空 | 400 | 「草稿为空，不能采纳」 |
| 保存草稿但草稿已不存在 | 404 | 「草稿已被替换或删除，请刷新」 |
| 修订不存在或不属于该场景 | 404 | 「修订不存在」 |
| 生成开始后的网络 / 服务商错误 | 200 + `error` 事件 | 可读中文 + 已保留字数 |

生成端点在返回 `StreamingResponse` 之前完成全部校验与准备（含模型解析、上下文组装、提示词渲染），
因此「未绑模型」等错误不会先花一分钱；运行记录在流生成器开头创建（见 §4.3）。

## 6. 搜索索引

- `_scene_doc` 的 `body` 追加 `scene.body`（已采纳正文）；AI 草稿不入索引。
- `SEARCH_INDEX_VERSION` 从 `1` 升到 `2`，使既有项目的索引在下一次检索时惰性重建。
- 采纳、作者保存、恢复修订都在提交前 `mark_dirty`；其余场景字段写入路径的标脏不变。
- 检索片段可能包含正文句子；标题仍保持「第 X 卷 第 Y 章 场景 Z + 目标」。

## 7. 前端写作台

### 7.1 路由与布局

- `App.tsx` 新增 `/write` 路由与侧栏项「写作台」，放在「章节设计」之后。
- 页面 `frontend/src/pages/Writing.tsx`，根布局沿用 `space-y-*`、slate 暗色与 indigo/emerald/amber 语义色。
- 三栏（宽屏 `grid grid-cols-[240px_minmax(0,1fr)_320px]`，窄屏纵向堆叠）：
  - 左：卷 / 章 / 场景只读树，当前场景高亮；
  - 中：场景卡摘要（可折叠）→ 工具栏 → 正文 / 草稿编辑区 → 生成流 → diff 面板；
  - 右：上下文预览、运行信息、修订历史。

### 7.2 数据与竞态

- 复用 `getChapterTree` 取树；切项目时用请求代际 token 丢弃迟到响应。
- 选中场景后请求 `GET /scenes/{id}/text` 与 `GET /scenes/{id}/context-preview`；
  两者都带场景代际 token，切场景后旧响应不得写状态。
- 生成请求持有 `AbortController`；切场景、切项目、卸载页面、点「停止」都会 abort，
  并作废该次生成的 token，迟到的 SSE 事件一律忽略。
- 未保存的正文 / 草稿在切场景或切项目时用 `window.confirm` 提示，确认后才丢弃本地修改。
- 数据未就绪前显示加载态；空态区分「没选项目」「没选场景」「没正文」三种。

### 7.3 生成流

- 前端新增 `streamSceneGeneration(sceneId, handlers, signal)`：`fetch` POST + `ReadableStream`，
  用纯函数 `lib/sse.ts` 做增量解析（缓冲跨 chunk 的半行与多行 `data:`）。
- 事件处理：
  - `run`：记录 `run_id`、模型、裁剪信息；
  - `delta`：追加到流式缓冲区并滚动到底部；
  - `done`：重新拉取 `text` 与运行信息，进入草稿视图；
  - `error`：显示可读原因与已保留字数，保留流式缓冲区供查看。
- 生成中禁用重复发起与草稿编辑；工具栏显示「生成中…」与「停止」。
- 点「停止」后 abort；随后刷新 `text` 与运行记录，若后端已存部分草稿则显示。

### 7.4 编辑、采纳与 diff

- **两个编辑视图**：「已采纳正文」与「AI 草稿」，各自独立的受控 textarea。
  - 正文视图：`保存正文`（仅在内容变化时调用 `PUT body`）；`取消修改` 还原。
  - 草稿视图：`保存草稿`、`丢弃草稿`、`采纳为正文`。
- 采纳前若有正文，展示整场行级 diff（旧 = `body`，新 = `draft.content`）；
  没有正文时只展示草稿全文与「首次生成」提示。
- diff 由 `lib/diff.ts` 的纯函数生成：按行做最长公共子序列，输出 `same / add / remove` 行数组；
  行数超过 4000 时退化为「整份替换」以免卡顿。diff 面板只读，采纳动作仍是整份。
- 采纳成功：清空草稿视图、刷新正文与修订历史、提示「已采纳，已生成修订快照」。
- 丢弃草稿：`window.confirm` 后调用 DELETE。
- 工具栏实时显示正文字数（来自 `TextState.word_count`）。

### 7.5 修订历史

- 右栏列出 `RevisionSummary`：来源标签（AI 采纳 / 作者保存 / 恢复）、时间、字数、预览。
- 点一条加载全文（`RevisionDetail`）在只读面板展示；「恢复此版本」二次确认后调用 restore。
- 恢复后刷新正文与列表；新修订的来源显示为「恢复」。

### 7.6 纯逻辑下沉

按项目约定「UI 不写自动化测试」，以下逻辑放 `frontend/src/lib/` 并用 vitest 覆盖：

- `sse.ts`：SSE 事件增量解析（跨 chunk、多行 data、空行分隔、未知字段）。
- `diff.ts`：行级 diff、相同行合并、增删标记、超长退化。
- 其余展示与交互留在组件里，不写组件测试。

## 8. 测试策略

### 8.1 后端

| 范围 | 用例 |
|---|---|
| 迁移 v4 | 存量库副本执行一次、自动备份、数据保留、二次启动不重复；全新库直接最新 |
| 模型/服务 | 草稿新建/覆盖/编辑/丢弃；采纳生成 `ai` 修订并清草稿；保存正文未变化不产生修订；恢复生成 `restore` 修订 |
| 字数 | `count_words` 空串、纯空白、中英混排、换行 |
| 槽位 | `scene_card` 内容完整；`scene_characters` 只收人物、完整字段；`recent_text` 取最近两场且保留尾部；缺数据返回 None；优先级/永不裁剪 |
| 执笔预置 | 全新库与既有库都出现 `writer`；当前版本可绑定模型；`output_schema` 为空 |
| 流式 | 假 `ChatClient` 逐块返回：`run/delta/done` 顺序、运行落库 `ok`、草稿写入、token/费用估算 |
| 中断 | 假客户端中途抛错：运行 `partial/error`、已收文本落库、无草稿时存部分、有草稿时不覆盖 |
| 取消 | `finalize_run` 以 `cancelled` 结束且幂等；重复调用不覆盖终态 |
| API | 正文/草稿/采纳/修订/预览的成功与 400/404/409；生成前未绑模型 400 且不创建运行 |
| 检索 | `scene.body` 进入场景文档；采纳后立即可检索；索引版本升到 2 |
| 树 | 场景节点带 `has_body`，不返回正文 |

### 8.2 前端

- `lib/sse.test.ts`：单块、多块拆分、多行 data、`[DONE]` 之外的未知事件、空块。
- `lib/diff.test.ts`：相同文本、纯新增、纯删除、替换、空旧稿、超长退化。
- 既有 18 条纯逻辑测试保持全绿；`pnpm build` 干净。

### 8.3 手工走查

- 临时数据目录 + 假模型跑通 UI 全流程（生成流、停止、编辑、diff、采纳、修订、恢复）。
- 空态、错误态、切项目 / 切场景的中途响应作废。
- 走查清单写入 `docs/superpowers/plans/2026-10-18-p2a-walkthrough.md`。

## 9. 真实模型复验

- **前置**：先确认阿里云百炼 `qwen3.8-flash` 的免费额度余量；不调用额度不明的模型。
- **环境**：用 SQLite 备份 API 把作者真实库复制到临时目录，同时复制 `secrets.bin` 与 `settings.json`
  （含 WAL / SHM），后端用 `STORYFORGE_DATA_DIR=<副本>` 启动；作者原库不写入。
  若副本里没有可写的场景，可在**副本**里补建一个场景与必要的人物 / 设定；原库不动。
- **步骤**：
  1. 副本启动：迁移 v4 执行一次、自动备份；执笔预置出现；
  2. 在工作室内给执笔绑定模型；
  3. 选一个有场景卡的项目，打开写作台，确认上下文预览列出槽位与估算；
  4. 生成一场：观察分块流式到达；再生成一场并在中途停止，确认运行记录保留部分文本；
  5. 编辑草稿 → 查看 diff → 采纳 → 检查正文、修订与字数；
  6. 作者保存一次、恢复一次，确认修订来源；
  7. 用 FTS 检索正文里的一个短句，确认能命中场景；
  8. 记录耗时、token 估算、费用估算与截图 / 控制台报错为 0。
- 复验结束后删除临时副本；在阶段记录里写明调用次数与 token 估算。

## 10. 风险与取舍

| 风险 | 对策 |
|---|---|
| 客户端断开时生成器被取消，数据库写入可能来不及 | 终止逻辑独立为幂等 `finalize_run`，用新会话；在 `finally` 兜底；单测直接覆盖 |
| 流式 token 费用不准 | 明确标注估算；精确 usage 留给 P3；不阻塞写作 |
| 部分内容覆盖旧草稿 | 仅在成功时覆盖草稿；失败 / 取消时保留旧草稿，部分内容留在运行记录 |
| 上下文过长或空槽位导致质量差 | 预览可见、裁剪明示；场景卡与人物卡永不裁剪；其余按既有预算 |
| 既有库没有执笔预置 | `seed_agents` 启动补建；不静默改其他角色卡 |
| 搜索索引旧文档不含正文 | `SEARCH_INDEX_VERSION` 升到 2，惰性重建 |
| 前端长流式请求的竞态 | AbortController + 场景/项目代际 token；迟到事件丢弃 |
| diff 行数过大卡顿 | 超过 4000 行退化为整份替换 |
| 迁移失败导致库半更新 | 沿用框架：每步一个事务、失败拒绝启动、执行前自动备份 |

## 11. 文件结构

### 后端

```text
backend/app/
├── agents/roster.py                  # 追加 writer 预置与提示词
├── api/
│   ├── text.py                       # 新增：正文/草稿/采纳/修订/预览/生成 SSE
│   ├── chapters.py                   # 场景节点补 has_body
│   └── main.py                       # 注册 text 路由
├── db/
│   ├── migrations.py                 # v4：scene.body
│   └── models/
│       ├── chapter.py                # Scene.body
│       └── text.py                   # 新增 SceneDraft / SceneRevision
├── runtime/
│   ├── context.py                    # 三个新槽位注册
│   └── execute.py                    # 抽取可复用的准备步骤（保持行为）
├── services/
│   ├── runtime_service.py            # prepare() 复用
│   ├── slot_source.py                # scene_card / scene_characters / recent_text
│   ├── text_service.py               # 新增：草稿、正文、修订、生成终态
│   └── search_service.py             # 场景文档加 body；索引版本 2
└── text_stats.py                     # count_words 纯函数
```

### 前端

```text
frontend/src/
├── App.tsx                           # /write 路由与侧栏
├── api/client.ts                     # 类型 + streamSceneGeneration
├── pages/Writing.tsx                 # 写作台
├── components/writing/
│   ├── WritingTree.tsx
│   ├── SceneTextView.tsx
│   ├── GenerationStream.tsx
│   ├── DiffPanel.tsx
│   ├── ContextPreview.tsx
│   └── RevisionHistory.tsx
└── lib/
    ├── sse.ts / sse.test.ts
    └── diff.ts / diff.test.ts
```

### 文档

```text
docs/superpowers/
├── specs/2026-10-18-p2a-writing-loop-design.md     # 本文件
├── plans/2026-10-18-p2a-writing-loop.md            # 实施计划（下一步）
├── plans/2026-10-18-p2a-walkthrough.md             # 手工走查清单
└── plans/2026-10-18-p2a-ledger.md                  # 实施账本（归档）
```

## 12. 遗留与后续

本段完成后，P2 剩余的切片：

1. **两道检查**：一致性审计（确定性 + LLM）与逻辑自检（五层、宽松默认、问题清单与四种处理）；
2. **回写**：人物状态逐章推进、伏笔实际回收、章摘要、章节 / 卷状态；
3. **续跑与批量**：本章连续、整卷队列、暂停 / 续跑 / 重试；
4. **导出**：TXT 先行，EPUB 归 P5；
5. **正文增强**：段落级就地重写、逐块采纳、结果缓存、风格样本、防复读、TipTap 精修。

本段刻意留下的已知小项：

- 流式用量为估算值；
- `recent_text` 只取同章最近两场，不做跨章摘要链；
- 一个场景只有一条草稿；多次生成的原始输出仍可在 `generation_run` 中追溯；
- 写作台不做连续生成与队列。
