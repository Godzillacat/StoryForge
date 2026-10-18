import { describe, expect, it } from 'vitest'
import { createSseParser } from './sse'

describe('createSseParser', () => {
  it('parses one complete event', () => {
    const parser = createSseParser()
    expect(parser.push('event: delta\ndata: {"text":"甲"}\n\n')).toEqual([
      { event: 'delta', data: '{"text":"甲"}' },
    ])
  })

  it('buffers an event split across chunks', () => {
    const parser = createSseParser()
    expect(parser.push('event: delta\ndata: {"te')).toEqual([])
    expect(parser.push('xt":"乙"}\n\n')).toEqual([
      { event: 'delta', data: '{"text":"乙"}' },
    ])
  })

  it('joins multi-line data and ignores comments', () => {
    const parser = createSseParser()
    expect(parser.push(': ping\nevent: done\ndata: 第一行\ndata: 第二行\n\n')).toEqual([
      { event: 'done', data: '第一行\n第二行' },
    ])
  })

  it('defaults the event name to message', () => {
    const parser = createSseParser()
    expect(parser.push('data: x\n\n')).toEqual([{ event: 'message', data: 'x' }])
  })

  it('skips blocks without data', () => {
    const parser = createSseParser()
    expect(parser.push('event: ping\n\n')).toEqual([])
  })

  it('normalizes CRLF', () => {
    const parser = createSseParser()
    expect(parser.push('event: run\r\ndata: {}\r\n\r\n')).toEqual([
      { event: 'run', data: '{}' },
    ])
  })
})
