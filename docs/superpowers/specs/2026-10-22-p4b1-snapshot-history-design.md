# StoryForge P4b-1 设计：项目快照与改动历史

> 2026-10-22。P4 的第二段（第一段 P4a 已交付锁定与影响面）。产品 §4.11 要求三件事：**项目快照（可命名、可回滚）**、场景级分支、**改动历史按目标对象粒度记录**。前两件与第三件里的「快照 / 历史」共享同一套序列化与追溯机制；场景分支是平行的实验机制，单独留 P4b-2。
>
> 上位依据：`StoryForge-产品设计文档.md` §3.1（内容三级）、§4.11（版本与分支）、D-03（可编辑、可追溯、可回退、可锁定）、D-04（作者原文永不被覆盖）。

## 1. 阶段定义

### 1.1 这一段要解决什么

**问题一：没有「整部作品回到某个时刻」的能力。** 作者今天能回退的只有单个场景的正文（`scene_revision`）。但真正会让人后悔的操作往往是成片的：一次章纲替换把三卷十章全删了、一次批量生成把二十场的草稿铺满了、一次故事圣经采纳把幕骨架重排了。这些动作**没有整体回退**。

**问题二：改动发生后查不到「谁改的、什么时候改的」。** `generation_run` 只记 AI 调用；作者自己的编辑、采纳、删除、替换全都没有痕迹。作者想回忆「这一章摘要什么时候被改短的」只能靠记忆。

P4b-1 交付两件事：

1. **项目快照**：把当前项目结构（含已采纳正文）存成一份可命名、可预览、可回滚的快照；回滚前自动再存一份「回滚前自动备份」，所以回滚本身也可撤销。
2. **改动历史**：按目标对象（场景 / 章 / 卷 / 设定条目 / 故事圣经）记录增删改与来源（作者 / AI 采纳 / 恢复 / 回滚），在项目级列表里可按对象筛选。

### 1.2 验收标准

1. **快照可建可查**
   - 可命名（重名报错）并附备注；创建时记下当时的规模（卷 / 章 / 场景数、总字数）。
   - 列表按时间倒序；可删除（删快照不影响项目本身）。
   - 创建快照与删除快照都**不会改动项目数据**。
2. **回滚**
   - 回滚把项目结构恢复到快照当时的状态：卷 / 章 / 场景（含场景卡、已采纳正文、锁定与段落锁）、设定条目与关系、时间线、伏笔、故事圣经与幕骨架。
   - **回滚前自动创建一份「回滚前自动备份」快照**，所以回滚可撤销。
   - 回滚后**快照列表本身仍在**（它是历史记录，不是被回滚的数据）。
   - 回滚**不动**：灵感原话（D-04）、生成运行记录、修订历史、审计与逻辑问题、批量任务、管线、智能体与服务商。
3. **改动历史**
   - 至少覆盖：场景正文保存 / 采纳 / 恢复、场景卡编辑、章编辑、卷编辑、设定条目新建 / 编辑 / 删除（含人物）、故事圣经采纳、快照回滚。
   - 每条记录：时间、目标类型与名称、动作、来源、一句话摘要；写入与业务改动**同一事务**，业务失败则不留记录。
   - 可按目标类型 / 目标 id 筛选；默认按时间倒序，分页。
4. **边界**
   - 回滚到一份「空项目快照」是合法的（等于清空结构），但必须二次确认。
   - 目标已被删除的历史记录仍然可读（记的是当时的名称，不依赖对象还在）。
5. **基线**：后端既有 809 条全绿；前端 30 条全绿、`pnpm build` 干净。
6. **本段不调用模型**：全部是确定性行为，用临时数据目录走查。

### 1.3 明确不做

- **场景级分支** —— 属 P4b-2（并行实验、对比、合并或丢弃是另一套机制）。
- **自动定时快照 / 快照保留策略** —— 作者手动建。单机单人，自动快照会让「为什么多了这些快照」变得难以解释。
- **快照的增量存储与压缩** —— 快照是完整 JSON。一部百万字长篇的单份快照约几 MB，本机磁盘不是瓶颈；增量会让「删一份快照会不会影响另一份」变成需要推理的问题。
- **回滚的合并 / 部分回滚** —— 要么整份回滚，要么不动。部分回滚需要逐对象冲突解决，是另一个产品决定。
- **跨项目的快照或改动历史** —— 每个项目自己的。
- **作者原文（灵感）纳入快照** —— 见 §2 的裁定。

## 2. 已定决策

| 决策 | 结论 | 理由 |
|---|---|---|
| 快照覆盖什么 | **结构与正文**（含场景卡、已采纳正文、锁定），**不含**灵感原话 | D-04 说作者原话永久保留。回滚把作者后来写下的原话删掉，是产品明令禁止的事；这条边界让「回滚」永远不会伤到最不能丢的那份材料 |
| 快照不含什么 | 运行记录、修订历史、审计/逻辑问题、草稿、批量任务、管线、待复核标记、智能体、服务商、单价 | 它们是**日志或配置**，不是作品结构。回滚作品不该回滚「AI 花过多少钱」或「作者调过的提示词」 |
| 快照的存储 | 一份完整 JSON（`project_snapshot.data_json`） | 增量存储会让「删一份会不会影响另一份」需要推理；完整快照是自包含的，删了就删了 |
| 回滚前自动备份 | **每次都建**，名为「回滚前自动备份（快照名）」 | 回滚是整项目级操作，误点的代价最高；自动备份让回滚本身可撤销，成本只是一次 JSON 序列化 |
| 回滚的实现 | 先删当前结构、再按快照里的 **原 id** 重建 | 保留 id 才能让修订历史、审计问题、伏笔链接继续指得着同一个对象 |
| 回滚遇到被删对象的引用 | 审计问题 / 修订指向的场景随结构重建恢复；指向不再存在的对象的行按既有外键语义置空 | 不新造一套引用修复逻辑，沿用 `SET NULL` / `CASCADE` |
| 改动历史的范围 | 产品点名的四类（场景、章节、设定、人物卡）+ 故事圣经 + 快照回滚 | 产品 §4.11 原话是「场景、章节、设定、人物卡」；人物卡就是设定条目的一种类型，不单列 |
| 改动历史的写法 | 在同一事务里插入，**先写日志后提交** | 业务失败时日志跟着回滚，不会出现「记了一笔没发生的事」 |
| 目标名称要冗余存一份 | `target_label` 存当时的名称 | 对象后来被删或被改名，历史记录仍可读 —— 否则作者看到一串裸 UUID |
| 迁移 | **无**。两张新表走 `create_all` | 本段不改已有表 |

## 3. 数据

### 3.1 `project_snapshot`

| 列 | 类型 | 说明 |
|---|---|---|
| id | str(36) | |
| project_id | FK project CASCADE，索引 | |
| name | str(120) | 项目内唯一（`uq_snapshot_project_name`） |
| note | text | 作者备注 |
| data_json | JSON | 完整结构，见 §4.1 |
| volumes / chapters / scenes | int | 建快照时的规模，列表页不必解析 JSON |
| words | int | 总字数 |
| created_at / updated_at | | |

### 3.2 `change_log`

| 列 | 类型 | 说明 |
|---|---|---|
| id | str(36) | |
| project_id | FK project CASCADE，索引 | |
| target_type | str(20) | `scene` / `chapter` / `volume` / `entry` / `architecture` / `snapshot` / `project` |
| target_id | str(36) | 不建外键：日志要比对象的命长 |
| target_label | str(200) | **当时的**名称 |
| action | str(20) | `create` / `update` / `delete` / `adopt` / `restore` / `rollback` |
| source | str(20) | `author` / `ai` / `snapshot` |
| summary | text | 一句话，例如「正文 599 字」「采纳 AI 草稿 577 字」 |

索引 `(project_id, created_at)` 与 `(project_id, target_type, target_id, created_at)`。

## 4. 服务设计

### 4.1 `snapshot_service.py`

序列化范围（一份 `data_json`）：

```
architecture + acts
setting_entry + entry_relation
timeline_event
volume → chapter → scene（含 body / locked / locked_paragraphs）
foreshadow
idea.parsed_json（派生卡，不是原话）
```

**不含** `idea.raw_text`、`generation_run`、`scene_revision`、`scene_draft`、`audit_issue`、`batch_job`、`pipeline*`、`review_mark`、`agent*`、`provider`、`model_price`、`setting`。

```
create_snapshot(session, project_id, name, note) -> ProjectSnapshot
restore_snapshot(session, snapshot_id) -> dict      # 含自动备份的名字
delete_snapshot(session, snapshot_id) -> None
list_snapshots(session, project_id) -> list[dict]
get_snapshot(session, snapshot_id) -> dict          # 含预览摘要
```

**回滚步骤**（全程一个事务，失败即整体回滚）：

1. 先建自动备份快照（另起一个已提交的事务 —— 它必须在回滚失败后依然存在）。
2. 删除当前结构：`volume`（级联章与场景）、`setting_entry`（级联关系）、`timeline_event`、`foreshadow`、`act`、`architecture`。
3. 按快照里的 id 重建。
4. 写一条 `change_log`（`target_type=snapshot`、`action=rollback`）。

重建时**保留锁定状态**：作者锁住的东西不该因为回滚而解锁。

### 4.2 `change_service.py`

```
record(session, project_id, *, target_type, target_id, target_label, action, source, summary)
list_changes(session, project_id, *, target_type=None, target_id=None, limit=100, offset=0)
```

`record` 只 `session.add`，不提交 —— 由调用方的业务事务一起提交。

**接入点**：

| 位置 | target_type | action | source |
|---|---|---|---|
| `text_service.save_body` | scene | update | author |
| `text_service.adopt_draft` | scene | adopt | ai |
| `text_service.restore_revision` | scene | restore | author |
| `scene_service.update_scene` | scene | update | author |
| `chapter_service.update_chapter` / `update_volume` | chapter / volume | update | author |
| `world_service.create_entry` / `update_entry` / `delete_entry` | entry | create / update / delete | author |
| `architecture_service.adopt` | architecture | adopt | author |
| `snapshot_service.restore_snapshot` | snapshot | rollback | snapshot |

摘要取「改了什么」的短句（正文记字数，编辑记字段名，采纳记来源），不复制全文。

## 5. 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/projects/{id}/snapshots` | 列表（含规模与自动备份标记） |
| POST | `/api/projects/{id}/snapshots` | `{name, note}`，201 |
| GET | `/api/snapshots/{id}` | 详情与内容摘要 |
| POST | `/api/snapshots/{id}/restore` | 回滚，返回新结构与自动备份名 |
| DELETE | `/api/snapshots/{id}` | 204 |
| GET | `/api/projects/{id}/changes` | 查询参数 `target_type` / `target_id` / `limit` / `offset` |

错误码：项目或快照不存在 404；重名 400；名称为空 400。

## 6. 前端

- **仪表盘**新增「版本与快照」卡片：建快照（名称 + 备注）、列表（名称、规模、时间、自动备份标记）、回滚（二次确认，明示会回到何时、会丢掉什么）、删除。
- **仪表盘**新增「最近改动」卡片：最近 20 条，按对象类型着色；点一条跳到对应页面。
- **写作台**与**章节页**：选中对象时可看「这一处的改动历史」（按 target_type + target_id 过滤）。

## 7. 测试策略

| 层 | 内容 |
|---|---|
| 序列化往返 | 建快照 → 改动 → 回滚 → 结构与正文逐字段一致（含锁定、段落锁、伏笔链接） |
| 回滚边界 | 灵感原话不变；运行记录 / 修订 / 审计问题 / 快照列表不变 |
| 回滚可撤销 | 回滚后自动备份存在，用它再回滚一次能回到回滚前 |
| 空项目回滚 | 结构与正文清空，项目本身还在 |
| 重名 / 空名 / 不存在 | 400 / 400 / 404 |
| 改动历史 | 每个接入点各一条；业务失败时不留下记录；对象删除后记录仍可读 |
| 接口 | 六条路由的状态码与载荷 |
| 前端 | 只做 build 与手工走查（项目约定：UI 不写自动化测试） |

## 8. 风险

- **快照 JSON 会随正文变大**：百万字约几 MB，列表页只读冗余的规模列、不解析 JSON；详情才解析。
- **回滚后 id 被复用**：修订、审计问题、伏笔若指向被回滚掉又重建的同 id 对象，语义上是对的（同一个对象回到了旧状态）；指向**不存在**对象的行按 FK 语义置空，不新造修复逻辑。
- **改动历史的写入必须在业务事务内**：接入点全部在 `session.commit()` 之前 `record()`，否则会出现「业务回滚了、日志留下了」。
