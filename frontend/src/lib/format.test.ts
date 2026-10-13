import { describe, expect, it } from 'vitest'
import { costLabel, durationLabel, maskPreview, tokensLabel } from './format'

describe('costLabel', () => {
  it('显示至多四位小数的美元金额', () => {
    expect(costLabel(0.00024)).toBe('$0.0002')
  })
  it('零金额显示为 $0', () => {
    expect(costLabel(0)).toBe('$0')
  })
  it('较大金额保留两位小数', () => {
    expect(costLabel(1.23456)).toBe('$1.23')
  })
})

describe('durationLabel', () => {
  it('毫秒以下按毫秒显示', () => {
    expect(durationLabel(840)).toBe('840 ms')
  })
  it('秒级按秒显示', () => {
    expect(durationLabel(2400)).toBe('2.4 s')
  })
})

describe('tokensLabel', () => {
  it('合并输入输出 token', () => {
    expect(tokensLabel(120, 340)).toBe('120 + 340 tokens')
  })
})

describe('maskPreview', () => {
  it('长文本截断并加省略号', () => {
    expect(maskPreview('一二三四五六七八九十', 4)).toBe('一二三四…')
  })
  it('短文本原样返回', () => {
    expect(maskPreview('短', 4)).toBe('短')
  })
})
