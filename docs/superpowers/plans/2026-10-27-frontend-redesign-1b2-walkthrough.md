# 前端界面重塑 · 批次 1b-2 走查记录（写作台）

- 日期：2026-10-31
- 分支：`worktree-frontend-redesign`（承接 0a/0b / 1a / 1b-1）
- 计划：`docs/superpowers/plans/2026-10-27-frontend-redesign-1b2.md`
- 设计：`docs/superpowers/specs/2026-10-25-frontend-redesign-design.md`（§5、§8.2、§9.9、§11）
- 本批**不调用模型**，额度未变；**未写入作者真实库**

---

## 1. 做法

| 步骤 | 做法 |
|---|---|
| 数据 | 临时数据目录 `.cache/walkthrough-1b2/`（仓库内、已 gitignore），沿用 10-27 播种的 1 项目 / 1 卷 2 章 2 场；后端 `STORYFORGE_DATA_DIR=<临时目录> uv run uvicorn app.main:app --port 8795` |
| 页面 | **同源托管**：后端直接服务 `frontend/dist`（生产路径，不另起 Vite） |
| 截图 | **Edge DevTools 协议驱动**（`.cache/shoot-1b2.mjs`）：Node 24 自带全局 `WebSocket`，直接 `Runtime.evaluate` 点按钮 / 切页签、`Page.captureScreenshot` 截图，**不引入任何依赖** |
| 机械核对 | `.cache/verify-1b2.py`（逻辑要素对照基线 `3a8a1cb`）、`.cache/t7-style-diff.py`（T7 剥 `className` 逐行 diff）—— 只用于走查，不属于产品代码 |

截图共 **11 张**，落在 `.cache/shots/write-*.png`（`.cache/` 已 gitignore，不入库）。

## 2. 命令与结果

| 项 | 期望 | 实测 |
|---|---|---|
| `pnpm vitest run` | 基线 156 + `writingLayout`（7 例）与 `chartTokens` 新增用例 | **164 passed / 25 files** ✅（+8） |
| `pnpm run build` | 干净 | 干净 ✅（仅 chunk > 500 kB 的既有提示） |
| `pnpm run lint` | 0 error；warning 与基线 32 持平 | **0 error / 32 warning** ✅ |
| `slate-` / `text-xs`（本批 16 个文件） | 全为 0 | 全部 **0** ✅ |
| `slate-` 出现次数（全仓） | 524 → 276 | **276** ✅（清掉 248 处） |
| `LEGACY_DARK` | 9 → 8 | **8** ✅（剩灵感 / 架构 / 关系网 / 时间线 / 术语表 / 管线 / 工作室 / 模型与费用） |
| 横向溢出（11 张截图逐一量 `scrollWidth - clientWidth`） | 0 | 全部 **0px** ✅ |
| 后端 / 数据库 / 额度 | 零改动 | 零改动，未调用模型 ✅ |

## 3. §5.2 逻辑不变量核对

写作台压着九套机制，逐项机械核对如下（基线 = 1b-1 收口的 `3a8a1cb`）：

| 项 | 结果 |
|---|---|
| **五套代际令牌**相关行（`treeToken` 10 / `sceneToken` 63 / `logicToken` 10 / `batchToken` 13 / `generateToken` 15 行） | 逐字一致 ✅；`stop()` 不递增 `generateToken`、`refreshTree` 不递增 `treeToken` 两条保留 |
| **原有 5 个 `useEffect` 依赖数组** | 逐字一致 ✅（`[]` / `[projectId]` / `[batchJob?.id, batchJob?.status]` / `[hasUnsaved]` 等）；新增 3 个：`[storedLayoutMode]`（宽度监听，存过偏好就不挂）、`[drawerOpen]`（ESC）、`[moreOpen]`（外点 + ESC），均在关闭时卸载监听 |
| **`api.*` 调用序列** | **25 条，顺序完全一致** ✅（`loadScene` 的 `Promise.allSettled` 六接口顺序同此） |
| **`setNotice` 调用** | **59 处，逐字一致** ✅ |
| **`window.confirm` / `prompt`** | 页面 7 处逐字一致；组件侧 AbPanel 4、BranchPanel 3 一致 ✅ |
| **`disabled` 表达式** | **16 条集合完全一致** ✅（顺序随工具栏重组变化；四处面板互斥组合 —— 生成 / 审校 / 逻辑 / 回写 —— 全部在位） |
| **`hasUnsaved` 判定** | 原 5 行逐字一致 ✅；新增 1 行是工具栏「已保存 / 有未保存的改动」显示 |
| **`projectGuard` 登记** | 4 行逐字一致 ✅ |
| **分支令牌捕获 / 合并回调** | 7 行逐字一致 ✅；`const token = sceneToken.current` 与 `sceneToken.current === token` 共 48 行（含 `Promise.allSettled`）逐字一致 |
| **`useState` 声明** | 40 → 46：新增 6 个全是布局状态（`storedLayoutMode` / `width` / `rightCollapsed` / `drawerOpen` / `asideTab` / `moreOpen`），原有 40 个逐字一致 ✅ |
| **15 个 `components/writing/*`** | `useEffect` / `confirm` / `api` / `setNotice` / `useState` / `disabled` 全部逐字一致 ✅ |
| **T7 纯样式提交** | 剥 `className` 后残差只有：`button→Button`、`input→Input`、`textarea→Textarea` 的标签与 `variant`/`size`、颜色常量改令牌、`LogicChainGraph` 的裸 hex 换 `chartTokens`；`ParagraphLocks` 剥类名后**逐行完全一致** ✅ |
| **T5 `SceneTextView`** | 只有排版类名；额外的「正文 N 字」从组件标题移到工具栏（T5 的既定动作），`value` / `onChange` / `disabled` / `rows` / `placeholder` 未动 ✅ |

## 4. 截图看到的

| 截图 | 结果 |
|---|---|
| `write-work-1440x900` | 1440 默认工作态：壳 236 / 树 236 / 正文 / 右栏 336；工具栏一行（面包屑 · 已保存 · 字数 \| 生成正文 · 采纳为正文 · 更多） |
| `write-aside-上下文 / 分支 / 审校 / 日志` | 四页签逐个展开，内容组与计划 §T4 的映射一致；页签切换不丢状态 |
| `write-more-1440x900` | 「更多」下拉：审校 / 逻辑自检 / 回写建议 / 保存正文 / 取消修改 / 保存草稿 / 丢弃草稿；禁用项正确灰显 |
| `write-work-collapsed-1440x900` | 工作态收起右栏 → 44px 竖条 + 展开按钮，正文获得整列宽度 |
| `write-focus-1440x900` | 手动切专注态：左树变「章节」抽屉入口，正文 620 居中，右栏浮层不遮挡稿子，底部状态条出现 |
| `write-focus-collapsed-1440x900` | 专注态收起面板：浮层与 336px 留白一起还回去，真正「正文独占」 |
| `write-focus-1280x800` | 1280 默认即专注态（工作态下限 1440）；正文 ≥560，无横向滚动 |
| `write-drawer-1280x800` | 抽屉 236px + 遮罩，ESC / 点遮罩关闭 |

## 5. 本次收口发现并修掉的四处

1. **`aside: 'none'` 只改了栅格、没有真的收起。** 原实现只把列模板改成单列，`<aside>` 仍作为第二个栅格项渲染到下一行。改为 `shape.aside === 'none'` 时不渲染 aside 内容。
2. **页面内边距丢失。** 走查修复让 `/write` 不吃外壳 `p-6`，注释写着「自带 px-4」，但根节点并没有内边距 —— 当前实际是内容贴边。已在页面根节点加 `p-4`，宽度验算（1440 − 236 − 32 − 236 − 336 − 32 = **568**）与注释一致。
3. **专注态没有收起面板的入口。** 收起开关原先只在工作态显示；专注态一旦收起就回不来。改为两种模式都显示「收起 / 展开右栏」。
4. **`writingLayout.ts` 的预算注释沿用了 spec 漏算内边距的 600。** 已改为 568 并注明：spec 的 600–680 目标区要右栏缩到 288 才够，属作者待裁决项。

修好后重跑：164 测试全绿、构建干净、11 张截图横向溢出均 0。

## 6. 请作者手点（本机无 Playwright，交互未自动化）

控制台须 0 ERROR。截图只证明布局与配色，以下行为只能手点：

1. 两种模式：1440 下工作态、1280 下专注态；手动切换后刷新仍记住；抽屉打开 → ESC 关闭。
2. 右栏：四页签逐个展开；切换页签不打断在途请求（生成 / 审校 / 批量轮询）；收起后能再展开。
3. 流式生成：逐字流入 → 中途停止（保留已收内容）→ 结束后按钮冷却约 1 秒。
4. 草稿：改草稿 → diff 出现 → 保存草稿 → 采纳为正文（先存草稿再采纳）→ 丢弃草稿。
5. 正文：改正文 → 保存正文 → 取消修改。
6. 段落锁：勾选若干段 → 采纳时缺段被拒绝并列出。
7. A/B：建组 → 两版都出 → 采纳一版（同组两条一起清掉）→ 本场已有未处理组时再建被拒。
8. 分支：新建 → 派生（默认名避让重名）→ 合入主版 → 丢弃。
9. 审校 / 逻辑自检：跑一次、切逻辑阶段、四种处理方式、无模型时的降级警告。
10. 回写建议：生成 → 勾选 → 应用。
11. 批量：开始 → 暂停 → 继续 → 取消 → 重试失败。
12. 修订历史：看某一版全文 → 恢复。
13. 切场景 / 切项目：确认提示；切换后在途响应不串台。
14. 1440×900 与 1280×800 两档无横向滚动、无内容裁切。

## 7. 遗留与待裁决

- **正文列 568px 低于 spec §8.2 的 600–680 目标区**（高于 §11 验收的 560 下限）。要达 600 需把右栏 336 缩到 288；本批不擅自改，等作者裁决。
- **「对比草稿」开关未做**（计划 §T3 的裁定）：diff 仍是「有草稿就自动显示」，与 spec §9.9 的措辞偏离，已记录在计划 T3。
- **`text-xs` 未在本批收口**：本批 16 个文件已为 0，全仓剩 76 处，随批次 2–4 迁移自然消失，批次 4 统一收尾。
- **`LEGACY_DARK` 剩 8 页**：批次 2（5 页）与批次 3（4 页）做完后整体删除。
- **中间态（有意为之）**：`RunTrace` / `Snapshots` / `Locking` 在未迁移页上仍是浅色卡片落在深色页面里。
- **分支尚未合并 master**：本批完成后按计划把 0a/0b + 1a + 1b-1 + 1b-2 一起合入。
