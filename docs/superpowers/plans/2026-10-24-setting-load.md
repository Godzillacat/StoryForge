# 设定投放曲线 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 结构设计页新增「设定投放」视图：按章统计新出现设定数、总提及与每千字密度；没写正文的章灰显。

**Architecture:** 后端一次扫描（词表 + 正则 + 场景正文），返回只读投影；前端柱 + 线，纯布局函数 + vitest。

**Tech Stack:** FastAPI + SQLAlchemy + pytest；React + TS + vitest。

**Spec:** `docs/superpowers/specs/2026-10-24-setting-load-design.md`

## Global Constraints

- **不调用模型**，按字面命中（与术语表同一套白名单）。
- 长 form 优先（`阿明哥` 不同时算 `阿明`）。
- 同一 form 多个条目：名字相等优先，否则最早创建；计入 `ambiguities`。
- **没有已采纳正文的章不参与新/旧判定**，前端灰显。
- 密度 `mentions / (chars/1000)`，`chars=0` → 0。
- 不落库缓存；注释中文、标识符英文。

## Review Focus

1. **词表**：空名、重复别名、大小写/空白、`aliases_json` 非数组。
2. **正则**：form 含正则元字符（`.` `(` `|`）必须转义；超长词表不会炸。
3. **归属**：同场多次命中计次数但只列一次新词；跨场景按阅读顺序取首次。
4. **无正文**：`has_body=false` 的章不计入「从未出现」。
5. **性能**：N 场景 × M form 不许退化成 O(N×M) 的逐词 `in`；用一次正则扫描。

## File Structure

- `backend/app/services/setting_load_service.py`（新建）
- `backend/app/api/logic.py`（加路由）
- `backend/tests/test_setting_load.py`（新建）
- `frontend/src/lib/settingLoad.ts` + `settingLoad.test.ts`（新建）
- `frontend/src/components/chapters/SettingLoadCurve.tsx`（新建）
- `frontend/src/pages/Chapters.tsx`、`frontend/src/api/client.ts`

---

### Task 1: 后端投影与接口

**Files:** `backend/app/services/setting_load_service.py`、`backend/app/api/logic.py`、`backend/tests/test_setting_load.py`

**Interfaces:**
- Produces: `build_load(session, project_id) -> dict`（形状见 spec §3.1）；`GET /api/projects/{id}/setting-load`

- [ ] **Step 1: 写失败的测试**

```python
def test_long_form_wins(session, project_with_bodies):
    data = setting_load_service.build_load(session, project.id)
    ch = data["chapters"][0]
    assert {"阿明哥"} == {t["form"] for t in ch["new_terms"]}   # 不是「阿明」
    assert ch["mentions"] == 1


def test_chapter_without_body_is_not_counted(session, project_with_bodies):
    data = setting_load_service.build_load(session, project.id)
    empty = next(c for c in data["chapters"] if not c["has_body"])
    assert empty["new_count"] == 0 and empty["density"] == 0
    assert data["totals"]["never_seen"] == 1   # 只在无正文里出现的条目仍算从未出现


def test_first_appearance_is_by_reading_order(session, project_with_bodies):
    data = setting_load_service.build_load(session, project.id)
    firsts = [c for c in data["chapters"] if any(t["name"] == "雾港" for t in c["new_terms"])]
    assert len(firsts) == 1 and firsts[0]["label"].endswith("第2章")
```

另测：重名 `ambiguities`、空项目 `reason`、项目不存在 404。

- [ ] **Step 2: 跑测试确认失败**
- [ ] **Step 3: 实现**

1. `tree = chapter_service.build_tree`；取项目场景 `Scene.id/body/chapter_id`（一次查询）。
2. 取 `SettingEntry`（project 内）：`name` + `aliases_json`（容错非数组）→ form 表；空 form 跳过；
   `form -> entry` 名字相等优先、否则 `created_at` 最早；冲突计 `ambiguities`。
3. 编译一次正则：`"|".join(re.escape(f) for f in sorted(forms, key=len, reverse=True))`；
   对每个有正文场景 `finditer`，按命中 form 归属章。
4. 阅读顺序 = 卷 seq → 章 seq → 场景 seq；`new_terms` 取 form 首次出现的章。
5. `chars` 用 `count_words`；`density` 保留一位小数。
6. `never_seen`：form 从未在任何**有正文**的场景命中。

- [ ] **Step 4: 跑测试确认通过**
- [ ] **Step 5: 提交** `feat: 设定投放的后端投影`

---

### Task 2: 前端布局纯函数

**Files:** `frontend/src/lib/settingLoad.ts`、`settingLoad.test.ts`

**Interfaces:**
- Produces: `buildLoadSeries(data) -> {chapters: [{id,label,x,newCount,density,hasBody}], maxNew, maxDensity}`

- [ ] **Step 1: 写失败的 vitest**：x 递增；空数据；`maxNew` 至少 1（防除零）；无正文章 `hasBody=false`。
- [ ] **Step 2–4: 红 → 实现 → 绿**
- [ ] **Step 5: 提交** `feat: 设定投放曲线的布局纯函数`

---

### Task 3: 视图与接线

**Files:** `frontend/src/components/chapters/SettingLoadCurve.tsx`（新建）、`frontend/src/pages/Chapters.tsx`、`frontend/src/api/client.ts`

- [ ] **Step 1: 实现**：`client.ts` 类型 + `settingLoad(projectId)`；组件用 SVG 柱（`new_count`）+ 折线（`density`），
  无正文章灰色占位并标「未写」，悬停显示「新 3 / 提及 14 / 3200 字」，点章回调；顶部汇总；空态文案用 `reason`。
  `Chapters.tsx` 加视图页签与数据加载（独立 error，不拖垮整页）。
- [ ] **Step 2: `pnpm vitest run` 与 `pnpm build`**
- [ ] **Step 3: 提交** `feat: 结构设计页的设定投放曲线`

---

### Task 4: 走查与收口

- [ ] 临时目录造 2 卷 4 章（一章无正文）+ 6 个条目（含核心设定第 3 章才出现、一个只在无正文章出现），核对曲线与汇总。
- [ ] 点章跳转；截图。
- [ ] 走查记录 + `CLAUDE.md` §7/§8 + 合并 master。
