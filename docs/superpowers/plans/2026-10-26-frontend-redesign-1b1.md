# 前端界面重塑 · 批次 1b-1 实施计划（章节设计）

- 日期：2026-10-26
- 分支：`worktree-frontend-redesign`（承接 0a/0b 的 13 个提交与 1a 的 2 个提交，不新开分支）
- 依据：`docs/superpowers/specs/2026-10-25-frontend-redesign-design.md`（§9.8 章节设计、§6 设计语言、§8 布局预算、§12 分批）
- 前置：0a/0b（令牌与组件层、外壳）与 1a（仪表盘 + 世界观）已完成

---

## 1. 这一段做什么

把**章节设计页**（`pages/Chapters.tsx` + `components/chapters/` 全部 12 个文件）从旧深色重排到新语言：页签 7 → 4 组 + 「视图」二级切换、两张手写 SVG 图与一张 div 伪图换配色、表格密度与锁定标记统一，并摘掉 `/chapters` 的 `LEGACY_DARK`。

**不做**：写作台（1b-2）；其余九页（批次 2–3）；动效、骨架屏、错误态（批次 4）。

### 1.1 为什么把 1b 再切一刀

侦察数字：章节设计 **3168 行**（`Chapters.tsx` 799 + `components/chapters/` 2369），写作台 **3749 行**（`Writing.tsx` 1512 + `components/writing/` 2237）。两页**没有任何共享组件**（唯一交叠是 `Locking` / `Snapshots`，已在 1a 浅色化完毕），合起来 6917 行 —— 比 0a/0b 整个批次还大。

更要紧的是风险不同：章节设计只重排 JSX 与配色（见 §3.1，页签重组可以零新状态），而写作台要新增专注态、抽屉、右栏四页签、`localStorage` 持久化 —— 那是压在六套既有状态机之上的**新交互状态**。沿用本项目反复写下的教训：**切片越大真实验证越晚**。

**流程也据此分档**（依据见 §8 变更记录 2026-10-26 那条）：本批**不配逐任务审查**，以 diff 级机械核对 + 新纯模块的 vitest 覆盖为准；1b-2 仍走全套（实施者 + 独立审查 + 整支复查）。

## 2. 现状（侦察所得，写计划时已逐条核对）

| 项 | 数字 |
|---|---|
| 总行数 | **3168**（`Chapters.tsx` 799 + 12 个组件 2369） |
| `slate-` 出现次数 | **308**（最多 `ChapterPlanDraft` 43、`SceneEditor` 40、`CharacterDrift` 36） |
| `text-xs` 出现次数 | **76** |
| `transition` | **0** |
| **`src/ui/` 组件使用** | **0 处** —— 0a 建的组件层在这两页里一个都没用上 |
| `src/ui/Tabs.tsx` 全仓引用 | **0 处**（0a 交付至今无人使用） |
| 页签 | 1 组、**7 个手写 `<button>`**（`Chapters.tsx:533–547`），非 `Tabs` |
| 图表 | 2 张手写 SVG（`RhythmCurve` 304 行、`SettingLoadCurve` 253 行）+ 1 张绝对定位 div 伪图（`CausalMap` 187 行） |
| 写死的十六进制 | 只在两处：`RhythmCurve.tsx:12–20`（5 个）、`SettingLoadCurve.tsx:10–15`（4 个） |
| 逻辑规模 | 25 个 `useState`、4 个 `useRef`（含**三套代际令牌**）、**2 个 `useEffect`**（依赖数组 `[]` 与 `[projectId]`）、`Promise.allSettled` 一次发 7 条接口、2 处 `window.confirm` |

**`src/ui/` 零使用是这一段最值得记下的事实**：0a 的组件层与令牌至今只被外壳与 1a 的两页用到，真正的考验从这一批开始。

## 3. 本批的两条关键裁定

### 3.1 页签重组**不引入任何新状态**（这是本批风险低的原因）

spec §9.8 写「页签收敛为「结构 / 节奏 / 伏笔 / 视图」四组，后三组合并为「视图」下的二级切换（因果链、设定投放、性格漂移、剧情线）」。这句话本身**自相矛盾**（「视图」既是四组之一，又被说成「后三组」的容器）。按括号里的清单反推，唯一能覆盖现有 7 个页签且不丢项的映射是：

| 一级组 | 二级 | 现有 `view` 值 |
|---|---|---|
| 结构 | —— | `structure` |
| 节奏 | —— | `rhythm` |
| 伏笔 | —— | `foreshadows` |
| 视图 | 因果链 / 设定投放 / 性格漂移 / 剧情线 | `causal` / `settingLoad` / `characterDrift` / `lanes` |

**裁定：`view` 仍是原来那一个 `ViewTab` 状态，不新增任何 state。** 一级页签的选中态由 `view` **投影**得出（`groupOf(view)`），点一级组即 `setView(该组默认视图)`，点二级即 `setView(子项)`。因此：

- `Chapters.tsx` 里 **8 处 `view === 'xxx' && …` 渲染分支（L513 / 549 / 733 / 741 / 753 / 761 / 772 / 782）一行都不用改**；
- 页签重组只动 L533–547 那一段页签条 + 一个新纯模块。

### 3.2 图表配色抽成 `src/ui/chartTokens.ts`（本批唯一新增的纯逻辑）

现状：两张图的颜色写在各自文件顶部的裸十六进制里（`RhythmCurve` 6 个 + 3 处内联，`SettingLoadCurve` 4 个 + 3 处内联），而 `src/ui/palette.ts` 的注释明写「页面与组件只能引用这里的值，不得写裸十六进制」。1b-2 的 `LogicChainGraph` 有同样问题（9 个 hex），所以这个模块建在本批、由 1b-2 扩展消费。

- **只收敛颜色，不收敛几何。** 实施时核对过：`RhythmCurve` 的列宽是 44、`SettingLoadCurve` 用的是 `lib/settingLoad.ts` 导出的 `COL_W = 56`，两张图的几何**确实不同**（一张是四行堆叠小多图、一张是单一绘图区），强行统一会为了「单点定义」而写错。几何留在各自文件里。
- 颜色**全部取自现有 `PALETTE`**，不新增调色板条目（避免动 `palette.ts` / `tailwind.config.js` / `contrast.test.ts` 三处的一致性断言）。
- **节奏图从 4 种序列色收敛成 2 种**：墨绿实线（`accent`）+ 沙色虚线（`line-strong`）。理由有二：一是四行本来就是各自独立的小图、左侧各有文字标签，**颜色不承担区分职责**；二是原文件顶部的注释自己记着「emerald 与 amber 的 CVD 差落在 6–8 警告带」—— 收敛到两种颜色顺带消掉这个色觉障碍隐患。虚线保留给「钩子」那一行，即既有的次级编码不动。
- 设定投放图两条序列是**同一绘图区里并置**的，必须能分开：柱用 `accent`、密度线用 `warn`。
- 绘图区底用 `surface`、网格用 `sunken`（spec §6.1 明确把 `sunken` 给「图表网格」）、卷带底用 `paper`、点描边用 `surface`（与绘图区底同色，让点从线上「咬」出来）。
- 该模块是**纯数据**，配 vitest：断言每个取值都确实是 `PALETTE` 里的成员（挡住日后有人再贴一个裸 hex），以及「并置的两条序列色不相同」。


## 4. 任务拆分（6 个）

> 每个任务一个实施者，**不配逐任务审查**；全部完成后做一次 diff 级逻辑不变量核对（§5.2）；最后作者在浏览器手点（§5.3）。

### T1 · 图表层：新增 `src/ui/chartTokens.ts` 并让三张图改用它

- 新增 `frontend/src/ui/chartTokens.ts`（纯数据 + 纯函数 + vitest）。
- `components/chapters/RhythmCurve.tsx`（304 行，9 处 slate、5 个 hex）：删掉文件顶部 5 个 hex，改用 `chartTokens`；四行小多图同用 `accent`，参考虚线用 `line-strong`，网格用 `line`；`slate-` 清零。
- `components/chapters/SettingLoadCurve.tsx`（253 行，4 个 hex）：同上；柱用 `accent`、密度线用 `accent-ink`、未写章灰块用 `sunken`。
- `components/chapters/CausalMap.tsx`（187 行）：它是绝对定位 div 而非 SVG，只换类名与断点标记色（`warn`）；**结构不动**。
- 完成判据：三个文件 `grep -o 'slate-[0-9]*' | wc -l` 为 0、无裸 hex；build 干净。

### T2 · 页签层：新增 `lib/chapterTabs.ts` 并把页签条换成 `src/ui/Tabs`

- 新增 `frontend/src/lib/chapterTabs.ts`（纯数据 + 纯函数 + vitest）：`ViewTab` 类型、`TAB_GROUPS`、`groupOf(view)`、`defaultViewOf(group)`。**`ViewTab` 从 `Chapters.tsx` 搬到这里**（现在定义在 L40，是个私有类型）。
- `Chapters.tsx` 的页签条（L533–547）换成两层 `Tabs`：一级四个组；当选中组是「视图」时，其下再渲染一行二级 `Tabs`（用 `Tabs` 的 `count` 显示各视图的条目数，若有现成数字；没有就留空）。这是 `src/ui/Tabs.tsx` 交付以来**第一次被使用**。
- **8 处 `view === 'xxx' &&` 分支、`setView` 的调用点、`openInStructure`（L485–500）一律不动。**
- 完成判据：`TABS` 常量从 `Chapters.tsx` 消失；7 个页签仍全部可达；vitest 新增 `chapterTabs` 用例全绿。

### T3 · 编辑器与草稿类组件浅色化（6 个文件）

`ChapterTree.tsx`(100) / `VolumeEditor.tsx`(91) / `ChapterEditor.tsx`(133) / `SceneEditor.tsx`(262) / `ChapterPlanDraft.tsx`(181) / `ScenePlanDraft.tsx`(122)。

- 表单控件改用 `src/ui/Field.tsx` 的 `Field` / `Input` / `Textarea` / `Select`；容器改用 `Card`；按钮改用 `Button`。
- **`SceneEditor` 的 `entriesReady` 守卫（L238–247）与 `resolvedNameOf` 过滤一行不动** —— 那是「条目未加载完时不把人物/地点写成空值」的保护。
- **两份草稿的替换/追加确认文案与 `mode` 状态不动**（`ChapterPlanDraft` L52、`ScenePlanDraft` L37 的 `window.confirm`）。
- `ChapterTree` 的 `active()` 选中态（L25–26）改 `accent-soft` / `accent-ink`，并给选中行加左侧 2px 墨绿（spec §9.8）。
- 完成判据：六个文件 `slate-` 清零；build 干净。

### T4 · 视图与表格类组件浅色化（3 个文件）

`ForeshadowLedger.tsx`(293) / `Swimlanes.tsx`(100) / `CharacterDrift.tsx`(343)。

- 表格改用 `src/ui/Table.tsx` 的 `Table` / `Th` / `Td`（行高 44px 由 `Td` 的 `py-[11px]` 承担）；徽标改用 `Badge`。
- **`ForeshadowLedger` 的 `statusIsLegacy` / `statusIsDerived` 分支与「清掉实际回收」不动**；`api.updateForeshadow` 的两个调用点不动。
- **`CharacterDrift` 的 `saved → closeEditor → onReload` 顺序、`putCharacterState` / `deleteCharacterState` 调用点不动。**
- 完成判据：三个文件 `slate-` 清零；build 干净。

### T5 · `Chapters.tsx` 页面骨架重排

- 栅格 `lg:grid-cols-[300px_1fr]` → **`grid-cols-[308px_1fr]`**（与世界观页对齐）；左列 `ChapterTree` 放进 `Panel`，右列编辑区各块改 `Card`。
- 标题行（h2 + 「AI 排卷章」+ notice）改成新语言；`notice` 走 `warn` 提示条。
- 锁定标记统一成**锁形图标 + `warn` 小标签**（`Icon name="lock"`，取代 L629 的「锁定」文字与 `CausalMap` L136 的 🔒）。
- `ReviewMarkList` 的挂载点与 props 不动。
- **两个 `useEffect` 的依赖数组、三套代际令牌、`Promise.allSettled` 七接口顺序与「因果/投放/漂移各自独立报错、不牵连页头」的分流一律不动。**

### T6 · 摘掉 `LEGACY_DARK` 的 `/chapters` 并收口

- `App.tsx` 的 `LEGACY_DARK` 删除 `'/chapters'`（10 → 9）。
- 跑 §5.1 全部检查；按 §5.2 做不变量核对；生成走查清单与截图。

## 5. 验证与验收

### 5.1 命令与产物

| 项 | 期望 |
|---|---|
| `pnpm vitest run` | 基线 150 + **新增的 `chapterTabs` / `chartTokens` 用例**；**除这两组外数字不变** —— 变了就说明动了别的逻辑，必须解释 |
| `pnpm run build` | 干净 |
| `pnpm run lint` | 0 error；warning 与基线 32 持平（新增即为回归） |
| `slate-` 残留 | 本批 13 个文件全为 0；全仓 **832 → 524**（清掉 308 处） |
| 裸十六进制 | 本批文件里 0 处 |
| `LEGACY_DARK` | 10 → 9 |
| 无头截图 | 1440×900 与 1280×800，七个视图逐个切换后各截一张（确认无横向滚动、无裁切） |

### 5.2 控制方的 diff 级逻辑不变量核对（替代逐任务审查）

- [ ] `Chapters.tsx` 两个 `useEffect` 的依赖数组（`[]`、`[projectId]`）**逐字未变**；effect 体里 `return` 清理的 `dataRequestRef.current += 1` 未变
- [ ] 三套代际令牌的 `++` 与比对点未变：`runToken`（L103）、`dataRequestRef`（L106）配 `projectIdRef` 双检、`characterDriftRequestRef`（L108）
- [ ] `Promise.allSettled` 一次发 7 条接口的**顺序**未变；「因果 / 投放 / 漂移各自独立报错、不牵连页头」的分流未变
- [ ] `refresh()` 的 `projectIdRef` 早返回与 finally 的三个 `*ProjectId` 收尾未变
- [ ] 8 处 `view === 'xxx' && …` 渲染分支未变；`setView` 调用点未变；`openInStructure` 未变
- [ ] `SceneEditor` 的 `entriesReady` 守卫与 `resolvedNameOf` 过滤未变
- [ ] `ForeshadowLedger` 的 `statusIsLegacy` / `statusIsDerived` 分支未变
- [ ] `CharacterDrift` 的 `saved → closeEditor → onReload` 顺序未变
- [ ] 2 处 `window.confirm` 的调用点与文案未变（`deleteSelected`、两份草稿的替换/追加）
- [ ] `LockToggle` / `ImpactPanel` / `ReviewMarkList` 的 props 与回调未变
- [ ] `api.*` 调用序列与次数：逐文件与改造前对照一致

### 5.3 作者手点（浏览器，控制台须 0 ERROR）

1. 七个视图**逐个点开**都渲染正确（尤其「视图」组的四个二级项）；一级组选中态与二级一致。
2. 章节树：选卷 / 章 / 场景，右侧编辑器跟着换；增删卷章场景、上下移、删除有确认。
3. 场景卡：人物 chip 增删、地点选择、伏笔埋设/回收选择；**条目未加载完时保存不会把人物/地点清空**。
4. 节奏图与设定投放图：配色是新的，数值与改造前一致；悬停/点击跳转仍生效。
5. 伏笔账本：行内改状态、旧值按钮、清掉实际回收、筛选。
6. 性格漂移：点格子改状态、删除；保存后表格刷新。
7. 因果链：断点标记、锁定标记（新图标）、点节点跳回结构设计并选中该场。
8. 1440×900 与 1280×800 两档无横向滚动、无裁切。

## 6. 已知中间态与遗留

- **中间态（有意为之）**：`LEGACY_DARK` 剩 9 条；`RunTrace` / `Locking` / `Snapshots` 在 Idea / Architecture / Studio 上仍是浅色卡片落在深色页面里，直到批次 2–3 落地。
- **不合并 master**：本批完成后仍不合，等 1b-2（写作台）做完一起合 —— 那时 13 页里已有 5 页是新语言。
- **`text-xs` 未在本批清理**：本页 76 处随迁移自然消失，批次 4 统一收口（spec §11 验收 #3）。
- **spec §9.8 那句话的自相矛盾已按括号清单裁定**（§3.1），并记入 §8 变更记录。
- **`count` 角标视数据可得性而定**：`Tabs` 支持 `count`，但各视图的条目数不一定都有现成数字；没有就留空，不为凑角标加请求。
