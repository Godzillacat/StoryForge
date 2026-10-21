# P3b Implementation Plan：管线编排

> **For agentic workers:** 按任务顺序实施，每个任务先写失败测试再实现，提交信息用中文 Conventional Commits。

**Goal:** 让作者看见并编辑一条按自己顺序串起来的智能体流水线，并能连续执行、在检查点停下、出错时说清原因。

**Architecture:** 四张新表（`pipeline` / `pipeline_node` / `pipeline_run` / `pipeline_run_node`，全走 `create_all`）；执行器注册表把「每个节点做什么」关在一个文件里；状态机是**同步单步函数** `advance_run`，线程只循环调用它，因此每条分支都能被 pytest 直接覆盖。

**Tech Stack:** Python 3.13 + FastAPI + SQLAlchemy + SQLite，React 19 + TypeScript + Vite + Tailwind，pytest / vitest。

**Spec:** `docs/superpowers/specs/2026-10-21-p3b-pipeline-design.md`

## Global Constraints

- 实施在隔离 worktree `worktree-p3b-pipeline`（从本地 `master` 切出）；master 在收口前不动。
- 基线：后端 **653 passed**，前端 **30 passed**，`pnpm build` 干净。
- `api` 不写业务逻辑；`services` 不碰 HTTP；`runtime` 不依赖 FastAPI。
- **本段无迁移**：四张全是新表，归 `create_all`。
- **写库边界**：只有 `idea_parse` 写 `idea.parsed_json`；其余节点只产出运行记录（D-03 / D-04）。
- **不写作者真实库**；真实模型复验只用临时数据目录，模型用 `qwen3.8-flash`。
- 不要用 `git stash`；不要擅自 rebase / 改写历史。
- 每个任务一个提交。

---

### Task 1: 词表与默认模板（`pipeline_types.py`）

**Files:**
- Create: `backend/app/pipeline_types.py`
- Test: `backend/tests/test_pipeline_types.py`

**Interfaces:**
- Produces: `PIPELINE_POLICIES` / `POLICY_LABELS` / `RUN_STATUSES` / `NODE_STATUSES` / `DEFAULT_PIPELINE` / `normalize_policy(value)` / `default_nodes()`。
- Consumes: 无。

- [ ] **Step 1: 写失败测试**

- `DEFAULT_PIPELINE` 依次是 `idea_parse` / `architecture` / `worldbuilding` / `chapter_plan` / `scene_plan`。
- 只有 `architecture` 与 `chapter_plan` 是检查点（对应产品 §5.3 的 ★拍板 / ★调整）。
- `normalize_policy`：三档原样通过，未知值回落 `key_only`。
- `default_nodes()` 返回**新列表**（改一个元素不影响下一次调用）。
- 所有 `task_type` 都在 `roster.TASK_TYPES` 里。

- [ ] **Step 2: 实现**

```python
DEFAULT_PIPELINE = [
    {"name": "灵感解析", "task_type": "idea_parse", "checkpoint": False},
    {"name": "架构推荐", "task_type": "architecture", "checkpoint": True},
    {"name": "世界观补全", "task_type": "worldbuilding", "checkpoint": False},
    {"name": "章纲策划", "task_type": "chapter_plan", "checkpoint": True},
    {"name": "场景卡", "task_type": "scene_plan", "checkpoint": False},
]
```

- [ ] **Step 3: 跑测试** `cd backend && uv run pytest tests/test_pipeline_types.py -q`

- [ ] **Step 4: 提交** `feat(pipeline): 管线词表与默认模板`

---

### Task 2: 四张表

**Files:**
- Create: `backend/app/db/models/pipeline.py`
- Modify: `backend/app/db/models/__init__.py`
- Test: `backend/tests/test_pipeline_models.py`

**Interfaces:**
- Produces: `Pipeline` / `PipelineNode` / `PipelineRun` / `PipelineRunNode`。
- Consumes: `Base`、`Project`。

- [ ] **Step 1: 写失败测试**

- `Pipeline.project_id` 唯一；删除项目级联删除管线与运行。
- 删除管线级联删除节点；**不**级联删除历史运行（`pipeline_run.pipeline_id` 不建外键）。
- `PipelineRunNode` 默认 `status="pending"`、`summary_json={}`。
- `PipelineRun` 默认 `status="paused"`、`cursor=0`。

- [ ] **Step 2: 实现**

按 spec §3 建表。注意：
- `pipeline_run.pipeline_id` 是 `String(36)` **不加外键** —— 管线被改/删不应影响历史运行。
- `pipeline_run_node` 存 `name / task_type / agent_id` 的快照副本。
- 索引：`ix_pipeline_node_pipeline`、`ix_pipeline_run_project`、`ix_pipeline_run_node_run`。

- [ ] **Step 3: 跑测试**，再跑全量确认 `create_all` 不报错。

- [ ] **Step 4: 提交** `feat(pipeline): 管线与运行的数据表`

---

### Task 3: 执行器注册表

**Files:**
- Create: `backend/app/pipeline_executors.py`
- Test: `backend/tests/test_pipeline_executors.py`

**Interfaces:**
- Produces: `Executor(label, check, run)`、`EXECUTORS`、`get_executor(task_type)`、`NodeOutcome(summary, message=None)`。
- Consumes: `RuntimeService`、`agent_service`、`architecture_service`、`idea_service`、`chapter_plan_service`。

- [ ] **Step 1: 写失败测试**

每个执行器两条：
- `check()` 在缺前置时返回**含「去哪补」的中文原因**，齐全时返回 `None`。
- `run()` 用假传输层跑通，返回的摘要含 spec §4 表里承诺的键。

重点覆盖：
- `idea_parse` 无灵感 → 阻塞；有灵感 → 摘要含 `fields` 与 `open_questions`，且**写回了 `idea.parsed_json`**。
- `architecture` 没有已解析灵感 → 阻塞；成功时**不**写 `architecture` 表。
- `chapter_plan` 没有幕骨架 → 阻塞；成功时摘要含 `volumes` / `chapters`。
- `scene_plan` 没有章 → 阻塞。
- 未知 `task_type` → `get_executor` 返回 `None`。

- [ ] **Step 2: 实现**

每个执行器的 `run` 都走 `RuntimeService(session).execute(project_id, agent_id, extra)`；
`agent_id` 优先取节点绑定的，否则 `agent_service.find_by_task_type`。
**任何执行器都不写项目结构**（`idea_parse` 的 `write_parsed` 是唯一例外，与单点按钮一致）。

- [ ] **Step 3: 跑测试**，再跑全量。

- [ ] **Step 4: 提交** `feat(pipeline): 节点执行器注册表`

---

### Task 4: 状态机（`advance_run`）

**Files:**
- Create: `backend/app/services/pipeline_service.py`
- Test: `backend/tests/test_pipeline_service.py`

**Interfaces:**
- Produces: `ensure_pipeline`、`update_pipeline`、`reset_pipeline`、`start_run`、`advance_run`、`pause_run`、`resume_run`、`cancel_run`、`recover_runs`、`serialize_*`。
- Consumes: Task 2/3。

- [ ] **Step 1: 写失败测试**（直接调 `advance_run`，不起线程）

- 管线懒创建：`ensure_pipeline` 两次调用只建一条。
- `update_pipeline` 整体替换节点并重排 `seq`；空列表被拒。
- 开始运行：创建 run + 全部节点 `pending`，节点内容**快照**自当前管线。
- **disabled 节点** → `skipped`，游标前进。
- **未知 task_type** → `skipped` 并写明原因。
- **check() 阻塞** → 该节点 `blocked`，run → `paused`，**后续节点保持 pending**。
- **执行失败**（假传输层抛错）→ 节点 `failed`，run → `paused`。
- **三档策略**：`every` 在每个 ok 节点后 `awaiting`；`key_only` 只在 `checkpoint` 节点后；`auto` 不暂停，一直跑到 `completed`。
- **继续**：从 `awaiting` 恢复 → 下一步；从 `blocked` 节点继续 → **重试该节点**。
- **取消**：run → `cancelled`，未执行的节点也标 `cancelled`；已在跑的节点保持原状态。
- **末尾** → `completed`，`message` 为空。
- **快照隔离**：运行开始后改管线，进行中的运行仍按旧节点跑。

- [ ] **Step 2: 实现**

```python
def advance_run(session: Session, run_id: str) -> None:
    """执行一步。返回时 run 可能推进、暂停、完成或失败。"""
```

要点：
- 每一步**重新读 run**（线程里跨 session），`cursor` 越过末尾即完成。
- 节点执行前后各提交一次，保证重启后进度不丢。
- 检查点判断在节点成功后：`every` / `key_only and node.checkpoint` → `awaiting`。
- 阻塞与失败都把 run 设为 `paused` 并写 `message`。

- [ ] **Step 3: 线程与控制**

`start_run` / `resume_run` 启动守护线程循环 `advance_run` 直到 run 不再 `running`；`_ACTIVE` 集合 + 锁保证同项目只有一个。

- [ ] **Step 4: 跑测试**，再跑全量。

- [ ] **Step 5: 提交** `feat(pipeline): 运行状态机与线程`

---

### Task 5: API 与重启恢复

**Files:**
- Create: `backend/app/api/pipeline.py`
- Modify: `backend/app/main.py`（注册路由、lifespan 调 `recover_runs`）
- Modify: `backend/app/api/schemas.py`
- Test: `backend/tests/test_pipeline_api.py`

**Interfaces:**
- Consumes: Task 4。

- [ ] **Step 1: 写失败测试**

- `GET /api/projects/{id}/pipeline` 懒创建并返回 5 个默认节点。
- `PUT` 替换节点与策略；空节点列表 → 400。
- `reset` 回到默认模板。
- 开始运行后立即 `GET .../runs/latest` 能看到 run。
- 同项目第二次开始 → 409。
- 不存在的 run → 404。
- `recover_runs`：`running` → `paused`，节点 `running` → `pending`。

- [ ] **Step 2: 实现**，错误映射按 spec §6。

- [ ] **Step 3: 跑测试**，再跑全量。

- [ ] **Step 4: 提交** `feat(pipeline): 管线接口与重启恢复`

---

### Task 6: 前端 `/pipeline`

**Files:**
- Create: `frontend/src/pages/Pipeline.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/api/client.ts`
- Test: `frontend/src/lib/*.test.ts`（若有纯逻辑）

- [ ] **Step 1: 类型与调用** —— `Pipeline` / `PipelineNode` / `PipelineRun` / `PipelineRunNode` 类型与 8 个方法。

- [ ] **Step 2: 页面**

- 顶部：策略下拉 + 开始 / 恢复默认。
- 节点表：序号、名称、任务类型、绑定智能体、检查点、启用、上移 / 下移 / 删除。
- 追加节点：选任务类型。
- 运行面板：状态、进度、每节点徽标与消息、去审阅链接、暂停 / 继续 / 取消、2 秒轮询。
- 底部提示：正文写作在写作台 / 批量生成。

- [ ] **Step 3: 跑测试与构建**

- [ ] **Step 4: 提交** `feat(frontend): 管线编排页`

---

### Task 7: 走查、真实模型复验与文档

**Files:**
- Create: `docs/superpowers/plans/2026-10-21-p3b-walkthrough.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: 临时数据目录走查**（假传输层）：编辑节点、三档策略、阻塞提示、继续重试、取消、链接跳转。
- [ ] **Step 2: 真实模型复验**（临时目录，`qwen3.8-flash`）：灵感解析 → 架构推荐自动档，两次调用。
- [ ] **Step 3: 文档同步与提交**

---

## 自检

| 检查 | 结果 |
|---|---|
| spec 每条验收标准都有任务覆盖 | 可编辑→T1/T2/T4/T6；执行与检查点→T4；前置条件→T3/T4；不越权→T3；复验→T7 |
| 是否新增迁移 | 否，四张新表走 `create_all` |
| 状态机是否可脱离线程测试 | 是，`advance_run` 是同步单步函数 |
| 是否引入重型依赖 | 无 |
