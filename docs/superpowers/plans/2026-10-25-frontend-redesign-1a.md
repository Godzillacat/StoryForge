# 前端界面重塑 · 批次 1a 实施计划（仪表盘 + 世界观）

- 日期：2026-10-25
- 分支：`worktree-frontend-redesign`（承接 0a/0b 的 12 个提交，不新开分支）
- 依据：`docs/superpowers/specs/2026-10-25-frontend-redesign-design.md`（§9.1 仪表盘、§9.4 世界观、§6 设计语言、§12 分批）
- 前置：0a/0b 已交付（令牌、`src/ui/` 组件层、外壳、项目状态归外壳）

---

## 1. 这一段做什么

把 **仪表盘** 与 **世界观** 两页从旧深色样式重排到新语言，并摘掉 `App.tsx` 里对应的两条 `LEGACY_DARK`。

**不做**：写作台、章节设计（批次 1b）；其余九页（批次 2–3）；动效、骨架屏、错误态（批次 4）。

**硬约束（沿用 spec §12 规则 2）**：只动 JSX 结构与 `className`。不改 `useEffect` 依赖、请求顺序、代际令牌、锁判定、采纳规则、`setNotice` 的文案与成败判定。**本批 diff 里出现逻辑改动即回退。**

## 2. 本批的关键约束：跨批次的共享组件

两页用到 7 个组件，其中 4 个是**页面专属**、3 个**被别的批次也用**：

| 组件 | 行数 | 使用者 | 归属 |
|---|---|---|---|
| `EntryEditor` | 168 | World | 本批专属 |
| `CandidateList` | 145 | World | 本批专属 |
| `RunTrace` | 71 | World、Chapters(1b)、Idea(2)、Architecture(2)、Studio(3) | **跨批次** |
| `Snapshots` | 201 | Dashboard、Writing(1b) | **跨批次** |
| `Locking` | 541 | World、Architecture(2) | **跨批次** |

三个跨批次组件目前**自身透明**（无底色，`text-slate-300` 靠外层深底提供对比）。这决定了一件不能回避的事：

- **不改它们** → 两页变浅底后，`text-slate-400` 落在 `#F4F1EA` 上约 2.4:1，**读不清**，违反 spec §4 反目标。
- **改它们** → 未迁移的 Idea / Architecture / Studio 上会出现一张**浅色卡片落在深色页面里**。

**裁定：改，接受「浅色卡片落在深色页面」这个中间态。** 理由：三个组件改成自备底色（`Card` / `Panel` 本就是 `bg-surface`），在新页面与旧页面上**都保持可读**（深底上的浅卡只是观感突兀，不违反任何验收条款）；而反向不做则直接不可读。代价如实记下：Idea / Architecture / Studio 三页在批次 2–3 落地前会看到浅卡。

**考虑过并否掉的替代方案**：给三个组件加 `tone` 双套类名（由路由驱动）。它能让每个中间提交都完全一致，但要在 541 行的 `Locking` 上把 26 处类名全部条件化，换来的只是观感 —— 而本项目已经用 `LEGACY_DARK` 接受过同类中间态。不引入第二套脚手架。

## 3. 任务拆分（5 个）

> 流程：**每任务一个实施者，不配逐任务审查**；全部完成后由控制方做一次 **diff 级逻辑不变量核对**（§5.2）；最后作者在浏览器手点（§5.3）。
> 理由：本批被硬约束禁止引入新逻辑，审查 agent 的杠杆（读逻辑）在这一批上没有落点。写作台那一批（1b）才需要真实审查。

### T1 · 三个跨批次组件浅色化

- `components/RunTrace.tsx`（10 处）：容器 → `Card`；`bg-slate-900` 的 `<pre>` → `bg-sunken`；amber/red 提示 → `warn-soft` / `danger` 令牌；`text-slate-*` → `ink-2` / `muted` / `faint`。
- `components/Snapshots.tsx`（25 处）：`SnapshotPanel` → `Card`；`ChangeList` 的 `<li>` 分隔线 → `border-line`；链接色 `text-indigo-400` → `text-accent-ink`；两处 `window.confirm` **原样保留**（spec §10 明写本轮不替换）。
- `components/Locking.tsx`（32 处）：`ImpactPanel` 与 `LockToggle` 只换类名与底色，**判定与请求顺序一行不动**（这一文件承载锁语义，是本批最需要小心的地方）。
- 完成判据：三个文件 `grep -o 'slate-[0-9]*' | wc -l` 全为 0；`pnpm run build` 干净。

### T2 · 两个页面专属组件浅色化

- `components/EntryEditor.tsx`（27 处）：表单控件改用 `src/ui/Field.tsx` 的 `Field` / `Input` / `Textarea` / `Select`。**类型专属字段仍由接口清单驱动**（`character_fields` 循环），不硬编八项。
- `components/CandidateList.tsx`（7 处）：候选行改 `Card` + `Button` + `Badge`；类型标记的取值路径不变。
- 完成判据：两文件 `grep -o 'slate-[0-9]*' | wc -l` 为 0；build 干净。

### T3 · 世界观页重排（spec §9.4）

- 栅格 `260px_1fr` → **`308px_1fr`**；列表项：类型标签定宽 + 名称 + 硬度 / 锁定标记。
- 详情区：标题行带锁定状态与「影响面 / 标为待复核」入口；人物八项用**两列栅格**（`multiline` 的字段跨列）；别名 / 称呼做成 chip 行；关联条目单独一段。
- 顶部工具栏：`Button` 化的「新建条目」与「让 AI 提候选」；候选区、待确认问题、`RunTrace` 三个区块改为 `Card`，顺序不变。
- **`EntryEditor` 的 `onChange` / `EMPTY_DRAFT` / `characterFieldsOf` / 深链 effect / `dataToken` / `runToken` 一律不动。**

### T4 · 仪表盘重排（spec §9.1）

- 顶部一行：标题 + 当前项目名（只读回显，选择在侧栏）+ 右侧两个动作。
- **KPI 四列**（全部用现有 `report` 字段）：总字数 `total_words`、已写场景 `scenes − scenes_without_body.length / scenes`、未回收伏笔 `unrecovered_foreshadows.length`、待处理问题 `open_audit_issues + open_logic_issues`。数字用 `font-serif`。
- 下方两栏：左「体检单 + 最近改动」，右「导出与成品报告 + 版本与快照」。
- **删掉两处无数据源的指标**（spec 已定）：分卷进度条、本周每日写作柱。
- 导出卡片的模板下拉与封面控件**行为不变**（`epubTemplate` 不落库、`coverSet` 单独存 state、`coverInput` 的 `value=''` 重置）。

### T5 · 摘掉 `LEGACY_DARK` 两条并收口

- `App.tsx` 的 `LEGACY_DARK` 删除 `'/dashboard'` 与 `'/world'` 两行（12 → 10）。
- 跑 §5.1 全部检查；生成走查清单；按需截图归档。

## 4. 本批的裁定（spec 未覆盖或与代码不符，记在此处）

1. **仪表盘的项目列表：删掉。** spec §9.1 的「现状」与「新版」都没提它，而 0b 已把项目选择收进侧栏 —— 留着就是第二个选择器。它原先独有的两件事保留：`listError` 的「读取项目列表失败，这不是没有项目」提示条、零项目时的 `EmptyState`，都提到页面顶部。`runProjectGuard` 仍由 `ProjectSwitcher` 调用，仪表盘不再需要它。
2. **spec §9.4 的「提及数」无数据源。** `GET /api/projects/{id}/entries` 返回的 `SettingEntry` 没有提及数（提及数只在 `/setting-load` 里按章算）。**不为此引入第二个请求**；列表显示「类型标签 + 名称 + 硬度 / 锁定」。若日后要，应由后端在 entries 响应里补一个字段，而不是前端拼两个接口。
3. **顶部两个动作改为「导出 Markdown」与「导出 EPUB」两个直达链接。** 原计划定的是「刷新」+「新建快照」，实施时否掉：
   - 「刷新」要重跑 `report` / `cost` / `snapshots` / `changes` 那一个 effect，而本批硬规则禁止动 effect 的依赖数组；可行的替代是把 effect 体抽成函数由按钮与 effect 共用 —— 那正是「本批不许出现的逻辑改动」。**留给批次 4**（动效与状态反馈那一批本来就要重构这块），届时在审查下做。
   - 「新建快照」需要把 ref 传进 `SnapshotPanel` 才能聚焦输入框，同样要改组件的 props 与内部逻辑。
   - 两个导出直达链接零逻辑改动，且补上一个真实缺口：现在导出三个入口在右栏卡片里，作者要滚动才够得到。
4. **人物八项改回单列，不做两列栅格。** spec §9.4 写「人物八项用两列栅格（长文本跨列）」，实施时查 `app/world_types.py` 的 `CHARACTER_FIELDS`：**八项里七项是多行长文本**（只有「弧光类型」单行）。两列栅格的实际效果是七行整宽 + 一个孤立的半宽字段，与单列无异，却多一层嵌套。已回退成单列，并在 `EntryEditor` 的注释里写明理由。
5. **锁定行去掉重复的「锁定」标签。** 原文案是 `<span>锁定</span>` + 按钮（按钮自己写着「锁定 / 已锁定」），读作「锁定 锁定」。改为只留按钮 + 一句说明「锁上之后 AI 不会改动这一条；你仍然可以编辑。」
6. **仪表盘的零项目空态文案改了**：`先去「故事仪表盘」新建一个项目` → `先在左侧项目选择器里新建一个项目`。本批删掉了仪表盘的项目列表，建项目入口只剩侧栏，旧文案成了错指。
7. **`window.confirm` 不替换**（spec §10 已定）；`Dialog` 组件本批不新增调用点。
8. **阅读器不参与本批**：`/read` 不在 `LEGACY_DARK` 里，它自铺配色。

## 4.1 走查时观察到、但不在本批范围的一处可读性问题

仪表盘「最近改动」里，一次章纲替换会显示成 `项目 · 南滨旧城 · 删除 · 替换章纲：1 卷 / 2 章`。查证：`app/services/chapter_plan_service.py:425` 把替换写入记为 `target_type="project"` + `action="delete"`（替换确实会删掉旧结构），是 P4b-1 的既有设计，**不是本批引入的回归**。但那一行的动作列写着「删除」，容易被读成「这个项目被删了」。属文案问题，记在此处供后续处置。


## 5. 验证与验收

### 5.1 命令与产物

| 项 | 期望 |
|---|---|
| `pnpm vitest run` | **150 passed 不变** —— 本批是纯样式，不新增纯逻辑，故不新增用例。若数字变了，说明动了逻辑，必须解释 |
| `pnpm run build` | 干净 |
| `pnpm run lint` | 0 error；warning 数与 0a/0b 的 32 持平（新增即为回归） |
| `grep -o 'slate-[0-9]*' \| wc -l` | 本批 7 个文件全为 0；全仓 **999 → 832**（本批清掉 167 处） |
| 无头截图 | 1280×800 与 1440×900 两档，两页无横向滚动、无裁切 |

### 5.2 控制方的 diff 级逻辑不变量核对（替代逐任务审查）

在整批 diff 上逐条核，**任一不成立即回退该 hunk**：

- [ ] `useEffect` 依赖数组：`World` 的四个 effect 依赖项一字未变
- [ ] 请求顺序与请求数：`listEntries` / `listRelations` / `suggestEntries` / `createEntry` / `updateEntry` / `deleteEntry` / `createRelation` / `deleteRelation` / `getExportReport` / `projectCost` / `listSnapshots` / `listChanges` 的调用位置与次数不变
- [ ] 代际令牌：`dataToken` / `runToken` / `reportToken` 的递增与比对位置不变
- [ ] 锁：`LockToggle` / `ImpactPanel` 的 `targetType` / `targetId` / `onChanged` / `onMarksChanged` 传参不变
- [ ] 草稿：`EMPTY_DRAFT` / `draftOf` / `payloadOf` / `characterFieldsOf` 未改；人物八项仍按 `type === 'character'` 守卫
- [ ] 深链：`deepLinkApplied` 只应用一次、`?project=` 先核对再 `select`、失效提示走 `linkWarning`
- [ ] 封面：`coverSet` 仍是独立 state；`coverInput.current.value = ''` 仍在 `finally` 里
- [ ] 导出模板：`epubTemplate` 仍未落库、未进 `localStorage`
- [ ] `window.confirm` 的调用点与文案未变

### 5.3 作者手点（浏览器，控制台须 0 ERROR）

1. 两页在 1280×800 与 1440×900 下无横向滚动、无裁切。
2. 仪表盘：KPI 四个数字与 `report` 对得上；刷新按钮能重取；新建快照能建、列表刷新；导出三个链接与模板下拉照旧；封面上传 / 移除照旧；回滚后报告与费用重新拉取。
3. 世界观：新建条目 → 保存 → 列表出现；改类型到人物 → 八项出现且是两列；别名 chip 行可编辑；锁定开关可设可解；影响面面板照旧；删条目有确认。
4. 切项目：两页都跟着换、无残留（沿用 0a/0b 的手点清单第 1 条）。
5. 未迁移页（Idea / Architecture / Studio）上的 `RunTrace` / `Locking` 浅卡**可读**（预期是观感突兀，不是读不清）。

## 6. 已知中间态与遗留

- **中间态（有意为之）**：`LEGACY_DARK` 剩 10 条；三个跨批次组件在 Idea / Architecture / Studio 上显示为浅色卡片，直到批次 2–3 落地。
- **不合并 master**：本批完成后仍不合，等批次 1b（章节设计 + 写作台）一起，那时 13 页里已有 4 页是新语言。
- **遗留**：spec §11 验收 #3（全站无 `slate-` / `text-xs`）与 #10（`prefers-reduced-motion`）属批次 4；骨架屏、Toast、行内错误条同样属批次 4，本批只用现有 `notice` 文案与样式。
- **`text-xs` 未在本批清理**：新字阶由令牌与组件层承担，存量 `text-xs` 随各页迁移自然消失，批次 4 统一收口。
