# 性格漂移曲线 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 结构设计页新增「性格漂移」视图：按章给人物的手记状态，标出哪几章变了；格子可改。

**Architecture:** 新表 `character_state`（`create_all` 建，无迁移）；服务层 upsert + 整本投影；前端网格与内联编辑。

**Tech Stack:** FastAPI + SQLAlchemy + pytest；React + TS + vitest。

**Spec:** `docs/superpowers/specs/2026-10-24-character-drift-design.md`

## Global Constraints

- **不调用模型**；状态是作者手记的一行文本。
- 唯一约束 `(chapter_id, entry_id)`，写入 upsert。
- `changed` 与**该人物上一条记录**比较；首条恒 `false`；没记录的格子留空，不是 0。
- 只有 `type == "character"` 的条目可记录。
- 新表归 `create_all`，**不写迁移**（遵守「迁移只改已有表」）。
- 注释中文、标识符英文。

## Review Focus

1. **幂等与并发**：同章同人重复 PUT 不产生第二行；唯一约束在库里真的建了。
2. **归属**：章与条目都必须属于该项目，否则 404（不是 400）。
3. **变化判定**：与上一条记录比，首条不算变；删掉中间一条后 `changed` 会重算。
4. **空 vs 零**：没记录是缺格；`sparse` 只数「仅一条记录」的人物。
5. **级联**：删章 / 删人物条目时状态行跟着走。

## File Structure

- `backend/app/db/models/chapter.py` 或新文件 `character_state.py`（模型）
- `backend/app/services/character_drift_service.py`（新建）
- `backend/app/api/chapters.py` 或 `api/logic.py`（路由）
- `backend/tests/test_character_drift.py`（新建）
- `frontend/src/lib/characterDrift.ts` + 测试
- `frontend/src/components/chapters/CharacterDrift.tsx`
- `frontend/src/pages/Chapters.tsx`、`frontend/src/api/client.ts`

---

### Task 1: 模型、服务与接口

**Files:** 模型、`character_drift_service.py`、路由、`test_character_drift.py`

**Interfaces:**
- `get_drift(session, project_id) -> dict`（spec §3.2）
- `put_state(session, chapter_id, entry_id, note) -> dict`
- `delete_state(session, chapter_id, entry_id) -> None`
- 路由三条（GET/PUT/DELETE）

- [ ] **Step 1: 写失败的测试**

```python
def test_first_record_is_not_a_change(session, project_with_chapters):
    drift = character_drift_service.get_drift(session, project.id)
    row = drift["characters"][0]
    assert row["cells"][0]["changed"] is False
    assert row["changes"] == 0


def test_same_note_is_not_a_change(session, project_with_chapters):
    ...  # 两条相同 → changes == 0
def test_upsert_keeps_one_row(session, project_with_chapters):
    ...  # 两次 PUT → 一条，note 是后写的
def test_non_character_is_rejected(client, project_with_chapters):
    ...  # 400
```

另测：稀疏计数、章/条目不属于项目 404、空 note 400、删除不存在 404、删章级联。

- [ ] **Step 2: 跑测试确认失败**
- [ ] **Step 3: 实现**（模型加唯一约束与级联；服务按阅读顺序投影；`changed` 与上一条比）
- [ ] **Step 4: 跑测试确认通过**
- [ ] **Step 5: 提交** `feat: 人物状态的存储与投影`

---

### Task 2: 前端网格纯函数

- [ ] `characterDrift.ts`：`buildDriftGrid(data)` 按 `chapters` 对齐、缺格填空、`sparse` 原样透传；vitest 三条（对齐、空、变化标记）。

### Task 3: 视图与内联编辑

- [ ] `CharacterDrift.tsx`：表格（列 = 章，行 = 人物），变化格琥珀、相同格灰、空格留白；点格弹输入（预填），保存 / 删除；顶部汇总；空态用 `reason`。
- [ ] `Chapters.tsx` 加页签与数据加载（独立 error）；保存后只刷新该视图。

### Task 4: 走查与收口

- [ ] 临时目录 2 人物 4 章，A 记 3 条（1 条重复）、B 记 1 条 → 核对 `changes` / `sparse`；截图。
- [ ] 改一条后回读；删一条看 `changed` 重算。
- [ ] 走查记录 + `CLAUDE.md` §7/§8 + 合并 master。
