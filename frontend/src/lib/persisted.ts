/**
 * localStorage 读写。隐私模式、配额满、被禁用时一律静默降级 ——
 * 侧栏折叠与上次项目是便利，丢了不该让页面崩。
 */

export const KEY_CURRENT_PROJECT = 'storyforge.currentProject'
export const KEY_SIDEBAR_COLLAPSED = 'storyforge.sidebarCollapsed'
// 写作台的三项：模式（工作 / 专注）、右栏是否折叠成条、右栏当前页签。
// 抽屉的开合**不持久化** —— 它是瞬时的，下次进来应该回到干净状态。
export const KEY_WRITING_MODE = 'storyforge.writingMode'
export const KEY_WRITING_RIGHT_COLLAPSED = 'storyforge.writingRightCollapsed'
export const KEY_WRITING_ASIDE_TAB = 'storyforge.writingAsideTab'

function store(): Storage | null {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

export function readString(key: string): string | null {
  try {
    return store()?.getItem(key) ?? null
  } catch {
    return null
  }
}

export function writeString(key: string, value: string): void {
  try {
    store()?.setItem(key, value)
  } catch {
    // 写不进去就算了：下次启动会回落默认值。
  }
}

export function readFlag(key: string, fallback: boolean): boolean {
  const raw = readString(key)
  if (raw === 'true') return true
  if (raw === 'false') return false
  return fallback
}

export function writeFlag(key: string, value: boolean): void {
  writeString(key, String(value))
}
