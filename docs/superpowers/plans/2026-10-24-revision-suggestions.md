# 生成修订建议 · 逐条确认 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 影响面面板能针对当前目标生成结构化修订建议，作者逐条勾选后一次性应用，锁定与已变化的对象被跳过。

**Architecture:** 复用影响面分析得到下游清单 → 过滤出未锁的场景/章 → 组两个临时槽位跑「修订建议师」 → 建议落在 `generation_run.parsed_json`（不建表）→ 应用时服务端从运行记录取内容、只收下标，写字段并记改动历史。

**Tech Stack:** FastAPI + SQLAlchemy + pytest；React + TS + vitest。

**Spec:** `docs/superpowers/specs/2026-10-24-revision-suggestions-design.md`

## Global Constraints

- **只改结构化字段**：场景 `goal/conflict/turn`、章 `summary`；绝不写正文。
- 建议**只存在 `generation_run`**，不建新表；应用请求**只带下标**，内容从运行记录取。
- 应用前三条硬检查：字段白名单、对象未锁（场景走 `effective_scene_lock`，章走章锁 + 卷锁）、现值 `== before`。
- 模型给的 `target_label` 对不上就丢弃并计数，**不许猜**。
- 单次最多 12 条建议；同一对象同一字段只留第一条。
- 锁定对象**不生成**建议（双重：生成时过滤，应用时再查）。
- 界面文案、注释中文；标识符英文；不新增依赖。

## Review Focus

1. **标签歧义**：两个章同名、两个场景标签撞车时，映射必须精确到 id，不能"第一个匹配"就写。
2. **before 伪造**：`before` 必须由服务端填当前值；模型返回的 before 一律忽略。
3. **下标越界 / 重复**：`accepted` 含负数、越界、重复时不能写坏数据。
4. **锁定竞态**：生成后对象被锁，应用时必须跳过而不是写入。
5. **空与失败**：影响面为空、全是锁定、模型 0 条、模型失败 —— 四种都不能显示半截 JSON。

## File Structure

- `backend/app/runtime/context.py` — 注册两个新槽位
- `backend/app/services/slot_source.py` — `__getattr__` 通用转发 `extra_slots`
- `backend/app/agents/roster.py` — `REVISION_SCHEMA` / `REVISION_PROMPT` / 预置 / `TASK_TYPES`
- `backend/app/services/revision_service.py`（新建）— `suggest()` / `apply()`
- `backend/app/api/impact.py` — 两个路由
- `backend/app/api/schemas.py` — `RevisionSuggestRequest` / `RevisionApplyRequest`
- `backend/tests/test_revision_service.py`、`backend/tests/test_revision_api.py`（新建）
- `frontend/src/api/client.ts`、`frontend/src/components/Locking.tsx`、`frontend/src/lib/revisionView.ts`（新建）

---

### Task 1: 槽位、预置与任务类型

**Files:**
- Modify: `backend/app/runtime/context.py:53-74`
- Modify: `backend/app/services/slot_source.py:42-56`
- Modify: `backend/app/agents/roster.py`（`TASK_TYPES`、`TASK_TYPE_LABELS`、新 schema/prompt、`PRESETS` 末尾）
- Test: `backend/tests/test_revision_service.py`（新建，先放槽位用例）

**Interfaces:**
- Produces: 槽位键 `impact_target`、`impact_candidates`；`task_type="revision_suggest"`；预置 `preset_key="revision-advisor"`

- [ ] **Step 1: 写失败的测试**

```python
def test_impact_slots_render_from_extra(session, project):
    from app.services.runtime_service import RuntimeService
    from app.services import agent_service
    agent = agent_service.find_by_task_type(session, "revision_suggest")
    assert agent is not None
    prepared = RuntimeService(session).prepare_context(
        project.id, agent.id,
        {"impact_target": "主角动机改为替妹妹赎罪", "impact_candidates": "1. 第1卷 第1章 场景2 · 目标：旧值"},
    )
    assert "主角动机" in prepared[2].prompt
    assert "场景2" in prepared[2].prompt


def test_revision_agent_has_contract_and_slots(session):
    from app.services import agent_service
    agent = agent_service.find_by_task_type(session, "revision_suggest")
    version = session.get(type(agent).__mro__[0], agent.current_version_id) if False else None
    assert agent.task_type == "revision_suggest"
    assert agent.preset_key == "revision-advisor"
```

> 第二条写成直接读 `agent.current_version_id` 对应版本并断言 `output_schema_json` 与 `context_slots_json` 含两个新槽位；`session.get` 的类用 `from app.db.models.agent import AgentVersion`。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend; $env:UV_CACHE_DIR="$env:TEMP\sf-uv-cache"; uv run pytest tests/test_revision_service.py -q`
Expected: FAIL（找不到任务类型 / 槽位未注册）

- [ ] **Step 3: 实现**

`context.py` 的 `SLOT_REGISTRY` 加：

```python
SlotSpec("impact_target", "这次改了什么", P_NEVER, "never"),
SlotSpec("impact_candidates", "受影响对象的现值", P_HIGH, "summarize"),
```

`slot_source.py` 的 `DbSlotSource` 加：

```python
def __getattr__(self, name: str):
    """未显式实现的槽位从 `extra_slots` 取 —— 调用方显式传的临时槽位。"""
    if name.startswith("_"):
        raise AttributeError(name)

    def _from_extra() -> str | None:
        value = self._extra.get(name)
        return str(value) if value else None

    return _from_extra
```

`roster.py`：
- `TASK_TYPES` 加 `"revision_suggest"`，`TASK_TYPE_LABELS` 加 `"revision_suggest": "修订建议"`。
- 新增 `REVISION_SCHEMA`（`suggestions` 数组，元素 `target_label/field/after/reason` 全必填，另加 `open_questions: string[]`）与 `REVISION_PROMPT`（中文；要求 ≤12 条、只改四个字段、`reason` 一句话、不要编造对象名；**不写英文键**）。
- `PRESETS` 末尾加一张卡：`key="revision-advisor"`、`name="修订建议师"`、`task_type="revision_suggest"`、`context_slots=["project_core","story_bible","impact_target","impact_candidates"]`、`output_schema=REVISION_SCHEMA`、`param_profile="balanced"`、`trigger_mode="manual"`。

- [ ] **Step 4: 跑测试确认通过**

Run: 同 Step 2
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/runtime/context.py backend/app/services/slot_source.py backend/app/agents/roster.py backend/tests/test_revision_service.py
git commit -m "feat: 修订建议师的槽位、契约与预置"
```

---

### Task 2: `revision_service.suggest()`

**Files:**
- Create: `backend/app/services/revision_service.py`
- Test: `backend/tests/test_revision_service.py`

**Interfaces:**
- Consumes: `impact_service.analyze()`、`lock_service.effective_scene_lock`、`agent_service.find_by_task_type`、`RuntimeService.execute`
- Produces: `suggest(session, project_id, target_type, target_id, client=None) -> dict`
  `{run_id: str|None, llm_status: "ok"|"skipped"|"error", suggestions: list[dict], dropped: int, warning: str}`
  每条 `{index, target_type, target_id, target_label, field, field_label, before, after, reason}`

- [ ] **Step 1: 写失败的测试**

用 `HttpxChatClient(transport=httpx.MockTransport(handler))` 返回固定契约 JSON（沿用 `tests/test_world_api.py:161` 的写法）。断言：

```python
def test_suggest_filters_locked_and_unknown_labels(session, project_with_scenes, fake_client):
    result = revision_service.suggest(session, project.id, "architecture", arch_id, client=fake_client)
    assert result["llm_status"] == "ok"
    labels = [s["target_label"] for s in result["suggestions"]]
    assert all("锁定" not in label for label in labels)
    assert result["dropped"] >= 1          # 处理器里混一条编造的对象名
    assert all(s["before"] for s in result["suggestions"])   # before 由服务端填
    assert all(s["field"] in {"goal", "conflict", "turn", "summary"} for s in result["suggestions"])


def test_suggest_caps_at_twelve_and_dedupes(session, project_with_many_scenes, fake_client):
    result = revision_service.suggest(...)
    assert len(result["suggestions"]) <= 12
    keys = [(s["target_id"], s["field"]) for s in result["suggestions"]]
    assert len(keys) == len(set(keys))
```

- [ ] **Step 2: 跑测试确认失败**（模块不存在）

- [ ] **Step 3: 实现**

要点（按顺序）：
1. `report = impact_service.analyze(...)`；取 `report["groups"]` 里 `type in {"scene","chapter"}` 且 `locked is False` 的 items。
2. 组装 `candidates`：场景标签用 `impact_service.scene_label(volume, chapter, scene.seq)`（需要按 item.id 回表拿 seq 与所属卷章）；章标签用 `f"第{chapter.seq + 1}章（{chapter.title}）"`。`before` 取当前字段值（场景三字段拼成一段、章摘要一段），写进候选清单文本。
3. 取前 12 条；空则返回 `llm_status="skipped", warning="没有可建议的下游对象"`。
4. `agent_service.find_by_task_type(session, "revision_suggest")`；缺失 → skipped + 中文提示。
5. `RuntimeService(session, client=client).execute(project.id, agent.id, {"impact_target": ..., "impact_candidates": ...}, allow_missing=True)`。
6. 从 `run.parsed_json` 取 `suggestions`；逐条：`target_label` 精确匹配候选（**先建 label→对象映射，重复 label 直接判为歧义丢弃**）→ `field` 白名单 → 同 (id, field) 去重 → 填 `before`（服务端当前值）与 `index`。
7. 失败（异常）→ `llm_status="error"` + 中文原因，不抛 500。

- [ ] **Step 4: 跑测试确认通过**
- [ ] **Step 5: 提交** `feat: 修订建议生成（过滤、映射、上限）`

---

### Task 3: `revision_service.apply()`

**Files:**
- Modify: `backend/app/services/revision_service.py`
- Test: `backend/tests/test_revision_service.py`

**Interfaces:**
- Produces: `apply(session, project_id, run_id, accepted: list[int]) -> dict`
  `{applied: [{index, target_label, field}], skipped: [{index, reason}]}`

- [ ] **Step 1: 写失败的测试**

```python
def test_apply_writes_only_accepted_and_records_history(session, project, run_with_suggestions):
    out = revision_service.apply(session, project.id, run.id, [0])
    assert [a["index"] for a in out["applied"]] == [0]
    assert session.get(Scene, scene_id).goal == "新的目标"
    rows = session.scalars(select(ChangeLog).where(ChangeLog.target_id == scene_id)).all()
    assert len(rows) == 1 and rows[0].source == "ai"


def test_apply_skips_stale_locked_and_bad_indices(session, project, run_with_suggestions):
    scene.goal = "生成后被作者改过"
    out = revision_service.apply(session, project.id, run.id, [0, 1, 99, -1, 0])
    reasons = {s["reason"] for s in out["skipped"]}
    assert "现值已变化" in reasons and "已锁定" in reasons and "下标无效" in reasons
    assert out["applied"] == []
```

- [ ] **Step 2: 跑测试确认失败**
- [ ] **Step 3: 实现**

1. 读 `GenerationRun`，校验 `project_id` 一致、`parsed_json` 有 `suggestions`，否则 `ValueError`（路由映射 404/400）。
2. 下标去重、越界/负数 → skipped「下标无效」。
3. 每条：对象仍存在（否则「对象已删除」）→ 锁检查（场景 `effective_scene_lock`；章 `chapter.locked or volume.locked`）→ 现值 `!= before` →「现值已变化」→ 白名单兜底。
4. 写入字段 + `change_service.record(..., target_type, target_id, target_label, action="update", source="ai", summary=f"修订建议 · {field_label}")`；**同一事务提交**。
5. 返回 applied/skipped。

- [ ] **Step 4: 跑测试确认通过**
- [ ] **Step 5: 提交** `feat: 修订建议逐条应用（锁、现值、下标）`

---

### Task 4: API 与请求模型

**Files:**
- Modify: `backend/app/api/impact.py`
- Modify: `backend/app/api/schemas.py`
- Test: `backend/tests/test_revision_api.py`（新建）

**Interfaces:**
- Produces: `POST /api/projects/{id}/impact/revisions`、`POST /api/projects/{id}/impact/revisions/apply`

- [ ] **Step 1: 写失败的测试**

```python
def test_generate_revisions_endpoint(client, project, fake_llm):
    response = client.post(f"/api/projects/{project_id}/impact/revisions",
                           json={"target_type": "architecture", "target_id": arch_id})
    assert response.status_code == 200
    body = response.json()
    assert body["llm_status"] == "ok" and body["suggestions"]


def test_apply_rejects_a_run_from_another_project(client, project, other_project, run):
    response = client.post(f"/api/projects/{other_id}/impact/revisions/apply",
                           json={"run_id": run.id, "accepted": [0]})
    assert response.status_code == 404
```

- [ ] **Step 2: 跑测试确认失败**
- [ ] **Step 3: 实现**

`schemas.py`：

```python
class RevisionSuggestRequest(BaseModel):
    target_type: str
    target_id: str


class RevisionApplyRequest(BaseModel):
    run_id: str
    accepted: list[int] = Field(default_factory=list)
```

`impact.py` 两个路由，错误沿用 `_error()`（`run_id` 不存在 → 404）。

- [ ] **Step 4: 跑测试确认通过**
- [ ] **Step 5: 提交** `feat: 修订建议的生成与应用接口`

---

### Task 5: 前端面板

**Files:**
- Create: `frontend/src/lib/revisionView.ts`
- Test: `frontend/src/lib/revisionView.test.ts`
- Modify: `frontend/src/api/client.ts`、`frontend/src/components/Locking.tsx`

**Interfaces:**
- Consumes: 上面两个接口；`RevisionSuggestion` 类型
- Produces: `isSelectable(item) -> boolean`、`countSelected(items, selected) -> number`

- [ ] **Step 1: 写失败的测试**

```ts
it('locks are not selectable', () => {
  expect(isSelectable({ locked: true } as never)).toBe(false)
  expect(isSelectable({ locked: false } as never)).toBe(true)
})
it('counts only selectable selected rows', () => {
  expect(countSelected([{ locked: false }, { locked: true }] as never, new Set([0, 1]))).toBe(1)
})
```

- [ ] **Step 2: 跑测试确认失败**
- [ ] **Step 3: 实现**

- `client.ts`：`ImpactRevision`、`ImpactRevisionResult` 类型 + `generateRevisions(projectId, body)` + `applyRevisions(projectId, body)`。
- `Locking.tsx`：启用按钮 → 生成中态 → 建议列表（checkbox、对象、字段、现在/建议、理由、锁定禁用）→「采纳选中 n 条」→ 应用后显示 applied/skipped（「已变化」红字）。
- 空态：影响面为空或全锁时按钮禁用并说明。

- [ ] **Step 4: 跑 `pnpm vitest run` 与 `pnpm build`**
- [ ] **Step 5: 提交** `feat: 影响面面板的修订建议逐条确认`

---

### Task 6: 真实模型复验、走查与收口

- [ ] 用临时数据目录起真实 uvicorn；造：故事圣经 + 3 章 9 场 + 一条人物动机；改动机后跑影响面 → 生成建议（真实模型，1 次调用）。
- [ ] 勾选 1 条应用 → 字段落库、改动历史出现「修订建议」；再应用同一条 → 全部「现值已变化」。
- [ ] 换一条锁定场景 → 生成时不出现在建议里。
- [ ] 走查记录写 `docs/superpowers/plans/2026-10-24-revision-suggestions-walkthrough.md`；同步 `CLAUDE.md` §7/§8；合并 master。
