import { describe, expect, it } from 'vitest'
import { diffLines } from './diff'

describe('diffLines', () => {
  it('marks identical text as same', () => {
    expect(diffLines('甲\n乙', '甲\n乙')).toEqual([
      { kind: 'same', text: '甲', oldLine: 1, newLine: 1 },
      { kind: 'same', text: '乙', oldLine: 2, newLine: 2 },
    ])
  })

  it('marks pure additions', () => {
    expect(diffLines('甲', '甲\n乙')).toEqual([
      { kind: 'same', text: '甲', oldLine: 1, newLine: 1 },
      { kind: 'add', text: '乙', oldLine: null, newLine: 2 },
    ])
  })

  it('marks pure removals', () => {
    expect(diffLines('甲\n乙', '甲')).toEqual([
      { kind: 'same', text: '甲', oldLine: 1, newLine: 1 },
      { kind: 'remove', text: '乙', oldLine: 2, newLine: null },
    ])
  })

  it('marks replacements', () => {
    expect(diffLines('旧', '新')).toEqual([
      { kind: 'remove', text: '旧', oldLine: 1, newLine: null },
      { kind: 'add', text: '新', oldLine: null, newLine: 1 },
    ])
  })

  it('handles an empty old text', () => {
    expect(diffLines('', '新')).toEqual([
      { kind: 'add', text: '新', oldLine: null, newLine: 1 },
    ])
  })

  it('falls back to whole replacement for very long text', () => {
    const oldText = Array.from({ length: 2500 }, (_, i) => `旧${i}`).join('\n')
    const newText = Array.from({ length: 2500 }, (_, i) => `新${i}`).join('\n')
    const rows = diffLines(oldText, newText)
    expect(rows.filter((row) => row.kind === 'remove')).toHaveLength(2500)
    expect(rows.filter((row) => row.kind === 'add')).toHaveLength(2500)
    expect(rows.every((row) => row.kind !== 'same')).toBe(true)
  })
})
