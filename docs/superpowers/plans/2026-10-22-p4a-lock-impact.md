# P4a 实施计划：锁定与影响面分析

> 设计：`docs/superpowers/specs/2026-10-22-p4a-lock-impact-design.md`
> 基线：后端 717 passed / 前端 30 passed + `pnpm build` 干净
> 分支：`worktree-p4a-lock-impact`

## 任务表

| # | 任务 | 产出 | 依赖 |
|---|---|---|---|
| 1 | 数据层：迁移 v8 + `locked` 列 + `review_mark` 表 | `db/models/*`、`db/migrations.py` | — |
| 2 | `lock_service.py`：有效锁定、设置、段落锁、`missing_locks` | `app/lock_service.py`、`app/lock_types.py` | 1 |
| 3 | 锁定 API：PATCH 统一入口 + 段落锁 | `api/locks.py` | 2 |
| 4 | 强制执行点：生成 / 采纳 / 批量 / 两种 replace 写入 / 架构采纳 / 回写 | 各 service 改动 + 测试 | 2 |
| 5 | `impact_service.py`：五种目标的影响面 | `app/impact_service.py` | 2 |
| 6 | `review_service.py` + 影响面与待复核 API | `app/review_service.py`、`api/impact.py` | 5 |
| 7 | 对象删除时清理标记；导出报告加锁定/待复核 | `world_service` / `chapter_service` / `export_service` | 6 |
| 8 | 前端：锁定开关、锁定段落面板、影响面面板、待复核标记 | `frontend/src/**` | 3,4,6 |
| 9 | 走查、测试收口、文档同步 | walkthrough + CLAUDE.md | 全部 |

## 各任务细节

### 任务 1 · 数据层

1. `SettingEntry` / `Volume` / `Chapter` / `Scene` 各加 `locked: bool = False`；`Scene` 加 `locked_paragraphs_json: list[str] = []`。
2. `review_mark` 新模型文件 `db/models/review.py`，注册进 `db/models/__init__.py`。
3. 迁移 v8，五条语句，`requires=("setting_entry", "volume", "chapter", "scene")`。
4. 测试：`test_migrations.py` 加 v8 形状测试；`test_models.py` 加列存在与默认值；`test_review_models.py` 唯一约束。

### 任务 2 · `lock_service`

- `app/lock_types.py`：`LOCK_TARGETS`（五类 + 中文标签）、`normalize_target_type`。
- `app/lock_service.py`：
  - `effective_scene_lock(session, scene) -> dict`（`locked` / `source` / `source_id`）
  - `effective_chapter_lock` / `effective_volume_lock`
  - `set_locked(session, target_type, target_id, locked)`（404 由调用方转）
  - `locked_items_in(session, target_type, ids)`（供 replace 写入批量判定）
  - `paragraph_locks` / `set_paragraph_locks`
  - `missing_locks(content, locks)` 纯函数
- 测试：继承三种情形；`missing_locks` 四种输入；段落锁去重与去空。

### 任务 3 · 锁定 API

- `PATCH /api/locks/{target_type}/{target_id}`；`PUT /api/scenes/{scene_id}/paragraph-locks`。
- 未知类型 400、目标不存在 404。
- 测试：五类目标各一条往返 + 两条错误码。

### 任务 4 · 强制执行点

按设计 §4.3 逐条实施，每条都配「锁定拒绝 / 未锁放行」成对测试。要点：

- `prepare_generation` 的拒绝必须发生在**任何运行记录创建之前**。
- `adopt_draft` 先查有效锁定、再查段落锁，两条错误文案不同。
- `write_chapter_plan` / `write_scenes` 在 `replace` 分支的**删除之前**收集锁定对象并拒绝。
- `batch_service` 跳过锁定场景；`serialize_job` 增加 `skipped_locked` 计数（由 `scene_ids_json` 与可跑集合之差算出，不改表）。
- `writeback_service.apply` 返回 `skipped` 列表；三类目标各自判定。

### 任务 5 · `impact_service`

- 按设计 §4.2 的五种目标实现；`_scene_label` 复用 `export_service` 的标签格式（抽成公共函数避免第二份）。
- FTS 分组只对 `entry` 生效，结果里标注「按全文检索」。
- 测试：五种目标各一条；锁定计数；只读性（调用前后行数不变）。

### 任务 6 · 待复核 + API

- `app/review_service.py`：`add_marks`（幂等）、`list_marks`、`clear_mark`、`clear_marks`。
- `api/impact.py`：四条路由（GET impact、GET/POST review-marks、DELETE 单条、POST clear）。
- 测试：幂等、批量、404。

### 任务 7 · 清理与报告

- `delete_entry` / `delete_volume` / `delete_chapter` / `delete_scene` 清理标记。
- `export_service.build_report` 加 `locked_counts` 与 `review_marks`。
- 前端 Dashboard 报告卡片显示两项。

### 任务 8 · 前端

- `client.ts`：七个新方法 + 类型。
- 章节页 / 世界观页 / 架构页：锁定开关 + 影响面面板 + 待复核角标。
- 写作台：锁定横幅、按钮禁用、锁定段落面板、采纳被拒的缺失段落提示。

### 任务 9 · 收口

- 全量测试、`pnpm build`。
- 临时数据目录走查（锁定拦截、影响面、待复核、导出报告）。
- 写 `docs/superpowers/plans/2026-10-22-p4a-walkthrough.md`，同步 CLAUDE.md §7 / §8。
