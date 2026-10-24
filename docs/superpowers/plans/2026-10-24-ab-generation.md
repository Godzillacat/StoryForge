# A/B 并排生成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 同一场戏一键生成两版正文，并排比较，采纳一版写进正文并记修订，另一版丢弃；两版都遵守锁。

**Architecture:** 一次 A/B = 两条带 `ab_group` 的分支；生成复用 `/branches/{id}/generate`；采纳 = adopt 草稿 → merge 到正文 → 删同组两条，一次提交；分支列表过滤掉 A/B。

**Tech Stack:** FastAPI + SQLAlchemy + pytest；React + TS + vitest。

**Spec:** `docs/superpowers/specs/2026-10-24-ab-generation-design.md`

## Global Constraints

- **不新增生成链路**：两版都用 `POST /api/branches/{id}/generate`。
- A/B 分支对普通分支列表**不可见**（`ab_group is not null` 过滤）。
- 采纳必须**一次提交**：adopt + merge + 删两条，任一步失败整体回滚。
- 锁定检查沿用既有：场景锁（含卷/章继承）、段落锁。
- 迁移语句冻结字面量；新增列只加可空列。
- 不新增依赖；注释中文、标识符英文。

## Review Focus

1. **半途失败**：A 建好、B 建失败；A 生成成功、B 失败；merge 失败但 adopt 已提交 —— 任何一种都不能让正文或分支处于半截状态。
2. **锁竞态**：建 A/B 时没锁、采纳时锁了 —— 采纳必须拒绝且不留改动。
3. **归属**：`branch_id` 属于别的场景/别的 A/B 组时拒绝。
4. **列表污染**：A/B 分支不能出现在普通分支列表、不能进快照（分支本就进不了快照）。
5. **命名冲突**：同场景已有叫「A」的分支时自动加序号，不报错。

## File Structure

- `backend/app/db/models/branch.py` — 加 `ab_group`
- `backend/app/db/migrations.py` — v12
- `backend/app/services/branch_service.py` — `commit` 参数、`list_branches` 过滤、`ab_create` / `ab_adopt` / `ab_discard`
- `backend/app/api/branches.py` — 三个路由
- `backend/app/api/schemas.py` — `AbCreate`（目前无参数，可留空模型）
- `backend/tests/test_ab_service.py`、`backend/tests/test_ab_api.py`（新建）
- `frontend/src/api/client.ts`、`frontend/src/lib/abDiff.ts`、`frontend/src/components/writing/AbPanel.tsx`、`frontend/src/pages/Writing.tsx`

---

### Task 1: 迁移 v12 与列表过滤

**Files:**
- Modify: `backend/app/db/models/branch.py`
- Modify: `backend/app/db/migrations.py`
- Modify: `backend/app/services/branch_service.py`（`list_branches`）
- Test: `backend/tests/test_ab_service.py`（新建）

**Interfaces:**
- Produces: `SceneBranch.ab_group: str | None`；`GET /scenes/{id}/branches` 不再返回 A/B 分支

- [ ] **Step 1: 写失败的测试**

```python
def test_ab_branches_are_hidden_from_the_regular_list(session, scene):
    a = branch_service.create_branch(session, scene.id, "A")
    a.ab_group = "g1"
    session.commit()
    branch_service.create_branch(session, scene.id, "普通分支")
    names = [row["name"] for row in branch_service.list_branches(session, scene.id)]
    assert names == ["普通分支"]


def test_migration_12_adds_ab_group_to_an_existing_database(...):
    # 沿用 tests/test_migrations.py 的存量库夹具写法：建到 v11 的库 → run_migrations → PRAGMA table_info 含 ab_group
```

- [ ] **Step 2: 跑测试确认失败**
- [ ] **Step 3: 实现**

- `branch.py` 的 `SceneBranch` 加 `ab_group: Mapped[str | None] = mapped_column(String(36), nullable=True)`。
- `migrations.py` 末尾加 `Migration(version=12, note="scene_branch 加 ab_group（A/B 并排）", requires=("scene_branch",), statements=("ALTER TABLE scene_branch ADD COLUMN ab_group TEXT",))`。
- `list_branches` 查询加 `.where(SceneBranch.ab_group.is_(None))`。

- [ ] **Step 4: 跑测试确认通过**
- [ ] **Step 5: 提交** `feat: A/B 分支标记与列表过滤（迁移 v12）`

---

### Task 2: 服务层的 A/B 生命周期

**Files:**
- Modify: `backend/app/services/branch_service.py`
- Test: `backend/tests/test_ab_service.py`

**Interfaces:**
- Produces:
  - `create_branch(session, scene_id, name, note="", commit: bool = True)`
  - `adopt_branch_draft(session, branch_id, commit: bool = True)`
  - `merge_branch(session, branch_id, commit: bool = True)`
  - `ab_create(session, scene_id) -> dict` → `{group, branches:[{id,label}]}`
  - `ab_adopt(session, scene_id, branch_id) -> dict` → `{revision_created: bool, body: str, chars: int, discarded: [str]}`
  - `ab_discard(session, scene_id, branch_id) -> dict` → `{removed: [str]}`

- [ ] **Step 1: 写失败的测试**

```python
def test_ab_adopt_is_one_transaction(session, scene_with_body):
    created = branch_service.ab_create(session, scene.id)
    a, b = created["branches"]
    # 给 A 造草稿、B 也造草稿
    ...
    out = branch_service.ab_adopt(session, scene.id, a["id"])
    assert out["chars"] > 0
    assert session.get(SceneBranch, b["id"]) is None
    revisions = session.scalars(select(SceneRevision).where(SceneRevision.scene_id == scene.id)).all()
    assert any(r.source == "branch" for r in revisions)


def test_ab_adopt_rejects_a_branch_from_another_group(session, scene):
    created = branch_service.ab_create(session, scene.id)
    other = branch_service.ab_create(session, scene.id)   # 第二组
    with pytest.raises(ValueError, match="不属于"):
        branch_service.ab_adopt(session, scene.id, other["branches"][0]["id"])
```

另测：`ab_create` 在锁定时 `ValueError`；命名冲突时名字变 `A2`；`ab_discard` 删一条后同组只剩一条时把剩的也删；`ab_adopt` 时场景锁定 → 拒绝且 A 的草稿仍在。

- [ ] **Step 2: 跑测试确认失败**
- [ ] **Step 3: 实现**

1. 三个既有函数加 `commit: bool = True`，把 `session.commit()` 改为 `if commit: session.commit()`。
2. `ab_create`：`scene = _scene`；`lock_service.effective_scene_lock` 锁 → `ValueError("这一场已锁定…")`；生成 `group = uuid4().hex`；两次 `create_branch(..., commit=False)`，名字 `A`/`B` 冲突时 `_unique_name` 加序号；设置 `ab_group`；一次 `session.commit()`；失败 `rollback`。
3. `ab_adopt`：取分支 → 校验 `ab_group` == 该场景下未完成的组且 `branch.scene_id == scene_id` → `adopt_branch_draft(..., commit=False)` → `merge_branch(..., commit=False)` → 删除同组两条 → `session.commit()`；异常 `rollback` 后重抛。
4. `ab_discard`：删该分支；同组空则结束；一次提交。

- [ ] **Step 4: 跑测试确认通过**
- [ ] **Step 5: 提交** `feat: A/B 创建、采纳与丢弃（一次事务）`

---

### Task 3: 三个路由

**Files:**
- Modify: `backend/app/api/branches.py`
- Test: `backend/tests/test_ab_api.py`（新建）

**Interfaces:**
- Produces: `POST /api/scenes/{id}/ab`、`GET /api/scenes/{id}/ab`（查最近一组）、`POST /api/scenes/{id}/ab/{branch_id}/adopt`、`POST /api/scenes/{id}/ab/{branch_id}/discard`（只删该条）

- [ ] **Step 1: 写失败的测试**：正常创建返回两条；锁定场景 409；采纳 200 且 `discarded` 含另一条；别的场景的 branch 404；丢弃后 `GET /scenes/{id}/branches` 看不到。
- [ ] **Step 2: 跑测试确认失败**
- [ ] **Step 3: 实现**：沿用 `_value_error` 映射（「这一场已锁定」→ 409；「不属于」/「不存在」→ 404）。
- [ ] **Step 4: 跑测试确认通过**
- [ ] **Step 5: 提交** `feat: A/B 并排生成的接口`

---

### Task 4: 前端并排面板

**Files:**
- Create: `frontend/src/lib/abDiff.ts` + `frontend/src/lib/abDiff.test.ts`
- Modify: `frontend/src/api/client.ts`、`frontend/src/pages/Writing.tsx`
- Create: `frontend/src/components/writing/AbPanel.tsx`

**Interfaces:**
- Consumes: 三个 A/B 接口 + 现有 `POST /api/branches/{id}/generate`（SSE）
- Produces: `diffParagraphs(a: string, b: string) -> { same: number; changed: number }`

- [ ] **Step 1: 写失败的 vitest**：相同文本 `changed=0`；一段不同 `changed=1`；空文本两边都空 `same=0 changed=0`。
- [ ] **Step 2: 跑测试确认失败**
- [ ] **Step 3: 实现**

- `client.ts`：`AbSession` 类型 + `createAb` / `adoptAb` / `discardAb`。
- `AbPanel.tsx`：点「A/B 并排生成」→ `createAb` → 先流式生成 A、再 B（复用现有 `generateBranchStream` 风格的 SSE 调用；若没有现成封装，直接 `fetch` + `readSse`）；两栏显示字数、差异段数、只读预览；「用这一版」→ `adoptAb` → 刷新正文与章节树；「两版都不要」→ 两条 `discardAb`。
- `Writing.tsx`：右栏挂 `AbPanel`（`selectedSceneId` 与锁定状态传入）。

- [ ] **Step 4: 跑 `pnpm vitest run` 与 `pnpm build`**
- [ ] **Step 5: 提交** `feat: 写作台 A/B 并排生成与采纳`

---

### Task 5: 真实模型复验、走查与收口

- [ ] 真实模型（作者库副本）生成两版，确认两版文本不同、字数与差异段数正确。
- [ ] 采纳 A：正文变成 A、修订历史来源 `branch`、B 分支消失；`GET /branches` 看不到 A/B。
- [ ] 锁定场景：入口禁用 / 接口 409。
- [ ] 走查记录 + `CLAUDE.md` §7/§8 + 合并 master。
