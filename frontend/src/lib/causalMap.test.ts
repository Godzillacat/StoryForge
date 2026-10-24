import { describe, expect, it } from 'vitest'
import type { CausalChapter, CausalMapData, CausalScene } from '../api/client'
import {
  NODE_GAP,
  NODE_WIDTH,
  ROW_HEIGHT,
  buildCausalRows,
  summarize,
} from './causalMap'

function makeScene(id: string, seq: number, overrides: Partial<CausalScene> = {}): CausalScene {
  return {
    id,
    seq,
    label: `场景${seq + 1}`,
    goal: '',
    turn: '',
    status: 'planned',
    locked: false,
    breaks: [],
    issues: [],
    ...overrides,
  }
}

function makeChapter(
  id: string,
  label: string,
  scenes: CausalScene[],
  volumeLabel = '第一卷',
): CausalChapter {
  return { id, label, volume_label: volumeLabel, scenes }
}

/** totals 按接口语义从数据里算，用于对照 summarize 是否与后端一致。 */
function makeData(chapters: CausalChapter[]): CausalMapData {
  const scenes = chapters.flatMap((chapter) => chapter.scenes)
  return {
    chapters,
    totals: {
      scenes: scenes.length,
      breaks: scenes.reduce((sum, scene) => sum + scene.breaks.length, 0),
      chapters: chapters.length,
    },
    logic_checked: true,
  }
}

describe('causal map geometry', () => {
  it('keeps the agreed node size and row height', () => {
    expect(NODE_WIDTH).toBe(180)
    expect(NODE_GAP).toBe(28)
    expect(ROW_HEIGHT).toBe(120)
  })

  it('lays nodes out left to right with a fixed stride', () => {
    const data = makeData([
      makeChapter('c1', '第1章 雨夜', [
        makeScene('s1', 0, { goal: '交信', turn: '信是假的' }),
        makeScene('s2', 1),
        makeScene('s3', 2, { goal: '追问' }),
      ]),
    ])

    const [row] = buildCausalRows(data).rows
    expect(row.nodes.map((node) => node.x)).toEqual([0, 208, 416])
    expect(row.nodes.map((node) => node.x)).toEqual([
      0,
      NODE_WIDTH + NODE_GAP,
      2 * (NODE_WIDTH + NODE_GAP),
    ])
  })
})

describe('buildCausalRows', () => {
  it('gives an empty chapter a row with no nodes', () => {
    const data = makeData([makeChapter('c1', '第1章 空章', [])])

    const { rows } = buildCausalRows(data)
    expect(rows).toHaveLength(1)
    expect(rows[0].nodes).toEqual([])
    expect(rows[0].chapter.label).toBe('第1章 空章')
  })

  it('carries scene breaks, issues and chapter identity into the row', () => {
    const issue = {
      id: 'i1',
      layer: 'causality',
      layer_label: '因果链',
      severity: 'major',
      title: '转折没有前置因',
    }
    const data = makeData([
      makeChapter(
        'c1',
        '第1章 雨夜',
        [
          makeScene('s1', 0, {
            goal: '',
            turn: '信是假的',
            breaks: ['missing_goal', 'causality_issue'],
            issues: [issue],
            locked: true,
          }),
        ],
        '第一卷',
      ),
    ])

    const [row] = buildCausalRows(data).rows
    expect(row.chapter.volume_label).toBe('第一卷')
    expect(row.nodes[0]).toMatchObject({
      id: 's1',
      label: '场景1',
      goal: '',
      turn: '信是假的',
      breaks: ['missing_goal', 'causality_issue'],
      issues: [issue],
      locked: true,
    })
  })

  it('returns no rows for a project without chapters', () => {
    expect(buildCausalRows(makeData([]))).toEqual({
      rows: [],
      totals: { scenes: 0, breaks: 0, chapters: 0 },
    })
  })
})

describe('summarize', () => {
  it('counts scenes, breaks and chapters the same way the backend totals do', () => {
    const data = makeData([
      makeChapter('c1', '第1章', [
        makeScene('s1', 0, { breaks: ['missing_goal'] }),
        makeScene('s2', 1, { breaks: ['missing_goal', 'missing_turn'] }),
      ]),
      makeChapter('c2', '第2章', [
        makeScene('s3', 0, { breaks: ['causality_issue'] }),
        makeScene('s4', 1),
      ]),
    ])

    expect(summarize(data)).toEqual({ scenes: 4, breaks: 4, chapters: 2 })
    expect(summarize(data)).toEqual(data.totals)
  })

  it('handles missing payloads', () => {
    expect(summarize(null)).toEqual({ scenes: 0, breaks: 0, chapters: 0 })
  })
})
