# StoryForge P1c-1 章节结构（卷 / 章 / 场景卡 + 策划智能体）设计文档

> 版本 1.0 · 2026-10-18
>
> 上位依据：`StoryForge-产品设计文档.md` v1.0 —— §4.5 章节设计、§5.2–§5.4 智能体与上下文、§7.3 数据模型、§8 落地节奏、§9.1 决策 D-02 / D-04 / D-07 / D-09。
>
> 前序：`2026-10-13-storyforge-p1a-design.md`、`2026-10-14-p1a-hardening-design.md`、`2026-10-16-p1b1-worldbuilding-design.md`、`2026-10-16-migration-and-contract-design.md`、`2026-10-17-p1b2a-characters-design.md`、`2026-10-17-p1b2b-relations-timeline-design.md`。

---

## 1. 阶段定义

### 1.1 为什么这样切

P1c 一次装三块相对独立的工作：

1. **卷 / 章 / 场景卡**（章节结构 + 策划智能体）；
2. **节奏曲线与伏笔账本**（已有章节数据的辅助视图）；
3. **pywebview 外壳与打包**（桌面交付基础设施）。

沿用 P1a 的教训「切片越大，真实验证越晚」，按**依赖不依赖模型**切：

- **P1c-1（本段）**要新增两个策划智能体、扩输出契约与上下文槽位，必须尽早拿真实模型验证；
- **P1c-2** 是纯视图，不依赖模型；
- **打包归 P5**。设计文档 §8 把「打包安装包」放在 P5，P1 的完成标志是「不出正文也能完整策划一部作品」；CLAUDE.md 的 P1c 行把打包也写进 P1c，是笔误，本段修正并记入变更记录。

本段把 P1c-2 需要的**数据底座**一起落库（伏笔表、章级节奏指标），P1c-2 只画视图，不建表、不迁移。

### 1.2 验收标准

1. **新表**：`volume` / `chapter` / `scene` / `foreshadow` 由 `create_all` 建出；存量库启动后四张表齐全，原有数据不受影响（无迁移）。
2. **手工结构**：建卷 → 建章 → 建场景，树形读回；上移 / 下移改变顺序；删除卷级联章与场景；删除章级联场景；删除场景把伏笔的埋设/回收外键置空。
3. **场景卡**：目标 / 冲突 / 转折、人物（只收人物条目）、地点（任意条目）、故事内时间、POV、字数区间、埋设/回收伏笔；名称解析失败给可读错误，不静默丢。
4. **伏笔**：项目内名称唯一；每条有埋设场景、计划回收场景、状态；场景写入时按名称匹配或新建；同一伏笔不能被两个场景同时埋设或同时计划回收（冲突给可读错误）。
5. **两个预置智能体**：章纲策划（`chapter_plan`）与场景策划（`scene_plan`）被预置到新库与存量库；契约通过跨产物一致性护栏；新增槽位出现在 `/api/slots`。
6. **章纲策划运行**：真实/假模型返回结构化 `volumes[].chapters[]`；候选只落在 `generation_run`，**不写卷章表**；`open_questions` 单列；未匹配的幕序号给 warning。
7. **场景策划运行**：返回结构化 `scenes[]`；只出现在世界观里的人物/地点名；找不到的人物/地点进 `warnings`；候选不写场景表。
8. **草稿写入**：`PUT /api/projects/{id}/chapters` 与 `PUT /api/chapters/{id}/scenes` 支持 `replace` / `append`，整次一个事务；`replace` 的删除语义在界面上确认；草稿写入时若带 `source_run_id`，它写到本次新建的卷/章/场景（及新建伏笔），手工新建的记录为 `null`。
9. **前端**：新页「章节设计」有卷/章/场景树、手工编辑器、两个 AI 草稿面板、写入确认与错误展示；项目切换清空状态。
10. **真实模型复验**：确认阿里云百炼额度后，在作者库副本上各跑一次章纲与场景策划，采纳后编辑器回显一致。
11. **既有 292 条测试全绿**，并补齐本段新增测试。

### 1.3 明确不做

- **正文生成、审校、逻辑自检** —— P2 / P4。
- **节奏曲线、伏笔账本、主线/副线泳道视图** —— P1c-2（本段只落数据）。
- **pywebview 外壳、PyInstaller / Inno 打包** —— P5（修正 CLAUDE.md 的笔误）。
- **锁定、快照、分支、影响面分析** —— P4；本段不建 `locked` 空列。
- **伏笔的闭环状态推进**（实际回收、未回收告警）—— P4；本段只存 `planned` 等规划状态。
- **逐章人物状态推进** —— P1c-1 只建章节结构；状态推进与 P2 的正文更新一起做。
- **FTS5 全文检索** —— 仍顺延到 P2 之前。

---

## 2. 数据模型

四张新表**全部归 `create_all`**，不新增迁移（迁移只改已有的表）。

### 2.1 `volume`

| 列 | 类型 | 说明 |
|---|---|---|
| `project_id` | FK → `project`，CASCADE，索引 | |
| `seq` | Integer，默认 0 | 项目内卷序，由服务层维护 |
| `name` | String(200) | 必填 |
| `purpose` | Text，默认空串 | 本卷要做什么 |
| `summary` | Text，默认空串 | |
| `act_seq` | Integer，可空 | 对应第几幕的**快照**；不建外键 |
| `target_words` | Integer，可空 | 本卷目标字数 |
| `status` | String(20)，默认 `planned` | `planned` / `confirmed` |
| `source_run_id` | String(36)，可空 | AI 采纳来源（D-03） |
| 时间戳 | 沿用 `IdMixin` / `TimestampMixin` | |

**`act_seq` 不建外键是刻意的。** 架构采纳会整批删除并重建 `act`；若卷外键到幕，重新采纳架构会断链。快照让卷独立存活；架构变化只在界面上提示「对齐可能已变」，不改数据。

### 2.2 `chapter`

| 列 | 类型 | 说明 |
|---|---|---|
| `volume_id` | FK → `volume`，CASCADE，索引 | |
| `seq` | Integer，默认 0 | 卷内章序 |
| `title` | String(200) | 必填 |
| `pov` | String(100)，默认空串 | |
| `target_words` | Integer，可空 | |
| `emotional_tone` | String(100)，默认空串 | 情绪基调 |
| `lines_json` | JSON，默认 `[]` | 本章推进的线（字符串列表） |
| `hook` | String(200)，默认空串 | 章末钩子 |
| `summary` | Text，默认空串 | 供生成时使用 |
| `conflict_level` | Integer，可空 | 1–5，节奏视图输入 |
| `dialogue_ratio` | Float，可空 | 0–1，节奏视图输入 |
| `hook_strength` | Integer，可空 | 1–5，节奏视图输入 |
| `status` | String(20)，默认 `planned` | |
| `source_run_id` | String(36)，可空 | |
| 时间戳 | 沿用 mixin | |

`lines_json` 用字符串列表而不是独立剧情线表：P1c-2 的泳道视图按同名分组即可；P2/P4 真需要跨章跟踪时再收敛成表（记入变更记录）。

### 2.3 `scene`

| 列 | 类型 | 说明 |
|---|---|---|
| `chapter_id` | FK → `chapter`，CASCADE，索引 | |
| `seq` | Integer，默认 0 | 章内场景序 |
| `goal` | Text，默认空串 | 场景目标 |
| `conflict` | Text，默认空串 | 冲突 |
| `turn` | Text，默认空串 | 转折 |
| `characters_json` | JSON，默认 `[]` | 人物条目 ID 列表 |
| `location_id` | FK → `setting_entry`，可空，`SET NULL` | 地点（任意条目） |
| `story_time` | String(200)，默认空串 | 故事内时间 |
| `pov` | String(100)，默认空串 | 可覆盖章 POV |
| `target_words_min` / `target_words_max` | Integer，可空 | 目标字数区间 |
| `status` | String(20)，默认 `planned` | |
| `source_run_id` | String(36)，可空 | |
| 时间戳 | 沿用 mixin | |

### 2.4 `foreshadow`

| 列 | 类型 | 说明 |
|---|---|---|
| `project_id` | FK → `project`，CASCADE，索引 | |
| `name` | String(200) | 项目内唯一（`UniqueConstraint(project_id, name)`） |
| `note` | Text，默认空串 | |
| `plant_scene_id` | FK → `scene`，可空，`SET NULL`，索引 | 埋设场景 |
| `plan_pay_scene_id` | FK → `scene`，可空，`SET NULL`，索引 | 计划回收场景 |
| `status` | String(20)，默认 `planned` | 规划状态；P4 再闭环 |
| `source_run_id` | String(36)，可空 | |
| 时间戳 | 沿用 mixin | |

**场景表上不再存 `foreshadow_plant_json` / `foreshadow_pay_json`。** 上位文档 §7.3 同时画了场景 JSON 与 `foreshadow` 表，那是两份真相；本设计只保留 `foreshadow` 表，场景卡通过它显示「本场埋设/回收」。同一伏笔只能有一个埋设场景与一个计划回收场景；冲突由服务层拒绝并给出可读原因。`actual_pay_scene_id`（实际回收）等 P2 写正文时再加列。

### 2.5 状态词汇

`volume` / `chapter` / `scene` / `foreshadow` 的 `status` 在 P1c-1 只接受：

- `planned`（默认，规划中）
- `confirmed`（作者确认过这一层的计划）

未知值返回 400。P2 写正文时再扩展 `written` 等值，P4 再扩展伏笔的闭环状态；扩展时必须同步服务层校验与前端下拉。

### 2.6 刻意不建的东西

- **不建 `locked`** —— P4。
- **不建剧情线表** —— 先用 `lines_json`。
- **不建场景版本表** —— P4 的分支/快照。
- **不建 `actual_pay_scene_id`** —— P2；届时新开迁移。

---

## 3. 智能体与上下文

### 3.1 两个预置智能体

沿用 P1b 的预置指纹与显式更新机制：新库直接建立；存量库启动时按 `preset_key` 认领/创建，不会覆盖作者改过的版本。

| 项 | 章纲策划 | 场景策划 |
|---|---|---|
| `key` | `chapter_planner` | `scene_planner` |
| 名称 / 定位 | 章纲策划 / 章节 | 场景策划 / 场景 |
| `task_type` | `chapter_plan`（已有） | `scene_plan`（新增到 `TASK_TYPES`） |
| 上下文槽位 | `project_core`、`story_bible`、`architecture`、`parsed_idea`、`world_context`、`tool_library` | `project_core`、`story_bible`、`architecture`、`world_context`、`timeline`、`volume_outline`、`chapter_outline`、`tool_library` |
| 参数档 | `strict` | `balanced` |
| 输出 | `volumes[]` + `open_questions` | `scenes[]` + `open_questions` |

两个智能体各有一份**窄契约**；不把卷/章/场景塞进同一个 `output_schema`。

### 3.2 新增上下文槽位

| 槽位 | 内容 | 优先级 / 超预算 |
|---|---|---|
| `world_context` | 人物 / 势力 / 地理 / 组织 / 规则 / 历史事件 / 物品 / 概念 / 术语的紧凑摘要；人物带欲望、恐惧、当前状态；规则带硬度 | 高 / 压缩 |
| `timeline` | 故事内事件：时间标注、标题、参与者、地点、描述 | 中 / 压缩 |
| `volume_outline` | 当前卷的名称 / 目的 / 幕序号 / 目标字数 + 章列表（标题、POV、摘要、钩子、状态） | 高 / 压缩 |
| `chapter_outline` | 当前章的全部字段 + 已有场景（目标 / 冲突 / 转折 / 人物 / 地点 / 伏笔名） | 高 / 压缩 |

`world_context` 示例格式：

```text
【人物】陈默（别名：阿默、老陈）— 概述：…；欲望：…；恐惧：…；当前状态：…
【势力】记忆交易局（别名：交易局）— 概述：…
【地理】南滨旧城 — 概述：…
【规则体系】死者不能复活（硬规则）— 概述：…
```

- `DbSlotSource` 新增四个方法；`SlotSource` 协议同步扩展。
- `volume_outline` / `chapter_outline` 需要 `extra_slots` 里的 `volume_id` / `chapter_id`；不属于当前项目就返回 `None`，不泄漏别的项目。
- 新增槽位自动出现在 `/api/slots`，工作室的槽位勾选不必硬编。
- 槽位文本要有长度上限（每条摘要截断），避免把整个世界观塞进上下文；超预算仍走既有裁剪。

### 3.3 输出契约

契约字段的中文名写在 `title`，键名仍然是英文；渲染层自动生成【输出契约】块，提示词里不手抄字段名。校验器支持 `type`、`required`、`properties`、`items`、`minItems`、`enum`，**不支持 `minimum` / `maximum`** —— 数值范围写进 `title`（如「冲突强度（1–5）」），并由计划归一化与服务层再做一次范围校验/钳制。

**章纲策划契约**（顶层）：

```json
{
  "type": "object",
  "required": ["volumes", "open_questions"],
  "properties": {
    "volumes": {
      "type": "array", "minItems": 1, "title": "卷",
      "items": {
        "type": "object", "required": ["name", "chapters"],
        "properties": {
          "name": {"type": "string", "title": "卷名"},
          "purpose": {"type": "string", "title": "本卷要做什么"},
          "act_seq": {"type": "integer", "title": "对应第几幕（没有就省略）"},
          "target_words": {"type": "integer", "title": "本卷目标字数"},
          "summary": {"type": "string", "title": "本卷摘要"},
          "chapters": {
            "type": "array", "minItems": 1, "title": "章",
            "items": {
              "type": "object", "required": ["title"],
              "properties": {
                "title": {"type": "string", "title": "章标题"},
                "pov": {"type": "string", "title": "POV"},
                "target_words": {"type": "integer", "title": "目标字数"},
                "emotional_tone": {"type": "string", "title": "情绪基调"},
                "lines": {"type": "array", "items": {"type": "string"}, "title": "推进的线"},
                "hook": {"type": "string", "title": "章末钩子"},
                "summary": {"type": "string", "title": "本章摘要"},
                "conflict_level": {"type": "integer", "title": "冲突强度（1–5）"},
                "dialogue_ratio": {"type": "number", "title": "对话占比（0–1）"},
                "hook_strength": {"type": "integer", "title": "钩子强度（1–5）"}
              }
            }
          }
        }
      }
    },
    "open_questions": {"type": "array", "items": {"type": "string"}, "title": "没把握的问题"}
  }
}
```

**场景策划契约**（顶层）：

```json
{
  "type": "object",
  "required": ["scenes", "open_questions"],
  "properties": {
    "scenes": {
      "type": "array", "minItems": 1, "title": "场景",
      "items": {
        "type": "object", "required": ["goal", "conflict", "turn"],
        "properties": {
          "goal": {"type": "string", "title": "场景目标"},
          "conflict": {"type": "string", "title": "冲突"},
          "turn": {"type": "string", "title": "转折"},
          "characters": {"type": "array", "items": {"type": "string"}, "title": "出场人物（用标准名）"},
          "location": {"type": "string", "title": "地点（用标准名）"},
          "story_time": {"type": "string", "title": "故事内时间"},
          "pov": {"type": "string", "title": "POV"},
          "target_words_min": {"type": "integer", "title": "目标字数下限"},
          "target_words_max": {"type": "integer", "title": "目标字数上限"},
          "foreshadow_plants": {"type": "array", "items": {"type": "string"}, "title": "埋设的伏笔名"},
          "foreshadow_pays": {"type": "array", "items": {"type": "string"}, "title": "回收的伏笔名"}
        }
      }
    },
    "open_questions": {"type": "array", "items": {"type": "string"}, "title": "没把握的问题"}
  }
}
```

### 3.4 提示词要点

章纲策划：

1. 按幕骨架排卷；每卷有本卷目标与卷末高潮，卷首承接上一卷；
2. 每卷排章；每章写 POV、目标字数、情绪基调、推进的线、章末钩子、摘要，并估计冲突强度、对话占比、钩子强度；
3. 只用【世界观】里已有的人物 / 势力 / 地点 / 规则，不编造；没有合适素材时写进待确认问题；
4. 章数与字数符合项目目标；卷 / 章目标字数要与项目目标量级一致；
5. 卷的幕序号只在能明确对应时填，不确定就省略并进待确认问题；
6. 不写正文；返回符合输出契约的 JSON。

场景策划：

1. 把本章拆成 3–6 个场景；每场有具体目标、冲突与转折；转折要让处境更糟或更难；
2. 只用【世界观】里已有的人物与地点名称；人物只用人物条目，地点可用任意条目；没有合适地点就省略并进待确认问题；
3. 每场写故事内时间、POV、目标字数区间；沿用本章 POV，除非有明确理由；
4. 埋设与回收的伏笔用名称；回收的伏笔必须是前文已埋设或本章埋设的；不确定的进待确认问题；
5. 不写正文；返回符合输出契约的 JSON。

### 3.5 名称与 ID 的边界

契约里模型写**名称**，不写 UUID：模型看到的是名称，强行让它编 UUID 只会产生幻觉。

- 人物：先按 `SettingEntry.name` 精确匹配；再按别名匹配。只接受 `type == "character"`；匹配不到或歧义 → 可读错误。
- 地点：同样的匹配，任意类型；为空允许。
- 伏笔：按 `foreshadow.name` 匹配；不存在则新建（写场景时）。伏笔名不做别名。
- 计划响应里的未匹配人物 / 地点放在 `warnings`，不阻断作者编辑；**写入时**匹配失败直接拒绝整次写入，并列出所有失败名称。
- 同一场景内重复的人物名去重。

---

## 4. 服务层与 API

### 4.1 树与手工 CRUD

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/projects/{id}/chapters/tree` | 卷 → 章 → 场景整棵树；场景内嵌 `foreshadows: {plants: [...], pays: [...]}` |
| `POST` | `/api/projects/{id}/volumes` | 建卷；追加到末尾 |
| `PATCH` / `DELETE` | `/api/volumes/{id}` | 编辑 / 删除（级联章、场景） |
| `POST` | `/api/volumes/{id}/move` | `{direction: up\|down}` |
| `POST` | `/api/volumes/{id}/chapters` | 建章；追加到卷末 |
| `PATCH` / `DELETE` | `/api/chapters/{id}` | 编辑 / 删除（级联场景） |
| `POST` | `/api/chapters/{id}/move` | |
| `POST` | `/api/chapters/{id}/scenes` | 建场景；名称解析、伏笔挂接 |
| `PATCH` / `DELETE` | `/api/scenes/{id}` | 编辑 / 删除 |
| `POST` | `/api/scenes/{id}/move` | |

排序：服务层维护连续 `seq`；上移 / 下移交换并重排；新建追加到末尾；写入草稿按数组顺序重排。删除留下空档时由下一次移动或写入重排。

### 4.2 策划运行

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/projects/{id}/chapters/plan` | 跑章纲策划；返回 `run`、`volumes`、`open_questions`、`warnings`、`structured`、`parse_error`、`raw_text` |
| `POST` | `/api/chapters/{id}/scenes/plan` | 跑场景策划；返回 `run`、`scenes`、`open_questions`、`warnings`、`structured`、`parse_error`、`raw_text` |

- 候选只落在 `generation_run`（D-04），不写 `volume` / `chapter` / `scene`。
- 运行时按智能体的 `context_slots` 取上下文；场景策划额外带 `chapter_id`（以及它的卷）给 `chapter_outline` / `volume_outline`。
- 计划响应做**边界归一化**（类似 P1b 的 `_normalized_candidates`）：缺省数组补空、数值越界钳成 `null` 并加 warning、`act_seq` 不在当前幕里加 warning。归一化是纯逻辑，pytest 覆盖。
- 未匹配的人物 / 地点名放进 `warnings`；伏笔名不 warning（写入时可新建）。
- 运行失败（网络、超时、模板缺变量）沿用既有 `_reason` 的可读中文。

### 4.3 草稿写入

| 方法 | 路径 | 说明 |
|---|---|---|
| `PUT` | `/api/projects/{id}/chapters` | body：`{mode: replace\|append, source_run_id, volumes: [...]}` |
| `PUT` | `/api/chapters/{id}/scenes` | body：`{mode: replace\|append, source_run_id, scenes: [...]}` |

- **整次一个事务**；任一校验失败 → 全部回滚。
- `replace`：删掉该项目全部卷（或该章全部场景），再按数组顺序创建；删除场景会把伏笔的 `plant_scene_id` / `plan_pay_scene_id` 置空，伏笔名与状态保留。界面必须先确认。
- `append`：追加到末尾并重排。
- `source_run_id` 写到新建的卷 / 章 / 场景（以及本次新建的伏笔）；手工建的记录为 `null`。
- 写入响应返回更新后的项目树，前端一次替换状态。

### 4.4 伏笔

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/projects/{id}/foreshadows` | 伏笔列表（P1c-2 账本与场景选择器共用） |
| `POST` | `/api/projects/{id}/foreshadows` | 手工建伏笔（名称必填，项目内唯一） |
| `PATCH` | `/api/foreshadows/{id}` | 改名称 / 备注 / 计划回收场景 / 状态 |
| `DELETE` | `/api/foreshadows/{id}` | 删除；场景里的链接自然消失 |

- **同一伏笔只能有一个埋设场景和一个计划回收场景**：场景写入时，若名称已在别的场景埋设/计划回收，整次写入拒绝并列出冲突。
- 从场景上移除某个伏笔名：若该伏笔的 `plant_scene_id` / `plan_pay_scene_id` 正指向本场景，置空。
- 场景删除 / 章删除 / 卷删除由 FK `SET NULL` 清理链接。
- `foreshadow.status` 在 P1c-1 只允许 `planned` / `confirmed`（P4 再扩展实际回收）。

### 4.5 错误处理

- 所有校验错误给中文可读原因，不用 500。
- 名称解析失败列出全部失败名称（人物 / 地点分开），一次改完。
- 404：卷 / 章 / 场景 / 伏笔不存在；400：父子关系、范围、名称冲突、伏笔占用冲突。
- 运行失败沿用运行时错误分类（template / network / timeout / auth 等）。

---

## 5. 前端

新页「章节设计」（`/chapters`），导航放在术语表之后、智能体工作室之前。

### 5.1 手工结构

- 左栏：卷 → 章 → 场景树；右栏：选中项编辑器。
- 新建卷 / 章 / 场景（需要选中父级）；上移 / 下移；删除需确认。
- 章编辑器：标题、POV、目标字数、情绪基调、推进的线（顿号分隔）、章末钩子、摘要、冲突强度（1–5）、对话占比（0–100%，内部 0–1）、钩子强度（1–5）、状态（计划 / 已确认）。
- 场景编辑器：目标、冲突、转折、人物多选（只列人物）、地点选择（全部条目）、故事内时间、POV、字数区间、埋设/回收伏笔（可选已有或输入新名）。
- 伏笔名在场景编辑器里以可增删的标签呈现；新建名称写入时自动创建伏笔行。

### 5.2 AI 草稿

- 顶部「AI 排卷章」：跑章纲策划；结果进入**可编辑草稿树**（卷 / 章两级），作者逐项改；「写入项目」时选「替换现有结构 / 追加」并二次确认。待确认问题单列。
- 选中一章后可「AI 写场景卡」：跑场景策划；结果进入**可编辑场景草稿列表**；「写入本章」同样选替换 / 追加。
- 草稿里的人物 / 地点未匹配名用醒目提示标出；写入失败时把后端列出的全部名称显示出来。
- 运行期间按钮禁用；切换项目作废在途请求（沿用 `World.tsx` 的 token 模式）。
- 项目没有故事圣经 / 世界观时，给作者可照做的提示（沿用既有 `_reason` 文案）。

### 5.3 前端不写自动化测试

沿用项目约定：`pnpm vitest run` 保持既有 8 条通过，`pnpm build` 干净；新页以手工 / 无头浏览器走查验收。

---

## 6. 真实模型验证

- **调用前确认额度**（记忆里的约定：阿里云百炼免费额度，模型需在额度内）。
- 用作者真实库的**副本**（SQLite 备份 API 复制），启动应用，让预置服务建立两个新智能体。
- 选已有故事圣经与世界观的 `0cce…` 项目：
  1. 跑章纲策划（`qwen3.8-flash`），检查结构化、卷/章数量、是否引用真实人物/势力/地点、待确认问题、warning 是否为空；
  2. 把草稿写入副本库（替换），选一章跑场景策划，检查结构化、场景数、人物/地点名匹配、伏笔名、待确认问题；
  3. 写入场景，确认落库、树接口与编辑器回显一致。
- 两次真实调用；若模型输出不结构化，先修提示词/契约，再重跑。副本验证后删除，不动作者原库。

---

## 7. 测试策略

| 层 | 测什么 |
|---|---|
| 模型 | 四张表默认值、唯一约束（伏笔项目内名称）、级联与 FK `SET NULL` |
| 服务 | 卷/章/场景 CRUD、追加与移动、树排序、名称解析（精确名/别名/歧义/跨项目/类型）、伏笔占用冲突、`replace`/`append` 事务、`source_run_id` |
| 计划归一化 | 缺省数组、越界数值钳制 + warning、`act_seq` 不在幕中 warning、未匹配人物/地点 warning |
| 槽位 | 四个新槽位的内容与项目隔离；`extra_slots` 错误时返回 `None` |
| 契约 | 两个新契约的字段、必填、数组与跨产物一致性（ASCII 标识符 − 槽位 − 白名单） |
| API | CRUD、移动、树、策划（假运行时，类似 P1b 的 `_patch_runtime`）、写入、404/400 |
| 回归 | 既有 292 条全绿 |
| 真实模型 | 章纲 + 场景各一次，采纳与回显（人工） |

---

## 8. 任务拆分

| # | 任务 | 验证方式 |
|---|---|---|
| 1 | `volume` / `chapter` / `scene` / `foreshadow` 模型 + 级联/唯一约束测试 | pytest |
| 2 | 卷 / 章服务与 API：树、CRUD、移动、状态 | pytest |
| 3 | 场景服务与 API：名称解析、人物/地点校验、伏笔挂接与冲突、删除清理 | pytest |
| 4 | 伏笔服务与 API：列表、新建、编辑、删除、计划回收场景 | pytest |
| 5 | 四个上下文槽位 + `SlotSource` / `DbSlotSource` | pytest |
| 6 | 两个预置智能体：`TASK_TYPES`、契约、提示词、跨产物一致性 | pytest |
| 7 | 策划与写入服务 / API：章纲、场景、归一化 warning、replace/append 事务 | pytest |
| 8 | 前端章节设计页：树、手工编辑器、移动、伏笔标签 | 手工走查 |
| 9 | 前端 AI 草稿树 / 场景草稿、真实模型复验、CLAUDE.md 与走查清单 | 真实调用 + 人工 |

---

## 9. 与上位文档的一致性核对

| 上位要求 | 本设计 | 一致？ |
|---|---|---|
| §4.5 三层卷 → 章 → 场景卡 | 四张表 + 树形 API + 页面 | ✅ |
| §4.5 章字段（序号、标题、POV、目标字数、情绪、推进线、钩子、摘要、状态） | 全部落库 | ✅ |
| §4.5 场景卡字段（目标、冲突、转折、出场角色/地点/时间、伏笔、POV、字数区间） | 全部落库；伏笔改为 `foreshadow` 表单一真相 | ⚠️ 有意偏离，已记 |
| §4.5 节奏曲线 / 伏笔账本 / 泳道 | 数据在 P1c-1，视图在 P1c-2 | ✅（分段） |
| §5.2 策划职责「卷-章纲、场景卡、钩子与节奏」 | 两个窄契约智能体 | ✅ |
| §5.3 章纲 → ★调整 → 场景卡 → ★确认 | 草稿树编辑 + 一次写入 + 替换/追加确认 | ✅ |
| §5.4 上下文（本章章纲、本卷纲要、人物卡、时间线） | `chapter_outline` / `volume_outline` / `world_context` / `timeline` | ✅ |
| §7.3 `volume / chapter / scene / foreshadow` | 四张表；场景 JSON 伏笔字段改由 `foreshadow` 表承担 | ⚠️ 有意偏离 |
| §7.3 `locked` | P4；本段不建空列 | ⏭️ |
| §8 P1 完成标志「不出正文也能完整策划」 | 本段 + P1c-2 视图 | ✅ |
| §8 P5 打包 | 不在 P1c；修正 CLAUDE.md 笔误 | ✅ |
| D-04 内容三级 / D-07 大纲→场景卡→正文 | 候选只在运行记录，写入才落库；不写正文 | ✅ |
| D-09 上下文裁剪 | 新槽位接入既有预算与裁剪 | ✅ |

---

## 10. 待记入变更记录的决定

- P1c 拆为 **P1c-1 章节结构 + 策划智能体** 与 **P1c-2 节奏/伏笔视图**；打包归 P5，修正 CLAUDE.md 的 P1c 行。
- 卷与幕**不建外键**，`act_seq` 快照。
- 伏笔**只保留 `foreshadow` 表**，不在场景表上复制 JSON；同一伏笔只有一个埋设/一个计划回收场景。
- 章级节奏指标 `conflict_level` / `dialogue_ratio` / `hook_strength` 在 P1c-1 落库，P1c-2 只读。
- 剧情线先用 `chapter.lines_json`，不建线表。
- AI 契约用**名称**、写入时解析为 ID；未匹配名称在计划阶段给 warning，写入阶段拒绝。
- 场景写入 `replace` 删除旧场景但保留伏笔行（链接置空）；界面必须确认。
- 不建 `locked` / `actual_pay_scene_id`；P2/P4 再加列并走迁移。
