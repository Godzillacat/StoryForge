# 前端界面重塑 · 批次 1a 走查记录（仪表盘 + 世界观）

- 日期：2026-10-26
- 分支：`worktree-frontend-redesign`
- 计划：`docs/superpowers/plans/2026-10-25-frontend-redesign-1a.md`
- 本批**不调用模型**，额度未变；**未写入作者真实库**

---

## 1. 做法

| 步骤 | 做法 |
|---|---|
| 数据 | 临时数据目录 `.cache/walkthrough-1a/`（仓库内、`.gitignore` 已覆盖），后端 `STORYFORGE_DATA_DIR=<临时目录>` 启动在 8791 |
| 页面 | **同源托管**：后端直接服务 `frontend/dist`（生产路径，不另起 Vite）。深链 `/world?project=…&entry=…` 验证过 200 |
| 播种 | `.cache/seed-1a.py`：1 项目 / 3 设定（地理 · 规则 · 人物）/ 1 卷 2 章 / 每章 1 场。脚本开头先删掉已有项目，可重复运行 |
| 截图 | 无头 Edge（`--headless=new --virtual-time-budget=9000`），两档视口 1440×900 与 1280×800 |
| 截图位置 | `.cache/shots/*.png` —— **`.cache/` 已 gitignore，截图不入库**，仅本机留档 |

播种后的真实数字：`report` = 0 字 / 1 卷 / 2 章 / 2 场（未写正文，符合预期）。

## 2. 命令与结果

| 项 | 期望 | 实测 |
|---|---|---|
| `pnpm vitest run` | 150 passed **不变** | **150 passed** ✅ |
| `pnpm run build` | 干净 | 干净 ✅ |
| `pnpm run lint` | 0 error；warning 与 0a/0b 的 32 持平 | **0 error / 32 warning**（`set-state-in-effect` 21 · `only-export-components` 6 · `exhaustive-deps` 5）✅ |
| `slate-` 残留（本批 7 个文件） | 全为 0 | 全部 0 ✅ |
| `slate-` 出现次数（全仓） | 999 → 832 | **832** ✅（清掉 167 处） |
| `LEGACY_DARK` | 12 → 10 | **10** ✅ |
| 两档视口 | 无横向滚动、无裁切、无跳动 | 通过 ✅ |

## 3. §5.2 逻辑不变量核对（替代逐任务审查）

用两个脚本做**机械核对**，而不是通读：

1. **剥 `className` 后逐行 diff**（`components/` 五个文件）：剩下的差异只有「元素类型 / import / `type="button"` / 新增包裹元素」。
2. **逻辑区 diff**（`pages/` 两个文件，取 `return (` 之前的一切）＋ **effect 依赖数组与 `api.*` 调用序列对照**：

| 文件 | effect 依赖数组 | api 调用序列 |
|---|---|---|
| `pages/World.tsx` | 4 个，逐字相同 | 10 个，顺序相同 |
| `pages/Dashboard.tsx` | 3 个，逐字相同 | 相同，**多 2 处 `exportUrl`**（见下） |
| `components/Snapshots.tsx` | 无 | 3 个，相同 |
| `components/Locking.tsx` | 无 | 8 个，相同 |
| `components/EntryEditor.tsx` | 无 | 无 |

逐条对照计划 §5.2 的清单：

- [x] `useEffect` 依赖数组 —— `World` 四个、`Dashboard` 三个，全部逐字未变
- [x] 请求顺序与请求数 —— `listEntries` / `listRelations` / `suggestEntries` / `createEntry` / `updateEntry` / `deleteEntry` / `createRelation` / `deleteRelation` / `getExportReport` / `projectCost` / `listSnapshots` / `listChanges` 位置与次数不变
- [x] 代际令牌 —— `dataToken` / `runToken` / `reportToken` 的递增与比对位置不变
- [x] 锁 —— `LockToggle` / `ImpactPanel` 的 `targetType` / `targetId` / `onChanged` / `onMarksChanged` 传参不变
- [x] 草稿 —— `EMPTY_DRAFT` / `draftOf` / `payloadOf` / `characterFieldsOf` 未改；人物八项仍按 `type === 'character'` 守卫
- [x] 深链 —— `deepLinkApplied` 只应用一次、`?project=` 先核对再 `select`、失效提示走 `linkWarning`
- [x] 封面 —— `coverSet` 仍是独立 state；`coverInput.current.value = ''` 仍在 `finally` 里
- [x] 导出模板 —— `epubTemplate` 仍未落库、未进 `localStorage`
- [x] `window.confirm` —— 调用点与文案未变（`Snapshots` 两处、`Locking` 一处）

**唯一的 api 序列差异**是 `Dashboard` 多出 2 处 `api.exportUrl(...)`。它是**拼 URL 的纯函数**，不发请求；对应顶部新增的两个导出直达链接。这两处刻意写成 `<a href>` 而不是带 `onClick` 的按钮，正是为了不在本批引入命令式跳转（第一版用了 `window.location.href`，已改掉）。

## 4. 截图看到的

| 页面 | 结果 |
|---|---|
| 仪表盘 1440 / 1280 | 标题 + 项目名 + 右上两个导出直达链接；KPI 四列衬线数字；左「体检单 + 最近改动」、右「导出与成品报告 + 版本与快照」；项目列表已删、选择器只在侧栏；两档均无横向滚动 |
| 世界观 1440 / 1280 | 列表列 308px，类型标签 + 名称 + 硬度右对齐；详情区选中态为 accent-soft；工具栏两个按钮在右上 |
| 世界观（深链选中人物） | 锁定行只留按钮 + 一句说明；类型/标准写法并排；人物八项单列、逐项可编辑；八项的值全部正确回显（外貌/性格/欲望/恐惧/弧光类型/能力边界…） |

## 5. 走查中发现并当场改掉的两处

1. **人物八项的两列栅格没有意义** —— 查 `app/world_types.py` 的 `CHARACTER_FIELDS`：八项里**七项是多行长文本**，只有「弧光类型」单行。两列栅格实际渲染成七行整宽 + 一个孤立的半宽字段，与单列无异却多一层嵌套。已回退成单列并写明理由（计划 §4.5）。
2. **锁定行读作「锁定 锁定」** —— 原文案是 `<span>锁定</span>` + 一个自己写着「锁定 / 已锁定」的按钮。已改为只留按钮 + 一句「锁上之后 AI 不会改动这一条；你仍然可以编辑。」

## 6. 观察到、但不在本批范围的一处

仪表盘「最近改动」里，一次章纲替换显示为 `项目 · 南滨旧城 · 删除 · 替换章纲：1 卷 / 2 章`。查证 `app/services/chapter_plan_service.py:425`：替换写入被记为 `target_type="project"` + `action="delete"`（替换确实会整批删掉旧结构），是 P4b-1 的既有设计，**不是本批引入的回归**。但动作列写着「删除」容易被读成「项目被删了」。属文案问题，已记入计划 §4.1。

## 7. 请作者手点（本机无 Playwright，以下未自动化）

浏览器里逐条确认，控制台须 0 ERROR：

1. 两页在 1280×800 与 1440×900 下无横向滚动、无内容裁切。
2. 仪表盘：KPI 四个数字与「导出与成品报告」里的数字对得上；右上两个导出链接能下载；模板下拉切到「传统」后右上 EPUB 链接跟着变；封面上传 / 换一张 / 移除照旧；建一个快照后列表立即出现。
3. 仪表盘：「最近改动」里点条目名能跳到 `/world?entry=…` 并选中。
4. 世界观：新建条目 → 保存 → 左侧列表立即出现；改类型到「人物」→ 八项出现且可编辑 → 保存后回读一致；规则类选「硬度」；别名/标签用顿号分隔；删除有确认。
5. 世界观：锁定开关点一下变「🔒 已锁定」、左侧列表出现锁形图标；再点一次解锁（有确认）。
6. 世界观：「看看会影响什么」展开影响面；「只改上层，下游标为待复核」能标上。
7. 切项目：两页都跟着换、无上一个项目的残留（沿用 0a/0b 手点清单第 1 条）。
8. **未迁移页的观感**：去「灵感与解析」「架构推荐」「智能体工作室」，看那里的 `RunTrace` / `Locking` / `SnapshotPanel` 是否只是「浅色卡片落在深色页面」（预期如此，直到批次 2–3 落地），**且文字可读**。
