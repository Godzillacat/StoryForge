# StoryForge P1c-2 节奏 / 伏笔 / 剧情线视图设计文档

> 2026-10-18。本段是 P1c 的第二半：只读视图，不新建表、不迁移、不调用模型。
> 上位依据：`StoryForge-产品设计文档.md` §4.5（辅助视图）。
> 前置：`docs/superpowers/specs/2026-10-18-p1c1-chapter-design.md`（数据底座已落库）。

## 1. 阶段定义

### 1.1 为什么这一段

P1c-1 已把视图需要的数据全部落库并暴露：

- `GET /api/projects/{id}/chapters/tree` 一次返回卷 → 章 → 场景，章带 `target_words` / `conflict_level` / `dialogue_ratio` / `hook_strength` / `lines`，场景带伏笔埋设与回收；
- `GET /api/projects/{id}/foreshadows` 返回每条伏笔的 `plant_scene_id` / `plan_pay_scene_id` / `status`；
- `GET /api/chapter-types` 下发状态中文标签。

所以本段**只做读取与呈现**：不碰模型、不碰数据库、不碰后端。P1c-1 spec §1.3 把「节奏曲线、伏笔账本、主线/副线泳道视图」明确留给 P1c-2；产品设计文档 §4.5 同样列了这三项。CLAUDE.md 的 P1c-2 行只写了前两项，是漏记，本段按上位文档补齐并记入变更记录。

三个视图都挂在 `/chapters` 页内，因为它们是章节结构的辅助视图，复用同一份已加载的树与伏笔数据，避免再造一套项目选择与请求。

### 1.2 验收标准

1. `/chapters` 顶部有四个页签：**结构设计 / 节奏曲线 / 伏笔账本 / 剧情线**；结构设计页签的现有行为不变；切到视图页签时隐藏章节树、编辑器与 AI 按钮，视图占满宽度。
2. **节奏曲线**：按故事顺序铺开全部章，四行共享 x 轴（目标字数、冲突强度、钩子强度、对话占比）；卷有分带与卷名；`null` 处断线，`0` 保留为有效值；点击任意章（含无指标章）切回结构设计并选中该章。
3. **伏笔账本**：每条伏笔解析出埋设位置与计划回收位置（卷 / 章 / 场景），场景被删除或外键为空时显示「未安排」；缺埋设置顶，其余按埋设的故事顺序；提供「全部 / 缺埋设 / 缺计划回收」筛选；状态列沿用章节状态词表并标为「规划状态」；点击位置切回结构设计并选中场景；本页只读。
4. **剧情线（泳道）**：行 = `chapter.lines` 中的线名（trim 后去重，按首次出现排序），列 = 故事顺序的章，列头按卷分组；有线处显示标记，点击选中该章；无线时给空态。
5. **纯投影有 vitest 覆盖**：扁平化顺序、卷分带、`null` 与 `0`、伏笔连接与缺失、排序与筛选、泳道去重与排序、空树；前端既有 8 条测试全绿，`pnpm build` 干净。
6. **请求代际**：树 / 条目 / 伏笔三类响应统一凭一个代际 token 生效；切项目后迟到的旧响应不得覆盖当前项目。视图在数据未就绪时显示加载态，不把「加载中」误报为「没有数据」。
7. **手工走查**：用临时数据目录（`STORYFORGE_DATA_DIR`）+ API 播种的夹具走查三个视图与空态；不写作者真实库，不调用模型、不消耗额度。
8. 后端测试仍为 339 条全绿；本段不新增后端测试。

### 1.3 明确不做

- **仪表盘摘要**（结构完整度、节奏缩略、伏笔回收率）—— 见 §9 的一致性说明；且真实「回收率」要等 P2/P4 有实际回收状态，现在做只能反映计划，容易误导。
- **视图内编辑** —— 修改仍走结构设计里的卷 / 章 / 场景编辑器；账本与曲线只读。
- **伏笔元数据编辑界面**（名称 / 备注 / 规划状态）—— 现有后端接口可用，但前端没有入口；本段不补，记入遗留。
- **实际字数** —— 正文要到 P2 才存在；本段只用 `target_words`，文案明确写「目标字数」。
- **伏笔生命周期状态**（已埋设 / 已回收 / 逾期）—— P4；本段状态列沿用现有的「规划中 / 已确认」。
- **后端投影接口、数据库改动、迁移** —— 数据已经在前端手里。
- **图表库**（Recharts / visx 等）—— 四组简单序列手写 SVG 即可，符合「不用重型依赖解决本可手写的小问题」。
- **页签写入 URL** —— 用本地状态；刷新回到「结构设计」。
- **泳道的自动分析**（主线 / 副线判定、断线告警）—— 只按字面分组显示。
- **FTS5** —— 仍顺延到 P2 之前。

## 2. 数据来源与投影

### 2.1 现有接口（不改）

| 接口 | 用到的字段 |
|---|---|
| `GET /api/projects/{id}/chapters/tree` | `volumes[].{id,seq,name}`；`chapters[].{id,seq,title,target_words,conflict_level,dialogue_ratio,hook_strength,lines}`；`scenes[].{id,seq}` |
| `GET /api/projects/{id}/foreshadows` | `{id,name,note,plant_scene_id,plan_pay_scene_id,status}` |
| `GET /api/chapter-types` | `statuses[].{key,label}` |

页面已经在同一项目下加载这三份数据；本段不新增请求，也不改后端。

### 2.2 纯函数（`frontend/src/lib/chapterViews.ts`）

所有派生逻辑集中在纯函数里，UI 只负责画。类型与函数签名：

```ts
export interface RhythmChapter {
  id: string
  label: string            // 第N章 标题
  volumeName: string
  volumeSeq: number
  chapterSeq: number       // 卷内序号；显示时 +1
  targetWords: number | null
  conflict: number | null
  dialogue: number | null
  hook: number | null
  lines: string[]
}

export interface VolumeBand {
  id: string
  name: string
  start: number            // 全局章序，含
  end: number              // 全局章序，不含
}

export interface RhythmSeries {
  chapters: RhythmChapter[]
  bands: VolumeBand[]
  maxTargetWords: number   // 至少为 1，避免除零
  missing: { targetWords: number; conflict: number; dialogue: number; hook: number }
}

export function buildRhythmSeries(volumes: VolumeNode[]): RhythmSeries

export interface LedgerLocation {
  volumeSeq: number
  volumeName: string
  chapterSeq: number
  chapterTitle: string
  sceneId: string
  sceneSeq: number
  shortLabel: string       // 第1卷·第3章·场景2（序号均从 1 起，场景为章内序号）
  fullLabel: string        // 第1卷《卷名》· 第3章《标题》· 场景2
}

export type LedgerFilter = 'all' | 'missing_plant' | 'missing_pay'

export interface LedgerRow {
  id: string
  name: string
  note: string
  status: string           // 原样 key，标签由组件用 statuses 映射
  plant: LedgerLocation | null
  pay: LedgerLocation | null
  missingPlant: boolean
  missingPay: boolean
  sameScene: boolean       // 两端都指向同一场
}

export function buildForeshadowLedger(
  volumes: VolumeNode[],
  foreshadows: Foreshadow[],
): LedgerRow[]

export function filterLedger(rows: LedgerRow[], filter: LedgerFilter): LedgerRow[]

export interface SwimlaneChapter {
  id: string
  label: string
  volumeSeq: number
  chapterSeq: number
  volumeName: string
}

export interface SwimlaneRow {
  name: string
  cells: boolean[]         // 与 chapters 等长
  count: number
}

export interface SwimlaneModel {
  chapters: SwimlaneChapter[]
  bands: VolumeBand[]
  rows: SwimlaneRow[]
}

export function buildSwimlanes(volumes: VolumeNode[]): SwimlaneModel
```

- **顺序与编号**：卷按数组顺序（接口已按 `seq` 排好），章按数组顺序；全局章序只用于定位（卷分带、泳道列对齐）。显示给作者的章号一律是**卷内序号 `seq + 1`**，账本与曲线列标签同一口径。
- **空值**：`null` 原样保留，不转 0、不填充。`0` 是有效值。
- **伏笔连接**：用树里的场景建 `sceneId → 场景 / 章 / 卷` 索引。`plant_scene_id` / `plan_pay_scene_id` 为 `null` 或索引里找不到时，对应位置为 `null`（找不到是防御性分支，正常数据不会出现跨项目引用）。
- **排序**（`buildForeshadowLedger` 内部完成）：缺埋设的行置顶（按名称）；其余按 `plant.volumeSeq → plant.chapterSeq → plant.sceneSeq → name` 升序。
- **泳道**：`lines` 逐项 `trim`，空串忽略；同一章内重复线名只留一次；行按该线首次出现的全局章序排序，同序按名称；`cells` 与章列对齐。
- **位置标签**：`shortLabel` 用于表格（`卷一·第3章·场景2`），`fullLabel` 用于悬停 `title`。

### 2.3 请求代际与加载态（对 `Chapters.tsx` 的小修）

P1c-1 留下的缺口：切项目时只有条目请求带 token，树的迟到响应仍可能覆盖新项目；伏笔请求同样没有。视图直接读这两份状态，会把旧项目的数据画出来。

- 把现有 `entriesRequestRef` 语义扩大为**统一的请求代际**（更名 `dataRequestRef`）：项目切换、刷新、卸载时自增；树、条目、伏笔三者的成功与失败路径都先校验 token，再写状态或提示。
- 项目级加载合并为一次 `Promise.allSettled([getChapterTree, listForeshadows])`（条目仍可并行）：任一份失败只影响它自己，另一份照常写入，错误合并进页头 `notice`。用 `viewsLoading` 表示「当前项目的树与伏笔都已有结果」；成功或失败都把 loading 置 false。
- 视图页签在 `viewsLoading` 时显示「正在读取章节结构…」；结束后才可能显示空态。结构设计页签维持现状，不因本修改变更行为（token 修复对它同样生效）。

## 3. 页面结构

### 3.1 页签

```text
章节设计  [项目选择器]                （结构设计页签下：AI 排卷章）
[ 结构设计 | 节奏曲线 | 伏笔账本 | 剧情线 ]
提示条（notice，所有页签共享）
```

- 页签是本地状态 `structure | rhythm | foreshadows | lanes`，默认 `structure`；切项目保留页签，数据清空重载。
- `structure`：渲染现有 AI 按钮、草稿面板、章节树 + 编辑器，原样不动。
- 其余三个页签：不渲染 AI 按钮、草稿面板与树/编辑器；渲染对应视图组件，占满宽度。
- 草稿状态（`chapterPlan` / `scenePlan`）在切走时保留，切回结构设计仍可见；在视图页签下不渲染。
- 无项目时视图显示空态「先选一个项目」。

### 3.2 跳回结构设计

页面提供一个 `openInStructure(selection: Selection)`：

- 节奏曲线点击章 → `{kind:'chapter', id}`；
- 伏笔账本点击埋设/回收位置 → `{kind:'scene', id}`；
- 泳道点击格子 → `{kind:'chapter', id}`。

行为：`setView('structure')` + `setSelected(selection)`。若该 id 已不在当前树里（极端竞态），只提示「这一项已不在当前结构里」，不改选中。

### 3.3 空态与错误态

| 情况 | 视图表现 |
|---|---|
| `viewsLoading` | 「正在读取章节结构…」 |
| 无卷或章 | 「还没有卷章。去『结构设计』建卷，或先用 AI 排卷章。」 |
| 有章但四项指标全为空 | 曲线仍画 x 轴与卷分带，并在上方提示「章还没填节奏指标，去结构设计里补」 |
| 无伏笔 | 「还没有伏笔。在结构设计的场景编辑器里挂上伏笔后，这里会按故事顺序列出。」 |
| 无推进线 | 「章还没填推进的线。在结构设计里编辑章，填『推进的线』后这里会按线分组。」 |
| 请求失败 | 现有 `notice` 显示在页头；视图显示空态，不伪造数据 |

## 4. 节奏曲线

### 4.1 布局

手写 SVG，**四行共享 x 轴的小多图**，避免四组序列挤在同一坐标系：

1. **目标字数**（柱状）—— 文案固定为「目标字数（P1 尚无正文，不是实际字数）」；
2. **冲突强度 1–5**（折线，主序列）；
3. **钩子强度 1–5**（折线，虚线区分）；
4. **对话占比 0–100%**（折线）——按百分比显示，取整到整数；悬停给原始值。

x 轴每列一章；列宽最小 44px，宽度不足时横向滚动（`overflow-x-auto`），不压缩到不可读。左侧固定行标题；卷分带用交替浅底 + 竖分隔线，顶部标卷名（过长截断，`title` 给全名）。列标签写**卷内章序号**（`1, 2, 3…`，与账本「第N章」同一口径），完整标题进悬停提示。

### 4.2 空值与交互

- `null`：折线在该处断开，不跨章插值，不画点；柱状不画柱；汇总行显示「冲突未评 N 章 · 钩子未评 N 章 · 对话未评 N 章 · 目标字数未填 N 章」。
- `0`：正常画（对话占比 0% 是最低点，不是缺失）。
- 每章在整个绘图区上盖一个透明点击矩形（跨四行），带 `<title>`：章标题、卷名、四项值（无则「未评」）、推进线；`onClick` 跳回结构设计。
- 矩形可键盘聚焦（`tabIndex=0`），Enter / 空格触发跳转。
- 无章时不画空坐标系，直接空态。

### 4.3 颜色与可读性

- 深色底（现有 slate 主题）上三条线分别用 indigo / emerald / amber 系；钩子同时用虚线，不只靠颜色区分。
- 坐标轴与网格低对比，数据序列高对比；文字用现有 slate 文本层级。
- 实施时按 `dataviz` 技能的方法核对配色与标记规范；不引入图表库。

## 5. 伏笔账本

### 5.1 表格

列：**名称｜备注｜埋设位置｜计划回收位置｜规划状态｜提示**。

- 位置列渲染 `shortLabel` 的按钮，`title` 给 `fullLabel`；点击跳回并选中场景。
- 备注 `truncate`，`title` 给全文。
- 状态列用 `/api/chapter-types` 的 `key → label` 映射；未知 key 原样显示。表头写「规划状态」，并在下方一行小字说明「P1c 只有规划中 / 已确认；已埋设、已回收等生命周期状态属 P4」。
- 提示列只做派生，不判错：
  - `缺埋设`（`missingPlant`）；
  - `缺计划回收`（`missingPay`）；
  - `埋设与回收同一场`（`sameScene`，中性提示）。
  多个提示用空格分隔；无提示留空。

### 5.2 排序与筛选

- 缺埋设的行置顶，其余按埋设的故事顺序；顺序在 `buildForeshadowLedger` 内完成。
- 顶部筛选：`全部 / 缺埋设 / 缺计划回收`，用 `filterLedger` 纯函数。筛选严格按各自一端判定：`missing_plant` = 埋设为空，`missing_pay` = 计划回收为空。未埋设且也没有计划回收的行会同时命中两个筛选；**未埋设但已安排计划回收的行只命中缺埋设**（2026-10-18 走查修正：数据模型允许先排回收、后埋设，旧表述「未埋设天然也缺回收」不成立）。
- 汇总：`共 N 条 · 缺埋设 X · 缺计划回收 Y`。

### 5.3 只读边界

本页不提供新增、编辑、删除。埋设 / 计划回收的挂接在结构设计的场景编辑器里改。**名称 / 备注 / 规划状态目前只有后端接口、没有界面**（`updateForeshadow` 已在前端 client 里定义但未被任何页面使用）——这是 P1c-1 留下的已知缺口，不在本段补，记入遗留。

## 6. 剧情线（泳道）

- 行 = 线名，列 = 故事顺序的章；列头按卷分组（卷名跨列 + 章序号/标题）。
- 每行左侧显示线名与该线出现的章数；横向滚动，行首列 `sticky left-0` 保持可见。
- 有线处画一个实心方块；格子带 `title`（第N章 标题），点击选中该章。
- 无线名（所有章 `lines` 为空）时给空态，不渲染空表。
- 匹配规则：`trim` 后精确匹配，同一章去重；不做同义、大小写或标点归并 —— 线名是作者的自由文本，静默合并比不合并更危险。

## 7. 测试策略

### 7.1 vitest（纯逻辑）

`frontend/src/lib/chapterViews.test.ts` 至少覆盖：

1. 两卷多章的扁平化顺序与 `bands` 的起止；
2. `null` 指标原样保留、`0` 不被当作空；
3. `maxTargetWords` 在无目标字数时为 1（不除零）；
4. 伏笔跨卷连接：埋设与计划回收在不同卷，标签正确；
5. `plant_scene_id` / `plan_pay_scene_id` 为 `null` 时为 `missingPlant` / `missingPay`，位置为 `null`；
6. 同一场景既埋设又回收 → `sameScene`；
7. 账本排序：缺埋设置顶，其余按卷序 / 章序 / 场景序 / 名称；
8. `filterLedger` 三种筛选；
9. 泳道：trim、章内去重、首次出现排序、卷分带、无线章仍占列；
10. 空树 / 空卷不抛错。

按项目约定，UI 不写自动化测试。

### 7.2 手工走查

临时数据目录（`STORYFORGE_DATA_DIR`）起后端与前端，用 HTTP API 播种：

- 2 卷 5 章：指标混合（部分 `null`、至少一个对话占比 `0`、一个目标字数为 `null`）；
- 4 个场景（其中两个属于同一章）、3 条伏笔：两端齐全 / 缺埋设 / 缺计划回收；
- 线名含重复与带空格的值，另有一章无线。

走查项：四页签切换、卷分带与断线、`0` 与未评的区分、点击跳转、账本排序与筛选、状态标签、泳道去重与点击、三个空态、控制台 0 报错。清单写入 `docs/superpowers/plans/2026-10-18-p1c2-walkthrough.md`。

**不调用真实模型，不消耗额度；不写作者真实库。**

## 8. 任务拆分（细化交给计划）

1. 纯投影函数 + vitest（`chapterViews.ts` / `.test.ts`）；
2. 页面页签、请求代际 / 加载态、跳转函数（`Chapters.tsx`）；
3. 节奏曲线组件；
4. 伏笔账本组件；
5. 泳道组件；
6. 手工走查、走查清单与 CLAUDE.md 同步。

任务 2 依赖 1 的类型；3–5 依赖 1 与 2；可顺序实施、逐个审查。

## 9. 与上位文档的一致性核对

| 上位要求 | 本设计 | 一致？ |
|---|---|---|
| §4.5 节奏曲线（字数、冲突、对话占比、钩子按卷铺开） | 四行小多图；字数用「目标字数」（P1 无正文） | ✅ 有标注的近似 |
| §4.5 伏笔账本（埋设位置、计划回收位置、当前状态） | 账本表格；状态是规划状态，生命周期状态属 P4 | ✅ 分段 |
| §4.5 主线 / 副线泳道 | 按 `lines` 字面分组的泳道 | ✅ |
| §4.1 仪表盘含节奏曲线与伏笔回收率 | 本段不改仪表盘；回收率在 P2/P4 前无真实语义 | ⏭️ 明确不做 |
| D-04 内容三级 | 视图只读，不产生也不采纳内容 | ✅ |
| §8 P1 完成标志「不出正文也能完整策划」 | 本段补齐规划视图，P1 闭环 | ✅ |
| CLAUDE.md P1c-2 行只写两项 | 本段补上泳道，并记入变更记录 | ⚠️ 文档修正 |

## 10. 待记入变更记录的决定

- **P1c-2 含剧情线泳道**：按产品设计文档 §4.5 与 P1c-1 spec §1.3 补齐，同时修正 CLAUDE.md 的 P1c-2 行。
- **P1c-2 纯前端投影**：复用现有树 / 伏笔接口，不加后端端点、不建表、不迁移、不加图表库。
- **`null` = 未评，`0` = 有效值**；曲线在 `null` 处断开，不插值。
- **节奏图用 `target_words` 并标「目标字数」**：实际字数等 P2 写正文。
- **伏笔状态列标为「规划状态」**：沿用章节状态词表（规划中 / 已确认），生命周期状态留 P4。
- **视图只读**：编辑仍走结构设计；点击位置只做跳转与选中。
- **账本排序**：缺埋设置顶，其余按埋设的故事顺序；提供缺埋设 / 缺回收筛选。
- **缺计划回收按解析后的计划回收位置 `pay === null` 判定**（`plan_pay_scene_id` 指向已删除或悬空场景时同样计为缺回收）：未埋设但已安排计划回收的行只算缺埋设。走查夹具推翻了「未埋设天然也缺回收」的旧表述。
- **泳道匹配**：`trim` 后精确匹配、章内去重、按首次出现排序，不做同义归并。
- **请求代际统一**：树 / 条目 / 伏笔共用一个 token，视图在数据就绪前显示加载态。
- **仪表盘不在本段**：节奏摘要与伏笔回收率留到 P2/P4 有真实数据之后。
- **账本只读；伏笔元数据（名称 / 备注 / 规划状态）没有编辑界面**，本段不补，记为遗留。
