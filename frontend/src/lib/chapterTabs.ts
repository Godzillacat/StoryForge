/**
 * 章节设计页的页签结构。
 *
 * spec §9.8 要求七个页签收敛成四组，后四者收进「视图」下的二级切换。
 * 这里只描述**分组**；页面上的 `view` 状态仍然只有原来那一个 —— 一级页签的
 * 选中态由它投影得出，切一级组即切到该组的默认视图。因此这次重组不引入
 * 任何新状态，八个 `view === 'xxx'` 渲染分支一行都不用改。
 *
 * 放在 `lib/` 而不是页面里，是为了让「分组不重不漏」这件事能被 vitest 守住。
 */

export type ViewTab =
  | 'structure'
  | 'rhythm'
  | 'foreshadows'
  | 'lanes'
  | 'causal'
  | 'settingLoad'
  | 'characterDrift'

export type ViewGroupKey = 'structure' | 'rhythm' | 'foreshadows' | 'view'

export interface ViewGroup {
  key: ViewGroupKey
  label: string
  /** 切到这一组时看哪个视图。带子项的组，它就是二级的默认项。 */
  defaultView: ViewTab
  /** 非空表示这一组下面还有一行二级切换。 */
  views?: { key: ViewTab; label: string }[]
}

export const VIEW_GROUPS: ViewGroup[] = [
  { key: 'structure', label: '结构', defaultView: 'structure' },
  { key: 'rhythm', label: '节奏', defaultView: 'rhythm' },
  { key: 'foreshadows', label: '伏笔', defaultView: 'foreshadows' },
  {
    key: 'view',
    label: '视图',
    defaultView: 'causal',
    views: [
      { key: 'causal', label: '因果链' },
      { key: 'settingLoad', label: '设定投放' },
      { key: 'characterDrift', label: '性格漂移' },
      { key: 'lanes', label: '剧情线' },
    ],
  },
]

/** 视图 → 所属组。由 `VIEW_GROUPS` 现算，不抄第二份清单。 */
const GROUP_KEY_BY_VIEW = new Map<ViewTab, ViewGroupKey>()
for (const group of VIEW_GROUPS) {
  if (group.views) {
    for (const item of group.views) GROUP_KEY_BY_VIEW.set(item.key, group.key)
  } else {
    GROUP_KEY_BY_VIEW.set(group.defaultView, group.key)
  }
}

export function groupOfView(view: ViewTab): ViewGroupKey {
  return GROUP_KEY_BY_VIEW.get(view) ?? VIEW_GROUPS[0].key
}

/** 一级组对应的视图；不认识的键返回 null（`Tabs` 的 onChange 只给字符串）。 */
export function viewOfGroup(groupKey: string): ViewTab | null {
  return VIEW_GROUPS.find((group) => group.key === groupKey)?.defaultView ?? null
}

/** 某组下面的二级视图；没有二级就返回空数组。 */
export function subViewsOf(groupKey: string): { key: ViewTab; label: string }[] {
  return VIEW_GROUPS.find((group) => group.key === groupKey)?.views ?? []
}
