/**
 * localStorage 读写。隐私模式、配额满、被禁用时一律静默降级 ——
 * 侧栏折叠与上次项目是便利，丢了不该让页面崩。
 */

export const KEY_CURRENT_PROJECT = 'storyforge.currentProject'
export const KEY_SIDEBAR_COLLAPSED = 'storyforge.sidebarCollapsed'

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
