import { describe, expect, it } from 'vitest'
import { blockText, parseInline, parseMarkdown } from './markdown'

describe('parseMarkdown', () => {
  it('把空行分开的段落切成独立的块', () => {
    const blocks = parseMarkdown('第一段。\n\n第二段。')

    expect(blocks).toHaveLength(2)
    expect(blocks[0]).toEqual({
      type: 'paragraph',
      inline: [{ type: 'text', text: '第一段。' }],
    })
  })

  it('段内软换行合并成一段', () => {
    const blocks = parseMarkdown('第一行\n第二行')

    expect(blocks).toHaveLength(1)
    expect(blocks[0].type).toBe('paragraph')
  })

  it('识别四级以内标题，更深的降为四级', () => {
    expect(parseMarkdown('# 一')[0]).toMatchObject({ type: 'heading', level: 1 })
    expect(parseMarkdown('### 三')[0]).toMatchObject({ type: 'heading', level: 3 })
    expect(parseMarkdown('##### 五')[0]).toMatchObject({ type: 'heading', level: 4 })
  })

  it('识别引用，多行合并成一条', () => {
    const blocks = parseMarkdown('> 第一句\n> 第二句')

    expect(blocks).toHaveLength(1)
    expect(blockText(blocks[0])).toBe('第一句第二句')
  })

  it('识别无序与有序列表', () => {
    expect(parseMarkdown('- 甲\n- 乙')[0]).toEqual({
      type: 'list',
      ordered: false,
      items: [[{ type: 'text', text: '甲' }], [{ type: 'text', text: '乙' }]],
    })
    expect(parseMarkdown('1. 甲\n2. 乙')[0]).toMatchObject({ type: 'list', ordered: true })
  })

  it('识别分隔线', () => {
    expect(parseMarkdown('---')[0]).toEqual({ type: 'divider' })
  })

  it('HTML 标签原样当文字，不解释', () => {
    const blocks = parseMarkdown('<script>alert(1)</script>')

    expect(blocks[0]).toEqual({
      type: 'paragraph',
      inline: [{ type: 'text', text: '<script>alert(1)</script>' }],
    })
  })

  it('空输入返回空列表', () => {
    expect(parseMarkdown('')).toEqual([])
    expect(parseMarkdown(null)).toEqual([])
    expect(parseMarkdown('   \n\n  ')).toEqual([])
  })
})

describe('parseInline', () => {
  it('识别粗体、斜体与行内代码', () => {
    expect(parseInline('他说**很好**')).toEqual([
      { type: 'text', text: '他说' },
      { type: 'strong', text: '很好' },
    ])
    expect(parseInline('*轻声*说话')[0]).toEqual({ type: 'em', text: '轻声' })
    expect(parseInline('用 `code` 举例')[1]).toEqual({ type: 'code', text: 'code' })
  })

  it('代码里的星号不被当成强调', () => {
    expect(parseInline('`**x**`')).toEqual([{ type: 'code', text: '**x**' }])
  })

  it('未闭合的标记当普通文字', () => {
    expect(parseInline('**没闭合')).toEqual([{ type: 'text', text: '**没闭合' }])
  })
})

describe('blockText', () => {
  it('去掉标记只留字', () => {
    const blocks = parseMarkdown('## 标题\n\n正文**加粗**。')

    expect(blocks.map(blockText)).toEqual(['标题', '正文加粗。'])
  })

  it('分隔线没有可读内容', () => {
    expect(blockText({ type: 'divider' })).toBe('')
  })
})
