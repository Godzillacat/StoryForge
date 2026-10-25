# 前端重塑 0a/0b · 走查记录

- 日期：2026-10-25
- 计划：`docs/superpowers/plans/2026-10-25-frontend-redesign-0a-0b.md`
- 分支：`worktree-frontend-redesign`（master 未动）
- 环境：后端取主检出（`backend/`，代码未改）+ `STORYFORGE_DATA_DIR=%TEMP%\sf-ui-verify`；前端 `pnpm exec vite --port 5199`（代理到 8756）；数据用 API 建了两个项目：`南滨旧城`、`第二本试验`。

## 1. 自动验证

| 项 | 结果 |
|---|---|
| `pnpm vitest run` | **149 passed**（基线 129；本切片新增 20：对比度 2、palette 1、cn 2、nav 2、persisted 3、projectSelection 4、projectGuard 3、projectMeta 3） |
| `pnpm run build` | 干净 |
| `pnpm run lint` | **0 error**，28 条既有 warning 未增 |
| `grep listProjects` | 只剩 `state/ProjectContext.tsx` 与 `api/client.ts` 两处 |

## 2. 真实数据下的观察（截图 `.cache/mock/v2-dashboard.png` / `v-world.png`）

- 侧栏项目选择器列出两个项目，**当前项目来自外壳**，页面内已无项目下拉（世界观页确认）。
- 「世界观」角标为 `0`、侧栏底部为 `0 卷 · 0 章 · 0 字` —— 计数与摘要走的是 `entries` 与 `report` 两个真实接口。
- 仪表盘的体检单、导出、快照都跟着当前项目取数（截图为空项目，数字为 0）。
- 控制台无报错。

## 3. 必须由作者手点的（本轮未自动化，按仓库惯例 UI 不写自动化测试）

1. 侧栏切到「南滨旧城」→ 13 页数据全部跟着换，不出现「页面停在旧项目」。
2. 侧栏「新建」→ 起名 → 创建 → 自动选中 → **刷新浏览器**仍在刚建的项目。
3. 收起侧栏 → 刷新 → 仍是收起态（`storyforge.sidebarCollapsed`）。
4. 写作台有未保存改动时切项目 → **弹出确认**；点取消则项目不变。
5. `/world?project=<随便一个不存在的 id>` → 停在当前项目并在页面顶部提示「链接里的项目不存在」。
6. 手动清空 `localStorage` 后刷新 → 自动选中第一个项目，不报错。
7. 停掉后端再打开任意页 → 页面显示错误/空态，不白屏（侧栏摘要显示「—」）。

## 4. 已知的中间态（有意为之，不是缺陷）

**外壳已经换新（浅色纸感），页面内容仍是旧的深色样式**，直到批次 1–3 逐页重排。
`App.tsx` 里的 `LEGACY_DARK` 就是为了让未迁移的页面继续用深色底、保持可读；
每迁移完一页删掉一条，批次 3 结束后整个常量连同使用处一起删除。

如果你更希望「外观统一了再合并」，这一片可以先不合入 master —— 等批次 1 把仪表盘 / 世界观 / 章节 / 写作台四页换成新语言，整体观感就立住了。
