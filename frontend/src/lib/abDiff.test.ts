import { describe, expect, it } from 'vitest'
import { diffParagraphs } from './abDiff'

describe('diffParagraphs', () => {
  it('两版完全相同：所有段落都算相同', () => {
    const text = '第一段。\n\n第二段。\n\n第三段。'
    expect(diffParagraphs(text, text)).toEqual({ same: 3, changed: 0 })
  })

  it('只有一段不同：相同段数与差异段数各归各的', () => {
    const a = '第一段。\n\n第二段。\n\n第三段。'
    const b = '第一段。\n\n改过的第二段。\n\n第三段。'
    expect(diffParagraphs(a, b)).toEqual({ same: 2, changed: 1 })
  })

  it('两边都空：0 段相同、0 段不同', () => {
    expect(diffParagraphs('', '   \n\n  ')).toEqual({ same: 0, changed: 0 })
  })
})
