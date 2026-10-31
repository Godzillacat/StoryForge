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

it('深链失效时回落到上次选择', () => {
  expect(pickProjectId('a', list, 'gone')).toBe('a')
})

it('没有项目时返回空串', () => {
  expect(pickProjectId('a', [])).toBe('')
  expect(pickProjectId(null, [], 'x')).toBe('')
})
