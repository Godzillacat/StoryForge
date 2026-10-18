# StoryForge FTS5 全文检索地基设计文档

> 2026-10-18。P2 生成闭环的硬前置：把「记忆 = 结构化 + 摘要链 + 全文检索」（D-08 / D-16）里的
> 全文检索真正接上。不新建业务数据表、不加迁移版本、不改既有业务数据、不调用模型。
>
> 上位依据：`StoryForge-产品设计文档.md` §5.2 / §5.4 / §6、D-08、D-16。
> 本段是 P2 之前的薄切片；完成后 P2 的执笔智能体可直接勾选「相关设定条目（检索）」槽位。

## 1. 阶段定义

### 1.1 为什么现在补

`CLAUDE.md` 从 P1a 起就把 SQLite FTS5 记为遗留，并两次顺延；产品设计文档把它列为
「长文不散架」的三根柱子之一。当前的实际状态是：

- `DbSlotSource.world_context` 把所有设定条目**不分相关性地**塞进上下文；
- §5.4 的「相关设定条目（检索）」槽位不存在；
- §5.2 的「全文检索」技能没有接口；
- P2 场景生成要靠检索召回相关设定，没有它就只能继续灌全量。

本机可行性已经实测（SQLite 3.45.3）：FTS5 可用，`trigram` 分词器可用；≥3 字中文
短语能命中，**2 字人名/地名 trigram 不命中**；FTS 表上的 `LIKE`、按项目/类型过滤、
`bm25`、`snippet`、按 `doc_id`/项目删除都可用。所以本段采用「trigram + 短词 LIKE 回退」，
不引入分词依赖。

### 1.2 验收标准

1. **索引存在**：全新库与存量库启动后都有 `search_document` FTS5 虚拟表与
   `search_index_state` 表；不新增 `MIGRATIONS` 版本；FTS5 不可用时启动给出清晰错误、拒绝启动。
2. **索引覆盖**：设定条目、章、场景三类文档；条目含名称/别名/标签/摘要/描述/硬度/人物八项，
   章含标题/摘要/钩子/推进线等，场景含目标/冲突/转折/人物名/地点名等。
3. **维护正确**：建 / 改 / 删 / 移动条目、卷、章、场景，`write_scenes` 与
   `write_chapter_plan` 的替换/追加，以及项目删除，下一次检索都反映最新状态；
   级联删除不残留可返回的旧文档；项目隔离不串。
4. **查询**：≥3 字词走 FTS + `bm25`；<3 字词走 `LIKE` 回退；多词 AND；类型过滤；
   空查询/特殊字符不抛 500；结果带标题与片段；limit 边界生效。
5. **API**：`GET /api/projects/{id}/search` 正常返回；项目不存在 404；非法 `types`/limit 400。
6. **槽位**：`SLOT_REGISTRY` 出现 `related_settings`（相关设定条目（检索）），
   `DbSlotSource.related_settings()` 优先用 `search_query`，否则用当前章的**标题**（不拼长摘要/钩子，
   它们会把整句当成一个检索词），都没有返回 `None`；取前 8 条相关条目并格式化；不改现有智能体的槽位勾选。
7. **既有基线**：后端既有 **339 条全绿**并补齐新增测试；前端不改，仍为 18 passed + build 干净。
8. **手工验证**：临时数据目录 + API 播种验证长词/短词、排序、片段、项目隔离、写入后重建、
   删除后消失；作者库副本验证存量库首次检索能重建出可搜结果。不写作者真实库，
   不调用模型、不消耗额度。

### 1.3 明确不做

- **前端搜索页**：阅读器全文检索属 P5；本段只交付接口与槽位。
- **向量检索**：D-16 一期只用 FTS5，向量二期再评估。
- **拼音、同义词、模糊匹配、搜索历史、高亮 UI**：YAGNI。
- **伏笔、时间线、正文段落索引**：伏笔/时间线已有结构化视图；正文要 P2 才有。
- **逐实体增量索引、数据库触发器**：本段用「标脏 + 按项目惰性重建」，理由见 §3。
- **跨项目搜索**：检索永远限定单个项目。
- **修改 `world_context` 的现有行为**：新槽位是 opt-in，旧槽位不动。

## 2. 存储与启动

### 2.1 `search_index_state`（普通表，`create_all` 建）

```text
project_id      TEXT PRIMARY KEY
dirty           INTEGER NOT NULL DEFAULT 1
schema_version  INTEGER NOT NULL DEFAULT 0
rebuilt_at      TEXT
```

- 每个项目一行；没有行等价于「需要重建」。
- `dirty=1` 表示基表在上次重建后发生过写入。
- `schema_version` 与 `SEARCH_INDEX_VERSION` 比较；文档构建字段变化时递增，令旧项目下次检索重建。
- 不加外键：项目删除由 `search_service.delete_project` 显式清理文档与状态行；
  加 FK 也管不到 FTS 虚拟表。

### 2.2 `search_document`（FTS5 虚拟表）

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS search_document USING fts5(
  doc_id UNINDEXED,
  project_id UNINDEXED,
  entity_type UNINDEXED,
  subtype UNINDEXED,
  title,
  body,
  tokenize='trigram'
);
```

- `doc_id` 形如 `entry:<id>` / `chapter:<id>` / `scene:<id>`，用于更新与删除。
- `entity_type` 取 `entry` / `chapter` / `scene`；`subtype` 存条目类型（人物/势力/规则…），章与场景为空。
- `title` / `body` 是唯一被索引的两列；`trigram` 支持中文子串。

### 2.3 启动装配

- 新增 `app/db/search.py`（基础设施）：
  - `SEARCH_INDEX_VERSION = 1`
  - `SEARCH_DDL`（上面的建表语句）
  - `ensure_search_index(engine)`：`CREATE VIRTUAL TABLE IF NOT EXISTS`，幂等。
- `init_db()` 的两条路径（全新库 / 存量库）在 `Base.metadata.create_all` **之后**调用
  `ensure_search_index(engine)`；失败向上抛，应用拒绝启动（与迁移失败同一原则）。
- **不新增迁移版本**：FTS 虚拟表无法用 SQLAlchemy metadata 表达，不能交给 `create_all`；
  迁移框架的既有规则是「迁移永不建表」，这里由检索模块自己保证 DDL 幂等。
  `search_index_state` 是普通表，照常由 `create_all` 建。
- 存量库不要求启动时全库重建：没有 state 行/版本落后时，**首次检索**该项目再重建。
- 测试夹具注意：`Base.metadata.drop_all` 不会删除 FTS 虚拟表。`conftest` 的 `session` fixture
  在重建表后必须清空 `search_document`（或调用 `search_service.clear_index`），
  否则旧测试的文档会跨用例累积。该清理只影响测试库。

## 3. 索引维护：写入标脏 + 惰性重建

### 3.1 机制

- `search_service.mark_dirty(session, project_id)`：在**写入事务内** upsert state 行（`dirty=1`）。
  写事务回滚时标记一并回滚，不会留下「脏了但数据没变」。
- `search_service.search(...)` 开头调用 `_ensure_fresh(session, project_id)`：
  - state 缺失 / `dirty=1` / `schema_version != SEARCH_INDEX_VERSION`
    → 删除该项目全部 `search_document` 行，按当前基表重建，置 `dirty=0`、
    写 `rebuilt_at`、`schema_version`。
  - 否则直接查询。
- 重建按**项目**进行。单机小说规模（条目数百、章数千、场景上万）可接受；
  若将来索引显著变大，再换增量索引，检索接口不变。
- 惰性重建会让一次 GET 检索产生提交（索引状态）。在接口文档里写明；
  P2 的上下文组装在读取阶段调用它时没有待提交的业务改动。

### 3.2 必须标脏的写入点（全部在 `session.commit()` 之前）

| 服务 | 操作 |
|---|---|
| `world_service` | `create_entry` / `update_entry` / `delete_entry` |
| `chapter_service` | 建 / 改 / 删 / 移动卷；建 / 改 / 删 / 移动章 |
| `scene_service` | 建 / 改 / 删 / 移动场景；`write_scenes`（替换与追加） |
| `chapter_plan_service` | `write_chapter_plan`（替换与追加） |
| `project_service` | `delete_project` → `search_service.delete_project`（删文档与状态行，不标脏） |

- 为什么卷与移动也要标：文档标题含卷序/章序/场景序，排序或级联删除会改变可搜文本；**卷名本身不进标题**，卷改名触发一次重建是无害的（保持标记口径简单）。
- 条目写入会改变场景文档里的出场人物名/地点名，所以条目增删改也要标。
- 伏笔、时间线、关系、智能体、服务商、设置不进入索引，不标脏。
- 逐实体增量索引需要覆盖上述全部路径并处理级联；触发器要把字段清单用 SQL 再抄一份。
  两者都比「一行标脏 + 一个 Python 文档构建器 + 首次检索重建」更容易漂移，故不采用。

### 3.3 结果校验

查询命中后按 `entity_id` 回查基表（条目/章/场景）；实体已不存在则丢弃该结果。
这是对任何漏标脏残留的兜底；它不能补出漏建的新文档，但能保证不返回已删除实体。

## 4. 文档构建

唯一构建器在 `search_service._build_docs(session, project_id)`；FTS 表只存结果。

| 类型 | `title` | `body` |
|---|---|---|
| `entry` | 条目名称 | 类型标签、别名、标签、摘要、描述、硬度、人物八项（从 `CHARACTER_FIELDS` 派生） |
| `chapter` | `第{卷序+1}卷 第{章序+1}章 {标题}` | POV、目标字数、情绪基调、推进线、钩子、摘要、状态标签 |
| `scene` | `第{卷序+1}卷 第{章序+1}章 场景{场景序+1} {目标或（未写目标）}` | 目标、冲突、转折、出场人物名、地点名、故事内时间、POV、字数区间、状态标签 |

- 人物/地点名在重建时用条目表解析；条目改名后，下次重建会更新场景文档。
- 字段清单只在构建器里出现一次，人物八项从 `CHARACTER_FIELDS` 派生；但**索引是历史产物**：
  新增人物字段时必须手动递增 `SEARCH_INDEX_VERSION`，让旧项目下次检索重建
  （与迁移冻结字面量同一教训 —— 旧索引不会自动知道新增字段）。
- `doc_id` 用 `entity_type:entity_id`；同一实体重复重建时先删后插。
- 空的条目/章/场景也建文档（至少名称/标题可搜）。

## 5. 查询

`search_service.search(session, project_id, query, entity_types=None, limit=20) -> list[SearchHit]`

### 5.1 规范化

- `query.strip()`；折叠空白；空查询返回 `[]`。
- 按空白切成词；最多取前 8 个词（防止构造超长 SQL）。**检索词按关键词/短语使用**：没有空格的中文长句会被当作一个短语匹配，不保证语义召回；P2 与未来界面应传短词，而不是整段正文。
- 含引号、`*`、`-`、`(` 等 FTS 特殊字符时，FTS 路径统一用双引号包裹并转义；`LIKE` 路径转义 `%`/`_`。
- 大小写：`LIKE` 对 ASCII 默认不区分；trigram 由 FTS5 处理。中文不做额外归并。

### 5.2 两条路径

- **所有词长度 ≥3** → FTS：
  ```sql
  SELECT doc_id, entity_type, subtype, title, body, bm25(search_document) AS rank
  FROM search_document
  WHERE search_document MATCH :match AND project_id = :pid [AND entity_type IN (...)]
  ORDER BY rank LIMIT :limit
  ```
  `:match` 为每个词加引号后 `AND` 拼接；按 `bm25` 升序（越负越相关）。
  FTS 语法异常（例如查询全是引号/特殊符号）时回退 `LIKE`，不把 500 抛给作者。
- **任一词长度 <3** → `LIKE` 回退：
  ```sql
  SELECT doc_id, entity_type, subtype, title, body
  FROM search_document
  WHERE project_id = :pid
    AND (title LIKE :like ESCAPE '\' OR body LIKE :like ESCAPE '\')
    [AND ... 每个词一组 ...] [AND entity_type IN (...)]
  LIMIT :scan_limit
  ```
  先多取（例如 `limit * 3`），在 Python 里按「标题精确 > 标题包含 > 正文包含」排序，
  再截到 `limit`。
- 类型过滤：`entity_types` 只允许 `entry` / `chapter` / `scene`；不传即三类。
- 项目隔离：两种路径都带 `project_id`。

### 5.3 结果与片段

```ts
{
  entity_type: 'entry' | 'chapter' | 'scene'
  entity_id: string
  subtype: string          // 条目类型；章/场景为空串
  title: string
  snippet: string
}
```

- `snippet`：在 `title + body` 里找第一个词（不区分 ASCII 大小写）的首次出现，取前后约 60 字；标题命中也因此能出现在片段里；
  找不到则取开头 80 字；折叠空白并加省略号。
- 回查基表确认实体仍存在；不存在则跳过。
- 不返回完整正文，不返回 `rank` 数值（排序已生效）。
- `limit` 默认 20，最大 50。

## 6. API

```text
GET /api/projects/{project_id}/search?q=...&limit=20&types=entry,chapter,scene
```

- `q`：必填，1–200 字符，空白视为 400。
- `limit`：1–50，默认 20。
- `types`：可选，逗号分隔；允许 `entry` / `chapter` / `scene`；非法值 400。
- 项目不存在 404。
- 返回 `{ "query": "...", "results": [...] }`。
- 可能触发该项目的惰性重建并提交索引状态；在接口 docstring 与 spec 里写明。
- 新增 `backend/app/api/search.py`，在 `main.py` 注册路由。

## 7. 上下文槽位

- `runtime/context.py`：
  - `SlotSource` 协议加 `related_settings(self) -> str | None`。
  - `SLOT_REGISTRY` 加
    `SlotSpec("related_settings", "相关设定条目（检索）", P_MID, "summarize")`。
- `DbSlotSource.related_settings()`：
  - 查询词：`extra_slots.get("search_query")`；没有则用当前章（`chapter_id`）的
    **`title`**；仍为空返回 `None`。不拼 `summary`/`hook`：它们通常是长句，
    按整句短语匹配会漏掉真正相关的条目；P2 应通过 `search_query` 传场景关键词。
  - `search_service.search(..., entity_types=["entry"], limit=8)`。
  - 每条格式化为 `【人物】沈砚 — <片段>`；类型标签来自 `ENTRY_TYPES`，片段用现有 `_clip`。
  - 无命中返回 `None`（槽位为空，不塞占位文本）。
- 新槽位**不加入任何现有智能体**的 `context_slots_json`；P2 的执笔智能体勾选它，
  并按场景卡传入 `search_query`。`/api/slots` 自动投影，工作室可见。
- 检索在槽位里触发惰性重建时可能提交；上下文组装阶段没有待提交的业务写入。

## 8. 测试与验证

### 8.1 pytest（新增）

- **启动**：全新库创建 FTS/state；存量库（模拟删掉 FTS 与 state）启动后重建出空索引；
  版本落后触发重建；FTS5 不可用时给出清晰错误（可在测试里 monkeypatch 连接/DDL 失败，
  至少验证异常不被吞）。
- **文档**：条目三类字段、章与场景标题/正文、人物与地点名解析、subtype、doc_id。
- **查询**：4 字与 2 字中文、多词 AND、短词 LIKE、类型过滤、项目隔离、空/特殊字符、
  bm25 排序、snippet、limit。
- **维护**：条目/卷/章/场景的建改删移；`write_scenes` 替换与追加；`write_chapter_plan`
  替换与追加；项目删除后检索为空且文档清理；级联删除不返回旧实体；写入后下一次检索重建。
- **API**：200 / 404 / 400（空 q、非法 types、越界 limit）、默认参数、返回结构。
- **槽位**：`search_query` 优先、章标题派生查询、无查询 None、项目隔离、格式化、前 8 条。
- **测试夹具**：`conftest.session` 在 `drop_all`/`create_all` 后清空 `search_document`
  （FTS 虚拟表不在 metadata 里）；否则跨用例文档累积。
- 既有 339 条全绿；新增测试计入阶段记录。

### 8.2 手工验证

- 临时数据目录（`STORYFORGE_DATA_DIR`）+ API 播种：
  - 条目：一个 4 字地名、一个 2 字人物名、别名与人物八项；
  - 卷/章/场景：含目标、冲突、人物、地点、推进线；
  - 用 curl 调 `/search` 验证 4 字与 2 字查询、类型过滤、snippet、项目隔离；
  - 改一条条目后再搜（验证标脏 + 重建）；删一个场景后再搜（验证消失）；
  - 检查控制台/日志无 500，索引无残留。
- 作者库副本：复制 `storyforge.db` + `secrets.bin`/`settings.json` 到临时目录，启动后端，
  检索一个作者库中已有的设定条目（如 4 字词与 2 字词），确认存量库首次检索能重建；
  原库不写入；验证后删除副本。**不调用模型、不消耗额度。**
- 前端不改：`pnpm vitest run` 仍 18 passed，`pnpm build` 干净。

## 9. 任务拆分（细化交给计划）

1. `search_index_state` 模型、FTS DDL、`ensure_search_index`、`init_db` 接线、测试夹具清理。
2. `search_service` 的文档构建、标脏、惰性重建、项目删除清理 + 纯服务测试。
3. 查询（FTS/LIKE、排序、片段、校验）+ 测试。
4. 所有写入点接入 `mark_dirty` + 维护测试（建改删移、批量、级联）。
5. API + 测试。
6. `related_settings` 槽位 + 协议/注册表 + 槽位测试。
7. 手工验证、作者库副本验证、CLAUDE.md 同步与走查清单。

任务 1 是地基；2–4 依赖 1；5、6 依赖 2–4；7 最后。

## 10. 与上位文档一致性

| 上位要求 | 本设计 | 一致？ |
|---|---|---|
| D-08 记忆 = 结构化 + 摘要链 + 全文检索 | 结构化查询已有；本段补 FTS5 检索；摘要链属 P2 | ✅ 分段 |
| D-16 一期只用 SQLite FTS5，向量二期 | 只建 FTS5 trigram，无向量 | ✅ |
| §5.4 相关设定条目（检索）槽位 | `related_settings`，优先级中、超预算压缩 | ✅ |
| §5.2 可调用技能含「全文检索」 | GET 接口提供调用面；技能绑定属 P3 | ✅ 分段 |
| §4.8 阅读器全文检索 | 接口可复用，UI 留 P5 | ⏭️ |
| §6 中文检索可行性 | trigram + 短词 LIKE 回退；已实测 | ✅ |
| 迁移框架「永不建表」 | FTS 虚拟表由检索模块 `ensure_search_index` 建；state 表走 `create_all` | ✅ 有记录的边界 |
| P1 完成标志不受影响 | 不新增前端页面；P2 前置 | ✅ |

## 11. 待记入变更记录的决定

- FTS5 索引覆盖**设定条目、章、场景**；伏笔/时间线/正文后续再加类型。
- **FTS 虚拟表不放进迁移**：由 `ensure_search_index` 在 `create_all` 后幂等创建；
  `search_index_state` 走 `create_all`；启动失败即拒绝启动。
- 索引维护采用**写事务内标脏 + 首次检索按项目重建**，不做逐实体增量、不用触发器；
  理由是字段清单只保留一个 Python 构建器，且天然覆盖级联删除与批量写入。
- 中文查询：**≥3 字 trigram + bm25；<3 字 LIKE 回退**；不引入分词依赖。
- 检索可能触发索引重建并在读请求里提交状态；接口文档写明。
- `related_settings` 槽位 **opt-in**；P2 执笔智能体负责勾选并传 `search_query`。
- 不做前端搜索页；P5 阅读器检索复用同一接口。
- 测试夹具必须清空 FTS 虚拟表（`drop_all` 不覆盖它）。
