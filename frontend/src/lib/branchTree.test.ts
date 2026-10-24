import { describe, expect, it } from 'vitest'
import {
  INDENT_PER_LEVEL,
  buildBranchRows,
  defaultChildName,
  type BranchNode,
} from './branchTree'

/** 后端 `list_branches` 的形状；`depth` / `parent_id` 缺省时由函数自算。 */
function branch(id: string, name: string, extra: Partial<BranchNode> = {}): BranchNode {
  return { id, name, ...extra }
}

describe('buildBranchRows', () => {
  it('lays a tree out in preorder: root first, child right after its parent', () => {
    const rows = buildBranchRows([
      branch('a', '阿明犹豫'),
      branch('a1', '阿明决意', { parent_id: 'a' }),
      branch('a11', '阿明决意（短版）', { parent_id: 'a1' }),
      branch('b', '第三人视角'),
    ])
    expect(rows.map((row) => row.name)).toEqual([
      '阿明犹豫',
      '阿明决意',
      '阿明决意（短版）',
      '第三人视角',
    ])
    expect(rows.map((row) => row.depth)).toEqual([1, 2, 3, 1])
  })

  it('indents by (depth - 1) * 16', () => {
    expect(INDENT_PER_LEVEL).toBe(16)
    const rows = buildBranchRows([
      branch('a', '一'),
      branch('a1', '二', { parent_id: 'a' }),
      branch('a11', '三', { parent_id: 'a1' }),
    ])
    expect(rows.map((row) => row.indent)).toEqual([0, 16, 32])
  })

  it('keeps the depth the backend sent instead of recomputing it', () => {
    // 后端按全场景算深度；前端重算会把跨层分支报浅。
    const rows = buildBranchRows([
      branch('a', '一'),
      branch('a1', '二', { parent_id: 'a', depth: 3 }),
    ])
    const child = rows.find((row) => row.id === 'a1')
    expect(child?.depth).toBe(3)
    expect(child?.indent).toBe(32)
  })

  it('treats an orphan (parent not in the list) as a root', () => {
    const rows = buildBranchRows([
      branch('a', '一'),
      branch('orphan', '孤儿', { parent_id: '被丢弃的分支' }),
    ])
    expect(rows.map((row) => row.id)).toEqual(['a', 'orphan'])
    expect(rows[1].depth).toBe(1)
    expect(rows[1].indent).toBe(0)
    expect(rows[1].parentName).toBeNull()
  })

  it('reports the parent name on child rows', () => {
    const rows = buildBranchRows([
      branch('a', '阿明犹豫'),
      branch('a1', '阿明决意', { parent_id: 'a' }),
    ])
    expect(rows[0].parentName).toBeNull()
    expect(rows[1].parentName).toBe('阿明犹豫')
  })

  it('computes depth from the tree when the backend omitted it', () => {
    const rows = buildBranchRows([
      branch('a', '一'),
      branch('a1', '二', { parent_id: 'a' }),
      branch('a11', '三', { parent_id: 'a1' }),
    ])
    expect(rows.map((row) => row.depth)).toEqual([1, 2, 3])
  })

  it('keeps every branch when dirty data forms a cycle', () => {
    const rows = buildBranchRows([
      branch('a', '环 A', { parent_id: 'b' }),
      branch('b', '环 B', { parent_id: 'a' }),
    ])
    expect(rows.map((row) => row.id).sort()).toEqual(['a', 'b'])
    expect(rows.every((row) => row.depth >= 1)).toBe(true)
  })

  it('returns an empty list for null / empty input', () => {
    expect(buildBranchRows([])).toEqual([])
    expect(buildBranchRows(null)).toEqual([])
  })
})

describe('defaultChildName', () => {
  it('suggests 父名 · 派生 when the name is free', () => {
    expect(defaultChildName('阿明犹豫', [])).toBe('阿明犹豫 · 派生')
    expect(defaultChildName('阿明犹豫', ['第三人视角'])).toBe('阿明犹豫 · 派生')
  })

  it('appends a sequence number when the default is taken', () => {
    expect(defaultChildName('阿明犹豫', ['阿明犹豫 · 派生'])).toBe(
      '阿明犹豫 · 派生 2',
    )
    expect(
      defaultChildName('阿明犹豫', ['阿明犹豫 · 派生', '阿明犹豫 · 派生 2']),
    ).toBe('阿明犹豫 · 派生 3')
  })

  it('skips over names that are taken out of order', () => {
    expect(
      defaultChildName('阿明犹豫', ['阿明犹豫 · 派生', '阿明犹豫 · 派生 3']),
    ).toBe('阿明犹豫 · 派生 2')
  })

  it('ignores surrounding whitespace when comparing, like the backend', () => {
    expect(defaultChildName('阿明犹豫', ['  阿明犹豫 · 派生  '])).toBe(
      '阿明犹豫 · 派生 2',
    )
    expect(defaultChildName(' 阿明犹豫 ', [])).toBe('阿明犹豫 · 派生')
  })
})

