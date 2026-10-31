import { expect, it } from 'vitest'
import { NAV_GROUPS, flatNavItems } from './nav'

it('十三条入口、分组顺序固定、路径唯一', () => {
  expect(flatNavItems()).toHaveLength(13)
  expect(NAV_GROUPS.map((group) => group.title)).toEqual(['总览', '构思', '设定', '写作', '阅读与发行', '系统'])
  const paths = flatNavItems().map((item) => item.to)
  expect(new Set(paths).size).toBe(13)
  expect(paths.every((path) => path.startsWith('/'))).toBe(true)
})

it('每个入口都有名称与图标', () => {
  for (const item of flatNavItems()) {
    expect(item.label.length).toBeGreaterThan(0)
    expect(item.icon.length).toBeGreaterThan(0)
  }
})
