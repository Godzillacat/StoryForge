import { describe, expect, it } from 'vitest'
import type {
  CharacterDriftCell,
  CharacterDriftData,
  CharacterDriftRow,
} from '../api/client'
import { buildDriftGrid } from './characterDrift'

function makeCell(
  chapterId: string,
  label: string,
  note: string,
  changed: boolean,
): CharacterDriftCell {
  return { chapter_id: chapterId, label, note, changed }
}

function makeRow(
  entryId: string,
  name: string,
  cells: CharacterDriftCell[],
  overrides: Partial<CharacterDriftRow> = {},
): CharacterDriftRow {
  return {
    entry_id: entryId,
    name,
    cells,
    changes: cells.filter((cell) => cell.changed).length,
    recorded: cells.length,
    ...overrides,
  }
}

function makeData(overrides: Partial<CharacterDriftData> = {}): CharacterDriftData {
  return {
    characters: [],
    chapters: [
      { id: 'c1', label: '第1章 雨夜' },
      { id: 'c2', label: '第2章 雾港' },
    ],
    totals: { characters: 0, changes: 0, sparse: 0 },
    reason: '',
    ...overrides,
  }
}

describe('buildDriftGrid', () => {
  it('aligns each character cells to the chapter order and leaves gaps null', () => {
    const data = makeData({
      chapters: [
        { id: 'c1', label: '第1章 雨夜' },
        { id: 'c2', label: '第2章 雾港' },
        { id: 'c3', label: '第3章 退潮' },
        { id: 'c4', label: '第4章 归航' },
      ],
      characters: [
        // 服务端的 cells 只含有记录的章，且这里故意乱序：对齐必须按章来，
        // 不能按数组下标 —— 否则「第3章」的状态会显示在「第2章」列上。
        makeRow('e1', '阿明', [
          makeCell('c3', '第3章 退潮', '决意', true),
          makeCell('c1', '第1章 雨夜', '犹豫', false),
        ]),
      ],
      totals: { characters: 1, changes: 1, sparse: 0 },
    })

    const grid = buildDriftGrid(data)

    expect(grid.chapters.map((chapter) => chapter.id)).toEqual(['c1', 'c2', 'c3', 'c4'])
    expect(grid.rows).toHaveLength(1)
    const row = grid.rows[0]
    expect(row.entryId).toBe('e1')
    expect(row.name).toBe('阿明')
    expect(row.cells).toHaveLength(4)
    expect(row.cells[0]).toMatchObject({ chapterId: 'c1', note: '犹豫', changed: false })
    expect(row.cells[1]).toBeNull()
    expect(row.cells[2]).toMatchObject({ chapterId: 'c3', note: '决意', changed: true })
    expect(row.cells[3]).toBeNull()
  })

  it('keeps an unchanged record as a cell, not as a gap', () => {
    // 「没记录」（null）与「记录过但没变」（changed=false）不是一件事：
    // 把后者画成空白会抹掉作者确认过的状态。
    const data = makeData({
      characters: [
        makeRow('e1', '阿明', [
          makeCell('c1', '第1章 雨夜', '犹豫', false),
          makeCell('c2', '第2章 雾港', '犹豫', false),
        ]),
      ],
      totals: { characters: 1, changes: 0, sparse: 0 },
    })

    const cells = buildDriftGrid(data).rows[0].cells
    expect(cells[1]).not.toBeNull()
    expect(cells[1]?.changed).toBe(false)
    expect(cells[1]?.note).toBe('犹豫')
  })

  it('returns no rows for empty or missing data', () => {
    expect(buildDriftGrid(null).rows).toEqual([])
    expect(buildDriftGrid(undefined).rows).toEqual([])
    expect(buildDriftGrid(null).chapters).toEqual([])

    const empty = buildDriftGrid(makeData())
    expect(empty.rows).toEqual([])
    expect(empty.chapters).toHaveLength(2)
    expect(empty.totals).toEqual({ characters: 0, changes: 0, sparse: 0 })
  })

  it('passes the server totals and per-row counts through unchanged', () => {
    // 变化判定在服务端（与「上一条记录」比）。前端只排版，不重算。
    const data = makeData({
      characters: [
        makeRow('e1', '阿明', [makeCell('c1', '第1章 雨夜', '犹豫', false)], {
          changes: 0,
          recorded: 1,
        }),
        makeRow(
          'e2',
          '阿岚',
          [
            makeCell('c1', '第1章 雨夜', '怯', false),
            makeCell('c2', '第2章 雾港', '狠', true),
          ],
          { changes: 1, recorded: 2 },
        ),
      ],
      totals: { characters: 2, changes: 1, sparse: 1 },
    })

    const grid = buildDriftGrid(data)
    expect(grid.rows.map((row) => row.changes)).toEqual([0, 1])
    expect(grid.rows.map((row) => row.recorded)).toEqual([1, 2])
    expect(grid.totals).toEqual({ characters: 2, changes: 1, sparse: 1 })
  })

  it('drops cells for chapters that are not in the chapter list', () => {
    // 章被删掉后状态行也会级联删除；万一还有残留，宁可少一格，也不能错位。
    const data = makeData({
      characters: [
        makeRow('e1', '阿明', [
          makeCell('c1', '第1章 雨夜', '犹豫', false),
          makeCell('c9', '第9章 已经不在了', '决意', true),
        ]),
      ],
    })

    const row = buildDriftGrid(data).rows[0]
    expect(row.cells).toHaveLength(2)
    expect(row.cells.filter((cell) => cell !== null)).toHaveLength(1)
    expect(row.cells[0]?.chapterId).toBe('c1')
  })

  it('carries the volume label so same-numbered chapters stay distinguishable', () => {
    // 两卷都可能有「第1章 雨夜」：表头截断后只剩「第1章 …」，悬停提示得靠卷名分开。
    const data = makeData({
      chapters: [
        { id: 'v1c1', label: '第1章 雨夜', volume_label: '第一卷' },
        { id: 'v2c1', label: '第1章 雨夜', volume_label: '第二卷' },
      ],
      characters: [
        makeRow('e1', '阿明', [
          makeCell('v1c1', '第1章 雨夜', '犹豫', false),
          makeCell('v2c1', '第1章 雨夜', '决意', true),
        ]),
      ],
    })

    const grid = buildDriftGrid(data)
    expect(grid.chapters.map((chapter) => chapter.volumeLabel)).toEqual(['第一卷', '第二卷'])
    // 格子各自落在自己的卷的列上，不会被同名标签挤到同一列。
    expect(grid.rows[0].cells[0]?.note).toBe('犹豫')
    expect(grid.rows[0].cells[1]?.note).toBe('决意')
  })

  it('falls back to an empty volume label when the payload has none', () => {
    expect(buildDriftGrid(makeData()).chapters.map((chapter) => chapter.volumeLabel)).toEqual([
      '',
      '',
    ])
  })

  it('labels cells from the chapter list so headers and cells always agree', () => {
    const data = makeData({
      chapters: [{ id: 'c1', label: '第1章 雨夜（改过标题）' }],
      characters: [
        // 状态行里的 label 可能是旧标题；列的真相是 chapters。
        makeRow('e1', '阿明', [makeCell('c1', '第1章 雨夜', '犹豫', false)]),
      ],
    })

    const grid = buildDriftGrid(data)
    expect(grid.chapters[0].label).toBe('第1章 雨夜（改过标题）')
    expect(grid.rows[0].cells[0]?.label).toBe('第1章 雨夜（改过标题）')
  })
})
