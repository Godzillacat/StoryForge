# 因果链图 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 结构设计页新增「因果链」视图：按章把场景卡摆成一条链，标出缺目标 / 缺转折 / 已报过的因果问题。

**Architecture:** 后端一个只读投影 `GET /api/projects/{id}/causal-map`（场景树 + 一次性问题查询）；前端纯布局函数 + 手写节点行，点节点复用现有跳转。

**Tech Stack:** FastAPI + SQLAlchemy + pytest；React + TS + vitest。

**Spec:** `docs/superpowers/specs/2026-10-24-causal-map-design.md`

## Global Constraints

- **不新增数据**：只用 `chapter_service.build_tree` 与 `audit_issue`。
- `issues` 只收 `check_type="logic"`、`stage="plan"`、`status="open"`、`layer="causality"`。
- 断点枚举：`missing_goal` / `missing_turn` / `causality_issue`；不把「缺目标」和「因果问题」画成同一种标记。
- 没跑过逻辑自检时 `logic_checked: false`，前端显示「未检查」，不得显示成通过。
- 不引入图表库；注释中文、标识符英文。

## Review Focus

1. **N+1**：不允许按场景逐条查问题。
2. **断点重复**：一个场景同时缺目标与缺转折只算两条断点，不因三项全空而重复计数。
3. **锁与归属**：场景锁用 `effective_scene_lock`（卷/章继承）；项目不存在 404。
4. **空与未检查**：空项目、空章、从未跑过逻辑自检三种空态各有正确文案。
5. **点击跳转**：点节点要选中对应场景，不能只跳页不选。

## File Structure

- `backend/app/services/causal_service.py`（新建）
- `backend/app/api/logic.py`（加路由）
- `backend/tests/test_causal_map.py`（新建）
- `frontend/src/lib/causalMap.ts` + `causalMap.test.ts`（新建）
- `frontend/src/components/chapters/CausalMap.tsx`（新建）
- `frontend/src/pages/Chapters.tsx`（加视图）
- `frontend/src/api/client.ts`（类型 + 方法）

---

### Task 1: 后端投影与接口

**Files:** `backend/app/services/causal_service.py`、`backend/app/api/logic.py`、`backend/tests/test_causal_map.py`

**Interfaces:**
- Produces: `build_map(session, project_id) -> dict`（形状见 spec §3.1）；`GET /api/projects/{id}/causal-map`

- [ ] **Step 1: 写失败的测试**

```python
def test_breaks_and_issue_flags(session, project_with_causal_scenes):
    data = causal_service.build_map(session, project.id)
    chapter = data["chapters"][0]
    scenes = chapter["scenes"]
    assert [s["breaks"] for s in scenes] == [["missing_turn"], [], ["causality_issue"]]
    assert scenes[2]["issues"][0]["layer_label"] == "因果链"
    assert data["totals"]["breaks"] == 2


def test_logic_checked_is_false_before_any_plan_check(session, project_with_scenes):
    assert causal_service.build_map(session, project.id)["logic_checked"] is False


def test_unknown_project_is_404(client):
    assert client.get("/api/projects/nope/causal-map").status_code == 404
```

- [ ] **Step 2: 跑测试确认失败**
- [ ] **Step 3: 实现**

1. `tree = chapter_service.build_tree(session, project_id)`；项目不存在先查 `Project`。
2. 一次取该项目全部场景 id → `select(AuditIssue).where(AuditIssue.scene_id.in_(ids), check_type=="logic", stage=="plan", status=="open", layer=="causality")`；按 `scene_id` 分组。
3. 每场：`breaks` 按 `goal.strip()` / `turn.strip()` 判定；有 issue 追加 `causality_issue`。
4. `logic_checked`：同项目存在任意 `check_type="logic" and stage="plan"` 的 `AuditIssue` 行即为 true（包括已处理的 —— 跑过就是跑过）。
5. `totals` 汇总。

- [ ] **Step 4: 跑测试确认通过**
- [ ] **Step 5: 提交** `feat: 因果链图的后端投影`

---

### Task 2: 前端布局纯函数

**Files:** `frontend/src/lib/causalMap.ts`、`causalMap.test.ts`

**Interfaces:**
- Produces: `buildCausalRows(data) -> {rows: [{chapter, nodes: [{id,label,goal,turn,x,breaks,issues}]}], totals}`；`summarize(data) -> {scenes, breaks, chapters}`

- [ ] **Step 1: 写失败的 vitest**：空章无 nodes；节点 x 按序递增（`NODE_WIDTH + GAP`）；`summarize` 与后端 totals 一致。
- [ ] **Step 2: 跑测试确认失败**
- [ ] **Step 3: 实现**（常量 `NODE_WIDTH=180`、`NODE_GAP=28`、`ROW_HEIGHT=120`）
- [ ] **Step 4: 跑测试确认通过**
- [ ] **Step 5: 提交** `feat: 因果链图的布局纯函数`

---

### Task 3: 视图与接线

**Files:** `frontend/src/components/chapters/CausalMap.tsx`（新建）、`frontend/src/pages/Chapters.tsx`、`frontend/src/api/client.ts`

**Interfaces:**
- Consumes: `buildCausalRows`、`GET /causal-map`
- Produces: 结构设计页第三个视图「因果链」

- [ ] **Step 1: 实现**

- `client.ts`：`CausalMapData` 类型 + `causalMap(projectId)`。
- `CausalMap.tsx`：props `{data, loading, error, onSelectScene, logicChecked}`；每章一行、节点盒子（目标/转折两行，空值显示「（空）」）、断点左边条与底部小字、因果问题红点 + `title`；点节点调 `onSelectScene`。
- `Chapters.tsx`：视图切换加「因果链」，选中场景复用现有逻辑（`setSelectedSceneId` 或等价）。

- [ ] **Step 2: `pnpm vitest run` 与 `pnpm build`**
- [ ] **Step 3: 提交** `feat: 结构设计页的因果链视图`

---

### Task 4: 走查与收口

- [ ] 临时目录造 2 卷 4 章 10 场（含缺目标、缺转折、带因果问题的场景），截图核对断点样式与计数。
- [ ] 点节点 → 跳转并选中该场。
- [ ] 走查记录 + `CLAUDE.md` §7/§8 + 合并 master。
