# P4c 实施计划：伏笔闭环与逻辑链文本视图

> 设计：`docs/superpowers/specs/2026-10-22-p4c-foreshadow-logic-design.md`
> 基线：后端 889 passed / 前端 30 passed + `pnpm build` 干净
> 分支：`worktree-p4c-foreshadow-logic`

## 任务表

| # | 任务 | 产出 | 依赖 |
|---|---|---|---|
| 1 | 伏笔状态词表与派生 | `app/foreshadow_types.py`、`foreshadow_service` | — |
| 2 | 账本汇总与回收率 + 接口 | `foreshadow_service.ledger_summary`、`api/foreshadows.py` | 1 |
| 3 | 逻辑链抽取（纯函数） | `app/logic_chain.py`、`api/logic.py` | — |
| 4 | 前端：账本四类计数 / 筛选 / 状态编辑 | `ForeshadowLedger.tsx`、`Chapters.tsx` | 2 |
| 5 | 前端：写作台「逻辑链」面板 | `components/writing/LogicChain.tsx`、`Writing.tsx` | 3 |
| 6 | 走查、测试收口、文档同步 | walkthrough + CLAUDE.md | 全部 |

## 各任务细节

### 任务 1 · 伏笔状态

- `FORESHADOW_STATUSES`（planned / planted / paid / dropped）+ 标签。
- `normalize_foreshadow_status`：接受英文键与中文标签；未知值报错；`confirmed` 归一到 `planned` 并保留原值以便显示（见 §3 的存量处理）。
- `effective_status(row)`：按设计 §4.2 的派生规则。
- 改 `foreshadow_service.create/update` 用新词表。
- 测试：六种组合、`confirmed` 归一化、未知值报错。

### 任务 2 · 汇总与接口

- `ledger_summary`：四类计数 + 回收率（`dropped` 不进分母；分母 0 时 rate = 0）。
- `GET /api/projects/{id}/foreshadows/summary`。
- 序列化里加 `effective_status` 与 `status_is_derived`。
- 测试：计数、回收率、空项目。

### 任务 3 · 逻辑链

- `extract_chain(text)` 纯函数：切段切句、三类连接词、一句多类型取第一个。
- `GET /api/scenes/{id}/logic-chain`：无正文返回 `{chain: [], reason: "..."}`。
- 测试：三类各一条、多类型、无连接词、空正文、段落序号正确。

### 任务 4 · 账本前端

- 顶部四类计数 + 回收率。
- 筛选加「已弃」。
- 每行显示有效状态；作者可改（调用 `PATCH`）。

### 任务 5 · 逻辑链面板

- 写作台右栏，与逻辑自检并列。
- 列出段落序号 / 类型 / 原句 / 连接词；空态说明。

### 任务 6 · 收口

全量测试、`pnpm build`、临时目录走查、浏览器走查、写 walkthrough、同步 CLAUDE.md。
