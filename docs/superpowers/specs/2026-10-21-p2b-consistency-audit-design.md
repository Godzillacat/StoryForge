# StoryForge P2b 一致性审计设计文档

> 2026-10-21。P2 的第二段：把「已采纳正文 → 规则检查 + LLM 语义审计 → 问题清单 → 作者处理状态」打通。
>
> 上位依据：`StoryForge-产品设计文档.md` §4.7（两道检查）、§5.3（管线与人工检查点）、§6（长文工程）、D-10 / D-13。
> 本段只做一致性审计；逻辑自检、状态与伏笔回写、批量生成、导出留给后续切片。

## 1. 阶段定义

### 1.1 为什么先做这一段

P2a 已经能把场景卡写成正文、采纳并留下修订，但「写出来的东西有没有和设定打架」还没有任何检查。产品设计把检查拆成两道：一致性审计问「有没有写错」，逻辑自检问「讲不讲得通」。前者的输入已经齐全（已采纳正文、设定条目、人物卡、术语、时间线），而且规则层可以完全离线验证；后者更主观、体量更大。

因此这一段先做**一致性审计**：规则层先给出确定性问题，LLM 层做「正文与设定/人物卡冲突」的语义比对，问题统一落到同一张表，作者逐条处理。逻辑自检复用这一段的问题模型与处理界面，但不在本段实现。

### 1.2 验收标准

1. **数据**：`audit_issue` 由 `create_all` 建出（不新增迁移）；删除场景级联删除问题，删除目标条目把 `target_entry_id` 置空。
2. **槽位**：`scene_text`（当前已采纳正文）注册为 `P_NEVER`；无正文返回 `None`；只在审校预置中使用。
3. **规则层**：对已采纳正文做三项确定性检查 —— 重复句、人物称呼歧义、场景出场人物未被提及；不需要模型；每条带稳定指纹。
4. **LLM 层**：新增「审校」预置（`task_type=continuity`），输出结构化问题；模型/服务商不可用或解析失败时**不阻塞**，仍返回规则层结果并给出可读警告。
5. **问题生命周期**：新一次审校把旧的 `open` 问题标为 `superseded`；`exception` 按指纹抑制后续重复上报；`resolved` 记录处理方式（改故事/改设定/改人物）；`exception` 记录为特例。
6. **API**：`POST /api/scenes/{id}/audit` 运行审校；`GET /api/scenes/{id}/audit` 取当前 open 问题与上次审校时间；`PATCH /api/audit/issues/{id}` 记录处理。无正文 400、场景不存在 404、问题不存在 404、非法处理方式 400。
7. **前端**：`/write` 有「审校」入口与问题面板；规则层与 LLM 层问题可区分；四种处理只记录状态并跳转，**不自动改稿**；LLM 跳过/失败时显示警告。
8. **基线**：后端既有 **430 条测试全绿**并补齐新增测试；前端既有 **30 条**全绿，`pnpm build` 干净。
9. **真实模型复验**：在作者库副本上走通「采纳正文 → 审校 → 结构化问题 → 处理/特例 → 再次审校不重复上报」；不写作者真实库；调用前确认阿里云百炼免费额度。

### 1.3 明确不做

- **逻辑自检**（五层、宽松默认、四种处理）—— 下一段；本段只复用问题模型与处理界面。
- **生成后自动审校** —— 本段手动触发；自动时机留到后续（见 §2 的决定）。
- **一键应用修改** —— 不改设定/人物/正文；只记录状态与跳转。
- **时间线倒退、表外新词、禁用词** —— 见 §4.3 的数据限制说明；本段显式延后，不静默省略。
- **草稿审校** —— 只审已采纳正文；草稿不是正式稿。
- **问题历史浏览、批量处理、按项目汇总** —— 本段只保留当前 open 问题与数据库行；历史留在 `audit_issue` 里，暂不做界面。
- **FTS 索引问题**、**导出/批量**、**锁定/快照** —— 不属本段。

## 2. 已定决策

| 决策 | 结论 | 理由 |
|---|---|---|
| 触发时机 | **采纳后手动** | 控制成本；审的是正式稿而不是草稿。产品文档的「生成后自动」留到后续。 |
| 切片范围 | 规则层 + LLM 层一次做完 | 规则层离线可测；LLM 层是本段的模型验证点，不能推后。 |
| 规则层范围 | 重复句、称呼歧义、出场人物未被提及 | 现有数据能可靠支撑；其余三项缺乏可解析数据或分词能力，显式延后。 |
| 问题状态 | `open` / `resolved` / `exception` / `superseded` | 只记录处理状态，不自动改稿。 |
| 特例抑制 | 按 `scene_id + fingerprint` 匹配已有 `exception` | 作者接受为特例后，后续审校不重复上报同一条。 |
| 规则层无模型 | 永远执行 | 没有模型也能用；LLM 层失败只降级为警告。 |
| LLM 任务类型 | 复用 `continuity` | 已在 `TASK_TYPES` 中登记，避免新增词表；逻辑自检保留 `logic_check`。 |
| 问题表 | 新建 `audit_issue`，`create_all` 建表 | 新表不归迁移；迁移只改已有表。 |
| 问题展示 | 当前 open 问题 + 上次审校时间 | 历史行保留但不做历史界面；保持本段简单。 |
| 跳转 | `?entry=<id>` 到世界观页 | 「改设定/改人物」跳到对应条目；没有目标就跳列表。 |

## 3. 数据模型

### 3.1 `audit_issue`（新表，`create_all` 建）

```text
id              TEXT PRIMARY KEY
project_id      TEXT NOT NULL        -- FK project.id ON DELETE CASCADE
scene_id        TEXT NOT NULL        -- FK scene.id ON DELETE CASCADE
run_id          TEXT                 -- FK generation_run.id ON DELETE SET NULL
source          TEXT NOT NULL        -- rule | llm
kind            TEXT NOT NULL        -- repetition | alias | setting | character | timeline | term | other
severity        TEXT NOT NULL        -- critical | major | minor
quote           TEXT NOT NULL DEFAULT ''
rule_ref        TEXT NOT NULL DEFAULT ''
explanation     TEXT NOT NULL DEFAULT ''
reader_impact   TEXT NOT NULL DEFAULT ''
options_json    JSON NOT NULL DEFAULT []
target_entry_id TEXT                 -- FK setting_entry.id ON DELETE SET NULL
fingerprint     TEXT NOT NULL        -- 稳定指纹，用于特例抑制与去重
status          TEXT NOT NULL DEFAULT 'open'  -- open | resolved | exception | superseded
resolution      TEXT                 -- story | setting | character | exception | NULL
created_at      TEXT NOT NULL
updated_at      TEXT NOT NULL
```

索引：`project_id`、`scene_id`、`status`、`fingerprint`。

- 一条问题只属于一个场景；项目用于删除级联与后续汇总。
- `run_id` 指向 LLM 审计那次运行；规则层问题为 `NULL`。
- `options_json` 是 2–3 条修正方向（字符串数组），不自动执行。
- `target_entry_id` 只在能可靠映射到设定条目时填写；LLM 用名称/别名精确匹配，匹配不到就是 `NULL`。
- `fingerprint` 规则见 §4.4；特例与去重都以它为准。

### 3.2 词表与归一化

新增 `backend/app/audit_types.py`，定义一次、其余处投影：

```python
AUDIT_KINDS = {
    "repetition": "重复",
    "alias": "称呼",
    "setting": "设定",
    "character": "人物",
    "timeline": "时间线",
    "term": "术语",
    "other": "其他",
}

AUDIT_SEVERITIES = {
    "critical": "致命",
    "major": "严重",
    "minor": "提示",
}

AUDIT_SOURCES = {"rule": "规则", "llm": "LLM"}
```

- `normalize_kind(value)`：接受中文标签或英文键，未知归 `other`，不报错。
- `normalize_severity(value)`：接受中英文，未知归 `minor`，不报错。
- `normalize_resolution(value)`：只接受 `story` / `setting` / `character` / `exception`，其余抛 `ValueError`（这是作者显式动作，不该静默猜）。
- 序列化时同时返回 key 与中文 label（`kind_label` / `severity_label` / `source_label`），前端不再维护第二份映射。

## 4. 规则层

新增 `backend/app/audit_rules.py`，纯函数、不碰数据库、不碰 HTTP。

### 4.1 输入

```python
run_rule_checks(
    body: str,
    terms: list[dict],            # world_service.list_terms 的投影
    scene_character_ids: list[str],
    entries: dict[str, SettingEntry],  # id -> 条目，用于解析人物名与别名
) -> list[RuleIssue]
```

`RuleIssue` 是 dataclass：`kind / severity / quote / rule_ref / explanation / reader_impact / options / fingerprint / target_entry_id`。

### 4.2 三项检查

1. **重复句**
   - 按 `。！？!?…` 与换行切句，去空白；只看规范化后长度 ≥ 12 的句子。
   - 同一句出现第 2 次起各报一条；`kind=repetition`，长度 ≥ 20 记 `major`，否则 `minor`。
   - `quote` 为原句，`rule_ref` 为「重复句」，`options` 为删掉/改写/确认有意复沓。
   - 指纹：`rule:repetition:<sha1(规范化句子)>`。

2. **人物称呼歧义**
   - 从 `terms` 中取 `type == "character"` 的 form（名字 + 别名）；同一 form 对应 >1 个条目即为歧义。
   - 只在正文实际出现该 form 时上报；`kind=alias`，`minor`，`target_entry_id=None`。
   - `rule_ref` 列出共用该称呼的人物名；`options` 为换专属称呼/改用本名/接受为特例。
   - 指纹：`rule:alias:<form>`。

3. **出场人物未被提及**
   - 对 `scene_character_ids` 中每个人物，若正文里既没有其名字、也没有任何别名，报一条。
   - `kind=alias`，`minor`，`target_entry_id` 为该人物；文案明确「可能用了代词，请人工确认」。
   - `options` 为确认是否漏写/补充称呼/接受为特例。
   - 指纹：`rule:unmentioned:<entry_id>`。

### 4.3 显式延后

- **时间线倒退**：`scene.story_time` 与 `timeline_event.story_time` 都是自由文本，且场景与时间线事件没有关联；没有可靠解析就不能做确定性判断。
- **表外新词**：中文没有分词器；引号/拉丁词的启发式会把对白和常见技术词误报。等术语白名单查找表或分词方案确定后再做。
- **禁用词**：项目没有禁用词表，也没有录入入口；不在本段新增一套无界面的数据。

这三项会记入 CLAUDE.md §8 的变更记录与阶段遗留，而不是当作已完成。

### 4.4 指纹与去重

- 规则层：按上面的前缀生成，稳定、不依赖时间或行号。
- LLM 层：`llm:<kind>:<rule_ref>:<sha1(quote)>`；`quote` 为空时用 `sha1(explanation)`。
- 同一批问题按指纹去重；已有 `exception` 指纹在插入前过滤。

## 5. LLM 审计

### 5.1 新槽位 `scene_text`

- `SLOT_REGISTRY` 追加：`SlotSpec("scene_text", "当前已采纳正文", P_NEVER, "never")`。
- `SlotSource` 协议与 `DbSlotSource` 增加 `scene_text()`：取当前场景 `body`，去空白后为空返回 `None`。
- 只给审校预置使用；执笔仍用 `recent_text`/`scene_card`，不改既有预置。

### 5.2 审校预置

`DEFAULT_ROSTER` 追加：

| 字段 | 值 |
|---|---|
| `key` | `auditor` |
| 名称 / 定位 / 颜色 | 审校 / 一致性 / `#f59e0b` |
| `task_type` | `continuity` |
| 输出契约 | `AUDIT_SCHEMA`（§5.3） |
| `param_profile` | `balanced` |
| `trigger_mode` | `manual` |
| 上下文槽位 | `project_core`, `story_bible`, `world_context`, `volume_outline`, `chapter_outline`, `timeline`, `scene_card`, `scene_characters`, `related_settings`, `scene_text` |

提示词要点（不写英文键，契约说明块由渲染层注入）：

1. 只找「写错了」：正文与设定、规则、人物卡、术语、时间线事实冲突；不评价文笔、节奏、逻辑是否好看。
2. 每条必须有正文原句引用与冲突对象；说不清就不报，不凑数。
3. 只对硬规则做硬约束；软规则给提示；氛围不检查。
4. 不给改稿，只给 2–3 个修正方向并说明代价。
5. 人物、地点、术语使用材料里的标准名；不新造设定。

### 5.3 输出契约

```jsonc
{
  "issues": [
    {
      "kind": "称呼 | 设定 | 人物 | 时间线 | 术语 | 其他",
      "severity": "致命 | 严重 | 提示",
      "quote": "正文原句",
      "rule_ref": "冲突的设定/规则/人物/时间线事实",
      "explanation": "为什么是错的",
      "reader_impact": "读者可能怎么感受",
      "options": ["修正方向 1", "修正方向 2"]
    }
  ]
}
```

契约字段名用英文、`title` 用中文；`kind` / `severity` 不用 enum，服务层归一化（沿用 `ENTRY_TYPES` 的先例：契约说明块不渲染 enum 的中文名，而提示词不许写英文键）。

### 5.4 服务层归一化

- `kind` / `severity` 走 `audit_types.normalize_*`；未知值归 `other` / `minor`。
- `quote`、`explanation` 去空白后为空的问题丢弃；`rule_ref`、`reader_impact` 可空。
- `options` 只保留字符串，最多 3 条。
- 最多保留 30 条，按 severity（critical → major → minor）、再按出现顺序排序。
- 同一批按指纹去重。
- `target_entry_id`：用 `rule_ref` 精确匹配条目的名字或别名；多个命中则 `NULL`（不猜）。
- `source = "llm"`；规则层 `source = "rule"`。

### 5.5 失败与降级

| 情形 | `llm_status` | 行为 |
|---|---|---|
| 审校预置不存在 / 停用 | `skipped` | 只返回规则层问题；警告「找不到审校智能体」 |
| 没有服务商 / 未绑模型 | `skipped` | 只返回规则层问题；警告可读原因 |
| 模型返回非结构化 | `unstructured` | 只返回规则层问题；警告「语义审计未结构化」；运行记录保留 |
| 模型调用失败 | `error` | 只返回规则层问题；警告模型错误；运行记录保留 |
| 成功 | `ok` | 规则 + LLM 问题合并 |

规则层永远先执行；LLM 失败不阻塞作者看到确定性问题。

## 6. 服务与 API

### 6.1 `audit_service`

新模块 `backend/app/services/audit_service.py`：

- `run_audit(session, scene_id) -> dict`：校验正文、取项目/场景上下文、跑规则层、把旧 `open` 标为 `superseded`、过滤特例、插入规则问题、尝试 LLM、插入 LLM 问题、提交；返回 `issues / suppressed / run_id / llm_status / warning`。
- `list_audit(session, scene_id) -> dict`：返回当前 `open` 问题、`last_audited_at`（该场景问题最新 `created_at`）、`suppressed` 不适用。
- `resolve_issue(session, issue_id, resolution: str) -> dict`：`story/setting/character` → `status=resolved`；`exception` → `status=exception`；非法值抛 `ValueError`。
- `_scene_extra`：复用 `text_service` 的场景 → 章 → 卷 → 项目与检索词助手；为了不跨模块引私有函数，把 `text_service._scene_extra` 提为公开 `scene_extra`，两处共用。
- `_insert_issues(session, ...)`：统一指纹去重、特例过滤、序列化。
- `_serialize_issue`：带 `kind_label / severity_label / source_label / target_entry_name`。
- 所有写路径在提交前不需要 `mark_dirty`（审计问题不进入 FTS）。

### 6.2 正文接口

| 方法与路径 | 请求 | 响应 |
|---|---|---|
| `POST /api/scenes/{id}/audit` | — | `AuditResult` |
| `GET /api/scenes/{id}/audit` | — | `AuditView` |
| `PATCH /api/audit/issues/{id}` | `{"resolution": "story"}` | `AuditIssue` |

```jsonc
// AuditResult
{
  "run_id": "..." | null,
  "issues": [AuditIssue],
  "suppressed": 0,
  "llm_status": "ok | skipped | unstructured | error",
  "warning": ""
}

// AuditView
{"issues": [AuditIssue], "last_audited_at": "..." | null}

// AuditIssue
{
  "id": "...", "source": "rule", "source_label": "规则",
  "kind": "alias", "kind_label": "称呼",
  "severity": "minor", "severity_label": "提示",
  "quote": "...", "rule_ref": "...", "explanation": "...",
  "reader_impact": "...", "options": ["..."],
  "target_entry_id": "...", "target_entry_name": "...",
  "status": "open", "resolution": null, "created_at": "..."
}
```

### 6.3 错误与状态码

| 情形 | 状态码 | 文案方向 |
|---|---|---|
| 场景不存在 | 404 | 「场景不存在」 |
| 场景没有已采纳正文 | 400 | 「还没有已采纳正文，无法审校」 |
| 场景章节结构损坏 | 409 | 「场景的章节结构已损坏」 |
| 问题不存在 | 404 | 「审计问题不存在」 |
| 处理方式非法 | 400 | 「不支持的处理方式」 |
| 审校智能体缺失 / 模型不可用 | 200 + warning | 规则层结果 + `llm_status=skipped` |

审校是同步请求，可能耗时数十秒；沿用运行时超时设置（默认 300 秒）。前端显示「审校中…」并禁用重复点击。

## 7. 前端

### 7.1 写作台入口

- 工具栏新增「审校」按钮：`text.has_body` 时可用；审校中禁用；点击调用 `POST /audit`。
- 右侧栏新增 `AuditPanel`（在上下文预览之后、运行信息之前）：
  - 标题与上次审校时间；
  - `llm_status` 非 `ok` 时显示 amber 警告；
  - 问题卡片：来源、严重度、原文引用、冲突对象、解释、读者观感、2–3 个修正方向；
  - 处理按钮：改故事 / 改设定 / 改人物 / 接受为特例；
  - 空态：没有正文、尚未审校、本次无问题三种。

### 7.2 处理动作

- 「改故事」：`PATCH {resolution:"story"}`，从当前列表移除，提示「已标记为改故事」；不自动改正文。
- 「改设定」：`PATCH {resolution:"setting"}`，然后跳转 `/world?entry=<target_entry_id>`；没有目标就跳 `/world`。
- 「改人物」：同上，`resolution:"character"`。
- 「接受为特例」：`PATCH {resolution:"exception"}`，提示「已记为特例，后续审校不再重复上报」。
- 所有 PATCH 失败只提示，不移除问题。

### 7.3 世界观深链

- `World.tsx` 读取 `?entry=<id>`：条目加载完成后选中该条目；找不到就保持原选择并提示。
- 这是为了「改设定/改人物」能落到具体条目，而不是让作者自己找。

### 7.4 竞态

- 审校请求持场景代际 token；切场景后迟到的审校响应不得写入当前场景。
- 审校与生成互斥：审校中禁用生成/保存/采纳；生成中禁用审校。
- `hasUnsaved` 不因审校改变；审校只读正文。

## 8. 测试策略

### 8.1 后端

| 范围 | 用例 |
|---|---|
| 数据 | `audit_issue` 往返、级联删除场景、删除目标条目置空、状态默认 open |
| 槽位 | `scene_text` 返回正文、无正文 None、注册为 never |
| 规则 | 重复句（含阈值/不同标点）、称呼歧义（共用 form）、出场人物未提及、正常正文无问题、指纹稳定 |
| 服务 | 规则层无模型可用；LLM 成功合并；LLM 非结构化/失败/无模型降级；新审校 supersede 旧 open；exception 抑制；resolve 三种状态；非法 resolution |
| 预置 | 全新库/既有库出现 `auditor`；契约字段有中文 title；槽位含 `scene_text`；提示词变量已注册 |
| API | POST 成功/无正文 400/场景 404；GET 列表；PATCH 成功/问题 404/非法 400 |
| 归一化 | 中文 kind/severity 映射、未知值兜底、空 quote 丢弃、30 条上限、目标条目映射 |
| 基线 | 既有 430 条全绿 |

### 8.2 前端

- 不写组件测试；既有 30 条保持全绿，`pnpm build` 干净。
- 若把问题排序/过滤下沉为纯函数，补 vitest。

### 8.3 手工走查

- 临时数据目录，不配置模型：保存一段带重复句的正文 → 审校 → 规则问题出现、警告显示「语义审计跳过」→ 处理/特例 → 再次审校不重复上报。
- 切场景/切项目：迟到的审校响应不覆盖新场景。
- 空态：无正文、未审校、无问题。
- 走查清单写入 `docs/superpowers/plans/2026-10-21-p2b-walkthrough.md`。

## 9. 真实模型复验

- **前置**：确认阿里云百炼 `qwen3.8-flash` 额度；不调用额度不明的模型。
- **环境**：SQLite 备份 API 复制作者库 + `secrets.bin`；`STORYFORGE_DATA_DIR=<副本>`；作者原库不写入，前后哈希一致。
- **步骤**：
  1. 副本启动：新表 `audit_issue` 由 create_all 建出；「审校」预置出现；原有数据一条不少；二次启动不重复预置。
  2. 在工作室内给审校绑定 `qwen3.8-flash`。
  3. 选一个已有已采纳正文的场景（没有就只在副本里补一个场景与正文）。
  4. 点审校：记录耗时、估算 token、`llm_status`、问题数；确认问题带原句引用与冲突对象。
  5. 处理一条为「改设定」、一条为「接受为特例」；再次审校，确认特例不再上报。
  6. 检查 `audit_issue` 行、`generation_run` 记录；控制台 0 报错。
- 复验结束后删除副本；在阶段记录写明调用次数与 token 估算。

## 10. 风险与取舍

| 风险 | 对策 |
|---|---|
| 规则层误报（称呼歧义/未提及） | 全部 `minor`，文案写「请人工确认」；作者可接受为特例 |
| LLM 问题质量不稳 | 契约强制 quote + rule_ref；服务层丢弃无引用的问题；规则层始终可用 |
| LLM 慢/失败阻塞作者 | 规则层先出结果；失败降级为 warning，不 500 |
| 正文过长挤压上下文 | `scene_text` 永不裁剪；其余槽位按既有预算裁剪；运行记录保留 trimmed |
| 问题越积越多 | 新审校 supersede 旧 open；只展示当前 open |
| 特例误抑制 | 指纹只按场景 + 规则/引用/原句；作者可再次审校或清库；本段不做「取消特例」界面 |
| 预置更新到不了旧库 | `seed_agents` 按 `preset_key`/任务类型新建；不静默改其他角色卡 |
| 作者误以为规则层=全部检查 | UI 明确标「规则/LLM」，LLM 跳过时 amber 警告 |

## 11. 文件结构

### 后端

```text
backend/app/
├── audit_types.py                 # kind/severity/source 词表与归一化
├── audit_rules.py                 # 三项确定性检查（纯函数）
├── agents/roster.py               # 追加 auditor 预置与 AUDIT_SCHEMA
├── api/
│   ├── audit.py                   # POST/GET/PATCH
│   └── main.py                    # 注册路由
├── db/models/
│   └── audit.py                   # AuditIssue
├── runtime/context.py             # scene_text 槽位
├── services/
│   ├── audit_service.py           # 规则 + LLM + 生命周期
│   ├── slot_source.py             # scene_text 取数
│   └── text_service.py            # scene_extra 公开化
└── tests/
    ├── test_audit_rules.py
    ├── test_audit_service.py
    ├── test_audit_api.py
    ├── test_audit_models.py
    ├── test_context.py
    ├── test_slot_source.py
    ├── test_roster.py
    └── test_seed_service.py
```

### 前端

```text
frontend/src/
├── api/client.ts                  # 类型与三个方法
├── components/writing/AuditPanel.tsx
├── pages/Writing.tsx              # 审校按钮、状态、右栏
└── pages/World.tsx                # ?entry=<id> 深链
```

### 文档

```text
docs/superpowers/
├── specs/2026-10-21-p2b-consistency-audit-design.md   # 本文件
├── plans/2026-10-21-p2b-consistency-audit.md          # 实施计划
└── plans/2026-10-21-p2b-walkthrough.md                # 走查清单
```

## 12. 遗留与后续

- 逻辑自检（五层、宽松默认、两种执行时机）—— 下一段，复用本段的问题表、处理状态与 AI 面板。
- 时间线倒退、表外新词、禁用词 —— 需要时间解析/分词器/禁用词表，后续单独设计。
- 生成后自动审校 —— 本段手动；等成本与噪声可控后再默认自动。
- 一键应用修改、问题历史、按项目汇总 —— 后续控制力深化。
- 特例的来源与锁定（世界规则层面的特例）—— 本段只按问题指纹抑制；P4 再做规则级特例。
