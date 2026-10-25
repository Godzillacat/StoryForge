# StoryForge 前端重塑（批次 0a · 0b）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立全站唯一的视觉语言（令牌 + `src/ui/` 组件 + 新外壳），并把「当前项目」从 13 个页面各自持有改为外壳统一持有。

**Architecture:** 先做纯样式地基（0a：令牌、对比度守卫、基础组件、图标、侧栏导航），再做唯一动数据流的一批（0b：`ProjectProvider` + `pickProjectId` 纯函数 + 侧栏选择器 + 13 页改读 context）。两批各自可独立交付、独立回退。

**Tech Stack:** React 19 + TypeScript 6 + Vite 7 + Tailwind 3.4 + vitest 5（jsdom）；不新增任何 npm 依赖。

**Spec:** `docs/superpowers/specs/2026-10-25-frontend-redesign-design.md`

## Global Constraints

- 不新增 npm 依赖（`package.json` 的 `dependencies` 与 `devDependencies` 都不动）。
- 不引 UI 组件库、不引图标库；图标手写 SVG。
- UI 不写自动化测试；只有纯逻辑（对比度、`cn`、导航数据、持久化读取、项目选择）写 vitest。
- 后端零改动：不碰 `backend/`、不碰数据库、不改接口。
- 只改 JSX 结构与 `className`；不动 `useEffect` 依赖数组、请求顺序、代际令牌、锁判定。
- 颜色值只能取自 `PALETTE`（`src/ui/palette.ts`），页面里不得出现裸十六进制颜色。
- 注释、界面文案用中文；标识符用英文。
- 每个任务结束必须：`pnpm -C frontend exec vitest run` 全绿、`pnpm -C frontend run build` 干净。
- 提交信息用 `feat:` / `refactor:` / `test:` + 中文描述。

## Review Focus

1. **首次启动没有任何项目**：13 个页面必须显示空态，不能白屏、不能抛错。→ Task 5 的 `pickProjectId` 空列表用例 + Task 7–9 每页的「无项目」检查项。
2. **切项目时在途请求把旧数据写进新项目**：现有各页都有代际令牌（`token` / `reportToken`），迁移时**不得删除**。→ Task 7–9 的迁移规则第 4 条。
3. **`localStorage` 被清空、写坏、或存了已删除项目的 id**：必须静默回落到第一个项目，且不崩。→ Task 4 的 `readFlag` 用例 + Task 5 的 `pickProjectId` 过期 id 用例。
4. **深链 `?project=<id>` 指向不存在/已删除项目**：回落到第一个项目，并在页面提示，不静默跳到错误项目。→ Task 5 的 override 过期用例 + Task 7 世界观页的深链处理。
5. **侧栏计数与摘要请求失败**（无该项目 / 500 / 超时）：侧栏显示 `—`，页面照常可用，不弹错误。→ Task 10 的失败分支。

---

## 文件结构

```
frontend/src/
├── lib/
│   ├── contrast.ts        对比度计算（纯函数）
│   ├── nav.ts             导航分组数据 + 扁平化
│   ├── persisted.ts       localStorage 读写（带守卫）
│   └── projectSelection.ts 选哪个项目（纯函数，含回落规则）
├── state/
│   ├── ProjectContext.tsx Provider + useCurrentProject
│   └── useProjectMeta.ts  侧栏计数与摘要（带缓存与失败降级）
├── ui/
│   ├── palette.ts         颜色常量（唯一真相）
│   ├── cn.ts              类名拼接
│   ├── Button.tsx / Field.tsx / Card.tsx / Tabs.tsx / Table.tsx
│   ├── Badge.tsx / EmptyState.tsx / Skeleton.tsx / Toast.tsx / Dialog.tsx
│   └── icons.tsx          手写图标
└── components/ProjectSwitcher.tsx
```

---

### Task 1: 色彩令牌与对比度守卫

**Files:**
- Create: `frontend/src/lib/contrast.ts`、`frontend/src/lib/contrast.test.ts`
- Create: `frontend/src/ui/palette.ts`
- Modify: `frontend/tailwind.config.js`、`frontend/src/index.css`

**Interfaces:**
- Produces: `relativeLuminance(hex: string): number`、`contrastRatio(a: string, b: string): number`、`PALETTE: Record<'paper'|'surface'|'sunken'|'ink'|'ink2'|'muted'|'faint'|'line'|'lineStrong'|'accent'|'accentInk'|'accentSoft'|'warn'|'warnSoft'|'danger', string>`

- [ ] **Step 1: 写失败测试**（`frontend/src/lib/contrast.test.ts`）

```ts
import { describe, expect, it } from 'vitest'
import { contrastRatio } from './contrast'
import { PALETTE } from '../ui/palette'

describe('对比度', () => {
  it('纸色底上的文字达到 AA', () => {
    expect(contrastRatio(PALETTE.ink, PALETTE.paper)).toBeGreaterThanOrEqual(7)
    expect(contrastRatio(PALETTE.ink2, PALETTE.paper)).toBeGreaterThanOrEqual(4.5)
    expect(contrastRatio(PALETTE.muted, PALETTE.paper)).toBeGreaterThanOrEqual(4.5)
    expect(contrastRatio(PALETTE.accent, PALETTE.paper)).toBeGreaterThanOrEqual(4.5)
    expect(contrastRatio(PALETTE.warn, PALETTE.paper)).toBeGreaterThanOrEqual(4.5)
    expect(contrastRatio(PALETTE.danger, PALETTE.paper)).toBeGreaterThanOrEqual(4.5)
  })
  it('主按钮白字在墨绿上达到 AA', () => {
    expect(contrastRatio('#FFFFFF', PALETTE.accent)).toBeGreaterThanOrEqual(4.5)
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pnpm -C frontend exec vitest run src/lib/contrast.test.ts`
Expected: FAIL — `Failed to resolve import "./contrast"`

- [ ] **Step 3: 实现** `contrast.ts`（sRGB 相对亮度 + `(L1+0.05)/(L2+0.05)`）与 `palette.ts`（值照抄 spec §6.1：`paper #F4F1EA`、`surface #FBF9F5`、`sunken #ECE7DC`、`ink #23201C`、`ink2 #4E4941`、`muted #6E6A61`、`faint #8D8679`、`line #E3DDD0`、`lineStrong #CFC7B6`、`accent #2F5D4E`、`accentInk #24483C`、`accentSoft #E6EFE9`、`warn #8A5C16`、`warnSoft #F6ECD8`、`danger #9B3B32`）

- [ ] **Step 4: 跑测试确认通过**

Run: `pnpm -C frontend exec vitest run src/lib/contrast.test.ts`
Expected: PASS（2 例）

- [ ] **Step 5: 接上 Tailwind 与全局样式**

`tailwind.config.js` 的 `theme.extend`：`colors` 用上面的令牌名（`paper`、`ink`、`ink-2`、`muted`、`faint`、`line`、`line-strong`、`accent`、`accent-ink`、`accent-soft`、`warn`、`warn-soft`、`danger`），`fontFamily.ui` / `fontFamily.serif` 照 spec §6.2，`borderRadius`（`tag 4px`、`control 6px`、`card 8px`、`overlay 10px`），`boxShadow.overlay` 照 spec §6.3。
`index.css`：`body` 改为 `@apply bg-paper text-ink font-ui antialiased`；加 `:focus-visible { outline: none; box-shadow: 0 0 0 3px var(--accent-soft) }` 的基底（用 CSS 变量），加 `@media (prefers-reduced-motion: reduce) { * { animation-duration: 0ms !important; transition-duration: 0ms !important } }`。

- [ ] **Step 6: 构建**

Run: `pnpm -C frontend run build`
Expected: 干净退出，无 TS 错误

- [ ] **Step 7: 提交**

```bash
git add frontend/tailwind.config.js frontend/src/index.css frontend/src/lib/contrast.ts frontend/src/lib/contrast.test.ts frontend/src/ui/palette.ts
git commit -m "feat(frontend): 设计令牌与对比度守卫"
```

---

### Task 2: `cn` 与基础控件

**Files:**
- Create: `frontend/src/ui/cn.ts`、`frontend/src/ui/cn.test.ts`
- Create: `frontend/src/ui/Button.tsx`、`Field.tsx`、`Card.tsx`、`Tabs.tsx`、`Table.tsx`、`Badge.tsx`、`EmptyState.tsx`、`Skeleton.tsx`、`Toast.tsx`、`Dialog.tsx`

**Interfaces:**
- Produces: `cn(...parts: Array<string | false | null | undefined>): string`
- Produces: `Button({ variant?: 'primary'|'secondary'|'ghost'|'danger', size?: 'sm'|'md', ...buttonProps })`、`IconButton({ label: string, ...buttonProps })`
- Produces: `Field({ label, children })`、`Input` / `Textarea` / `Select`（透传原生 props，`Select` 的 `options: { value: string; label: string }[]`）
- Produces: `Card({ title?, actions?, children })` 与 `Panel({ title?, children })`（**都从 `Card.tsx` 导出**，Panel 只是加了一层 `overflow-hidden` 的容器）
- Produces: `Tabs({ items: { key: string; label: string; count?: number }[], active: string, onChange: (key: string) => void })`
- Produces: `Table` / `Th` / `Td`（`Th` 接受 `align?: 'left'|'right'`）
- Produces: `Badge({ tone?: 'plain'|'accent'|'warn', children })`、`EmptyState({ title, hint?, action? })`、`Skeleton({ lines?: number })`
- Produces: `Toast({ tone: 'ok'|'warn'|'danger', message, onDismiss })`、`Dialog({ open, title, onClose, children, footer? })`（**本轮只建组件，不接线**）

- [ ] **Step 1: 写失败测试**（`cn.test.ts`）

```ts
import { expect, it } from 'vitest'
import { cn } from './cn'

it('拼接并丢弃假值', () => {
  expect(cn('a', false, undefined, 'b', null)).toBe('a b')
})
```

- [ ] **Step 2: 跑测试确认失败** → `pnpm -C frontend exec vitest run src/ui/cn.test.ts`，Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 `cn` 与全部组件**，只允许用 `PALETTE` 对应的 Tailwind 令牌类（如 `bg-paper`、`text-ink-2`、`border-line`、`bg-accent`）；尺寸与圆角取 spec §6.3；控件高度 `sm 26px / md 32px`，输入框 `32px`，表行 `44px`。

- [ ] **Step 4: 跑测试 + 构建** → `pnpm -C frontend exec vitest run`（全绿）、`pnpm -C frontend run build`（干净）

- [ ] **Step 5: 提交**

```bash
git add frontend/src/ui
git commit -m "feat(frontend): 基础控件层"
```

---

### Task 3: 手写图标

**Files:**
- Create: `frontend/src/ui/icons.tsx`

**Interfaces:**
- Produces: `Icon({ name: IconName, size?: number, className?: string })`，`IconName` 为下列字符串字面量联合：`dashboard | idea | architecture | world | relations | timeline | terms | chapters | write | read | pipeline | studio | models | chevron | close | lock | plus | search | more`

- [ ] **Step 1: 实现 19 个 20×20 SVG**（`fill="none"`、`stroke="currentColor"`、`strokeWidth={1.5}`、`strokeLinecap="round"`），全部走 `Icon` 一个出口，不导出裸 SVG

- [ ] **Step 2: 构建** → `pnpm -C frontend run build`，Expected: 干净

- [ ] **Step 3: 提交**

```bash
git add frontend/src/ui/icons.tsx
git commit -m "feat(frontend): 手写图标集"
```

---

### Task 4: 导航数据、持久化读取、外壳骨架

**Files:**
- Create: `frontend/src/lib/nav.ts`、`frontend/src/lib/nav.test.ts`
- Create: `frontend/src/lib/persisted.ts`、`frontend/src/lib/persisted.test.ts`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Produces: `NAV_GROUPS: NavGroup[]`（`{ title: string; items: NavItem[] }`，`NavItem = { to: string; label: string; icon: IconName; badge?: 'entries' }`）、`flatNavItems(groups?: NavGroup[]): NavItem[]`
- Produces: `readFlag(key: string, fallback: boolean): boolean`、`writeFlag(key: string, value: boolean): void`、`readString(key: string): string | null`、`writeString(key: string, value: string): void`
- Produces: 常量 `KEY_CURRENT_PROJECT = 'storyforge.currentProject'`、`KEY_SIDEBAR_COLLAPSED = 'storyforge.sidebarCollapsed'`

- [ ] **Step 1: 写失败测试**（`nav.test.ts`）

```ts
import { expect, it } from 'vitest'
import { NAV_GROUPS, flatNavItems } from './nav'

it('十三条入口、分组顺序固定、路径唯一', () => {
  expect(flatNavItems()).toHaveLength(13)
  expect(NAV_GROUPS.map((g) => g.title)).toEqual(['总览', '构思', '设定', '写作', '阅读与发行', '系统'])
  const paths = flatNavItems().map((i) => i.to)
  expect(new Set(paths).size).toBe(13)
  expect(paths.every((p) => p.startsWith('/'))).toBe(true)
})
```

- [ ] **Step 2: 写失败测试**（`persisted.test.ts`）

```ts
import { beforeEach, expect, it } from 'vitest'
import { KEY_SIDEBAR_COLLAPSED, readFlag, writeFlag } from './persisted'

beforeEach(() => localStorage.clear())

it('未存过时用默认值', () => {
  expect(readFlag(KEY_SIDEBAR_COLLAPSED, false)).toBe(false)
})
it('写坏的值回落默认值', () => {
  localStorage.setItem(KEY_SIDEBAR_COLLAPSED, '不是布尔')
  expect(readFlag(KEY_SIDEBAR_COLLAPSED, true)).toBe(true)
})
it('能读回写入的值', () => {
  writeFlag(KEY_SIDEBAR_COLLAPSED, true)
  expect(readFlag(KEY_SIDEBAR_COLLAPSED, false)).toBe(true)
})
```

- [ ] **Step 3: 跑测试确认两条都失败** → `pnpm -C frontend exec vitest run src/lib`，Expected: FAIL（模块不存在）

- [ ] **Step 4: 实现 `nav.ts` / `persisted.ts`**（`persisted` 全部 `try/catch`，`localStorage` 不可用时静默降级）

- [ ] **Step 5: 跑测试确认通过** → 同上命令，Expected: PASS

- [ ] **Step 6: 重写 `App.tsx` 外壳**

侧栏 236px（`bg-surface border-r border-line`）：品牌行 → 项目选择器占位（Task 6 填）→ 六个分组（组标题 11px/字距 .12em/`text-muted`）→ 底部摘要占位（Task 10 填）→ 折叠按钮。折叠态 56px 只留图标（`title` 与 `aria-label` 带名称）。`main` 保持 `flex-1 min-h-0 overflow-auto`，**本轮保留 `p-6` 与 `/read` 例外**（页面重排在各页批次做）。路由表保持不变。

- [ ] **Step 7: 构建 + 全量测试** → `pnpm -C frontend run build`、`pnpm -C frontend exec vitest run`

- [ ] **Step 8: 提交**

```bash
git add frontend/src/App.tsx frontend/src/lib/nav.ts frontend/src/lib/nav.test.ts frontend/src/lib/persisted.ts frontend/src/lib/persisted.test.ts
git commit -m "feat(frontend): 分组导航与可折叠外壳"
```

---

### Task 5: 当前项目状态（纯函数 + Provider）

**Files:**
- Create: `frontend/src/lib/projectSelection.ts`、`frontend/src/lib/projectSelection.test.ts`
- Create: `frontend/src/state/ProjectContext.tsx`
- Modify: `frontend/src/main.tsx`（包一层 `ProjectProvider`）

**Interfaces:**
- Produces: `pickProjectId(stored: string | null, list: Array<{ id: string }>, override?: string | null): string`
- Produces: `useCurrentProject(): { projects: Project[]; projectId: string; project: Project | null; loading: boolean; error: string; select(id: string): void; refresh(): Promise<void> }`
- Produces: `ProjectProvider({ children })`

- [ ] **Step 1: 写失败测试**（`projectSelection.test.ts`）

```ts
import { expect, it } from 'vitest'
import { pickProjectId } from './projectSelection'

const list = [{ id: 'a' }, { id: 'b' }]

it('优先深链，其次上次选择，最后第一个', () => {
  expect(pickProjectId('a', list, 'b')).toBe('b')
  expect(pickProjectId('a', list)).toBe('a')
  expect(pickProjectId(null, list)).toBe('a')
})
it('存了已删除的项目 id 时回落第一个', () => {
  expect(pickProjectId('gone', list)).toBe('a')
})
it('深链失效时回落，而不是用第一个以外的东西', () => {
  expect(pickProjectId('a', list, 'gone')).toBe('a')
})
it('没有项目时返回空串', () => {
  expect(pickProjectId('a', [])).toBe('')
})
```

- [ ] **Step 2: 跑测试确认失败** → `pnpm -C frontend exec vitest run src/lib/projectSelection.test.ts`，Expected: FAIL

- [ ] **Step 3: 实现 `projectSelection.ts` 与 `ProjectContext.tsx`**

Provider 行为：挂载时 `api.listProjects()`；用 `readString(KEY_CURRENT_PROJECT)` 与 `pickProjectId` 定初值；`select(id)` 写 state + `writeString`；`refresh()` 重新拉列表并重新校正 `projectId`（项目被删时回落）；`listProjects` 失败时 `error` 存可读中文、`loading` 置 false、不抛。

- [ ] **Step 4: 跑测试确认通过** → 同上，Expected: PASS（4 例）

- [ ] **Step 5: 接进 `main.tsx`**（`<ProjectProvider><App /></ProjectProvider>`），构建

- [ ] **Step 6: 提交**

```bash
git add frontend/src/lib/projectSelection.ts frontend/src/lib/projectSelection.test.ts frontend/src/state/ProjectContext.tsx frontend/src/main.tsx
git commit -m "feat(frontend): 当前项目状态由外壳持有（纯逻辑 + Provider）"
```

---

### Task 6: 侧栏项目选择器与新建入口

**Files:**
- Create: `frontend/src/components/ProjectSwitcher.tsx`
- Modify: `frontend/src/App.tsx`、`frontend/src/pages/Dashboard.tsx`

**Interfaces:**
- Consumes: `useCurrentProject()`（Task 5）
- Produces: `ProjectSwitcher()`，内含 `<Select>`（项目列表）、「新建」按钮、`Dialog` 输入名称

- [ ] **Step 1: 实现 `ProjectSwitcher`**：选择器显示当前项目名；「新建」打开 `Dialog` 输入名称 → `api.createProject({ name })` → `refresh()` 后 `select(newProject.id)`；失败时 `Toast tone="danger"` 显示错误，不关闭对话框

- [ ] **Step 2: 接到 `App.tsx` 侧栏顶部**

- [ ] **Step 3: 改 `Dashboard.tsx`**：删掉它自己的「新建项目」表单与 `create` 函数；无项目时显示 `EmptyState`（标题「还没有项目」，提示「用左侧选择器新建」，**不放新建按钮**——入口只有一处，避免两个地方建项目）。

- [ ] **Step 4: 构建 + 手验**：`pnpm -C frontend run build`；启动后确认「无项目 → 新建 → 自动选中 → 刷新后仍是它」

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/ProjectSwitcher.tsx frontend/src/App.tsx frontend/src/pages/Dashboard.tsx
git commit -m "feat(frontend): 侧栏项目选择器与新建入口"
```

---

### Task 7: 迁移高频四页（写作台、章节、世界观、仪表盘）

**Files:**
- Modify: `frontend/src/pages/Writing.tsx`、`Chapters.tsx`、`World.tsx`、`Dashboard.tsx`

**Interfaces:**
- Consumes: `useCurrentProject()`（`projectId`、`projects`、`loading`、`select`）

**迁移规则（四页同一套，逐页执行）**

1. 删掉本地的 `projects` / `projectId` state 与 `api.listProjects()` effect，改为 `const { projectId, loading: projectsLoading } = useCurrentProject()`。
2. 删掉页面工具栏里的项目 `<select>`（外壳已有）；保留其它工具栏内容不动。
3. `Dashboard` 原先从 `projects` 里挑 `selected`，改为 `project`；`report` / `cost` / 快照 effect 的依赖从 `selected` 改为 `projectId`，**代际令牌一律保留**。
4. **不得删除**任何 `token` / `reportToken` / 场景代际校验；diff 里出现令牌逻辑变化即回退本页。
5. `World` 额外处理深链：挂载时读 `searchParams.get('project')`，若该 id 在 `projects` 里存在则 `select(id)`；不存在则不清空当前项目、也不静默跳转，页面顶部给一条 `warn` 提示「链接里的项目不存在，已显示当前项目」。

- [ ] **Step 1: 迁移 `Writing.tsx`**，构建后手验：切项目 → 树刷新 → 生成/采纳仍可用
- [ ] **Step 2: 迁移 `Chapters.tsx`**，手验：切项目 → 树与场景表刷新
- [ ] **Step 3: 迁移 `World.tsx` + 深链规则**，手验：`/world?project=<有效id>` 与 `<无效id>` 两种
- [ ] **Step 4: 迁移 `Dashboard.tsx`**，手验：切项目 → 报告、费用、快照、改动全部换到新项目
- [ ] **Step 5: 全量测试 + 构建 + 提交**

```bash
git add frontend/src/pages/Writing.tsx frontend/src/pages/Chapters.tsx frontend/src/pages/World.tsx frontend/src/pages/Dashboard.tsx
git commit -m "refactor(frontend): 高频四页改读外壳项目状态"
```

---

### Task 8: 迁移设定五页（灵感、架构、关系网、时间线、术语表）

**Files:**
- Modify: `frontend/src/pages/Idea.tsx`、`Architecture.tsx`、`Relations.tsx`、`Timeline.tsx`、`Terms.tsx`

**迁移规则**：同 Task 7 的 1、2、4 条（这三页没有深链与 `selected` 对象，只删本地项目状态与 `<select>`，其余 effect 依赖改 `projectId`）。

- [ ] **Step 1: 五页一起迁移**（同一套改动，逐页对照规则 1/2/4）
- [ ] **Step 2: 手验**：每页切项目后数据跟着换；无项目时显示空态
- [ ] **Step 3: 全量测试 + 构建 + 提交**

```bash
git add frontend/src/pages/Idea.tsx frontend/src/pages/Architecture.tsx frontend/src/pages/Relations.tsx frontend/src/pages/Timeline.tsx frontend/src/pages/Terms.tsx
git commit -m "refactor(frontend): 设定五页改读外壳项目状态"
```

---

### Task 9: 迁移系统四页（工作室、模型与费用、管线、阅读器）

**Files:**
- Modify: `frontend/src/pages/Studio.tsx`、`Models.tsx`、`Pipeline.tsx`、`Reader.tsx`

**迁移规则**：同 Task 7 的 1、2、4 条。阅读器额外注意：它整页自铺、无内边距，**不要**给它加外层容器或改动滚动结构。

- [ ] **Step 1: 四页迁移**
- [ ] **Step 2: 手验**：阅读器切项目后目录与正文换书、进度记忆仍作用于「当前书」
- [ ] **Step 3: 全量测试 + 构建 + 提交**

```bash
git add frontend/src/pages/Studio.tsx frontend/src/pages/Models.tsx frontend/src/pages/Pipeline.tsx frontend/src/pages/Reader.tsx
git commit -m "refactor(frontend): 系统四页改读外壳项目状态"
```

---

### Task 10: 侧栏计数与项目摘要

**Files:**
- Create: `frontend/src/state/useProjectMeta.ts`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Produces: `useProjectMeta(projectId: string): { entryCount: number | null; volumes: number | null; chapters: number | null; words: number | null; loading: boolean }`

**行为**：`projectId` 变化时并发取 `api.listEntries(projectId)`（取 `length`）与 `api.getExportReport(projectId)`（取 `volumes` / `chapters` / `total_words`）；任一失败 → 对应字段 `null`（界面显示 `—`），不写 `notice`、不弹错；按 `projectId` 缓存在模块级 `Map`，同一项目重复进入不重复请求。

- [ ] **Step 1: 实现 hook**（失败降级 + `Map` 缓存 + 代际防护：`projectId` 变了就丢弃旧响应）
- [ ] **Step 2: 接到 `App.tsx`**：导航「世界观」旁的 `badge: 'entries'` 显示条目数；侧栏底部显示「N 卷 · M 章 · X 万字」，未知显示 `—`
- [ ] **Step 3: 构建 + 手验**：切项目数字跟着变；断网/停后端时显示 `—` 且页面可用
- [ ] **Step 4: 提交**

```bash
git add frontend/src/state/useProjectMeta.ts frontend/src/App.tsx
git commit -m "feat(frontend): 侧栏条目计数与项目摘要"
```

---

### Task 11: 批次验收

- [ ] **Step 1: 全量校验**

```bash
pnpm -C frontend exec vitest run
pnpm -C frontend run build
pnpm -C frontend run lint
```

Expected: 测试全绿（现有 129 + 新增约 12）、构建干净、lint 无新增 error

- [ ] **Step 2: 双分辨率截图**（1280×800 / 1440×900）：外壳 + 写作台 + 世界观 + 仪表盘各一张，确认侧栏分组、折叠态、选择器、摘要不出格

- [ ] **Step 3: 走查清单逐项手点**

- 无项目 → 新建 → 自动选中 → 刷新浏览器仍是它
- 13 页逐页切项目，数据跟着换；无项目时是空态而不是白屏
- 折叠侧栏 → 刷新后仍是折叠
- `localStorage` 手工清空 → 刷新 → 自动选中第一个项目，不报错
- `/world?project=<随便一个不存在的 id>` → 停在当前项目 + 一条 warn 提示
- 写作台切项目时立刻再切回 → 不出现旧项目内容串台

- [ ] **Step 4: 提交走查记录** `docs/superpowers/plans/2026-10-25-frontend-redesign-0a-0b-walkthrough.md`
- [ ] **Step 5: 同步 `CLAUDE.md` §7 阶段记录与本文档勾选状态**

---

## 后续批次（不在本计划内，各自单独写计划）

1. 批次 1 高频页：写作台（专注模式 + 右栏四页签 + 正文排版）、章节、世界观、仪表盘——这是第一批真正改变页面外观的，需单独走查。
2. 批次 2 设定五页；批次 3 系统四页与阅读器；批次 4 动效与空态收尾。
