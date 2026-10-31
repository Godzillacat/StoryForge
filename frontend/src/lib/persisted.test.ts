import { beforeEach, expect, it } from 'vitest'
import { KEY_SIDEBAR_COLLAPSED, readFlag, readString, writeFlag, writeString } from './persisted'

beforeEach(() => localStorage.clear())

it('未存过时用默认值', () => {
  expect(readFlag(KEY_SIDEBAR_COLLAPSED, false)).toBe(false)
  expect(readString('storyforge.missing')).toBeNull()
})

it('写坏的值回落默认值', () => {
  localStorage.setItem(KEY_SIDEBAR_COLLAPSED, '不是布尔')
  expect(readFlag(KEY_SIDEBAR_COLLAPSED, true)).toBe(true)
})

it('能读回写入的值', () => {
  writeFlag(KEY_SIDEBAR_COLLAPSED, true)
  expect(readFlag(KEY_SIDEBAR_COLLAPSED, false)).toBe(true)
  writeString('storyforge.currentProject', 'proj-1')
  expect(readString('storyforge.currentProject')).toBe('proj-1')
})
