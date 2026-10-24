import { expect, it } from 'vitest'
import type { LogicChainItem } from '../api/client'
import {
  buildLogicChainGraph, shortenSentence, columnCenterX, tickBaselineY, edgePathFor,
  NODE_WIDTH, NODE_HEIGHT, COLUMN_WIDTH, ROW_GAP, PAD_LEFT, PAD_TOP, PAD_BOTTOM, NODE_TEXT_MAX,
} from './logicChainGraph'

// kind_label 故意与 kind 不同：映射写错（把 kind 当标签）时断言会红。
const KIND_LABELS: Record<string, string> = { cause: '因果', turn: '转折', reveal: '揭示' }

function hit(paragraph: number, kind = 'cause', sentence = '因为下雨，他留下。'): LogicChainItem {
  return { paragraph, sentence, kind, kind_label: KIND_LABELS[kind] ?? kind, marker: '因为' }
}

/** 从 `M sx sy C c1x c1y, c2x c2y, tx ty` 里取出 8 个数字。 */
function pathNumbers(d: string): number[] {
  return (d.match(/-?\d+(?:\.\d+)?/g) ?? []).map(Number)
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

it('keeps both control points strictly between the two nodes on a cross-column edge', () => {
  // 6e451f7 修的缺陷：控制点外探会让边画成「过冲小圈」而不是连线。
  const graph = buildLogicChainGraph([hit(1), hit(2)], 2)
  const from = graph.nodes[0]
  const to = graph.nodes[1]
  expect(to.x).toBeGreaterThan(from.x + from.width)
  const numbers = pathNumbers(edgePathFor(from, to))
  expect(numbers).toHaveLength(8)
  for (const controlX of [numbers[2], numbers[4]]) {
    expect(controlX).toBeGreaterThan(from.x + from.width)
    expect(controlX).toBeLessThan(to.x)
  }
  // 两个控制点也不许交叉：交叉意味着曲线在 48px 空隙里先回头再往前，画出来是回勾。
  expect(numbers[2]).toBeLessThanOrEqual(numbers[4])
})

it('routes a same-column edge straight down, from the source bottom to the target top', () => {
  const graph = buildLogicChainGraph([hit(1, 'cause'), hit(1, 'turn')], 1)
  const from = graph.nodes[0]
  const to = graph.nodes[1]
  expect(to.kindLabel).toBe('转折')
  const numbers = pathNumbers(edgePathFor(from, to))
  const center = from.x + from.width / 2
  expect([numbers[0], numbers[2], numbers[4], numbers[6]]).toEqual([center, center, center, center])
  expect(numbers[1]).toBe(from.y + from.height)
  expect(numbers[7]).toBe(to.y)
  expect(numbers[7]).toBeGreaterThan(numbers[1])
})

it('keeps 40 columns and an 8-hit column intact', () => {
  const crowded = Array.from({ length: 8 }, () => hit(7))
  const graph = buildLogicChainGraph([...crowded, hit(40)], 40)
  expect(graph.columns).toHaveLength(40)
  expect(graph.columns[6].nodes).toHaveLength(8)
  expect(graph.height).toBeGreaterThan(8 * NODE_HEIGHT)
})

it('truncates node text at NODE_TEXT_MAX and adds one ellipsis character', () => {
  const over = shortenSentence('一'.repeat(NODE_TEXT_MAX + 1), NODE_TEXT_MAX)
  expect(over).toHaveLength(NODE_TEXT_MAX + 1)
  expect(over).toBe('一'.repeat(NODE_TEXT_MAX) + '…')
  // 默认上限（22）下，NODE_TEXT_MAX + 1 个字远没到截断线，原样返回。
  expect(shortenSentence('一'.repeat(NODE_TEXT_MAX + 1))).toBe('一'.repeat(NODE_TEXT_MAX + 1))
})

it('shortens long sentences and leaves short ones alone', () => {
  expect(shortenSentence('短句。')).toBe('短句。')
  expect(shortenSentence('一'.repeat(40))).toBe('一'.repeat(22) + '…')
})
