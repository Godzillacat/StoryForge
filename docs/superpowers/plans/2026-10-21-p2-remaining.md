# P2 收尾 Implementation Plan：逻辑自检、回写、批量、导出

> **For agentic workers:** 按任务顺序实施，每个任务先写失败测试再实现，提交信息用中文 Conventional Commits。

**Goal:** 补齐 P2 剩余四项：逻辑自检、状态与伏笔回写、批量生成、导出。

**Architecture:** 逻辑问题复用 `audit_issue`（新增 `check_type/layer/stage`）；回写走「建议 → 作者勾选 → apply」；批量用进程内单线程 worker + `batch_job` 持久化；导出用纯函数生成报告、Markdown/TXT 与基础 EPUB。

**Tech Stack:** Python 3.13 + FastAPI + SQLAlchemy + SQLite（stdlib `zipfile`），React 19 + TypeScript + Vite + Tailwind，pytest / vitest。

**Spec:** `docs/superpowers/specs/2026-10-21-p2-remaining-design.md`

## Global Constraints

- 实施在隔离 worktree `worktree-p2-remaining`（从本地 `master` 切出）；master 在收口前不动。
- 基线：后端 **493 passed**，前端 **30 passed**，`pnpm build` 干净。每个任务结束不得低于基线；新增测试按实际数记录。
- `api` 不写业务逻辑；`services` 不碰 HTTP；`runtime` 不依赖 FastAPI。
- 纯逻辑必须测（pytest / vitest）；**UI 不写自动化测试**。
- 新表 `batch_job` 归 `create_all`；改已有表走迁移 **v5 / v6**，SQL 冻结为字面量，两条迁移各自独立 `requires`。
- AI 产出永远只进草稿/建议，不自动改正文或结构化设定（D-04）。
- 不写作者真实库；真实模型复验只用库副本，调用前确认阿里云百炼免费额度，只用 `qwen3.8-flash`。
- 不要用 `git stash`；不要擅自 rebase / 改写历史。
- 每个任务一个提交（或按步骤中的提交点）。

---

### Task 1: 审计问题扩展与逻辑词表（迁移 v5）

**Files:**
- Create: `backend/app/logic_types.py`
- Modify: `backend/app/db/models/audit.py`
- Modify: `backend/app/db/migrations.py`
- Test: `backend/tests/test_logic_types.py`
- Test: `backend/tests/test_audit_models.py`
- Test: `backend/tests/test_migrations.py` / `test_migration_runner.py`

**Interfaces:**
- Produces: `LOGIC_LAYERS` / `LOGIC_STAGES` / `normalize_layer` / `normalize_stage`；`AuditIssue.check_type / layer / stage`；迁移 v5。
- Consumes: 既有 `AuditIssue`、迁移 runner。

- [ ] **Step 1: 写失败测试**

`test_logic_types.py`：中英文层名归一；未知层归 `other`；阶段只接受 `plan` / `text`，非法抛 `ValueError`；中文标签与 spec 一致。
`test_audit_models.py`：新问题默认 `check_type="consistency"`、`stage="text"`、`layer=None`；显式 logic 问题往返。
`test_migrations.py`：v5 版本号、语句含三列；`requires == ("audit_issue",)`。

- [ ] **Step 2: 运行确认失败**

Run: `uv run --directory backend pytest tests/test_logic_types.py tests/test_audit_models.py -q`
Expected: FAIL。

- [ ] **Step 3: 实现**

`logic_types.py`：五层 + 其他，中英文归一；阶段词表与 `normalize_stage`。
`db/models/audit.py`：加三列与 `Index("ix_audit_issue_scene_check", "scene_id", "check_type", "stage", "status")`。
`migrations.py`：v5 三条 `ALTER TABLE` + 索引；`requires=("audit_issue",)`。

- [ ] **Step 4: 跑测试与全量**

Run: `uv run --directory backend pytest tests/test_logic_types.py tests/test_audit_models.py tests/test_migrations.py tests/test_migration_runner.py -q`
Expected: PASS。
Run: `uv run --directory backend pytest -q`
Expected: ≥ 493。

- [ ] **Step 5: 提交**

```bash
git add backend/app/logic_types.py backend/app/db/models/audit.py backend/app/db/migrations.py backend/tests/test_logic_types.py backend/tests/test_audit_models.py backend/tests/test_migrations.py
git commit -m "feat(logic): 逻辑问题字段与词表"
```

---

### Task 2: 逻辑审查官预置

**Files:**
- Modify: `backend/app/agents/roster.py`
- Test: `backend/tests/test_roster.py`
- Test: `backend/tests/test_seed_service.py`

**Interfaces:**
- Produces: `LOGIC_SCHEMA`、`LOGIC_CHECKER_PROMPT`、`DEFAULT_ROSTER` 中的 `logic_checker`。
- Consumes: `LOGIC_LAYERS`、`SLOT_REGISTRY`。

- [ ] **Step 1: 写失败测试**

`test_roster.py`：
- `logic_checker` 存在，`task_type="logic_check"`，槽位含 `scene_text`；
- `LOGIC_SCHEMA` 的 `issues` 必填数组，每项字段有中文 title，层标题包含五层中文名；
- 提示词含「世界规则」「因果链」「动机与性格」「信息流」「设定载荷」与「不评价文笔」。
`test_seed_service.py`：全新库出现 `logic_check` 智能体，版本契约非空。

- [ ] **Step 2: 运行确认失败**

Run: `uv run --directory backend pytest tests/test_roster.py tests/test_seed_service.py -q`
Expected: FAIL。

- [ ] **Step 3: 实现**

按 spec §3.3 定义 `LOGIC_SCHEMA`（字段英文键 + 中文 title，`layer` / `severity` 不用 enum）与提示词；追加 `DEFAULT_ROSTER` 项；层标题由 `LOGIC_LAYERS` 派生。

- [ ] **Step 4: 跑测试与全量**

Run: `uv run --directory backend pytest tests/test_roster.py tests/test_seed_service.py -q`
Expected: PASS。
Run: `uv run --directory backend pytest -q`
Expected: ≥ 上一任务。

- [ ] **Step 5: 提交**

```bash
git add backend/app/agents/roster.py backend/tests/test_roster.py backend/tests/test_seed_service.py
git commit -m "feat(logic): 逻辑审查官预置"
```

---

### Task 3: 逻辑自检服务

**Files:**
- Create: `backend/app/services/logic_service.py`
- Test: `backend/tests/test_logic_service.py`

**Interfaces:**
- Produces: `run_logic_check(session, scene_id, stage) -> dict`、`list_logic_check(session, scene_id, stage) -> dict`。
- Consumes: `RuntimeService.execute`、`logic_types`、`audit_types`、`text_service.scene_extra`、`Project.logic_check_level`。

- [ ] **Step 1: 写失败测试**

用 `monkeypatch` 替换 `RuntimeService.execute`：
- `plan` 无正文可运行；`text` 无正文抛「还没有已采纳正文」；
- 合法阶段；非法阶段抛错；
- 结构化问题合并：层/严重度归一、空 quote/解释丢弃、30 条上限；
- `loose` 丢 `minor`，`standard` 保留；
- 新一次同阶段审校 supersede 旧 open，plan 与 text 互不影响；
- `exception` 指纹抑制；
- 无智能体 / 无模型 / 非结构化 / 运行 error / 非 `ValueError` 异常：对应 `skipped / unstructured / error`，规则不适用、警告可读、不抛 500；
- `list` 只返回当前 open，`last_checked_at` 按场景 + 阶段取；
- 指纹按阶段隔离。

- [ ] **Step 2: 运行确认失败**

Run: `uv run --directory backend pytest tests/test_logic_service.py -q`
Expected: FAIL。

- [ ] **Step 3: 实现**

按 spec §3.4：取场景与项目；阶段过滤；执行预置（`allow_missing=True`）；归一化与 loose 过滤；指纹、去重、特例；supersede 同场景同阶段；插入 `check_type="logic"`。失败一律降级为警告。

- [ ] **Step 4: 跑测试与全量**

Run: `uv run --directory backend pytest tests/test_logic_service.py -q`
Expected: PASS。
Run: `uv run --directory backend pytest -q`
Expected: ≥ 上一任务。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/logic_service.py backend/tests/test_logic_service.py
git commit -m "feat(logic): 逻辑自检服务"
```

---

### Task 4: 逻辑自检 API

**Files:**
- Create: `backend/app/api/logic.py`
- Modify: `backend/app/api/schemas.py`（`LogicCheckRequest`）
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_logic_api.py`

**Interfaces:**
- Produces: `POST /api/scenes/{id}/logic-check`、`GET /api/scenes/{id}/logic-check?stage=`。
- Consumes: `logic_service`。

- [ ] **Step 1: 写失败测试**

- POST 成功：返回 `issues / llm_status / warning / run_id`；
- POST 无正文（text）400、场景 404、非法阶段 400；
- GET 返回 `issues` 与 `last_checked_at`；无记录为 null；
- 路由可访问、应用能启动。

- [ ] **Step 2: 运行确认失败**

Run: `uv run --directory backend pytest tests/test_logic_api.py -q`
Expected: FAIL。

- [ ] **Step 3: 实现**

`api/logic.py`：router `/api`；错误映射（场景 404、无正文/非法阶段 400、章节结构 409）；`LogicCheckRequest(stage: str)`。`main.py` 注册。API 只做参数校验、错误翻译与调用。

- [ ] **Step 4: 跑测试与全量**

Run: `uv run --directory backend pytest tests/test_logic_api.py -q`
Expected: PASS。
Run: `uv run --directory backend pytest -q`
Expected: ≥ 上一任务。

- [ ] **Step 5: 提交**

```bash
git add backend/app/api/logic.py backend/app/api/schemas.py backend/app/main.py backend/tests/test_logic_api.py
git commit -m "feat(api): 逻辑自检接口"
```

---

### Task 5: 前端逻辑自检面板

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/components/writing/AuditPanel.tsx`（支持逻辑层标签）
- Create: `frontend/src/components/writing/LogicPanel.tsx`
- Modify: `frontend/src/pages/Writing.tsx`

**Interfaces:**
- Produces: `LogicCheckResult / LogicCheckView` 类型与 `runSceneLogicCheck / getSceneLogicCheck`；`LogicPanel`。
- Consumes: P2b 的 `AuditIssue`、`AuditResolution`、`resolveAuditIssue`。

- [ ] **Step 1: 客户端类型与方法**

`AuditIssue` 增加可选 `check_type / layer / layer_label / stage`（保持向后兼容）；新增两个方法。

- [ ] **Step 2: 面板**

`LogicPanel`：阶段切换（场景卡 / 正文）、运行按钮（`text` 无正文时禁用）、上次时间、amber 警告、问题卡片（层标签/严重度/原句/冲突对象/解释/读者观感/修正方向/四种处理）、空态。`AuditPanel` 显示 `layer_label ?? kind_label`。

- [ ] **Step 3: 写作台整合**

新增 `logicIssues / logicLastAt / logicLoading / logicWarning / logicStage`；场景加载时按当前阶段拉取；切换阶段重新拉取；运行与 resolve 持场景代际令牌；逻辑自检与审校/生成/保存互斥；右栏在一致性审校之后、运行信息之前。

- [ ] **Step 4: 构建与既有测试**

Run: `cd frontend && pnpm build`
Expected: 干净。
Run: `cd frontend && pnpm vitest run`
Expected: 30 passed。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/api/client.ts frontend/src/components/writing/AuditPanel.tsx frontend/src/components/writing/LogicPanel.tsx frontend/src/pages/Writing.tsx
git commit -m "feat(frontend): 写作台逻辑自检"
```

---

### Task 6: 逻辑自检真实模型复验

**Files:**
- Create: `docs/superpowers/plans/2026-10-21-p2-remaining-walkthrough.md`（先写逻辑部分）

- [ ] **Step 1: 作者库副本**

SQLite 备份 API 复制作者库 + `secrets.bin`；`STORYFORGE_DATA_DIR=<副本>` 启动；确认 v5 执行、`logic_checker` 预置出现、数据一条不少、二次启动不重复。

- [ ] **Step 2: 绑定与运行**

副本里给逻辑审查官绑定 `qwen3.8-flash`；选一个有正文的场景跑 `text`；记录耗时/tokens/层分布/问题质量；再跑 `plan`（可无正文），确认两个阶段互不 supersede。
处理一条为特例，重跑 `text` 确认抑制。

- [ ] **Step 3: 记录与清理**

把耗时、tokens、额度、问题样例写入走查文档；删除副本；作者库哈希前后一致。

- [ ] **Step 4: 提交**

```bash
git add docs/superpowers/plans/2026-10-21-p2-remaining-walkthrough.md
git commit -m "docs: 记录逻辑自检真实模型复验"
```

---

### Task 7: 伏笔实际回收（迁移 v6）

**Files:**
- Modify: `backend/app/db/models/chapter.py`
- Modify: `backend/app/db/migrations.py`
- Modify: `backend/app/services/foreshadow_service.py`
- Modify: `backend/app/services/chapter_service.py`（场景树返回 actual_pay）
- Modify: `backend/app/api/foreshadows.py`
- Test: `backend/tests/test_chapter_models.py` / `test_foreshadow_service.py` / `test_foreshadows_api.py` / `test_chapters_api.py`

**Interfaces:**
- Produces: `Foreshadow.actual_pay_scene_id`；API 返回 `actual_pay_scene_id`；迁移 v6。
- Consumes: 既有伏笔 CRUD 与场景树。

- [ ] **Step 1: 写失败测试**

- 模型往返 `actual_pay_scene_id`；删除场景置空；
- 迁移 v6 语句与 `requires == ("foreshadow",)`；
- API 序列化含新字段；
- 场景树 `foreshadows.pays` 仍表示计划回收，不混入实际回收（新增 `actual_pays` 或在树节点包含实际回收场景 id，按实现选择并测）。
- ledger 的纯函数投影测试（若新增前端纯函数）。

- [ ] **Step 2: 运行确认失败**

Run: `uv run --directory backend pytest tests/test_chapter_models.py tests/test_foreshadow_service.py tests/test_foreshadows_api.py -q`
Expected: FAIL。

- [ ] **Step 3: 实现**

模型加列；v6 加列 + 索引；服务序列化与 API；树与账本暴露实际回收。不改变 `status`。

- [ ] **Step 4: 跑测试与全量**

Run: `uv run --directory backend pytest tests/test_chapter_models.py tests/test_foreshadow_service.py tests/test_foreshadows_api.py tests/test_chapters_api.py tests/test_migrations.py tests/test_migration_runner.py -q`
Expected: PASS。
Run: `uv run --directory backend pytest -q`
Expected: ≥ 上一任务。

- [ ] **Step 5: 提交**

```bash
git add backend/app/db/models/chapter.py backend/app/db/migrations.py backend/app/services/foreshadow_service.py backend/app/services/chapter_service.py backend/app/api/foreshadows.py backend/tests/test_chapter_models.py backend/tests/test_foreshadow_service.py backend/tests/test_foreshadows_api.py backend/tests/test_chapters_api.py
git commit -m "feat(foreshadow): 记录伏笔实际回收场景"
```

---

### Task 8: 回写预置

**Files:**
- Modify: `backend/app/agents/roster.py`（`TASK_TYPES` 加 `writeback`；契约与提示词）
- Test: `backend/tests/test_roster.py`
- Test: `backend/tests/test_seed_service.py`

**Interfaces:**
- Produces: `WRITEBACK_SCHEMA`、`WRITEBACK_PROMPT`、`DEFAULT_ROSTER` 中的 `writeback`。
- Consumes: `SLOT_REGISTRY`。

- [ ] **Step 1: 写失败测试**

`task_type="writeback"`；契约含 `chapter_summary / character_updates / foreshadow_pays / open_questions` 且字段有中文 title；提示词含「只写正文实际发生的事」「证据」「标准名」「不发明」；种子出现该智能体。

- [ ] **Step 2: 运行确认失败**

Run: `uv run --directory backend pytest tests/test_roster.py tests/test_seed_service.py -q`
Expected: FAIL。

- [ ] **Step 3: 实现**

按 spec §4.2 定义契约与提示词；槽位与执笔相同但用 `scene_text` 替 `recent_text`。

- [ ] **Step 4: 跑测试与全量**

Run: `uv run --directory backend pytest tests/test_roster.py tests/test_seed_service.py -q`
Expected: PASS。
Run: `uv run --directory backend pytest -q`
Expected: ≥ 上一任务。

- [ ] **Step 5: 提交**

```bash
git add backend/app/agents/roster.py backend/tests/test_roster.py backend/tests/test_seed_service.py
git commit -m "feat(writeback): 回写助手预置"
```

---

### Task 9: 回写服务

**Files:**
- Create: `backend/app/services/writeback_service.py`
- Test: `backend/tests/test_writeback_service.py`

**Interfaces:**
- Produces: `suggest(session, scene_id) -> dict`、`apply(session, scene_id, payload) -> dict`。
- Consumes: `RuntimeService.execute`、`world_service.list_entries`、`foreshadow_service`、`chapter_service`。

- [ ] **Step 1: 写失败测试**

- 无正文抛「还没有已采纳正文」；
- 建议：人物按名称/别名精确匹配、伏笔按名称匹配；匹配不到进 warnings 且不返回该行；
- 非结构化 / 失败 / 无模型降级为 `llm_status` + warning；
- apply：只改所选；章节摘要、人物 `current_state`、伏笔 `actual_pay_scene_id` 正确；空值不改；
- 项目隔离：别的项目的人物/伏笔 id 被拒绝；非法 id 报错；
- 返回更新后的值。

- [ ] **Step 2: 运行确认失败**

Run: `uv run --directory backend pytest tests/test_writeback_service.py -q`
Expected: FAIL。

- [ ] **Step 3: 实现**

按 spec §4.3；归一化与匹配纯逻辑；apply 一次事务提交。

- [ ] **Step 4: 跑测试与全量**

Run: `uv run --directory backend pytest tests/test_writeback_service.py -q`
Expected: PASS。
Run: `uv run --directory backend pytest -q`
Expected: ≥ 上一任务。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/writeback_service.py backend/tests/test_writeback_service.py
git commit -m "feat(writeback): 回写建议与应用"
```

---

### Task 10: 回写 API 与前端面板

**Files:**
- Create: `backend/app/api/writeback.py`
- Modify: `backend/app/api/schemas.py`（`WritebackApply`）
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_writeback_api.py`
- Modify: `frontend/src/api/client.ts`
- Create: `frontend/src/components/writing/WritebackPanel.tsx`
- Modify: `frontend/src/pages/Writing.tsx`

**Interfaces:**
- Produces: `POST /api/scenes/{id}/writeback`、`POST /api/scenes/{id}/writeback/apply`；前端类型与面板。
- Consumes: `writeback_service`。

- [ ] **Step 1: 后端 API 测试与实现**

POST 建议成功/无正文 400/场景 404；apply 成功/非法 id 400；路由注册。API 只做校验、错误翻译与调用。

- [ ] **Step 2: 前端**

`WritebackPanel`：运行、警告、摘要编辑、人物状态勾选+文本、伏笔回收勾选、应用所选；默认不勾选；应用后清空建议并提示。写作台右栏加入；运行与应用持场景代际令牌；无正文禁用。

- [ ] **Step 3: 构建与全量**

Run: `uv run --directory backend pytest tests/test_writeback_api.py -q` → PASS。
Run: `uv run --directory backend pytest -q` → ≥ 上一任务。
Run: `cd frontend && pnpm build && pnpm vitest run` → 干净 / 30 passed。

- [ ] **Step 4: 提交**

```bash
git add backend/app/api/writeback.py backend/app/api/schemas.py backend/app/main.py backend/tests/test_writeback_api.py frontend/src/api/client.ts frontend/src/components/writing/WritebackPanel.tsx frontend/src/pages/Writing.tsx
git commit -m "feat(writeback): 回写接口与写作台面板"
```

---

### Task 11: 回写真实模型复验

- [ ] 在作者库副本上给回写助手绑定 `qwen3.8-flash`，对一个有正文的场景跑建议；记录耗时/tokens/建议质量。
- [ ] 勾选一条人物状态与一条伏笔回收应用；确认落库值、账本显示、章节摘要更新。
- [ ] 记录到走查文档；删除副本；作者库哈希一致。
- [ ] 提交 `docs: 记录回写真实模型复验`。

---

### Task 12: 批量任务模型与服务

**Files:**
- Create: `backend/app/db/models/batch.py`
- Modify: `backend/app/db/models/__init__.py`
- Create: `backend/app/services/batch_service.py`
- Test: `backend/tests/test_batch_service.py`

**Interfaces:**
- Produces: `BatchJob`；`create_job / advance_job / serialize_job / pause_job / resume_job / cancel_job / retry_failed / start_job / recover_jobs`。
- Consumes: `Chapter/Volume/Scene`、`text_service`、`agent_service`、`RuntimeService`。

- [ ] **Step 1: 写失败测试**

- 创建章/卷任务，场景顺序正确；已有正文/草稿的场景被过滤；没有可跑场景报错；同项目已有 running 报错；
- `advance_job` 成功生成一场：假 `RuntimeService.execute` 返回 ok，草稿落库、cursor 前进、run 关联；
- 失败记录到 failures、cursor 仍前进；
- 全部完成置 completed；
- pause/resume/cancel 状态机；
- retry_failed 只重跑失败场景；
- recover_jobs 把 running 改 paused。

- [ ] **Step 2: 运行确认失败**

Run: `uv run --directory backend pytest tests/test_batch_service.py -q`
Expected: FAIL。

- [ ] **Step 3: 实现**

新表与索引；`create_job` 收集与过滤；`advance_job` 单步（便于测试）；`start_job` 线程调用 `advance_job` 循环；控制函数；`recover_jobs`。`text_service` 增加 `save_generated_draft`（已有草稿不覆盖）。线程只用 `advance_job`，测试不启动线程。

- [ ] **Step 4: 跑测试与全量**

Run: `uv run --directory backend pytest tests/test_batch_service.py -q` → PASS。
Run: `uv run --directory backend pytest -q` → ≥ 上一任务。

- [ ] **Step 5: 提交**

```bash
git add backend/app/db/models/batch.py backend/app/db/models/__init__.py backend/app/services/batch_service.py backend/app/services/text_service.py backend/tests/test_batch_service.py
git commit -m "feat(batch): 批量任务模型与服务"
```

---

### Task 13: 批量 API 与启动恢复

**Files:**
- Create: `backend/app/api/batches.py`
- Modify: `backend/app/api/schemas.py`（`BatchCreate`）
- Modify: `backend/app/main.py`（路由注册 + lifespan 调 `recover_jobs`）
- Test: `backend/tests/test_batches_api.py`

**Interfaces:**
- Produces: 五个端点（创建/查询/暂停/继续/取消/重试失败 + 最近任务）。
- Consumes: `batch_service`。

- [ ] **Step 1: 写失败测试**

创建成功/范围不存在 404/无场景 400/同项目进行中 409；GET 进度；pause/resume/cancel 状态变化；retry-failed；latest；应用启动恢复 running→paused。

- [ ] **Step 2: 运行确认失败**

Run: `uv run --directory backend pytest tests/test_batches_api.py -q`
Expected: FAIL。

- [ ] **Step 3: 实现**

路由与错误映射；`main.py` lifespan 在 seed 后调用 `recover_jobs()`；API 不启动线程以外的业务。

- [ ] **Step 4: 跑测试与全量**

Run: `uv run --directory backend pytest tests/test_batches_api.py -q` → PASS。
Run: `uv run --directory backend pytest -q` → ≥ 上一任务。

- [ ] **Step 5: 提交**

```bash
git add backend/app/api/batches.py backend/app/api/schemas.py backend/app/main.py backend/tests/test_batches_api.py
git commit -m "feat(api): 批量生成接口与启动恢复"
```

---

### Task 14: 前端批量面板

**Files:**
- Modify: `frontend/src/api/client.ts`
- Create: `frontend/src/components/writing/BatchPanel.tsx`
- Modify: `frontend/src/pages/Writing.tsx`

**Interfaces:**
- Produces: `BatchJob` 类型与创建/查询/控制方法；`BatchPanel`。
- Consumes: 章节树当前卷/章。

- [ ] **Step 1: 客户端类型与方法**

`BatchJob`、`BatchFailure`；`createBatch / getBatch / listLatestBatch / pauseBatch / resumeBatch / cancelBatch / retryBatchFailed`。

- [ ] **Step 2: 面板与整合**

选择范围（当前章 / 当前卷）、开始；状态与进度条、失败列表、暂停/继续/取消/重试失败；轮询状态（页面有活动任务时每 2 秒，完成即停）；任务完成后刷新章节树；切项目清空。

- [ ] **Step 3: 构建与既有测试**

Run: `cd frontend && pnpm build && pnpm vitest run` → 干净 / 30 passed。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/api/client.ts frontend/src/components/writing/BatchPanel.tsx frontend/src/pages/Writing.tsx
git commit -m "feat(frontend): 写作台批量生成"
```

---

### Task 15: 导出报告

**Files:**
- Create: `backend/app/services/export_service.py`
- Test: `backend/tests/test_export_service.py`

**Interfaces:**
- Produces: `build_report(session, project_id) -> dict`。
- Consumes: `count_words`、`Foreshadow`、`AuditIssue`、章节树查询。

- [ ] **Step 1: 写失败测试**

- 字数/卷章场景计数正确；
- 未写场景列表；
- 未回收伏笔（实际回收为空、且有埋设或计划回收）；
- open 审计/逻辑问题按 `check_type` 计数；
- 空项目；
- 项目不存在报错。

- [ ] **Step 2: 运行确认失败**

Run: `uv run --directory backend pytest tests/test_export_service.py -q` → FAIL。

- [ ] **Step 3: 实现**

按 spec §6.1；只读、无 HTTP、不写库。

- [ ] **Step 4: 跑测试与全量**

Run: `uv run --directory backend pytest tests/test_export_service.py -q` → PASS。
Run: `uv run --directory backend pytest -q` → ≥ 上一任务。

- [ ] **Step 5: 提交**

`feat(export): 成品报告`

---

### Task 16: Markdown / TXT 导出

**Files:**
- Modify: `backend/app/services/export_service.py`
- Test: `backend/tests/test_export_service.py`

**Interfaces:**
- Produces: `build_markdown(session, project_id) -> str`、`build_text(session, project_id) -> str`。

- [ ] **Step 1: 写失败测试**

- 卷/章/场景顺序、空场景不产生空段；
- Markdown 标题层级与正文保留；
- TXT 去掉标题号/强调标记，段落保留；
- 空项目仍能导出。

- [ ] **Step 2: 运行确认失败**

Run: `uv run --directory backend pytest tests/test_export_service.py -q` → FAIL。

- [ ] **Step 3: 实现**

按 spec §6.2；TXT 只做保守的 Markdown 标记去除，不改写正文内容。

- [ ] **Step 4: 跑测试与全量**

Run: `uv run --directory backend pytest tests/test_export_service.py -q` → PASS。
Run: `uv run --directory backend pytest -q` → ≥ 上一任务。

- [ ] **Step 5: 提交**

`feat(export): Markdown 与 TXT 导出`

---

### Task 17: EPUB 导出

**Files:**
- Modify: `backend/app/services/export_service.py`
- Test: `backend/tests/test_export_service.py`

**Interfaces:**
- Produces: `build_epub(session, project_id) -> bytes`。

- [ ] **Step 1: 写失败测试**

- 返回 `PK` 开头的 zip；
- 第一个条目是 `mimetype` 且 `compress_type == ZIP_STORED`，内容为 `application/epub+zip`；
- 含 `META-INF/container.xml`、`OEBPS/content.opf`、`OEBPS/nav.xhtml`、每章 XHTML；
- HTML 转义（正文含 `<`、`&`）；
- 空项目也能生成。

- [ ] **Step 2: 运行确认失败**

Run: `uv run --directory backend pytest tests/test_export_service.py -q` → FAIL。

- [ ] **Step 3: 实现**

用 `zipfile.ZipFile(BytesIO(), "w")`；mimetype 先写且 STORED；其余 DEFLATED；手写 OPF/nav/章节 XHTML；段落转 `<p>`，转义。

- [ ] **Step 4: 跑测试与全量**

Run: `uv run --directory backend pytest tests/test_export_service.py -q` → PASS。
Run: `uv run --directory backend pytest -q` → ≥ 上一任务。

- [ ] **Step 5: 提交**

`feat(export): 基础 EPUB 导出`

---

### Task 18: 导出 API 与仪表盘入口

**Files:**
- Create: `backend/app/api/export.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_export_api.py`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/pages/Dashboard.tsx`

**Interfaces:**
- Produces: `GET /api/projects/{id}/export/report`、`GET /api/projects/{id}/export?format=`。
- Consumes: `export_service`。

- [ ] **Step 1: 后端测试与实现**

报告 200/项目 404；三种格式 200 且 `Content-Disposition` 含正确扩展名与 UTF-8 文件名；非法格式 400；路由注册。

- [ ] **Step 2: 前端**

仪表盘新增「导出与成品报告」卡片：报告数字、未闭环 amber 提示、三个下载按钮（用 `<a href>` 直接下载，不需要 fetch）。切项目刷新。

- [ ] **Step 3: 构建与全量**

Run: `uv run --directory backend pytest tests/test_export_api.py -q` → PASS。
Run: `uv run --directory backend pytest -q` → ≥ 上一任务。
Run: `cd frontend && pnpm build && pnpm vitest run` → 干净 / 30 passed。

- [ ] **Step 4: 提交**

`feat(export): 导出接口与仪表盘入口`

---

### Task 19: 临时目录走查与文档收口

**Files:**
- Modify: `docs/superpowers/plans/2026-10-21-p2-remaining-walkthrough.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: 全量基线**

Run: `uv run --directory backend pytest -q`；`cd frontend && pnpm vitest run && pnpm build`。

- [ ] **Step 2: 临时目录走查（不调用模型）**

1. 建项目、卷、章、两场；一场有正文、一场没有。
2. 逻辑自检：无模型时显示警告、不产生问题；plan 阶段无正文可运行。
3. 回写：无模型时警告；面板不误写。
4. 批量：无服务商时任务逐场失败、失败列表可读、可暂停/取消；不覆盖正文。
5. 导出：报告数字正确；MD/TXT 下载可读；EPUB 解压结构正确；空项目可导出。
6. 控制台 0 ERROR；切项目/切场景竞态。
7. 逐项写入走查文档；未验证项如实标注。

- [ ] **Step 3: 更新 CLAUDE.md**

路线图标记 P2 全部完成；追加阶段记录（设计与计划路径、四项产出、迁移 v5/v6、测试数字、真实模型调用次数/tokens/额度、遗留）；§8 追加设计裁定。

- [ ] **Step 4: 提交文档**

```bash
git add docs/superpowers/plans/2026-10-21-p2-remaining-walkthrough.md CLAUDE.md
git commit -m "docs: 归档 P2 收尾走查与阶段记录"
```

---

### Task 20: 整支复查与收口

- [ ] 独立只读复查从分叉点到 HEAD 的全部提交，重点：迁移、逻辑 supersede/指纹、回写 apply 隔离、批量线程与状态机、导出转义。
- [ ] 修复发现并补测试。
- [ ] 全量基线复跑；按前几个切片的方式合并回 master。

## 自审记录

- **Spec 覆盖**：逻辑（Task 1–6）、回写（7–11）、批量（12–14）、导出（15–18）、走查与文档（19）、复查（20）。
- **明确不做**：逻辑图形化、状态历史、伏笔生命周期状态/锁定、阅读器/朗读/EPUB 精修、批量多版本。
- **迁移安全**：v5/v6 各自独立 `requires`，覆盖从 P2a 存量库直接升级的路径。
- **控制力**：AI 产出只进草稿/建议，apply 需要作者勾选；批量不写正文。
- **测试计数**：以实际套件为准，每任务只要求不低于上一任务。
