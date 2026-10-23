import { describe, expect, it } from 'vitest'
import { parseMarkdown } from './markdown'
import { findMatches, speechChunksOf } from './reading'

describe('speechChunksOf', () => {
  it('标题与段落都进队列，去掉标记', () => {
    const blocks = parseMarkdown('## 第一章\n\n他推开门。')

    expect(speechChunksOf(blocks)).toEqual(['第一章', '他推开门。'])
  })

  it('分隔线不进队列', () => {
    const blocks = parseMarkdown('第一段。\n\n---\n\n第二段。')

    expect(speechChunksOf(blocks)).toEqual(['第一段。', '第二段。'])
  })

  it('列表逐项读出', () => {
    const blocks = parseMarkdown('- 甲\n- 乙')

    expect(speechChunksOf(blocks)).toEqual(['甲', '乙'])
  })

  it('空正文没有可读内容', () => {
    expect(speechChunksOf([])).toEqual([])
  })

  it('顺序不变', () => {
    const blocks = parseMarkdown('一。\n\n二。\n\n三。')

    expect(speechChunksOf(blocks)).toEqual(['一。', '二。', '三。'])
  })
})

describe('findMatches', () => {
  it('返回块序号与片段', () => {
    const blocks = parseMarkdown('雨停了。\n\n他走进旧城的巷子。\n\n巷子很深。')
    const hits = findMatches(blocks, '旧城')

    expect(hits).toHaveLength(1)
    expect(hits[0].block).toBe(1)
    expect(hits[0].snippet).toContain('旧城')
  })

  it('同一块只报一次', () => {
    const blocks = parseMarkdown('旧城。旧城又旧城。')

    expect(findMatches(blocks, '旧城')).toHaveLength(1)
  })

  it('大小写不敏感', () => {
    const blocks = parseMarkdown('The Old City waits.')

    expect(findMatches(blocks, 'old city')).toHaveLength(1)
  })

  it('空查询不返回命中', () => {
    expect(findMatches(parseMarkdown('正文'), '   ')).toEqual([])
  })

  it('长文本两端加省略号', () => {
    const blocks = parseMarkdown('甲'.repeat(80) + '命中' + '乙'.repeat(80))

    const snippet = findMatches(blocks, '命中', 5)[0].snippet

    expect(snippet.startsWith('…')).toBe(true)
    expect(snippet.endsWith('…')).toBe(true)
  })
})
