import { expect, it } from 'vitest'
import { VIEW_GROUPS, groupOfView, subViewsOf, viewOfGroup, type ViewTab } from './chapterTabs'

// 七个视图写全 —— 这里正是「重组不丢项」的断言，重组时漏掉一个就会红。
const ALL_VIEWS: ViewTab[] = [
  'structure',
  'rhythm',
  'foreshadows',
  'causal',
  'settingLoad',
  'characterDrift',
  'lanes',
]

it('四组、顺序固定，七个视图不重不漏', () => {
  expect(VIEW_GROUPS.map((group) => group.label)).toEqual(['结构', '节奏', '伏笔', '视图'])

  const covered = VIEW_GROUPS.flatMap((group) =>
    group.views ? group.views.map((item) => item.key) : [group.defaultView],
  )
  expect(new Set(covered).size).toBe(covered.length)
  expect([...covered].sort()).toEqual([...ALL_VIEWS].sort())
})

it('每个视图都归得到组，且每组的默认视图落在该组里', () => {
  for (const view of ALL_VIEWS) {
    const key = groupOfView(view)
    expect(VIEW_GROUPS.some((group) => group.key === key)).toBe(true)
  }
  for (const group of VIEW_GROUPS) {
    const keys = group.views ? group.views.map((item) => item.key) : [group.defaultView]
    expect(keys).toContain(group.defaultView)
    expect(groupOfView(group.defaultView)).toBe(group.key)
  }
})

it('一级键能取到该组视图，二级键只在「视图」组下', () => {
  expect(viewOfGroup('structure')).toBe('structure')
  expect(viewOfGroup('view')).toBe('causal')
  expect(viewOfGroup('不存在')).toBeNull()

  expect(subViewsOf('view').map((item) => item.key)).toEqual([
    'causal',
    'settingLoad',
    'characterDrift',
    'lanes',
  ])
  expect(subViewsOf('structure')).toEqual([])
})
