import { beforeEach, expect, it } from 'vitest'
import {
  ASIDE_TABS,
  modeForWidth,
  readAsideTab,
  readMode,
  readRightCollapsed,
  shapeFor,
  writeAsideTab,
  writeMode,
  writeRightCollapsed,
} from './writingLayout'
import {
  KEY_CURRENT_PROJECT,
  KEY_SIDEBAR_COLLAPSED,
  KEY_WRITING_ASIDE_TAB,
  KEY_WRITING_MODE,
  KEY_WRITING_RIGHT_COLLAPSED,
} from './persisted'

beforeEach(() => localStorage.clear())

it('1440 是工作态的下限，再窄就是专注态', () => {
  expect(modeForWidth(1600)).toBe('work')
  expect(modeForWidth(1440)).toBe('work')
  expect(modeForWidth(1439)).toBe('focus')
  expect(modeForWidth(1280)).toBe('focus')
})

it('没存过时按宽度推断，存过就以作者的选择为准', () => {
  expect(readMode(1440)).toBe('work')
  expect(readMode(1280)).toBe('focus')

  writeMode('focus')
  // 作者在宽窗口下手动切到专注态：拉窗口不该把他的选择冲掉。
  expect(readMode(1600)).toBe('focus')
  writeMode('work')
  expect(readMode(1280)).toBe('work')
})

it('两种模式的形态：专注态把左树收成抽屉、右栏变浮层、多一条状态条', () => {
  expect(shapeFor('work', false)).toEqual({
    tree: 'column',
    aside: 'column',
    statusBar: false,
  })
  expect(shapeFor('work', true)).toEqual({
    tree: 'column',
    aside: 'rail',
    statusBar: false,
  })
  expect(shapeFor('focus', false)).toEqual({
    tree: 'drawer',
    aside: 'overlay',
    statusBar: true,
  })
})

it('右栏页签读回、写坏的值回落第一个', () => {
  expect(readAsideTab()).toBe('context')
  writeAsideTab('log')
  expect(readAsideTab()).toBe('log')
  localStorage.setItem(KEY_WRITING_ASIDE_TAB, '不存在的页签')
  expect(readAsideTab()).toBe('context')
  expect(ASIDE_TABS.map((tab) => tab.key)).toEqual(['context', 'branch', 'review', 'log'])
})

it('右栏折叠的读写', () => {
  expect(readRightCollapsed()).toBe(false)
  writeRightCollapsed(true)
  expect(readRightCollapsed()).toBe(true)
})

it('写作台的键与外壳的键不重名', () => {
  const writing = [KEY_WRITING_MODE, KEY_WRITING_RIGHT_COLLAPSED, KEY_WRITING_ASIDE_TAB]
  expect(new Set(writing).size).toBe(3)
  expect(writing).not.toContain(KEY_CURRENT_PROJECT)
  expect(writing).not.toContain(KEY_SIDEBAR_COLLAPSED)
  expect(writing.every((key) => key.startsWith('storyforge.'))).toBe(true)
})
