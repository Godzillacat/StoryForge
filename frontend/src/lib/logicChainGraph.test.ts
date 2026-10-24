import { expect, it } from 'vitest'
import type { LogicChainItem } from '../api/client'
import {
  buildLogicChainGraph, shortenSentence, NODE_HEIGHT, COLUMN_WIDTH, ROW_GAP, PAD_LEFT, PAD_TOP,
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
    { from: 0, to: 1, kind: 'turn' },
    { from: 1, to: 2, kind: 'reveal' },
  ])
})

it('draws no edge for a single hit', () => {
  expect(buildLogicChainGraph([hit(2)], 2).edges).toEqual([])
})

it('trusts the hits when paragraphs under-reports', () => {
  const graph = buildLogicChainGraph([hit(5)], 0)
  expect(graph.columns).toHaveLength(5)
  expect(graph.nodes).toHaveLength(1)
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

it('shortens long sentences and leaves short ones alone', () => {
  expect(shortenSentence('短句。')).toBe('短句。')
  expect(shortenSentence('一'.repeat(40))).toBe('一'.repeat(22) + '…')
})
