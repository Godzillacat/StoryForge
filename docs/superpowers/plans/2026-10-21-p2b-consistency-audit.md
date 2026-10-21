# P2b 一致性审计 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 打通「已采纳正文 → 规则检查 + LLM 语义审计 → 问题清单 → 作者处理状态」的一致性审计闭环。

**Architecture:** 规则层是纯函数，永远可离线运行；LLM 层复用现有运行时与「审校」预置，失败只降级为警告；两类问题落到同一张 `audit_issue` 表，按指纹去重与特例抑制；前端在写作台右侧展示问题，处理动作只记录状态并跳转，不自动改稿。

**Tech Stack:** Python 3.13 + FastAPI + SQLAlchemy + SQLite，React 19 + TypeScript + Vite + Tailwind，pytest / vitest。

**Spec:** `docs/superpowers/specs/2026-10-21-p2b-consistency-audit-design.md`

## Global Constraints

- 实施在隔离 worktree（建议 `worktree-p2b-consistency-audit`，从本地 `master` 切出）；master 在收口前不动。
- 基线：后端 **430 passed**，前端 **30 passed**，`pnpm build` 干净。每个任务结束时不得低于基线；新增测试数按实际重算。
- `api` 不写业务逻辑；`services` 不碰 HTTP；`runtime` 不依赖 FastAPI。
- 纯逻辑必须测（pytest / vitest）；**UI 不写自动化测试**。
- 标识符与代码用英文；注释、界面文案、提示词用中文。
- 新表 `audit_issue` 由 `create_all` 建；**本段不新增迁移**。
- 只审已采纳正文（`scene.body`）；不审草稿；作者手动触发；不自动改稿。
- LLM 失败/跳过不得阻塞规则层结果；不得把未结构化结果假装成成功。
- 不写作者真实库；真实模型复验只用库副本与临时数据目录；调用前确认阿里云百炼免费额度。
- 不要用 `git stash`；不要擅自 rebase / 改写历史。
- 每个任务一个提交（或按步骤中的提交点）；提交信息用中文、遵循 Conventional Commits 前缀。
- 规则层的三项检查与三项显式延后（时间线倒退/表外新词/禁用词）以 spec §4 为准，不要顺手加启发式。

---

### Task 1: 审计问题模型与词表

**Files:**
- Create: `backend/app/audit_types.py`
- Create: `backend/app/db/models/audit.py`
- Modify: `backend/app/db/models/__init__.py`
- Test: `backend/tests/test_audit_models.py`
- Test: `backend/tests/test_audit_types.py`

**Interfaces:**
- Produces: `AuditIssue` ORM、`AUDIT_KINDS` / `AUDIT_SEVERITIES` / `AUDIT_SOURCES`、`normalize_kind` / `normalize_severity` / `normalize_resolution`。
- Consumes: 既有 `Base` / `IdMixin` / `TimestampMixin`、`Project`、`Scene`、`GenerationRun`、`SettingEntry`。

- [ ] **Step 1: 写失败测试**

`test_audit_types.py`:
- 中文/英文 kind 与 severity 都能归一；未知值兜底为 `other` / `minor`。
- `normalize_resolution` 接受四种值，拒绝其它值并抛 `ValueError`。
- 三个词表的中文标签与 spec §3.2 一致。

`test_audit_models.py`:
- 新建一条 `AuditIssue` 往返：默认 `status="open"`、`options_json=[]`、`source`/`kind`/`severity` 保留。
- 删除场景级联删除问题。
- 删除 `target_entry_id` 指向的条目后，问题仍在、目标为 `NULL`。
- `run_id` 删除后置 `NULL`（可选，若夹具成本高可只测目标条目）。

- [ ] **Step 2: 运行确认失败**

Run: `uv run --directory backend pytest tests/test_audit_models.py tests/test_audit_types.py -q`
Expected: FAIL（模块/模型不存在）。

- [ ] **Step 3: 实现词表与模型**

`audit_types.py`：按 spec §3.2 定义三张词表与三个归一化函数；`normalize_kind` / `normalize_severity` 不抛错，`normalize_resolution` 抛错。

`db/models/audit.py`：
- 表名 `audit_issue`。
- 字段与 spec §3.1 一致；`project_id` / `scene_id` / `target_entry_id` / `run_id` 外键与 `ondelete` 按 spec；`options_json` 用 `JSON`；`status` 默认 `open`。
- 加 `Index("ix_audit_issue_scene_status", "scene_id", "status")` 与 `fingerprint` 索引。
- 在 `models/__init__.py` 导入并加入 `__all__`。

- [ ] **Step 4: 跑测试与全量**

Run: `uv run --directory backend pytest tests/test_audit_models.py tests/test_audit_types.py -q`
Expected: PASS。
Run: `uv run --directory backend pytest -q`
Expected: 不低于 430；记录实际数。

- [ ] **Step 5: 提交**

```bash
git add backend/app/audit_types.py backend/app/db/models/audit.py backend/app/db/models/__init__.py backend/tests/test_audit_models.py backend/tests/test_audit_types.py
git commit -m "feat(audit): 审计问题模型与词表"
```

---

### Task 2: `scene_text` 槽位

**Files:**
- Modify: `backend/app/runtime/context.py`
- Modify: `backend/app/services/slot_source.py`
- Test: `backend/tests/test_context.py`
- Test: `backend/tests/test_slot_source.py`

**Interfaces:**
- Produces: `SlotSource.scene_text() -> str | None`；`SLOT_REGISTRY["scene_text"]`（`P_NEVER` / `never`）。
- Consumes: `Scene.body`、`DbSlotSource._scene_chain()`。

- [ ] **Step 1: 写失败测试**

`test_context.py`：`SLOT_REGISTRY["scene_text"].over_budget == "never"`，标签为「当前已采纳正文」。
`test_slot_source.py`：
- 有正文返回正文；
- 无正文（None / 空串/纯空白）返回 `None`；
- 没有 `scene_id` 返回 `None`。

- [ ] **Step 2: 运行确认失败**

Run: `uv run --directory backend pytest tests/test_context.py tests/test_slot_source.py -q`
Expected: FAIL。

- [ ] **Step 3: 实现**

`context.py`：`SlotSource` 协议加 `scene_text`；`SLOT_REGISTRY` 加 `SlotSpec("scene_text", "当前已采纳正文", P_NEVER, "never")`。
`slot_source.py`：用 `_scene_chain()`；`body = (scene.body or "").strip()`；非空返回原文，否则 `None`。

- [ ] **Step 4: 跑测试与全量**

Run: `uv run --directory backend pytest tests/test_context.py tests/test_slot_source.py -q`
Expected: PASS。
Run: `uv run --directory backend pytest -q`
Expected: 不低于上一任务。

- [ ] **Step 5: 提交**

```bash
git add backend/app/runtime/context.py backend/app/services/slot_source.py backend/tests/test_context.py backend/tests/test_slot_source.py
git commit -m "feat(context): 当前已采纳正文槽位"
```

---

### Task 3: 规则层三项检查

**Files:**
- Create: `backend/app/audit_rules.py`
- Test: `backend/tests/test_audit_rules.py`

**Interfaces:**
- Produces: `RuleIssue` dataclass 与 `run_rule_checks(body, terms, scene_character_ids, entries) -> list[RuleIssue]`。
- Consumes: `world_service.list_terms` 的投影形状；`SettingEntry` 的 `name` / `aliases_json` / `type`。

- [ ] **Step 1: 写失败测试**

至少覆盖：
- 重复句：同一句出现两次报一条；短于 12 字不报；不同标点切句正确；长句（≥20）为 `major`，否则 `minor`；指纹稳定。
- 称呼歧义：两个人物共用别名「老师」，正文出现「老师」报一条，`target_entry_id is None`；只出现一次或没有该 form 不报。
- 出场人物未提及：场景人物「沈砚」在正文中既无本名也无别名时报一条，带 `target_entry_id`；出现别名时不报。
- 正常正文（无重复、称呼唯一、人物都出现）返回空。
- 空正文返回空。
- `options` 非空、`quote`/`explanation` 非空。

- [ ] **Step 2: 运行确认失败**

Run: `uv run --directory backend pytest tests/test_audit_rules.py -q`
Expected: FAIL。

- [ ] **Step 3: 实现**

按 spec §4.2 实现：
- 句子切分与规范化；重复计数；`quote` 用原句。
- form → character entry ids 映射；歧义 form 在正文中的出现。
- 场景人物名字/别名在正文中的子串检查（含空别名过滤）。
- 指纹：`rule:repetition:<sha1>`、`rule:alias:<form>`、`rule:unmentioned:<entry_id>`。
- 所有规则问题 `severity` 按 spec；`reader_impact` 写可读中文；`options` 2–3 条。
- 不在本任务做时间线/表外新词/禁用词。

- [ ] **Step 4: 跑测试与全量**

Run: `uv run --directory backend pytest tests/test_audit_rules.py -q`
Expected: PASS。
Run: `uv run --directory backend pytest -q`
Expected: 不低于上一任务。

- [ ] **Step 5: 提交**

```bash
git add backend/app/audit_rules.py backend/tests/test_audit_rules.py
git commit -m "feat(audit): 规则层三项确定性检查"
```

---

### Task 4: 审计服务与问题生命周期

**Files:**
- Create: `backend/app/services/audit_service.py`
- Modify: `backend/app/services/text_service.py`（把 `_scene_extra` 提为公开 `scene_extra`，内部调用同步改）
- Test: `backend/tests/test_audit_service.py`

**Interfaces:**
- Produces:
  - `run_audit(session, scene_id) -> dict`
  - `list_audit(session, scene_id) -> dict`
  - `resolve_issue(session, issue_id, resolution) -> dict`
- Consumes: `audit_rules.run_rule_checks`、`audit_types`、`world_service.list_terms/list_entries`、`agent_service.find_by_task_type(session, "continuity")`、`RuntimeService.execute`、`text_service.scene_extra`。

- [ ] **Step 1: 写失败测试**

用 `monkeypatch` 替换 `RuntimeService.execute` 或注入假 `ChatClient`，覆盖：
- 无正文：`ValueError` 文案「还没有已采纳正文」。
- 规则层-only：无审校智能体时返回 `llm_status="skipped"` + 规则问题；有运行记录时不泄漏。
- LLM 成功：假 `RunResult`（`structured=True`, `parsed={"issues":[...]}`）与假 run；问题合并、`llm_status="ok"`、`run_id` 落库。
- 归一化：中文 kind/severity、空 quote 丢弃、30 条上限、目标条目按名字映射；未知值兜底。
- 非结构化 / 运行 error / `ValueError`（无模型）：`unstructured` / `error` / `skipped`，规则问题仍在，warning 可读。
- supersede：第二次审校把第一次 `open` 置 `superseded`；新问题为 `open`。
- 特例：把一条规则问题设为 `exception`，再次审校同指纹被过滤，`suppressed` 计数增加。
- resolve：`story/setting/character` → `resolved`；`exception` → `exception`；非法值抛错；问题不存在抛「审计问题不存在」。
- list：只返回 `open`；`last_audited_at` 为最新问题时间或 `None`。

- [ ] **Step 2: 运行确认失败**

Run: `uv run --directory backend pytest tests/test_audit_service.py -q`
Expected: FAIL。

- [ ] **Step 3: 实现**

`text_service.py`：`_scene_extra` 改名 `scene_extra`（公开），`prepare_generation` / `context_preview` 内调用同步改；行为不变。

`audit_service.py`：
- `_scene(session, scene_id)`：场景不存在抛「场景不存在：...」。
- `run_audit` 按 spec §6.1 流程；先规则、supersede、特例过滤、插入；再尝试 LLM；返回 `run_id / issues / suppressed / llm_status / warning`。
- LLM 降级表按 spec §5.5；`RuntimeService.execute` 返回的 `run.id` 作为 `run_id`；`result.structured` / `result.parsed` / `result.error` / `result.status` 判断。
- `_normalize_llm_issues`：kind/severity/quote/rule_ref/explanation/reader_impact/options/target_entry_id/fingerprint/source。
- `_insert_issues`：批内指纹去重、已有 exception 过滤、插入；返回 (inserted, suppressed)。
- `_serialize_issue`：带 labels 与 `target_entry_name`。
- `list_audit` / `resolve_issue` 按 spec。
- 不写 FTS、不发 HTTP。

- [ ] **Step 4: 跑测试与全量**

Run: `uv run --directory backend pytest tests/test_audit_service.py -q`
Expected: PASS。
Run: `uv run --directory backend pytest -q`
Expected: 不低于上一任务；既有 `test_text_service.py` 保持绿。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/audit_service.py backend/app/services/text_service.py backend/tests/test_audit_service.py
git commit -m "feat(audit): 审计服务与问题生命周期"
```

---

### Task 5: 审校预置智能体

**Files:**
- Modify: `backend/app/agents/roster.py`
- Test: `backend/tests/test_roster.py`
- Test: `backend/tests/test_seed_service.py`

**Interfaces:**
- Produces: `DEFAULT_ROSTER` 中的 `auditor`（`task_type=continuity`、`AUDIT_SCHEMA`、槽位含 `scene_text`）。
- Consumes: `audit_types` 的中文标签（若用于 schema title）；`CHARACTER_FIELDS` 既有派生。

- [ ] **Step 1: 写失败测试**

`test_roster.py`：
- `auditor` 存在，名称/定位/颜色/task_type/param_profile/trigger_mode 正确；
- `output_schema` 非空，`issues` 为必填数组，字段有中文 title；
- 槽位列表与 spec §5.2 一致，含 `scene_text`；
- 提示词不含手写英文键，变量 ⊆ `SLOT_REGISTRY`（既有不变量测试应自动覆盖）。

`test_seed_service.py`：`seed_agents` 在全新库创建 `auditor`；`output_schema_json` 非空；`scene_text` 在 `context_slots_json`。

- [ ] **Step 2: 运行确认失败**

Run: `uv run --directory backend pytest tests/test_roster.py tests/test_seed_service.py -q`
Expected: FAIL。

- [ ] **Step 3: 实现**

`roster.py`：
- 定义 `AUDIT_SCHEMA`（spec §5.3；字段英文键 + 中文 title；`issues` 为 array，每项 required 字段齐全）。
- 定义 `AUDITOR_PROMPT`：按 spec §5.2 的 5 条要点，使用已注册槽位变量；不写英文键；不出现「JSON」字面。
- `DEFAULT_ROSTER` 追加 `auditor` 项（`task_type="continuity"`、`param_profile="balanced"`、`trigger_mode="manual"`、`note` 说明只审已采纳正文）。

- [ ] **Step 4: 跑测试与全量**

Run: `uv run --directory backend pytest tests/test_roster.py tests/test_seed_service.py -q`
Expected: PASS。
Run: `uv run --directory backend pytest -q`
Expected: 不低于上一任务。

- [ ] **Step 5: 提交**

```bash
git add backend/app/agents/roster.py backend/tests/test_roster.py backend/tests/test_seed_service.py
git commit -m "feat(agents): 审校预置智能体"
```

---

### Task 6: 审计 API

**Files:**
- Create: `backend/app/api/audit.py`
- Modify: `backend/app/api/main.py`（按现有路由循环登记）
- Modify: `backend/app/api/schemas.py`（`AuditResolve`）
- Test: `backend/tests/test_audit_api.py`

**Interfaces:**
- Produces: `POST /api/scenes/{id}/audit`、`GET /api/scenes/{id}/audit`、`PATCH /api/audit/issues/{id}`。
- Consumes: `audit_service`、`get_session`、`AuditResolve`。

- [ ] **Step 1: 写失败测试**

- POST 成功：场景有正文，规则层问题返回；无模型时 `llm_status="skipped"` + warning；状态 200。
- POST 无正文：400，文案可读。
- POST 场景不存在：404。
- GET：返回 `issues` 与 `last_audited_at`；无审校时 `last_audited_at is null`。
- PATCH：`{"resolution":"exception"}` 成功，返回 `status="exception"`；非法值 422/400；问题 404。
- 路由注册：应用能启动，路径可访问。

- [ ] **Step 2: 运行确认失败**

Run: `uv run --directory backend pytest tests/test_audit_api.py -q`
Expected: FAIL（路由不存在）。

- [ ] **Step 3: 实现**

- `api/audit.py`：router prefix `/api`；三个路由；错误映射（场景/问题 404、无正文/非法处理 400、章节结构 409）；PATCH 请求模型 `AuditResolve`（`resolution: Literal[...]`）。
- `api/schemas.py`：追加 `AuditResolve`。
- `api/main.py`：在现有 `for module in (...)` 中加 `audit`。
- API 层只做参数校验、错误翻译与调用。

- [ ] **Step 4: 跑测试与全量**

Run: `uv run --directory backend pytest tests/test_audit_api.py -q`
Expected: PASS。
Run: `uv run --directory backend pytest -q`
Expected: 不低于上一任务。

- [ ] **Step 5: 提交**

```bash
git add backend/app/api/audit.py backend/app/api/main.py backend/app/api/schemas.py backend/tests/test_audit_api.py
git commit -m "feat(api): 一致性审计接口"
```

---

### Task 7: 前端审计 API 客户端

**Files:**
- Modify: `frontend/src/api/client.ts`

**Interfaces:**
- Produces: `AuditIssue` / `AuditResult` / `AuditView` / `AuditResolution`；`getSceneAudit` / `runSceneAudit` / `resolveAuditIssue`。

- [ ] **Step 1: 实现类型与三个方法**

- 类型与 spec §6.2 对齐（含 labels 与 `target_entry_name`）。
- `runSceneAudit` 用 `POST`，无 body；`resolveAuditIssue` 用 `PATCH` + `JSON_HEADERS`。
- `getSceneAudit` 用 `GET`。
- 复用现有 `request` 助手；不新增依赖。

- [ ] **Step 2: 构建**

Run: `cd frontend && pnpm build`
Expected: 干净。
Run: `cd frontend && pnpm vitest run`
Expected: 30 passed。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/api/client.ts
git commit -m "feat(frontend): 审计 API 客户端"
```

---

### Task 8: 审校问题面板

**Files:**
- Create: `frontend/src/components/writing/AuditPanel.tsx`

**Interfaces:**
- Consumes: `AuditIssue`、`AuditResolution`。
- Produces: 受控展示组件，供 Task 9 使用。

- [ ] **Step 1: 实现组件**

Props 建议：
```ts
interface Props {
  issues: AuditIssue[]
  lastAuditedAt: string | null
  running: boolean
  warning: string
  canRun: boolean
  onRun: () => void
  onResolve: (issue: AuditIssue, resolution: AuditResolution) => void
}
```
- 标题「一致性审计」、上次审校时间、「审校 / 重新审校」按钮。
- 警告用 amber 样式。
- 问题卡片：来源/严重度/类型标签、原文引用（`whitespace-pre-wrap`）、冲突对象、解释、读者观感、修正方向列表。
- 四个按钮：改故事 / 改设定 / 改人物 / 接受为特例；`running` 时禁用。
- 空态：`!canRun` → 「采纳正文后可审校」；无问题且无 warning → 「本次没有发现问题」；无上次审校 → 「还没有审校」。
- 不写组件测试；不新增依赖。

- [ ] **Step 2: 构建**

Run: `cd frontend && pnpm build`
Expected: 干净（组件尚未被引用也应通过 tsc）。
Run: `cd frontend && pnpm vitest run`
Expected: 30 passed。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/writing/AuditPanel.tsx
git commit -m "feat(frontend): 一致性审校面板"
```

---

### Task 9: 写作台审校入口与世界观深链

**Files:**
- Modify: `frontend/src/pages/Writing.tsx`
- Modify: `frontend/src/pages/World.tsx`

**Interfaces:**
- Consumes: Task 7 的三个客户端方法、Task 8 的 `AuditPanel`。
- Produces: `/write` 的审校按钮/状态/右栏；`/world?entry=<id>` 选中条目。

- [ ] **Step 1: 写作台状态与加载**

- 新增 `auditIssues`、`auditLastAt`、`auditLoading`、`auditWarning`。
- 场景加载 `Promise.allSettled([getSceneText, getContextPreview, getSceneAudit])`，全部受 `sceneToken` 守卫；审校结果迟到不得写入新场景。
- 切场景/切项目清空审校状态；`previewLoading` 等既有重置保持。
- `hasUnsaved` 不因审校改变。

- [ ] **Step 2: 审校动作**

- `runAudit`：捕获 `sceneId` 与 `sceneToken`；`setAuditLoading(true)`；调用 `runSceneAudit`；token 不匹配则丢弃；设置 issues/warning/lastAt；`finally` 清 loading。
- 与生成互斥：`auditLoading` 时禁用生成/保存/采纳；`generating`/`busy` 时禁用审校。
- `resolveIssue`：捕获 token；PATCH；失败只提示；成功且 `status !== "open"` 从列表移除；`setting`/`character` 且 `target_entry_id` 存在 → `navigate('/world?entry=<id>')`；没有目标 → `navigate('/world')`；`story` → 提示「已标记为改故事，请在正文中修改」；`exception` → 提示「已记为特例」。
- 工具栏加「审校」按钮（`text?.has_body` 且非 busy/generating/auditLoading）；右栏加 `AuditPanel`。

- [ ] **Step 3: 世界观深链**

- `World.tsx` 用 `useSearchParams` 读取 `entry`；条目加载完成后，若存在匹配 id 则 `selectEntry`；找不到不崩溃、显示提示。
- 不改变既有手工选择行为。

- [ ] **Step 4: 构建与既有测试**

Run: `cd frontend && pnpm build`
Expected: 干净。
Run: `cd frontend && pnpm vitest run`
Expected: 30 passed（若新增纯函数测试则按实际数）。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/pages/Writing.tsx frontend/src/pages/World.tsx
git commit -m "feat(frontend): 写作台审校入口与设定深链"
```

---

### Task 10: 走查、真实模型复验与阶段文档

**Files:**
- Create: `docs/superpowers/plans/2026-10-21-p2b-walkthrough.md`
- Modify: `CLAUDE.md`

**Interfaces:**
- 本任务不新增产品代码；发现缺陷时回到对应任务修复。

- [ ] **Step 1: 全量基线**

Run: `uv run --directory backend pytest -q`
Expected: 全绿（记录实际数）。
Run: `cd frontend && pnpm vitest run && pnpm build`
Expected: 30 passed；build 干净。

- [ ] **Step 2: 临时目录走查（不调用模型）**

1. 临时 `STORYFORGE_DATA_DIR`；后端 8756、前端 5273。
2. 建项目/卷/章/两场；保存一段带重复句、且漏掉一个出场人物的正文。
3. 点「审校」：无模型 → 规则问题出现、`llm_status=skipped` 警告、控制台 0 报错。
4. 「改故事」「改设定」「改人物」「接受为特例」各点一次；确认状态记录、跳转与提示；再次审校特例不重复上报。
5. 切场景/切项目：迟到的审校响应不覆盖新场景。
6. 空态：无正文、未审校、无问题。
7. 结果写入走查文档，逐项勾选；未验证项写「未验证」。

- [ ] **Step 3: 真实模型复验（作者库副本）**

1. 确认阿里云百炼 `qwen3.8-flash` 额度；只用该模型。
2. SQLite 备份 API 复制作者库 + `secrets.bin`；作者原库不写入，前后哈希一致。
3. 副本启动：`audit_issue` 表存在；「审校」预置出现；原有数据一条不少；二次启动不重复预置。
4. 在副本工作室给审校绑定 `qwen3.8-flash`（`POST /api/agents/{id}/versions` 保留其余字段）。
5. 选已有已采纳正文的场景（没有就只在副本补建）；点审校，记录耗时/估算 token/问题数/`llm_status`；确认问题带原句引用与冲突对象。
6. 处理一条「改设定」、一条「接受为特例」；再次审校，确认特例不重复上报。
7. 检查 `audit_issue` 行与 `generation_run`；控制台 0 ERROR；删除副本。

- [ ] **Step 4: 更新 CLAUDE.md**

1. 路线图：P2 剩余项中标记「一致性审计（P2b）」完成；逻辑自检、回写、批量、导出仍未开始。
2. 追加阶段记录「2026-10-21 · P2b 一致性审计」，包含：设计/计划路径；数据表；规则层三项与三项延后；审校预置与 `scene_text` 槽位；API；前端入口；测试数字；真实模型调用次数/耗时/token/额度；遗留。
3. §8 变更记录追加：
   - P2b 选择手动审校而非生成后自动（偏差与理由）；
   - 规则层只做三项、时间线/表外新词/禁用词显式延后；
   - 问题只记录状态与跳转，不自动改稿；
   - `audit_issue` 新表由 `create_all` 建，不新增迁移；
   - LLM 失败降级为规则层 + warning；
   - 审校任务类型复用 `continuity`。
4. 如实记录未完成项；不要把未验证的检查写成已完成。

- [ ] **Step 5: 提交文档**

```bash
git add docs/superpowers/plans/2026-10-21-p2b-walkthrough.md CLAUDE.md
git commit -m "docs: 归档 P2b 走查与阶段记录"
```

---

## 自审记录（计划完成后核对）

- **Spec 覆盖**：数据模型/词表（Task 1）、槽位（Task 2）、规则层（Task 3）、服务/生命周期/降级（Task 4）、审校预置（Task 5）、API（Task 6）、前端客户端/面板/页面（Task 7–9）、验证与文档（Task 10）。
- **明确不做**：逻辑自检、自动审校、一键应用、时间线倒退/表外新词/禁用词、草稿审校、问题历史、FTS/导出/批量。
- **类型/契约一致性**：`audit_types` 的词表是唯一真相；API 返回 labels；前端不维护第二份映射；`scene_text` 在协议、注册表、取数、预置四处一致。
- **测试计数**：基线 430 / 30 / build；每个任务的期望新增用例在任务中列出，最终以实际套件为准。
