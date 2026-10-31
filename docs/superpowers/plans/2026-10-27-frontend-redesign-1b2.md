# 前端界面重塑 · 批次 1b-2 实施计划（写作台）

- 日期：2026-10-27
- 分支：`worktree-frontend-redesign`（承接 0a/0b 的 13 + 1a 的 2 + 1b-1 的 2 个提交，不新开分支）
- 依据：`docs/superpowers/specs/2026-10-25-frontend-redesign-design.md`（§9.9 写作台、§8.2 宽度预算、§6 设计语言、§12 分批）
- 前置：0a/0b、1a、1b-1 已完成
- **这是「批次 1」的最后一段**；做完后 0a/0b/1a/1b-1/1b-2 一起合 master（作者已定）

---

## 1. 这一段做什么

把**写作台**（`pages/Writing.tsx` 1512 行 + `components/writing/` 15 个文件 2237 行 = **3749 行**）重排到新语言，并摘掉 `/write` 的 `LEGACY_DARK`。写作台是全项目最复杂的一页，它同时压着九套机制：流式生成（SSE）、草稿 diff、采纳、段落锁、A/B 并排生成、场景分支、审校、逻辑自检、回写、批量生成。

**不做**：其余九页（批次 2–3）；动效、骨架屏、错误态（批次 4）。

**这一批与前两批的根本不同**：1a / 1b-1 只重排 JSX 与配色，而本批要**新增交互状态** —— 工作态 / 专注态、左树抽屉、右栏四页签、`localStorage` 持久化。所以本批回到全套流程（见 §3）。

## 2. 现状（侦察所得，写计划时已逐条核对）

| 项 | 数字 |
|---|---|
| 总行数 | **3749**（`Writing.tsx` 1512 + 15 个组件 2237） |
| `slate-` / `text-xs` | **248 / 108** |
| `src/ui/` 组件使用 | **0 处** |
| 三栏栅格 | `Writing.tsx:1027`，`grid gap-4 xl:grid-cols-[240px_minmax(0,1fr)_320px]`（仅 `xl:` 断点生效，否则单列堆叠） |
| 右栏 | 一个 `<aside>`（L1301–1507）里**纵向堆叠 12 块** |
| 工具栏 | L1077–1224，**9 个按钮**，`disabled` 条件各自组合 `busy / generating / auditLoading / logicLoading / writebackBusy / sceneLock?.locked / text.has_body / mode` |
| 逻辑规模 | 45 个 `useState`、**10 个 `useRef`**（含**五套代际令牌**）、**14 个 `useEffect`** |
| 五套令牌 | `treeToken`(115) / `sceneToken`(116) / `logicToken`(117) / `batchToken`(118) / `generateToken`(119) |
| 交互确认 | 8 处 `window.confirm` + 1 处 `window.prompt`（分支派生） |
| 专注态 / 抽屉 / `localStorage` | **完全没有**（写作台内零 `localStorage`） |
| SSE | `streamSceneGeneration`（`api/client.ts:1411`）→ `lib/sse.ts`；事件 `run / delta / done / error`；三个调用点（`Writing.generate`、`AbPanel.runSide`、`BranchBodyEditor.generate`） |
| 裸十六进制 | 只在 `LogicChainGraph.tsx`（9 个）—— 1b-1 已建好 `ui/chartTokens`，本批让它消费 |
| `<textarea>` | 3 处：`SceneTextView`(rows=18, `font-mono text-sm leading-7`, **`resize-y`**) / `BranchPanel`(h-96) / `WritebackPanel`(rows=4) |

**右栏当前 12 块（按挂载顺序）**：①这一场的改动 `ChangeList` ②`AbPanel` ③`BranchPanel` ④`ParagraphLocks` ⑤`ContextPreview` ⑥`AuditPanel` ⑦`LogicChain` ⑧`LogicPanel` ⑨`WritebackPanel` ⑩`BatchPanel` ⑪内联「本次运行」 ⑫`RevisionHistory`

## 3. 流程：任务内按各自内容分档

本批**整体走全套流程**（每任务一个实施者 + 一个独立审查，末尾整支复查），但**同一批内不再一刀切**：

| 任务 | 性质 | 审查 |
|---|---|---|
| T1–T6 | 新增交互状态、重排容器 | **独立审查**（真审查：这些改动会改变渲染树与状态时序） |
| T7 | 纯样式（15 个组件的 className） | **diff 级机械核对**（剥 `className` 后逐行 diff + 处理函数体/条件逐字比对），不配审查 agent |
| T8 | 摘 `LEGACY_DARK` + 收口 | 控制方 |

依据是那条判据「这一批会不会引入新逻辑」在**任务粒度**上的应用 —— 一个批次里既有新状态也有纯样式时，按任务分档，而不是整批上全套（那会把审查费花在机械替换上）。

## 4. 任务拆分（8 个）

### T1 · 布局状态层：新增 `lib/writingLayout.ts`（纯逻辑 + vitest）

- 新增 `frontend/src/lib/writingLayout.ts`：`WritingMode = 'work' | 'focus'`；`modeForWidth(width)`（≥1440 工作态、1280–1439 专注态、<1280 专注态）；`KEY_WRITING_MODE` / `KEY_RIGHT_COLLAPSED` / `KEY_DRAWER_OPEN` 三个 `localStorage` 键（与 `lib/persisted.ts` 现有 `storyforge.` 命名空间一致）；`defaultsFor(mode)` 返回「左树形态 / 右栏形态 / 是否显示底部状态条」。
- **`lib/persisted.ts` 已有 `readFlag` / `writeFlag`**，直接复用，不写第二套读写。
- vitest：断点边界（1439 / 1440）、两种模式各自的形态默认值、键名不与外壳的键冲突。
- 完成判据：vitest 全绿；`pnpm run build` 干净。

### T2 · 三栏骨架与专注态

- 栅格：`xl:grid-cols-[240px_minmax(0,1fr)_320px]` → 按 §8.2 预算重写：外壳 236 已由 `App.tsx` 提供，页面内为 **左树 236 / 正文弹性（上限 680，余量作页边）/ 右栏 336**；专注态下左树改抽屉、正文 560–620 居中、右栏变浮层。
- 抽屉：工具栏左侧「章节」按钮呼出，**ESC 关闭**（`keydown` 监听要挂在窗口上并在卸载时移除）。
- 右栏可折叠成 44px 条（工作态）。
- **不改**：`treeToken` / `sceneToken` 的递增与比对、`loadScene` 的 6 条 `Promise.allSettled`、`selectScene` 的确认、`refreshTree` **刻意不递增 `treeToken`** 这条。
- 独立审查重点：抽屉的 ESC 监听有没有泄漏、切场景时抽屉/右栏状态有没有串、正文让位逻辑有没有与 `branch` 分支打架。

### T3 · 工具栏收成一行

spec §9.9 定的六项：面包屑、保存状态、对比草稿、采纳、生成正文、更多。

- 左：面包屑（卷 · 章 · 场景）+ 保存状态（未保存 / 已保存）+ 字数。
- 右：`生成正文 / 停止` · `采纳为正文` · `更多`。
- **`更多` 收进其余动作**：保存正文、取消修改、保存草稿、丢弃草稿、审校、逻辑自检、回写建议 —— **每个按钮的 `onClick` 与整段 `disabled` 表达式逐字保留**，只是换了位置。抽屉式的 `Dialog` 或轻量下拉，用 `ui/Dialog.tsx`（0a 已交付、至今零调用点）。
- **裁定：「对比草稿」不新增开关。** diff 现在是「有草稿就自动显示」（`text.draft && !generating`）；加一个显示开关是新状态，且 spec 那一项措辞模糊（「对比草稿」也可能指正文区已有的自动 diff）。本批保留自动显示，**记为与 spec 的偏离**，供作者裁决。
- 独立审查重点：`disabled` 表达式有没有在搬运中丢项（那会让按钮在生成中可点）；`更多` 打开时是否与抽屉/`Dialog` 的焦点管理冲突。

### T4 · 右栏 12 块 → 四页签

spec §9.9 定的四组，与现有 12 块的映射（**spec 只给了四个名字，没给映射；这是本批的裁定**）：

| 页签 | 收进来的块 | 理由 |
|---|---|---|
| **上下文** | ⑤`ContextPreview` ④`ParagraphLocks` | 都是「写这一场时该看到 / 该守住的东西」 |
| **分支** | ②`AbPanel` ③`BranchPanel` | spec 明写「普通分支 + A/B 并排」 |
| **审校** | ⑥`AuditPanel` ⑧`LogicPanel` ⑦`LogicChain` ⑨`WritebackPanel` | 一致性 + 逻辑自检；**逻辑链与逻辑自检保持并列**（P4c 的设计原话是「两者在写作台并列但绝不混在一起」）；回写建议是对正文的后续处置，同族 |
| **日志** | ①`ChangeList` ⑪本次运行 ⑫`RevisionHistory` ⑩`BatchPanel` | spec 明写「这一场的改动与运行」；批量任务是「运行」的一种 |

- 一屏只展开一组，面板内部各自滚动（`ui/Panel` 已支持）。
- 页签用 `ui/Tabs`（1b-1 已在章节页用起来）。
- 页签选中态**存 `localStorage`**（与专注态同一命名空间）。
- **不改**：A/B 的 409 守卫（先 `getAb` 查旧组 → confirm → 丢弃 → `createAb`）、`adopt` 一次提交、`discardOne` 只删一条、分支回调的**令牌捕获**（`onAdopted` / `onMerged` 先捕获 `sceneToken` + `sceneId` 再比对）、`ParagraphLocks.splitParagraphs` 与 `missing` 口径、`WritebackPanel` 的勾选应用顺序。
- 独立审查重点：块的**挂载顺序**变化有没有影响 effect 的执行时序（尤其 `ParagraphLocks` 与 `WritebackPanel` 各有 `useEffect`）；把面板放进条件渲染的页签后，未选中页签里的 effect 会不会不跑（这会影响数据加载）。

### T5 · 正文排版

- `components/writing/SceneTextView.tsx`：`font-mono text-sm leading-7` → **衬线、17px、行距 1.9、段间距 12px**；**去掉 `resize-y`**（拖动会破坏行宽与 diff 的视觉对齐）；**不做首行缩进**（`text-indent` 在 `textarea` 里只缩第一行，写全角空格会污染 Markdown 与导出 —— spec §9.9 已定，缩进只出现在阅读器与 EPUB 传统模板）。
- 字数从正文区移到工具栏（T3 已留位）。
- **`BranchPanel` 与 `WritebackPanel` 的 `<textarea>` 不改成衬线 17px**：它们不是正文，是辅助输入框。
- 独立审查重点：`SceneTextView` 的 props 与 `onChange` 有没有被动过；去掉 `resize-y` 后有没有别的地方依赖那个可拖高度。

### T6 · 底部状态条（专注态显示）

字数 / 目标字数 / 分支数 / 锁定状态。**数据全部来自已有状态**（`text`、`branch`、`sceneLock`），不新增请求。

### T7 · 15 个 `components/writing/*` 浅色化 + `LogicChainGraph` 用 `chartTokens`

- 15 个文件：`WritingTree` / `SceneTextView` / `GenerationStream` / `DiffPanel` / `ContextPreview` / `RevisionHistory` / `ParagraphLocks` / `AuditPanel` / `LogicPanel` / `BatchPanel` / `WritebackPanel` / `AbPanel` / `BranchPanel` / `LogicChain` / `LogicChainGraph`。
- `LogicChainGraph.tsx` 的 9 个裸十六进制改从 `ui/chartTokens` 取（1b-1 已建好；因果 / 转折 / 揭示三色在那里新增三个槽位）。
- **注意 `cn` 的坑**（1b-1 的发现）：给 `ui/` 组件传与自带类同属性的工具类**能否生效取决于 CSS 顺序**。要定宽就包一层无宽度 div；语义色用 `Button` 的 `primary/secondary/ghost/danger/accent/warn` 变体，不传颜色类。
- **审：diff 级机械核对**（不配审查 agent）：剥 `className` 后逐行 diff、处理函数体 / hooks / 条件 / `api.*` 逐字比对。
- 完成判据：15 个文件 `slate-` / `text-xs` / 裸 hex 全为 0。

### T8 · 摘掉 `LEGACY_DARK` 的 `/write` 并收口

- `App.tsx` 的 `LEGACY_DARK` 删除 `'/write'`（9 → 8）。
- 跑 §5 全部检查；生成走查清单与截图。

## 5. 验证与验收

### 5.1 命令与产物

| 项 | 期望 |
|---|---|
| `pnpm vitest run` | 基线 156 + `writingLayout` 的新用例；**除它之外数字不变** |
| `pnpm run build` | 干净 |
| `pnpm run lint` | 0 error；warning 与基线 32 持平（新增即为回归） |
| `slate-` 残留 | 本批 16 个文件全为 0；全仓 **524 → 276**（清掉 248 处） |
| `LEGACY_DARK` | 9 → 8 |
| 截图 | 写作台在 **1440×900（工作态）与 1280×800（专注态）** 各截：默认、抽屉打开、右栏四个页签逐个展开 |

### 5.2 控制方的 diff 级逻辑不变量核对

**这一节是本批最重要的一步**，因为写作台压着九套机制：

- [ ] **14 个 `useEffect` 的依赖数组逐字未变**（含 `[]` / `[projectId]` / `[batchJob?.id, batchJob?.status]` / `[hasUnsaved]` / `[branchId]`，以及组件内的 `[sceneId]` / `[branch.id]` / `[dialogOpen]` / `[sceneId, body]` / `[sceneId, locks]` / `[suggestion]`）
- [ ] **五套代际令牌**的 `++` 与比对点逐字未变：`treeToken` / `sceneToken` / `logicToken` / `batchToken` / `generateToken`；特别确认 `stop()` **刻意不递增 `generateToken`**、`refreshTree` **刻意不递增 `treeToken`** 这两条保留
- [ ] `loadScene` 的 **6 条 `Promise.allSettled` 顺序**未变；`saveBody → refreshSceneChanges → refreshTree` 的顺序未变；`adopt` 的「先存草稿再采纳」两段式未变；`startBatch` 的 create → resume 未变
- [ ] **面板互斥的 `disabled` 组合逐字未变**：`generate` / `runAudit` / `runLogic` / `runWriteback` 四处
- [ ] `hasUnsaved` 判定（`bodyDraft` / `aiDraft` / `branchDirty`）与 `setProjectGuard` 登记未变
- [ ] **A/B 的 409 守卫**未变；`adopt` 一次提交、`discardOne` 只删一条未变
- [ ] 分支回调的**令牌捕获**（先捕获 `sceneToken` + `sceneId` 再比对）未变
- [ ] `ParagraphLocks.splitParagraphs` 与 `missing` 口径未变
- [ ] `generate` 的 finally（冷却 1 秒、`refreshText` 双回读、`refreshRunRecord` 补拉）未变
- [ ] 9 处 `window.confirm` / `window.prompt` 的调用点与文案未变
- [ ] `setNotice` 的**全部文案与成败判定**未变（如 `runAudit` 的 `llm_status !== 'ok'` / `suppressed` / `issues.length` 四分支）
- [ ] `api.*` 调用序列与次数：逐文件与改造前对照一致

### 5.3 作者手点（浏览器，控制台须 0 ERROR）

**这一批的交互最多，手点是主要验收手段**（本机无 Playwright）。至少走完：

1. 两种模式：1440 下默认工作态、1280 下默认专注态；手动切换后刷新页面仍记住；抽屉打开 → ESC 关闭。
2. 流式生成：生成 → 逐字流入 → 中途停止（**保留已收内容**）→ 生成结束后按钮冷却约 1 秒。
3. 草稿：改草稿 → diff 自动出现 → 保存草稿 → 采纳为正文（**先存草稿再采纳**）→ 丢弃草稿。
4. 正文：改正文 → 保存正文 → 取消修改。
5. 段落锁：勾选若干段 → 采纳时缺段会被拒绝并列出。
6. A/B：建组 → 两版都出 → 采纳一版（另一版同组两条一起清掉）→ 本场已有未处理组时再建应被拒。
7. 分支：新建 → 派生（默认名避让重名）→ 合入主版 → 丢弃。
8. 审校 / 逻辑自检：跑一次、切逻辑阶段、处理问题（四种处理方式）、无模型时的降级警告。
9. 回写建议：生成 → 勾选 → 应用。
10. 批量：开始 → 暂停 → 继续 → 取消 → 重试失败。
11. 修订历史：看某一版全文 → 恢复。
12. 切场景 / 切项目：确认提示、无上一个场景的残留。
13. **右栏四个页签逐个展开**：面板内容与改造前一致；页签之间切换不丢状态；未选中的页签里的数据仍按原时序加载。
14. 1440×900 与 1280×800 两档无横向滚动、无内容裁切。

## 6. 已知中间态与遗留

- **做完即合并**：本批是「批次 1」的最后一段。完成后 0a/0b/1a/1b-1/1b-2 一起合 master —— 那时 13 页里已有 5 页是新语言（仪表盘 / 世界观 / 章节设计 / 写作台 + 外壳）。
- **`LEGACY_DARK` 剩 8 条**：Idea / Architecture / Relations / Timeline / Terms / Pipeline / Studio / Models。
- **`text-xs` 未清理**：本页 108 处随迁移自然消失，批次 4 统一收口。
- **中间态（有意为之）**：`RunTrace` / `Locking` / `Snapshots` 在未迁移页上仍是浅色卡片落在深色页面里。
- **「对比草稿」开关未做**（T3 的裁定），供作者裁决。
- **右栏 12 块的四页签映射是本批的裁定**（spec 只给了四个名字），若作者觉得某一块该换组，改一个数组即可。
