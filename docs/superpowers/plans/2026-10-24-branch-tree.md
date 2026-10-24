# 场景分支树 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 分支可从另一条分支派生（最多三层），列表按树缩进；采纳语义不变。

**Architecture:** `scene_branch.parent_branch_id` + 迁移 v13；服务层校验与深度计算；前端纯函数建树 + 缩进列表 + 「派生」动作。

**Tech Stack:** FastAPI + SQLAlchemy + pytest；React + TS + vitest。

**Spec:** `docs/superpowers/specs/2026-10-24-branch-tree-design.md`

## Global Constraints

- **采纳 / 合并语义不变**：任何分支都整份替换正文，不做逐层合并。
- **最多三层**（根 = 1 层）；父深度 3 时拒绝派生。
- **丢弃父分支 → 子分支提升为根**（`parent_id` 置空），不级联删。
- A/B 临时分支（`ab_group` 非空）不能当父。
- 迁移 v13 语句冻结成字面量；只加可空列，不写 FK。

## Review Focus

1. **深度**：根=1、两层=2、三层=3；父深 3 拒绝；脏数据成环时不会死循环。
2. **归属**：父分支必须同场景（跨场景 404），A/B 父 400。
3. **派生内容**：新分支正文复制父分支正文；父空则空；名字唯一。
4. **丢弃**：子分支提升为根且正文/草稿不动；A/B 丢弃路径不误伤。
5. **迁移**：存量库执行一次、旧分支 `parent_id` 全 NULL。

## File Structure

- `backend/app/db/models/branch.py`（加列）
- `backend/app/db/migrations.py`（v13）
- `backend/app/services/branch_service.py`（派生、深度、序列化、丢弃提升）
- `backend/app/api/branches.py`（建分支接受 `parent_id`）
- `backend/tests/test_branch_tree.py`（新建）
- `frontend/src/lib/branchTree.ts` + 测试
- `frontend/src/components/writing/BranchPanel.tsx`（或现有分支列表组件）与 `Writing.tsx`
- `frontend/src/api/client.ts`

---

### Task 1: 后端派生、深度与迁移

**Files:** 模型、迁移、服务、路由、`test_branch_tree.py`

**Interfaces:**
- `create_branch(session, scene_id, name, note="", parent_id=None) -> dict`
- `serialize_branch` 增加 `parent_id`、`depth`

- [ ] **Step 1: 写失败的测试**

```python
def test_depth_is_one_for_roots(session, scene_with_branches):
    rows = branch_service.list_branches(session, scene.id)
    assert [r["depth"] for r in rows if r["parent_id"] is None] == [1, 1]


def test_third_level_is_rejected(session, scene_with_branches):
    with pytest.raises(ValueError, match="最多三层"):
        branch_service.create_branch(session, scene.id, "四层", parent_id=level3.id)


def test_child_promoted_when_parent_discarded(session, scene_with_branches):
    branch_service.discard_branch(session, level2.id)
    child = branch_service.get_branch(session, level3.id)
    assert child["parent_id"] is None and child["depth"] == 1
```

另测：派生复制父正文、跨场景 404、A/B 父 400、迁移 v13 在存量库执行且旧行 `parent_id` 为 NULL。

- [ ] **Step 2: 跑测试确认失败**
- [ ] **Step 3: 实现**

1. 模型加 `parent_branch_id: Mapped[str | None]`（`String(36)`，无 FK）。
2. `migrations.py` 加 v13：`ALTER TABLE scene_branch ADD COLUMN parent_branch_id TEXT`，`requires=("scene_branch",)`。
3. 服务：
   - `_depth_map(session, scene_id)` 一次取全场景分支，沿父链算深度，**带环保护**（已访问集合，成环按 1 处理）；
   - `create_branch(..., parent_id=None)`：父存在且同场景（404）、`ab_group is None`（400）、`depth(parent) < 3`（400）、复制父 `content`；
   - `serialize_branch` 用传入的深度映射填 `depth`；`list_branches` 先建映射再序列化；
   - `discard_branch` 删除前 `UPDATE scene_branch SET parent_branch_id=NULL WHERE parent_branch_id=:id`。
4. 路由 `POST /api/scenes/{id}/branches` body 增加可选 `parent_id`。

- [ ] **Step 4: 跑测试确认通过**
- [ ] **Step 5: 提交** `feat: 分支派生与深度`

---

### Task 2: 前端建树纯函数

**Files:** `frontend/src/lib/branchTree.ts` + `branchTree.test.ts`

**Interfaces:**
- `buildBranchRows(branches) -> [{...branch, depth, indent, parentName}]`：按树前序排列；孤儿（父不在列表）当根。

- [ ] **Step 1: 写失败的 vitest**：根在前、子紧随父、三层顺序、孤儿当根、深度来自后端时不被覆盖。
- [ ] **Step 2–4: 红 → 实现 → 绿**
- [ ] **Step 5: 提交** `feat: 分支树纯函数`

---

### Task 3: 分支列表接线与「派生」

**Files:** 分支列表组件、`Writing.tsx`、`client.ts`

- [ ] **Step 1: 实现**：列表按 `buildBranchRows` 缩进渲染；显示「派生自 X」；每行「派生」按钮（`window.prompt` 取名，默认「父名 · 派生」）→ `createBranch(sceneId, name, parentId)` → 选中新分支；`depth >= 3` 禁用并说明；`client.ts` 的 `createBranch` 加 `parentId`。
- [ ] **Step 2: `pnpm vitest run` 与 `pnpm build`**
- [ ] **Step 3: 提交** `feat: 写作台的分支树与派生`

---

### Task 4: 走查与收口

- [ ] 临时目录：1 场景建三层分支，核对缩进/派生自/复制正文；丢弃中间父，子提升为根；采纳最深一条看正文与修订。
- [ ] 走查记录 + `CLAUDE.md` §7/§8（含「既定决策已推翻」的 §8 行） + 合并 master。
