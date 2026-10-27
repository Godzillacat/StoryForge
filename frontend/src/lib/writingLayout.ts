/**
 * 写作台的布局状态：工作态 / 专注态、左树形态、右栏形态。
 *
 * 放在 `lib/` 而不是页面里，是为了让「宽度 → 模式」这条判据与三个持久化键
 * 的读回都能被 vitest 守住 —— 写作台是全项目最复杂的一页，不该再往里塞
 * 可以在外面测的东西。
 *
 * 与 `App.tsx` 的外壳不冲突：外壳负责「侧栏 + 页面内容区」，这里只管页面
 * 内部的三栏（左树 / 正文 / 右栏）。
 */

import {
  KEY_WRITING_ASIDE_TAB,
  KEY_WRITING_MODE,
  KEY_WRITING_RIGHT_COLLAPSED,
  readFlag,
  readString,
  writeFlag,
  writeString,
} from './persisted'

export type WritingMode = 'work' | 'focus'

/**
 * 工作态的下限。取自 spec §8.2 的预算：1440 − 外壳 236 − 左树 236 − 右栏 336
 * − 两道 16px 间隙 = 600，正好落在正文目标区间 600–680 的下沿。再窄就放不下，
 * 所以 1280–1439 默认走专注态。
 */
export const WORK_MODE_MIN_WIDTH = 1440

export function modeForWidth(width: number): WritingMode {
  return width >= WORK_MODE_MIN_WIDTH ? 'work' : 'focus'
}

export interface LayoutShape {
  /** 左树：三栏里的常驻列，还是工具栏呼出的抽屉。 */
  tree: 'column' | 'drawer'
  /** 右栏：常驻列、折叠成 44px 的条，还是浮层。 */
  aside: 'column' | 'rail' | 'overlay'
  /** 底部状态条只在专注态出现 —— 工作态的字数在工具栏里。 */
  statusBar: boolean
}

export function shapeFor(mode: WritingMode, rightCollapsed: boolean): LayoutShape {
  if (mode === 'focus') {
    return { tree: 'drawer', aside: 'overlay', statusBar: true }
  }
  return { tree: 'column', aside: rightCollapsed ? 'rail' : 'column', statusBar: false }
}

/**
 * 作者显式选过的模式；没选过返回 null。
 *
 * 与「跟随窗口」分开，是因为两者行为不同：显式选过就永远以他为谁（拉窗口
 * 不该冲掉），没选过才按宽度走。`writeMode` 只在作者点切换时调用，所以
 * 存里有没有值，恰好就等于「他有没有表达过偏好」。
 */
export function readStoredMode(): WritingMode | null {
  const raw = readString(KEY_WRITING_MODE)
  return raw === 'work' || raw === 'focus' ? raw : null
}

export function resolveMode(stored: WritingMode | null, width: number): WritingMode {
  return stored ?? modeForWidth(width)
}

/** 首屏的初始模式：显式选择优先，否则按当时的窗口宽度。 */
export function readMode(width: number): WritingMode {
  return resolveMode(readStoredMode(), width)
}

export function writeMode(mode: WritingMode): void {
  writeString(KEY_WRITING_MODE, mode)
}

export function readRightCollapsed(): boolean {
  return readFlag(KEY_WRITING_RIGHT_COLLAPSED, false)
}

export function writeRightCollapsed(collapsed: boolean): void {
  writeFlag(KEY_WRITING_RIGHT_COLLAPSED, collapsed)
}

/** 右栏的四个页签。顺序即显示顺序。 */
export type AsideTab = 'context' | 'branch' | 'review' | 'log'

export const ASIDE_TABS: { key: AsideTab; label: string }[] = [
  { key: 'context', label: '上下文' },
  { key: 'branch', label: '分支' },
  { key: 'review', label: '审校' },
  { key: 'log', label: '日志' },
]

export const DEFAULT_ASIDE_TAB: AsideTab = 'context'

export function readAsideTab(): AsideTab {
  const raw = readString(KEY_WRITING_ASIDE_TAB)
  return ASIDE_TABS.find((tab) => tab.key === raw)?.key ?? DEFAULT_ASIDE_TAB
}

export function writeAsideTab(tab: AsideTab): void {
  writeString(KEY_WRITING_ASIDE_TAB, tab)
}
