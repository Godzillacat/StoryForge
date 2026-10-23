import { describe, expect, it } from 'vitest'
import { parseMarkdown } from './markdown'
import {
  blockAtScroll,
  blockIndexOfChunk,
  findInBook,
  findMatches,
  speechChunksOf,
} from './reading'

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

describe('blockIndexOfChunk', () => {
  it('一一段对应时下标相等', () => {
    const blocks = parseMarkdown('一。\n\n二。\n\n三。')

    expect(blockIndexOfChunk(blocks, 0)).toBe(0)
    expect(blockIndexOfChunk(blocks, 2)).toBe(2)
  })

  it('分隔线不占朗读段，跳过它', () => {
    const blocks = parseMarkdown('一。\n\n---\n\n二。')

    // 块 0 = 段落，块 1 = 分隔线，块 2 = 段落
    expect(blockIndexOfChunk(blocks, 0)).toBe(0)
    expect(blockIndexOfChunk(blocks, 1)).toBe(2)
  })

  it('列表被拆成多段，几段都指回同一个块', () => {
    const blocks = parseMarkdown('- 甲\n- 乙\n\n尾巴。')

    expect(blockIndexOfChunk(blocks, 0)).toBe(0)
    expect(blockIndexOfChunk(blocks, 1)).toBe(0)
    expect(blockIndexOfChunk(blocks, 2)).toBe(1)
  })

  it('越界返回 null', () => {
    expect(blockIndexOfChunk(parseMarkdown('一。'), 5)).toBeNull()
    expect(blockIndexOfChunk([], 0)).toBeNull()
  })
})

describe('blockAtScroll', () => {
  it('取第一块还没滚过去的块', () => {
    expect(blockAtScroll([0, 100, 200], 0)).toBe(0)
    // 滚到 120：第 0、1 块已经在上方看不见了，可见的是第 2 块。
    expect(blockAtScroll([0, 100, 200], 120)).toBe(2)
    // 停在块顶附近（8px 容差内）仍算那一块。
    expect(blockAtScroll([0, 100, 200], 97)).toBe(1)
    expect(blockAtScroll([0, 100, 200], 250)).toBe(2)
  })

  it('空列表返回 0', () => {
    expect(blockAtScroll([], 500)).toBe(0)
  })
})

describe('findInBook', () => {
  const chapters = [
    { id: 'c1', title: '开端', volumeName: '第一卷', content: '雨落在旧城。' },
    { id: 'c2', title: '转折', volumeName: '第二卷', content: '旧城的灯灭了。' },
    { id: 'c3', title: '空章', volumeName: '第二卷', content: '' },
  ]

  it('跨章找，每章各自报', () => {
    const hits = findInBook(chapters, '旧城')

    expect(hits.map((hit) => hit.chapterId)).toEqual(['c1', 'c2'])
    expect(hits[1].volumeName).toBe('第二卷')
  })

  it('空章节不参与', () => {
    expect(findInBook(chapters, '旧城').some((hit) => hit.chapterId === 'c3')).toBe(false)
  })

  it('没有命中时返回空数组', () => {
    expect(findInBook(chapters, '不存在')).toEqual([])
  })

  it('空查询不返回命中', () => {
    expect(findInBook(chapters, '  ')).toEqual([])
  })
})
