import { expect, it } from 'vitest'
import type { LogicChainItem } from '../api/client'
import {
  buildLogicChainGraph, shortenSentence, columnCenterX, tickBaselineY,
  NODE_WIDTH, NODE_HEIGHT, COLUMN_WIDTH, ROW_GAP, PAD_LEFT, PAD_TOP, PAD_BOTTOM,
} from './logicChainGraph'

function hit(paragraph: number, kind = 'cause', sentence = '因为下雨，他留下。'): LogicChainItem {
  return { paragraph, sentence, kind, kind_label: kind, marker: '因为' }
}

it('keeps empty paragraphs as columns', () => {
  const graph = buildLogicChainGraph([hit(1), hit(3)], 3)
  expect(graph.columns.map((c) => c.paragraph)).toEqual([1, 2, 3])
  expect(graph.columns[1].nodes).toEqual([])
})

it('stacks nodes top-down inside a column and numbers them flat', () => {
  const graph = buildLogicChainGraph([hit(1), hit(1), hit(2)], 2)
  expect(graph.columns[0].nodes.map((n) => n.index)).toEqual([0, 1])
  expect(graph.columns[0].nodes[0].y).toBe(PAD_TOP)
  expect(graph.columns[0].nodes[1].y).toBe(PAD_TOP + NODE_HEIGHT + ROW_GAP)
  expect(graph.columns[1].nodes[0].x).toBe(PAD_LEFT + COLUMN_WIDTH)
})

it('links consecutive hits with edges coloured by the target kind', () => {
  const graph = buildLogicChainGraph([hit(1), hit(2, 'turn'), hit(3, 'reveal')], 3)
  expect(graph.edges).toEqual([
    { fromIndex: 0, toIndex: 1, kind: 'turn' },
    { fromIndex: 1, toIndex: 2, kind: 'reveal' },
  ])
})

it('uses flat node indices for edges, not paragraph numbers', () => {
  // 同列两个节点（扁平下标 0、1）连一条，再连到下一列第一个节点（扁平下标 2）。
  // 按 chain 的 i → i+1 连，所以同列相邻两次命中之间也有边。
  // 判别点在第一条边：0 → 1（若误用段落下标会变成 1 → 1）。
  const graph = buildLogicChainGraph([hit(1), hit(1), hit(2)], 2)
  expect(graph.edges).toEqual([
    { fromIndex: 0, toIndex: 1, kind: 'cause' },
    { fromIndex: 1, toIndex: 2, kind: 'cause' },
  ])
})

it('sizes a single-column single-node graph exactly', () => {
  const graph = buildLogicChainGraph([hit(1)], 1)
  expect(graph.width).toBe(PAD_LEFT * 2 + NODE_WIDTH)
  expect(graph.height).toBe(PAD_TOP + NODE_HEIGHT + PAD_BOTTOM)
})

it('keeps the height and grows the width when the extra column is empty', () => {
  const single = buildLogicChainGraph([hit(1)], 1)
  const wider = buildLogicChainGraph([hit(2)], 2)
  expect(wider.height).toBe(single.height)
  expect(wider.width).toBeGreaterThan(single.width)
})

it('draws no edge for a single hit', () => {
  expect(buildLogicChainGraph([hit(2)], 2).edges).toEqual([])
})

it('trusts the hits when paragraphs under-reports', () => {
  const graph = buildLogicChainGraph([hit(5)], 0)
  expect(graph.columns).toHaveLength(5)
  expect(graph.nodes).toHaveLength(1)
})

it('falls back to the hits when paragraphs is not a finite number', () => {
  // 上游漏字段时会传进 undefined：列数必须回落到命中段，宽高也不能变成 NaN。
  const graph = buildLogicChainGraph([hit(2)], undefined as unknown as number)
  expect(graph.columns).toHaveLength(2)
  expect(graph.nodes).toHaveLength(1)
  expect(Number.isFinite(graph.width)).toBe(true)
  expect(Number.isFinite(graph.height)).toBe(true)
})

it('returns an empty graph when nothing matched', () => {
  const graph = buildLogicChainGraph([], 4)
  expect(graph).toEqual({ columns: [], nodes: [], edges: [], width: 0, height: 0, maxRows: 0 })
})

it('grows in both directions', () => {
  const tall = buildLogicChainGraph([hit(1), hit(1), hit(1), hit(2)], 2)
  expect(tall.maxRows).toBe(3)
  expect(tall.height).toBeGreaterThan(buildLogicChainGraph([hit(1), hit(2)], 2).height)
  const wide = buildLogicChainGraph([hit(1), hit(9)], 9)
  expect(wide.width).toBeGreaterThan(buildLogicChainGraph([hit(1), hit(2)], 2).width)
})

it('derives the column center from the shared geometric constants', () => {
  expect(columnCenterX(2)).toBe(PAD_LEFT + COLUMN_WIDTH + NODE_WIDTH / 2)
})

it('keeps the tick baseline inside the drawn svg', () => {
  const graph = buildLogicChainGraph([hit(1), hit(2)], 2)
  const y = tickBaselineY(graph.height)
  expect(y).toBeGreaterThan(0)
  expect(y).toBeLessThan(graph.height)
})

it('shortens long sentences and leaves short ones alone', () => {
  expect(shortenSentence('短句。')).toBe('短句。')
  expect(shortenSentence('一'.repeat(40))).toBe('一'.repeat(22) + '…')
})
