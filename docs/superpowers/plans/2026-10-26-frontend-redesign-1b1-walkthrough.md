# 前端界面重塑 · 批次 1b-1 走查记录（章节设计）

- 日期：2026-10-27
- 分支：`worktree-frontend-redesign`
- 计划：`docs/superpowers/plans/2026-10-26-frontend-redesign-1b1.md`
- 本批**不调用模型**，额度未变；**未写入作者真实库**

---

## 1. 做法

| 步骤 | 做法 |
|---|---|
| 数据 | 临时数据目录 `.cache/walkthrough-1b1/`（仓库内、已 gitignore），后端 `STORYFORGE_DATA_DIR=<临时目录>` 起在 8793 |
| 页面 | **同源托管**：后端直接服务 `frontend/dist`（生产路径，不另起 Vite） |
| 播种 | 复用 1a 的 `.cache/seed-1a.py`，本批扩了两处：给场景加 `target_words_min/max`，并让第 1 场埋下伏笔「档案背面的字迹」、第 2 场回收它 —— 这样伏笔账本有行、因果链有节点 |
| 截图 | **Edge DevTools 协议驱动**（`.cache/shoot-1b1.mjs`）：Node 24 自带全局 `WebSocket`，直接 `Runtime.evaluate` 点页签、`Page.captureScreenshot` 截图，**不引入任何依赖** |

**为什么不用无头截图一条命令搞定**：章节设计页的 `view` 是**本地状态、不在 URL 里**，没法深链；本机没有 Playwright 也没外网。用 CDP 点页签是唯一能真截到七个视图的办法。脚本只用于走查，不属于产品代码。

播种后的真实数字：1 项目 / 3 设定（地理 · 规则 · 人物）/ 1 卷 2 章 2 场 / 1 条伏笔。

## 2. 命令与结果

| 项 | 期望 | 实测 |
|---|---|---|
| `pnpm vitest run` | 基线 150 + 新增的 `chapterTabs` / `chartTokens` 用例 | **156 passed**（150 + 3 + 3）✅ |
| `pnpm run build` | 干净 | 干净 ✅ |
| `pnpm run lint` | 0 error；warning 与基线 32 持平 | **0 error / 32 warning**（`set-state-in-effect` 21 · `only-export-components` 6 · `exhaustive-deps` 5）✅ |
| `slate-` 残留（本批 13 个文件） | 全为 0 | 全部 0 ✅ |
| `slate-` 出现次数（全仓） | 832 → 524 | **524** ✅（清掉 308 处） |
| 裸十六进制（本批文件） | 0 | 0 ✅ |
| `LEGACY_DARK` | 10 → 9 | **9** ✅ |
| 横向溢出（10 张截图逐一量 `scrollWidth - clientWidth`） | 0 | 全部 **0px** ✅ |

截图：七个视图 × 1440×900，另取结构 / 节奏 / 设定投放 × 1280×800，共 10 张，落在 `.cache/shots/chapters-*.png`（**`.cache/` 已 gitignore，不入库**，仅本机留档）。

## 3. §5.2 逻辑不变量核对（替代逐任务审查）

三类机械核对，全部通过：

**一、`Chapters.tsx`（页面）**

| 项 | 结果 |
|---|---|
| 两个 `useEffect` 依赖数组 | `[]`、`[projectId]`，逐字相同 |
| `api.*` 调用序列 | **32 条，顺序完全一致** |
| `runToken` / `dataRequestRef` / `characterDriftRequestRef` / `projectIdRef` 四处 | 逐字相同 |
| `Promise.allSettled` 块（七接口 + 各自独立报错的分流） | 逐字相同 |
| 八处 `view === 'xxx' &&` 渲染分支 | 全部在位（L501 / 542 / 726 / 734 / 746 / 754 / 765 / 775） |
| 处理函数体 / hooks / 条件 / `window.confirm` | 逐字相同（唯二差异是页签重组新增的两处 `onChange` 与两个派生常量） |

**二、12 个 `components/chapters/*`**

用「抽处理函数体 + hooks 声明 + `if` 条件 + `api.*` 调用」逐字比对：

- `ChapterTree` / `VolumeEditor` / `ChapterEditor` / `SceneEditor`：**逐字相同**
- `ForeshadowLedger` / `CharacterDrift` / `Swimlanes`：剥掉 `className` 后**逐字相同**
- `ChapterPlanDraft` / `ScenePlanDraft`：每个 `onChange` / `onClick` 函数体、`useState`、`if` 条件、两处 `window.confirm` 文案、`void onWrite(...)` 调用**全部逐字相同**；差异只有元素改名与 `className`

计划点名的保护点逐一确认未动：`SceneEditor` 的 `entriesReady` 守卫与 `resolvedNameOf`、`ForeshadowLedger` 的 `statusIsLegacy` / `statusIsDerived` 与「清掉实际回收」、`CharacterDrift` 的 `saved → closeEditor → onReload` 顺序、两份草稿的替换/追加确认文案。

**三、新增的两个纯模块**（本批唯一的新逻辑，全部有 vitest）

- `lib/chapterTabs.ts`：3 条用例 —— 四组顺序固定、**七个视图不重不漏**、每组的默认视图落在该组里、未知键返回 null/空数组。
- `ui/chartTokens.ts`：3 条用例 —— 每个取值都在 `PALETTE` 里（挡裸 hex）、并置的两条序列色不相同、**网格与卷带都比绘图区底深**（用 WCAG 相对亮度算，挡住「浅色底上网格看不见」这个失败模式）。

## 4. 截图看到的

| 视图 | 结果 |
|---|---|
| 结构 | 两层页签（一级四个组，结构无二级故只有一行）；308px 树在 `Panel` 里；右上「AI 排卷章」；未选中时的空态提示 |
| 节奏 | 目标字数柱、冲突与对话**墨绿实线**、钩子**沙色虚线**、卷带名与章号、淡网格 —— 全部可读 |
| 伏笔 | 7 列表格（表头走 `Th`、行高 44px）；统计行与筛选 chip；**状态下拉是窄的、没有撑满整行**；底部口径说明 |
| 因果链 | **两层页签按设计工作**（一级「视图」+ 二级四项）；未跑逻辑自检的 warn 提示条；每章一行、场景节点显示目标/转折 |
| 设定投放 | 两条序列色可区分（绿柱 / 琥珀线）；未写章的虚线占位块与旋转的「未写」 |
| 性格漂移 / 剧情线 | 表格与泳道换到新令牌，无溢出 |
| 1280×800 三张 | 结构 / 节奏 / 设定投放均无横向溢出、无裁切 |

## 5. 走查中发现并当场修掉的三处

### 5.1 `cn` 只拼接、不消解冲突 —— 本批最要紧的发现

`src/ui/cn.ts` 是纯 `filter(Boolean).join(' ')`，**不做 Tailwind 冲突消解**。于是「给 `ui/` 组件传一个和它自带类同属性的工具类」能否生效，**取决于 CSS 生成顺序**，而不是类名在字符串里的先后。实测（读构建产物的字节位置）：

| 覆盖 | 结果 |
|---|---|
| `Input` 传 `w-40` | 生效 ✅ |
| `Select` 传 `w-auto` | **死类** ❌（`.w-full` 排在 `.w-auto` 之后） |
| `Textarea` 传 `min-h-[80px]` / `[96px]` | 生效 ✅ |
| `Textarea` 传 `min-h-[56px]` | **死类** ❌ |
| `Button` 传 `text-warn` | 生效 ✅ |
| `Button` 传 `text-accent-ink` | **死类** ❌ |

「有时生效、有时不生效」比「一律不生效」更危险 —— 后者一眼看得出来，前者会让人以为这套机制可用。**修法分两种，都不依赖 CSS 顺序**：

1. **要定宽就包一层 div**（`EntryEditor` 既有写法）。改掉了 `ForeshadowLedger` 那处 `w-auto`：把 `Select` 包进无宽度 div，即「按内容宽」。
2. **给 `Button` 加 `accent` 与 `warn` 两个变体**（`ui/Button.tsx`）。原先 6 个调用点靠 `className="text-accent-ink"` / `"text-warn"` 上色，其中 `text-accent-ink` 是死类（按钮实际显示成 muted 灰），`text-warn` 只是侥幸生效。改由组件自己拥有语义色，调用方只选变体 —— **全仓再没有一处给 `Button` 传颜色类**。

顺带把两处死类 `min-h-[56px]` 去掉（接受组件默认的 76px，卷/章摘要输入框略高 20px）。

### 5.2 人物八项那类「按 spec 字面写、实际无意义」的问题在本批没有再犯

`chartTokens` 最初计划里写的是「颜色 + 轴几何」一起收敛。实施时核对发现**两张图的几何确实不同**（`RhythmCurve` 列宽 44、`SettingLoadCurve` 用 `lib/settingLoad.ts` 的 `COL_W = 56`），强行统一会为了「单点定义」而写错。**已改为只收敛颜色**，几何留在各自文件里（计划 §3.2 已同步）。

### 5.3 节奏图的色觉障碍隐患顺带消掉

原文件顶部的注释自己写着「emerald 与 amber 的 CVD 差落在 6–8 警告带」。四行小图各有文字标签、颜色不承担区分职责，所以收敛成「墨绿实线 + 沙色虚线」两种 —— 隐患没了，画面也更安静。

## 6. 请作者手点（本机无 Playwright，交互未自动化）

控制台须 0 ERROR：

1. 七个视图**逐个点开**都渲染正确，一级组与二级项的高亮一致（「视图」组下点四项时，一级仍停在「视图」）。
2. 章节树：选卷 / 章 / 场景，右侧编辑器跟着换；「新建卷」、每行的 ↑ ↓ +章 / +场景、删除（有确认）。
3. 场景卡：人物 chip 增删、地点选择、伏笔埋设/回收选择；**条目未加载完时保存不会把人物/地点清空**。
4. 节奏图与设定投放图：配色是新的；点章能跳回结构设计并选中该章。
5. 伏笔账本：行内改状态、旧值「点此更新」按钮、清掉实际回收、五个筛选。
6. 性格漂移：点格子改状态、保存、删除。
7. 因果链：断点标记、锁定标记（现在是锁形图标而非 🔒）、点节点跳回结构设计并选中该场。
8. 「AI 排卷章」与「AI 写场景卡」两个按钮（后者要先选中一章）—— 本批只改了外观，行为应完全照旧。
9. 1440×900 与 1280×800 两档无横向滚动。
10. **未迁移页的观感**：去「灵感与解析」「架构推荐」「关系网」「时间线」「术语表」「写作台」「管线」「工作室」「模型与费用」，看那里的共享组件是否只是「浅色卡片落在深色页面」（预期如此，直到批次 2–3 落地），**且文字可读**。
