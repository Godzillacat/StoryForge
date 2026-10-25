import { expect, it } from 'vitest'
import { formatWords, summaryLine } from './projectMeta'

it('未知的数值显示破折号，不显示 0', () => {
  expect(summaryLine({ volumes: null, chapters: null, words: null })).toBe('— · — · —')
})

it('有数据时按「卷 · 章 · 字数」拼一行', () => {
  expect(summaryLine({ volumes: 3, chapters: 12, words: 284120 })).toBe('3 卷 · 12 章 · 28.4 万字')
})

it('不足一万字按字显示', () => {
  expect(formatWords(0)).toBe('0 字')
  expect(formatWords(8421)).toBe('8421 字')
})
