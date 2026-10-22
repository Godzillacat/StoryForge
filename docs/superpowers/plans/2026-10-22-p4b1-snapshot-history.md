# P4b-1 实施计划：项目快照与改动历史

> 设计：`docs/superpowers/specs/2026-10-22-p4b1-snapshot-history-design.md`
> 基线：后端 809 passed / 前端 30 passed + `pnpm build` 干净
> 分支：`worktree-p4b1-snapshot-history`

## 任务表

| # | 任务 | 产出 | 依赖 |
|---|---|---|---|
| 1 | 数据层：`project_snapshot` / `change_log` 两张新表 | `db/models/snapshot.py`、`db/models/history.py`、`__init__.py` | — |
| 2 | `change_service`：写入与查询 | `app/services/change_service.py` | 1 |
| 3 | `snapshot_service`：序列化、创建、列表、删除 | `app/services/snapshot_service.py` | 1 |
| 4 | `snapshot_service.restore`：回滚与自动备份 | 同上 | 3 |
| 5 | 改动历史接入九处写路径 | 各 service | 2 |
| 6 | API：六条路由 | `api/snapshots.py`、`api/history.py`、`schemas.py`、`main.py` | 4,5 |
| 7 | 前端：仪表盘两张卡片 + 对象级历史 | `Dashboard.tsx`、`ChangeLog.tsx`、`client.ts` | 6 |
| 8 | 走查、测试收口、文档同步 | walkthrough + CLAUDE.md | 全部 |

## 各任务细节

### 任务 1 · 数据层

1. `ProjectSnapshot`：`project_id` FK CASCADE、`name`（唯一约束）、`note`、`data_json`、`volumes/chapters/scenes/words` 四个整数、时间戳。
2. `ChangeLog`：`project_id` FK CASCADE、`target_type`、`target_id`、`target_label`、`action`、`source`、`summary`；两个复合索引。
3. **本段无迁移**（两张都是新表）。
4. 测试：唯一约束、索引存在、删除项目级联。

### 任务 2 · `change_service`

- `record(...)` 只 add 不 commit。
- `list_changes(...)` 支持按类型 / 对象过滤与分页，返回时间倒序。
- 测试：写入与查询、过滤、分页、`target_label` 冗余可读。

### 任务 3 · 快照序列化与创建

- `_dump(session, project)`：按设计 §4.1 的范围序列化；**排除** `idea.raw_text` 与所有日志类表。
- `create_snapshot`：名称去空白、项目内查重、算规模、落库。
- `list_snapshots` / `get_snapshot` / `delete_snapshot`。
- 测试：往返一致、重名 400、空名 400、创建不改项目、删除不动项目、灵感原话不在快照里。

### 任务 4 · 回滚

- `restore_snapshot`：先建自动备份（独立事务并提交）→ 删当前结构 → 按原 id 重建 → 写 change_log → 提交。
- 重建保留 `locked` / `locked_paragraphs_json`。
- 测试：往返、回滚边界（灵感 / 运行记录 / 修订 / 审计 / 快照列表不变）、回滚可撤销、空项目回滚、锁定保留。

### 任务 5 · 接入改动历史

按设计 §4.2 的九处，每处一条测试；另加两条判别测试：业务失败不留日志、对象删除后日志仍可读。

### 任务 6 · API

六条路由 + schema；错误码映射（404 / 400）。

### 任务 7 · 前端

- `client.ts`：六个方法 + 类型。
- `Dashboard.tsx`：版本与快照卡片、最近改动卡片。
- `ChangeLog.tsx`：可复用列表（项目级 / 对象级）。
- 回滚二次确认文案要点明：会回到哪份快照、会先自动备份。

### 任务 8 · 收口

- 全量测试、`pnpm build`。
- 临时目录走查（建快照 / 改动 / 回滚 / 再回滚回来 / 历史）。
- 写 `docs/superpowers/plans/2026-10-22-p4b1-walkthrough.md`，同步 CLAUDE.md §7 / §8。
