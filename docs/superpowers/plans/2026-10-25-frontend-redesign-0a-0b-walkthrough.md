# 前端重塑 0a/0b · 走查记录

- 日期：2026-10-25
- 计划：`docs/superpowers/plans/2026-10-25-frontend-redesign-0a-0b.md`
- 分支：`worktree-frontend-redesign`（master 未动）
- 环境：后端取主检出（`backend/`，代码未改）+ `STORYFORGE_DATA_DIR=%TEMP%\sf-ui-verify`；前端 `pnpm exec vite --port 5199`（代理到 8756）；数据用 API 建了两个项目：`南滨旧城`、`第二本试验`。

## 1. 自动验证

| 项 | 结果 |
|---|---|
| `pnpm vitest run` | **150 passed**（基线 129；本切片新增 21：对比度 2、palette 1、cn 2、nav 2、persisted 3、projectSelection 4、projectGuard 3、projectMeta 3、Dialog 焦点 1） |
| `pnpm run build` | 干净 |
| `pnpm run lint` | **0 error**（warning 28 → 32，全部是 React Compiler 对 `setState-in-effect` 的建议，与本切片前同类） |
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

## 5. 整支复查与修复波（2026-10-25 晚）

独立 reviewer 通看 `master...HEAD` 的 11 个提交，提 1 Critical、6 Important、4 Minor。**Critical 与 Important 全部修掉，Minor 3 条修复、1 条记账**：

| 级别 | 问题 | 修法 |
|---|---|---|
| Critical | `Dialog` 的 ESC effect 依赖内联 `onClose`，每次父组件重渲染都重装并 `focus()`，**把输入框焦点抢走** —— 新建项目对话框每敲一个字就失焦 | `onClose` 存进 ref；effect 只在 `open` 变化时跑；焦点只在「不在对话框内」时才接管。**补了 `Dialog.test.tsx`（RTL），先红后绿** |
| Important | 新建项目不走 `runProjectGuard`，从侧栏新建会静默丢掉写作台未保存的正文 | `create()` 先过守卫 |
| Important | 侧栏角标与摘要用了 `text-faint`（3.2:1），违反 spec §6.1 | 改 `text-muted`（4.8:1） |
| Important | 世界观深链 effect 依赖 `projectId`，在 `?project=B` 页里切到 C 会被拽回 B | 用 `deepLinkApplied` 保证只认一次 |
| Important | 「链接里的项目不存在」的提示被随后的 `setNotice('')` 冲掉 | 单独一条 `linkWarning`，不随项目切换清空 |
| Important | `useProjectMeta` 的缓存永不失效、失败也缓存 → 整会话停在首次数值 | 30 秒 TTL；失败结果不缓存；切到未缓存项目先清空为「—」 |
| Important | `ProjectContext.error` 没人读，后端挂了会被显示成「还没有项目」 | 侧栏显示「读取项目列表失败 + 重试」；仪表盘区分「失败」与「真的没有项目」 |
| Important | 世界观 / 关系网 / 时间线的条目加载没有代际令牌，迟到响应覆盖新项目 | 三页各加 `dataToken` |
| Minor | `LEGACY_DARK` 用精确路径匹配，`/world/` 漏网 | 统一去掉尾斜杠再比 |
| Minor | `refresh()` 无条件从 localStorage 推导当前项目，写入失败会换掉作者的选择 | 以内存中的选择为准，失效才回落 |
| Minor（记） | `projectGuard` 只有一个槽位，多页登记会互相覆盖 | 批次 1 若第二页也要登记，再换成按 key 的注册表 |

复查另有三条「需要作者拍板」，未动：中间态是否现在合 master、清空 localStorage 后默认落到哪一本、仪表盘是否保留自己的项目列表（与「入口只有一处」相抵）。
