# StoryForge P3b 设计：管线编排

> 2026-10-21。P3 把「选哪个模型 → 用什么采样参数 → 花了多少 → 是多少钱」这条链路接通了。P3b 接上它上游的那件事：**把这些智能体按作者自己的顺序串成一条流水线**。
>
> 上位依据：`StoryForge-产品设计文档.md` §3.2（三档介入）、§5.3（管线与人工检查点）、§5.1（角色卡）、D-03（AI 产出先落在编辑区）、D-04（AI 不得覆盖作者原文）、D-06（版本化）。

## 1. 阶段定义

### 1.1 这一段要解决什么

产品 §5.3 画了一条固定的流水线，并说「管线本身可编辑：增删节点、换绑智能体、调顺序」。现状是：**每个节点都有按钮，但没有「管线」这个东西**。

作者今天的实际路径是：灵感页点解析 → 去架构页点推荐 → 去世界观页点构建 → 回章节页点排卷章 → 再点场景卡。每一步都要自己记住「下一步该去哪、上一步有没有采纳」。这条路径**没有任何地方能看见全貌**，也无法按自己的习惯调整顺序或换绑智能体。

P3b 交付三件事：

1. **一条可见、可编辑的管线**：节点有序，每个节点可启用 / 停用、标记为检查点、换绑到具体的智能体、上下移动、增删。
2. **一次可暂停的连续执行**：点「开始」，按顺序跑下去；遇到检查点停下等作者；出错或前置条件不满足时停下并说清原因；可暂停 / 继续 / 取消。
3. **每步的产出与去向**：节点跑完后显示它产出了什么、在哪审阅、下一步卡在哪。

### 1.2 验收标准

1. **管线可编辑**
   - 每个项目一条管线，首次访问时按默认模板懒创建；可「恢复默认」。
   - 节点可：启用 / 停用、标记检查点、换绑智能体（默认按任务类型取第一个启用的）、上移 / 下移、删除、追加自定义节点。
   - 顺序、绑定、检查点标记都持久化，刷新后不变。
2. **执行**
   - 「开始」按顺序执行**启用**的节点；执行中显示当前节点与进度。
   - 检查点策略三档：**每步确认 / 仅关键步确认 / 连续自动**。前两档在对应节点后暂停（`awaiting`），作者点「继续」才往下走；自动档只在出错或前置条件不满足时停。
   - 可暂停（当前节点跑完后停在节点边界）、继续、取消。应用重启后未完成的运行恢复为「已暂停」。
   - 同一项目同时只允许一个进行中的管线运行。
3. **前置条件**
   - 每个节点声明前置条件（例如「章纲策划」要求已采纳的架构；「场景策划」要求已有章；「执笔」要求选中场景且场景卡完整）。
   - 不满足时该节点记 `blocked` 并写明缺什么、去哪补，**不发起模型调用、不花钱**。
   - 后续节点一并停下（不跳过继续跑，避免拿空上下文生成垃圾）。
4. **不越权**
   - 除「灵感解析」写回 `idea.parsed_json`（派生卡，与单点按钮行为一致，原文不动）外，**任何节点都不把 AI 产出写进项目结构**。架构、世界观、章纲、场景的产出仍只落在运行记录里，作者在各自主页采纳（D-03 / D-04）。
   - 因此管线是「材料的流水线」，不是「一键成书」。
5. **基线**：后端既有 653 条全绿；前端 30 条全绿、`pnpm build` 干净。
6. **真实模型复验**：在一个临时数据目录上跑一次「灵感解析 → 架构推荐」的自动档管线，验证两个节点依次成功、运行记录齐全、检查点策略生效。

### 1.3 明确不做

- **正文写作出现在管线里** —— 已有的「批量生成」就是逐场写草稿的执行器，再在管线里复制一遍会多一套暂停/重试/进度语义。管线页面底部给一个「正文写作去写作台 / 批量生成」的指引链接，不把它做成节点。
- **管线自动采纳** —— 违反 D-03 / D-04。检查点停下后由作者去对应页面采纳。
- **条件分支 / 循环 / 并行** —— 产品只要求「增删节点、换绑智能体、调顺序」。
- **A/B 并排生成**（同一节点同时跑两个智能体对比）—— 需要「多版本结果并排」的展示模型，与管线执行无共享代码；记入后续。
- **跨项目的管线模板库** —— 每个项目一条，恢复默认可覆盖绝大多数需要。
- **管线运行的历史对比** —— 只保留最近若干次运行，不做版本对比。

## 2. 已定决策

| 决策 | 结论 | 理由 |
|---|---|---|
| 管线粒度 | **每个项目一条**，懒创建 | 不同项目可以有不同的工作流；全局一条会让「改一个项目的顺序」影响所有项目 |
| 默认模板 | 来自代码常量 `DEFAULT_PIPELINE` | 与预置阵容同一套做法：代码是唯一真相，作者改的是自己的副本 |
| 节点身份 | `task_type` + 可选的 `agent_id` | 任务类型是产品概念；`agent_id` 让作者能换绑到自建的智能体 |
| 节点执行 | 一个 `task_type` 一个执行器（注册表） | 每个节点的输入与产出不同，用注册表把差异关在一个文件里，新增节点类型不改运行器 |
| 写库边界 | **只有 `idea_parse` 写**（派生卡）；其余只产出运行记录 | D-03 / D-04：AI 产出先落在编辑区，作者采纳才算数 |
| 检查点 | 节点上的布尔标记 + 项目级策略三档 | 产品 §5.3 的 ★ 就是节点属性；三档是作者对整条管线的耐心 |
| 前置条件不满足 | 节点记 `blocked`，**后续一并停下** | 拿空上下文继续跑只会花钱生成垃圾；停下并说清缺什么更有用 |
| 执行模型 | 进程内守护线程 + 运行状态落库（沿用 `batch_service`） | 单机单人，不引入队列；节点粒度落库让重启不丢进度 |
| 暂停时机 | 当前节点跑完后停在**节点边界** | 中途掐断会浪费已花的 token；节点边界是天然的检查点 |
| 重启恢复 | `running` → `paused` | 进程内线程不跨重启；作者手动继续 |
| 并发 | 同项目同时只允许一个进行中的运行 | 两个运行同时改同一个 `idea.parsed_json` 会互相覆盖 |

## 3. 数据

四张新表，全部走 `create_all`，**本段无迁移**。

### 3.1 `pipeline`

| 列 | 类型 | 说明 |
|---|---|---|
| id | str | |
| project_id | FK project CASCADE，唯一 | 一个项目一条 |
| policy | str(20) | `every` / `key_only` / `auto`，默认 `key_only` |

### 3.2 `pipeline_node`

| 列 | 类型 | 说明 |
|---|---|---|
| id | str | |
| pipeline_id | FK pipeline CASCADE，索引 | |
| seq | int | 顺序，从 0 开始 |
| name | str(120) | 显示名，可改 |
| task_type | str(40) | 决定用哪个执行器 |
| agent_id | str(36) NULL | 换绑到具体智能体；空 = 按 task_type 取第一个启用的 |
| checkpoint | bool | 是否关键检查点（`key_only` 策略下在此暂停） |
| enabled | bool | 停用的节点不执行 |
| target_json | JSON | 节点参数，如 `{"scene_id": "…"}` |

### 3.3 `pipeline_run`

| 列 | 类型 | 说明 |
|---|---|---|
| id | str | |
| project_id | FK project CASCADE，索引 | |
| pipeline_id | str(36) | 快照引用，不建外键（管线被改不影响历史运行） |
| policy | str(20) | **运行时快照**，之后改策略不影响进行中的运行 |
| status | str(20) | `running` / `paused` / `awaiting` / `completed` / `cancelled` / `failed` |
| cursor | int | 下一个待执行节点的序号（按**本次运行快照**的节点列表） |
| message | text | 停下时的原因（阻塞、失败、检查点） |

### 3.4 `pipeline_run_node`

| 列 | 类型 | 说明 |
|---|---|---|
| id | str | |
| run_id | FK pipeline_run CASCADE，索引 | |
| seq | int | |
| name / task_type / agent_id | | **运行开始时快照**，之后改管线不影响历史 |
| status | str(20) | `pending` / `running` / `ok` / `awaiting` / `blocked` / `skipped` / `failed` / `cancelled` |
| generation_run_id | str(36) NULL | 关联的模型运行记录 |
| summary_json | JSON | 产出的摘要（选项数、候选数、卷章数…）与去向链接 |
| message | text | 失败或阻塞的原因 |

**为什么要快照**：运行开始后作者可能去改管线。若运行器每步都读当前管线，改一次顺序就会让进行中的运行错位。快照把「这次运行按什么跑」钉死。

## 4. 执行器（`pipeline_executors.py`）

一个注册表：`EXECUTORS: dict[str, Executor]`，每个执行器：

```python
@dataclass(frozen=True)
class Executor:
    label: str
    run: Callable[[Session, Project, PipelineRunNode], NodeOutcome]
    check: Callable[[Session, Project, PipelineRunNode], str | None]  # 返回阻塞原因
```

| task_type | 前置条件 | 产出摘要 | 去向 |
|---|---|---|---|
| `idea_parse` | 项目里至少一条灵感 | 解析卡字段数、待确认问题数 | 写回 `idea.parsed_json`；链接 `/idea` |
| `architecture` | 已解析的灵感 | 方案数、故事圣经是否有 | 只落运行记录；链接 `/architecture` |
| `worldbuilding` | 已采纳的故事圣经 | 候选数、待确认问题数 | 只落运行记录；链接 `/world` |
| `chapter_plan` | 已采纳的架构（幕骨架） | 卷数、章数、警告 | 只落运行记录；链接 `/chapters` |
| `scene_plan` | 至少一章（`target_json.chapter_id` 或第一章） | 场景数、警告 | 只落运行记录；链接 `/chapters` |

- 每个执行器都走 `RuntimeService.execute`，因此模型分路、参数档、费用记账、`usage_source` 全部自动生效。
- 执行器**只返回摘要与链接**，不写项目结构。
- 新增节点类型 = 注册表加一项；运行器不认识 `task_type` 时该节点记 `skipped` 并说明。

## 5. 运行器（`pipeline_service.py`）

### 5.1 状态机

```
start(project) → 创建 run + run_nodes(pending) → 启动线程
每步：
  取 cursor 处节点
  ├ 节点 disabled → skipped，cursor+1
  ├ 执行器不存在 → skipped，cursor+1
  ├ check() 返回原因 → blocked，run → paused（后续节点保持 pending）
  ├ 执行 → ok / failed
  │   ├ failed → run → paused（可继续重试该节点）
  │   └ ok → cursor+1
  └ 检查点策略：
       every → awaiting
       key_only 且 node.checkpoint → awaiting
       auto → 继续
cursor 越过末尾 → completed
```

- `awaiting` 与 `paused` 的区别：`awaiting` 是「按计划停在这里等作者看」，`paused` 是「出了问题或作者手动暂停」。界面上文案不同。
- 「继续」把 `awaiting` / `paused` 改回 `running` 并重启线程。若停在一个 `blocked` / `failed` 的节点上，继续会**重试该节点**。
- 「取消」把 `cancelled` 落到 run 与未执行的节点；正在跑的节点跑完后不再推进。

### 5.2 线程与落库

沿用 `batch_service` 的形态：模块级 `_ACTIVE: set[str]` + 锁，守护线程，**每个节点一个独立 session**（模型调用可能几十秒，不能占着请求的 session）。

**`advance_run(session, run_id)` 是纯同步的单步函数**，线程只是循环调用它 —— 这样状态机的每一条分支都能被 pytest 直接覆盖，不需要起线程。

### 5.3 重启恢复

`main.py` 的 lifespan 调 `recover_runs()`：把 `running` 改成 `paused`，`running` 的节点改回 `pending`。

## 6. API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/projects/{id}/pipeline` | 管线 + 节点；不存在时懒创建 |
| PUT | `/api/projects/{id}/pipeline` | 整体替换节点列表与策略 |
| POST | `/api/projects/{id}/pipeline/reset` | 恢复默认模板 |
| POST | `/api/projects/{id}/pipeline/runs` | 开始一次运行 |
| GET | `/api/projects/{id}/pipeline/runs/latest` | 最近一次运行 |
| GET | `/api/pipeline-runs/{run_id}` | 单次运行详情 |
| POST | `/api/pipeline-runs/{run_id}/pause` / `resume` / `cancel` | 控制 |

错误映射：不存在 → 404；已有进行中的运行 → 409；其余 → 400。

## 7. 前端 `/pipeline`

- 顶部：策略选择（每步确认 / 仅关键步确认 / 连续自动）+「开始运行」+「恢复默认管线」。
- 节点表：序号、名称、任务类型、绑定智能体（下拉，含「按任务类型自动」）、检查点开关、启用开关、上移 / 下移 / 删除。
- 底部：「追加节点」—— 选任务类型，自动带出默认名称。
- 运行面板：状态、进度、每个节点的状态徽标与消息、`去审阅` 链接；暂停 / 继续 / 取消；2 秒轮询（沿用批量面板的做法）。
- 管线底部一行提示：正文写作在写作台 / 批量生成里，管线只产出结构材料。

## 8. 测试策略

| 层 | 测什么 | 方式 |
|---|---|---|
| 默认模板 | 节点顺序、task_type 覆盖已知类型、检查点标记 | 纯 pytest |
| 执行器 | 每个 `check()` 的阻塞与放行；`run()` 的摘要形状（假传输层） | pytest |
| 状态机 | 全部分支：disabled 跳过、未知类型跳过、blocked 停下、failed 停下、三档策略的暂停点、继续重试、取消、末尾完成 | 直接调 `advance_run`，不起线程 |
| 快照 | 运行开始后改管线不影响进行中的运行 | pytest |
| 重启恢复 | `running` → `paused`，节点 `running` → `pending` | pytest |
| API | 404 / 409 / 400 映射；懒创建；reset | pytest |
| 前端 | 纯逻辑（若有） | vitest |
| 走查 | 节点编辑、运行、检查点、阻塞提示、链接跳转 | 临时数据目录 |

## 9. 文件结构

```
backend/app/
  pipeline_types.py            # 默认模板、策略与状态词表、标签
  pipeline_executors.py        # 执行器注册表
  services/pipeline_service.py # 状态机、线程、序列化
  db/models/pipeline.py        # 四张表
  api/pipeline.py              # 路由
backend/tests/
  test_pipeline_types.py
  test_pipeline_executors.py
  test_pipeline_service.py
  test_pipeline_api.py
frontend/src/
  pages/Pipeline.tsx
  api/client.ts                # 类型与调用
  App.tsx                      # 导航与路由
```

## 10. 遗留与后续

- **正文写作 / 审校 / 逻辑自检 / 润色 不在管线里** —— 走写作台与批量生成；理由见 §1.3。
- **A/B 并排生成** —— 需要多版本并排的展示模型，后续。
- **条件分支与循环** —— 不做。
- **跨项目模板** —— 不做。
