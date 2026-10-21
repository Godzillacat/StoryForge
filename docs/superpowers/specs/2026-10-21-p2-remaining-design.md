# StoryForge P2 收尾设计：逻辑自检、状态回写、批量生成、导出

> 2026-10-21。P2 的最后一段，把「写出来的东西讲不讲得通」「写完之后状态有没有跟上」「能不能整卷稳定产出」「能不能交出去」四件事补齐。
>
> 上位依据：`StoryForge-产品设计文档.md` §4.6（写作台三种节奏）、§4.7（两道检查）、§4.8（阅读与导出）、§5.3（管线与检查点）、§6（长文工程）、D-08 / D-10 / D-12 / D-13 / D-21。

## 1. 阶段定义

### 1.1 为什么这四件事放在一段

它们按生成管线的顺序紧挨着：**开写前/定稿前自检 → 采纳后回写状态 → 整卷批量产出 → 成稿导出**。前三件都读写同一批场景 / 问题 / 伏笔数据，导出又必须建立在它们之上。分成四个工作树会反复改同一批文件、跑四遍同一套回归；合成一段实施、按子阶段各自验证，更省也更稳。

### 1.2 验收标准

1. **逻辑自检**
   - 复用 `audit_issue` 表，新增 `check_type / layer / stage` 三列（迁移 v5），存量问题默认 `consistency / text`。
   - 两个时机：`plan`（对场景卡与章纲，正文开写前）与 `text`（对已采纳正文，定稿前）。
   - 五层：世界规则、因果链、动机与性格、信息流、设定载荷；默认按项目 `logic_check_level=loose` **只保留致命与严重**。
   - 无模型/失败/未结构化只降级为警告，不 500、不阻塞其它功能。
   - 问题可处理（改故事/改设定/改人物/接受为特例），接受特例后同指纹不再重复上报。
   - 前端可切换两个时机、查看结果并处理；处理动作不自动改稿。
2. **状态与伏笔回写**
   - 场景有已采纳正文时可请求「回写建议」：章节摘要、人物当前状态、伏笔实际回收。
   - 建议**只展示不落库**；作者勾选后调用 apply 才写入（D-04）。
   - 伏笔新增 `actual_pay_scene_id`（迁移 v6）；账本显示实际回收位置，未回收筛选按实际回收判定。
   - 不自动改变章节/伏笔的规划状态；生命周期状态留 P4。
3. **批量生成**
   - 可按章或按卷创建批量任务；逐场生成并落为 AI 草稿；**绝不覆盖已采纳正文**；已有草稿或正文的场景默认跳过。
   - 支持暂停、继续、取消、失败重试；进度可查；应用重启后未完成任务恢复为暂停。
   - 同一项目同时只允许一个进行中的批量任务。
   - 每个场景成功或失败都落运行记录；失败原因可读。
4. **导出**
   - 成品报告：总字数、卷/章/场景数、未写正文的场景、未回收伏笔、未处理的审计与逻辑问题。
   - 导出 Markdown / TXT / EPUB；EPUB 为不含图片的基础版（P5 精修）。
   - 有未闭环项时报告明确列出，但不阻止导出。
5. **基线**：后端既有 493 条测试全绿；前端 30 条全绿、`pnpm build` 干净。新增测试按任务实际统计。
6. **真实模型复验**：逻辑自检（plan + text）与回写建议各至少一次真实调用；批量与导出用假传输层/纯逻辑验证，不额外消耗额度。

### 1.3 明确不做

- 逻辑自检的图形化视图（因果链图、性格漂移曲线）—— P4。
- 逐章状态日志 / 状态历史（`entity_state_log`）—— P4。
- 伏笔生命周期状态（planted / paid）与锁定 —— P4；本段只记录实际回收场景。
- 项目快照、场景分支、段落级重写 —— P4。
- 阅读器、朗读、EPUB 精修、封面与样式模板 —— P5。
- 批量生成的多版本对比、A/B —— P3/P5。
- 自检的 strict 档细调 —— 本段 `standard` 与 `strict` 行为相同（都不丢提示级），只在文案上标注。

## 2. 已定决策

| 决策 | 结论 | 理由 |
|---|---|---|
| 逻辑问题存放 | **复用 `audit_issue`**，加 `check_type=logic` / `layer` / `stage` | 处理状态、特例抑制、面板与 API 全部复用；另开表会多一套生命周期 |
| 逻辑自检数据迁移 | 迁移 **v5** 给 `audit_issue` 加三列，独立 `requires=("audit_issue",)` | 存量库可能没有 `audit_issue`（直接从 P2a 升级）；与其它表合并会导致「部分缺表」拒绝启动 |
| 逻辑自检严格度 | 读 `Project.logic_check_level`；`loose` 丢 `minor`，`standard` / `strict` 保留全部 | 产品默认宽松（D-12）；细档差异留后续 |
| 逻辑自检与规则层 | 逻辑自检**只有 LLM 层**，没有确定性规则 | 五层判断都需要语义理解；没有模型时明确警告而不是假装检查过 |
| 两个时机 | `plan` 用场景卡/章纲；`text` 额外用已采纳正文 | 产品明确「开写前先跑一次更值钱」；两者输入不同但问题模型相同 |
| 特例指纹 | `logic:<stage>:<layer>:<sha1(quote 或 explanation)>` | 与一致性审计同一套抑制机制；按阶段隔离，plan 的特例不吞 text 的问题 |
| 回写是否自动 | **建议 → 作者勾选 → apply** | D-04：AI 不直接改作者的结构化设定 |
| 回写范围 | 章节摘要、人物 `current_state`、伏笔 `actual_pay_scene_id` | 产品 §5.3 的三项；逐章状态日志留 P4 |
| 伏笔实际回收 | 迁移 **v6** 加可空 `actual_pay_scene_id`（FK SET NULL），独立 `requires=("foreshadow",)` | 与 v5 分开避免部分缺表；不改规划状态，账本从实际回收字段派生「已回收」 |
| 批量写入目标 | 只写 `scene_draft`，**永远不写 `scene.body`** | D-04；作者仍需逐场审阅采纳 |
| 批量跳过策略 | 已有正文或已有草稿的场景默认跳过；失败重试只重跑失败场景 | 不覆盖作者内容；避免重复花钱 |
| 批量执行模型 | 进程内单线程 worker + `batch_job` 表；非流式 `RuntimeService.execute` | 单机单人，不引入队列依赖；流式只服务作者实时观看，批量逐场落库更重要 |
| 重启恢复 | 启动时把所有 `running` 任务改为 `paused` | 进程内线程不跨重启；作者可手动继续，进度不丢 |
| 导出格式 | Markdown / TXT / EPUB；EPUB 用标准库 `zipfile` 手工拼 | 不引入重型依赖；P5 再做样式模板与精修 |
| 导出报告 | 只报告**可确定**的项：未写场景、未回收伏笔、未处理问题 | 锁定尚未实现，不虚报「锁定状态」 |
| 导出是否阻塞 | 报告只提示，不阻止导出 | 控制力：闭环情况交给作者决定 |

## 3. 逻辑自检

### 3.1 数据（迁移 v5）

`audit_issue` 追加：

```text
check_type TEXT NOT NULL DEFAULT 'consistency'   -- consistency | logic
layer      TEXT                                  -- logic 问题所属层；一致性为 NULL
stage      TEXT NOT NULL DEFAULT 'text'          -- plan | text
```

- 索引：`(scene_id, check_type, stage, status)`。
- 存量行自动成为 `consistency / text`。
- 新库由 `create_all` 直接建出最新结构；v5 的 `requires` 只含 `audit_issue`，缺失时整步跳过。

### 3.2 词表（`logic_types.py`）

```python
LOGIC_LAYERS = {
    "world_rule": "世界规则",
    "causality": "因果链",
    "motivation": "动机与性格",
    "information": "信息流",
    "setting_load": "设定载荷",
}
LOGIC_STAGES = {"plan": "场景卡", "text": "正文"}
```

归一化：接受中英文，未知层归 `other`（新增 `"other": "其他"` 到层词表），未知阶段报错（作者显式选择）。

### 3.3 审校预置

`DEFAULT_ROSTER` 追加 `logic_checker`：

| 字段 | 值 |
|---|---|
| key | `logic_checker` |
| 名称 / 定位 / 颜色 | 逻辑审查官 / 逻辑 / `#a855f7` |
| task_type | `logic_check` |
| output_schema | `LOGIC_SCHEMA` |
| param_profile | `balanced` |
| trigger_mode | `manual` |
| 槽位 | `project_core`, `story_bible`, `world_context`, `timeline`, `volume_outline`, `chapter_outline`, `scene_card`, `scene_characters`, `related_settings`, `scene_text` |

提示词要点：五个层面逐一检查；只对硬规则做硬约束，软规则提示、氛围不检查；每条必须引用原文/场景卡原句并指明违反的设定或事实；不评价文笔，不给改稿，只给 2–3 个方向；默认不凑数。

`LOGIC_SCHEMA` 字段：`issues` 数组，每项 `layer / severity / quote / rule_ref / explanation / reader_impact / options`；`layer` 与 `severity` 不用 enum，服务层归一化。

### 3.4 服务（`logic_service.py`）

- `run_logic_check(session, scene_id, stage)`：
  1. 校验场景与阶段；`text` 必须有正文，`plan` 不要求正文。
  2. 取项目 `logic_check_level`；取 `logic_check` 智能体。
  3. 用 `RuntimeService.execute(..., allow_missing=True)` 执行；`extra` 带 `scene_id / chapter_id / volume_id / search_query`；`plan` 时 `scene_text` 不注入（槽位取到正文也无妨，但 `plan` 的提示词不引用它）。
  4. 归一化：层/严重度/quote/explanation/options；空 quote 或空解释丢弃；按严重度排序；最多 30 条；`loose` 档丢弃 `minor`。
  5. 指纹 `logic:<stage>:<layer>:<sha1(quote|explanation)>`；同一批去重；已有 `exception` 指纹过滤。
  6. 把同场景同阶段旧的 `open` 逻辑问题标 `superseded`，插入新问题（`source="llm"`, `check_type="logic"`, `stage`）。
  7. 无智能体/无模型/失败/未结构化：`llm_status` 对应 `skipped` / `error` / `unstructured`，返回空问题与可读警告；规则层不适用。
- `list_logic_check(session, scene_id, stage)`：当前 open 问题 + 该场景该阶段最新问题时间。
- 处理复用 `audit_service.resolve_issue`。

### 3.5 API 与前端

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/scenes/{id}/logic-check` | `{"stage":"plan"|"text"}` |
| GET | `/api/scenes/{id}/logic-check?stage=plan` | 列表 + 上次时间 |
| PATCH | `/api/audit/issues/{id}` | 沿用 P2b 的处理接口 |

前端写作台右栏新增「逻辑自检」面板：阶段切换（场景卡 / 正文）、运行按钮、警告、问题卡片（层标签 + 严重度）、四种处理。与一致性审校共用 `AuditIssue` 类型与处理逻辑；逻辑问题显示 `layer_label` 而不是 `kind_label`。`plan` 阶段在没有正文时也可运行。

竞态与互斥：与审校共用场景代际令牌；逻辑自检进行中禁用生成 / 保存 / 采纳 / 审校，反之亦然。

## 4. 状态与伏笔回写

### 4.1 数据（迁移 v6）

`foreshadow` 追加：

```text
actual_pay_scene_id TEXT REFERENCES scene(id) ON DELETE SET NULL
```

- 索引 `ix_foreshadow_actual_pay`。
- 账本「已回收」= `actual_pay_scene_id` 非空；「缺回收」= 实际回收为空且计划回收为空（或计划位置悬空）。计划回收存在但未实际回收的行标「已计划、未回收」。
- 不修改 `status`。

### 4.2 预置 `writeback`

| 字段 | 值 |
|---|---|
| key | `writeback` |
| 名称 / 定位 / 颜色 | 回写助手 / 状态 / `#0d9488` |
| task_type | `writeback`（新增到 `TASK_TYPES`） |
| output_schema | `WRITEBACK_SCHEMA` |
| 槽位 | 与执笔相同，但用 `scene_text` 替掉 `recent_text` |

`WRITEBACK_SCHEMA`：

```jsonc
{
  "chapter_summary": "本章到目前为止发生了什么（客观摘要）",
  "character_updates": [
    {"character": "标准名", "current_state": "这一场之后的状态", "evidence": "正文原句"}
  ],
  "foreshadow_pays": [
    {"name": "伏笔标准名", "evidence": "正文原句"}
  ],
  "open_questions": ["没把握的问题"]
}
```

提示词要点：只写正文实际发生的事；人物与伏笔用材料里的标准名；摘要不超过项目约定；证据必须是正文原句；没把握进问题；不发明新状态。

### 4.3 服务（`writeback_service.py`）

- `suggest(session, scene_id)`：
  1. 校验正文；取项目、场景链。
  2. 执行 `writeback` 预置；失败/未结构化返回警告与空建议，不 500。
  3. 归一化：人物按名称/别名**精确**匹配人物条目，伏笔按名称精确匹配；匹配不到进 `warnings`（不猜）。
  4. 返回建议，**不落库**：`chapter_summary`、`character_updates[{entry_id, name, current_state, evidence}]`、`foreshadow_pays[{foreshadow_id, name, evidence}]`、`warnings`、`run_id`、`llm_status`。
- `apply(session, scene_id, payload)`：
  - 只接受上述结构化载荷；人物必须属于本项目且为人物条目；伏笔必须属于本项目。
  - 章节摘要写入该场景所属章；人物 `current_state` 覆盖；伏笔 `actual_pay_scene_id = scene.id`。
  - 空值表示不改该项；一次事务提交；返回更新后的摘要/人物/伏笔。

### 4.4 API 与前端

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/scenes/{id}/writeback` | 生成建议 |
| POST | `/api/scenes/{id}/writeback/apply` | 应用勾选项 |

前端写作台右栏新增「回写建议」面板：运行按钮；摘要文本框（可编辑后应用）；人物状态勾选与可编辑文本；伏笔回收勾选；警告列表；「应用所选」按钮。默认全不勾选，作者主动选择。没有正文时不可运行。

## 5. 批量生成

### 5.1 数据（新表，`create_all`）

`batch_job`：

```text
id TEXT PK
project_id TEXT NOT NULL FK project ON DELETE CASCADE
scope_type TEXT NOT NULL          -- chapter | volume
scope_id TEXT NOT NULL
scene_ids_json JSON NOT NULL      -- 有序场景 id
cursor INTEGER NOT NULL DEFAULT 0
status TEXT NOT NULL DEFAULT 'paused'  -- running | paused | completed | cancelled | failed
failures_json JSON NOT NULL DEFAULT [] -- [{scene_id, message}]
created_at / updated_at
```

索引 `project_id`、`status`。

### 5.2 服务与 worker

- `create_job(session, project_id, scope_type, scope_id)`：校验项目与范围；收集场景（卷按卷序/章序/场景序，章按场景序）；过滤已有正文或草稿的场景；为空时报错「没有需要生成的场景」；同项目已有 `running` 任务时报错；创建 `paused` 任务。
- `start_job(job_id)`：把状态置 `running` 并启动 daemon 线程（同 job 只启动一个）。
- `_run_job_loop(job_id)`：每轮开新 session 读 job；`status != running` 退出；取当前场景：
  - 若已有正文/草稿 → 记录跳过（不计失败），cursor+1；
  - 否则调用 `RuntimeService.execute(project_id, writer_agent_id, extra)`；成功则 `text_service.save_generated_draft(...)`，失败记录 `failures`；
  - cursor+1 提交；全部完成置 `completed`。
- `pause/resume/cancel`：改状态；pause 在场景边界生效；resume 从 cursor 继续；cancel 置 `cancelled`。
- `retry_failed(job_id)`：把 failures 的场景重置为 `scene_ids`、cursor=0、failures=[]、status=running，启动 worker。
- `recover_jobs()`：应用启动时把 `running` 改为 `paused`。
- 每次场景生成使用非流式运行时；token/费用按现有 `generation_run` 记录。

### 5.3 API 与前端

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/projects/{id}/batches` | `{"scope_type":"chapter"|"volume","scope_id":...}` |
| GET | `/api/batches/{id}` | 进度、当前场景、失败列表 |
| POST | `/api/batches/{id}/pause` / `resume` / `cancel` / `retry-failed` | 控制 |
| GET | `/api/projects/{id}/batches/latest` | 最近任务（页面恢复用） |

前端写作台新增「批量生成」面板：选择范围（当前章 / 当前卷）、开始；显示状态、进度（cursor / 总数）、失败列表；暂停/继续/取消/重试失败。页面加载时读取最近任务恢复显示；任务完成后刷新章节树。

## 6. 导出

### 6.1 报告（`export_service.build_report`）

```jsonc
{
  "project_id", "project_name",
  "total_words", "volumes", "chapters", "scenes",
  "scenes_without_body": [{"chapter", "scene", "goal"}],
  "unrecovered_foreshadows": [{"name", "planted", "planned_pay"}],
  "open_audit_issues": 0,
  "open_logic_issues": 0,
  "exportable": true
}
```

- 字数用 `count_words` 对 `scene.body` 求和。
- 未回收：`actual_pay_scene_id IS NULL` 且已有埋设或计划回收的伏笔。
- 未处理问题：`audit_issue.status='open'` 按 `check_type` 计数。
- `exportable` 始终为 true；报告只提示。

### 6.2 文件

- **Markdown**：`# 项目名`、卷标题、章标题、场景正文按顺序拼接；场景之间空行。
- **TXT**：同上，去掉常见 Markdown 标记（标题号、粗体/斜体星号、引用号、行内代码反引号），保留段落。
- **EPUB**：`zipfile` 手写；`mimetype` 第一条且不压缩；`META-INF/container.xml`；`OEBPS/content.opf`、`nav.xhtml`、每章一个 XHTML（按章合并场景正文，段落转 `<p>`，HTML 转义）；无图片/封面/样式文件。

### 6.3 API 与前端

| 方法 | 路径 | 响应 |
|---|---|---|
| GET | `/api/projects/{id}/export/report` | 报告 JSON |
| GET | `/api/projects/{id}/export?format=md|txt|epub` | 文件下载（`Content-Disposition`，UTF-8 文件名） |

前端故事仪表盘新增「导出与成品报告」卡片：显示字数、未写场景、未回收伏笔、未处理问题；三个下载按钮；报告有未闭环项时用 amber 提示但不禁用。

## 7. 测试策略

| 范围 | 用例 |
|---|---|
| 迁移 | v5/v6 在存量库执行一次、数据保留、二次启动不重复；部分缺表拒绝启动；新库盖章 |
| 逻辑 | 层/严重度归一化；plan/text 输入差异；loose 丢 minor；空 quote 丢弃；supersede；特例抑制；无模型/失败/未结构化降级；指纹按阶段隔离 |
| 回写 | 建议归一化与精确匹配、缺失名称进 warnings；apply 只改所选、项目隔离、非法 id 拒绝；无正文/无模型降级 |
| 批量 | 创建时过滤已写场景；逐步推进与完成；失败记录；pause/resume/cancel；retry-failed；项目内互斥；启动恢复 |
| 导出 | 报告计数；MD/TXT 内容与顺序；EPUB zip 结构与 mimetype 存储方式；空项目；HTML 转义 |
| 前端 | 不写组件测试；既有 30 条保持；纯函数（如阶段/进度格式化）可补 vitest |
| 基线 | 493 → 全部绿 |

## 8. 风险与取舍

| 风险 | 对策 |
|---|---|
| 逻辑自检噪声大 | 默认 loose 只报致命/严重；特例抑制；面板明确标「语义检查」 |
| 逻辑自检与一致性审计混淆 | `check_type` 分开存储与展示；面板标题分别写「一致性审计」「逻辑自检」 |
| 模型把回写建议写错 | 只建议不落库；逐项勾选；证据必须引用原句；匹配不到人物/伏笔只警告 |
| 批量覆盖作者内容 | 只写草稿；已有正文/草稿跳过；不自动采纳 |
| 批量进程中断 | 任务表持久化 cursor；启动恢复为 paused |
| 批量重复花钱 | 跳过已写场景；失败重试只跑失败项；同一项目互斥 |
| EPUB 兼容性 | 基础结构 + 标准转义；P5 再做精修与真机验证 |
| 迁移部分缺表 | v5/v6 各自独立 `requires`，避免「P2a 库升级」被判部分缺失 |

## 9. 文件结构

```text
backend/app/
├── logic_types.py                 # 五层词表与归一化
├── db/models/audit.py             # + check_type / layer / stage
├── db/models/chapter.py           # Foreshadow + actual_pay_scene_id
├── db/models/batch.py             # BatchJob（新表）
├── db/migrations.py               # v5 / v6
├── agents/roster.py               # logic_checker / writeback + 两个契约
├── services/
│   ├── logic_service.py
│   ├── writeback_service.py
│   ├── batch_service.py
│   ├── export_service.py
│   └── text_service.py            # save_generated_draft；scene 正文变化作废旧问题
├── api/
│   ├── logic.py
│   ├── writeback.py
│   ├── batches.py
│   ├── export.py
│   └── schemas.py
└── tests/...

frontend/src/
├── api/client.ts
├── components/writing/LogicPanel.tsx
├── components/writing/WritebackPanel.tsx
├── components/writing/BatchPanel.tsx
├── components/writing/AuditPanel.tsx   # 支持逻辑层标签
├── pages/Writing.tsx
├── pages/Dashboard.tsx
└── components/chapters/ForeshadowLedger.tsx
```

## 10. 遗留与后续

- 逻辑自检 standard / strict 的细差异与项目级设置界面（本段读字段、不提供设置入口）。
- 状态历史与逐章状态推进（P4）。
- 伏笔生命周期状态与锁定（P4）。
- 批量任务的卷级多模型分路、预算提醒（P3）。
- EPUB 样式模板、封面、目录层级与真机验证（P5）。
- 导出报告中的锁定状态（P4）。
