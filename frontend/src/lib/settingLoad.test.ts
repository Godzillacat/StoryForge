import { describe, expect, it } from 'vitest'
import type { SettingLoadChapter, SettingLoadData } from '../api/client'
import { COL_W, buildLoadSeries } from './settingLoad'

function makeChapter(
  id: string,
  label: string,
  overrides: Partial<SettingLoadChapter> = {},
): SettingLoadChapter {
  return {
    id,
    label,
    volume_label: '第一卷',
    has_body: true,
    chars: 1000,
    new_terms: [],
    new_count: 0,
    mentions: 0,
    density: 0,
    ...overrides,
  }
}

function makeData(chapters: SettingLoadChapter[]): SettingLoadData {
  return {
    chapters,
    // totals 由后端算，布局不重新数；这里只求形状完整。
    totals: { entries: 0, delivered: 0, never_seen: 0, ambiguities: 0 },
    reason: '',
  }
}

describe('buildLoadSeries', () => {
  it('lays chapters out left to right with a fixed stride', () => {
    const data = makeData([
      makeChapter('c1', '第1章 雨夜', { new_count: 3, density: 4.4 }),
      makeChapter('c2', '第2章 雾港', { new_count: 1, density: 1.2 }),
      makeChapter('c3', '第3章 退潮', { new_count: 5, density: 8.1 }),
    ])

    const series = buildLoadSeries(data)

    expect(series.chapters.map((chapter) => chapter.x)).toEqual([0, COL_W, 2 * COL_W])
    expect(series.chapters.map((chapter) => chapter.id)).toEqual(['c1', 'c2', 'c3'])
    expect(series.chapters.map((chapter) => chapter.label)).toEqual([
      '第1章 雨夜',
      '第2章 雾港',
      '第3章 退潮',
    ])
    expect(series.chapters.map((chapter) => chapter.newCount)).toEqual([3, 1, 5])
    expect(series.chapters.map((chapter) => chapter.density)).toEqual([4.4, 1.2, 8.1])
  })

  it('keeps the real maxima when there is data', () => {
    const data = makeData([
      makeChapter('c1', '第1章', { new_count: 2, density: 0.4 }),
      makeChapter('c2', '第2章', { new_count: 6, density: 4.4 }),
    ])

    const series = buildLoadSeries(data)
    // 不能被「至少 1」的兜底压成 1：密度小于 1 是正常的。
    expect(series.maxNew).toBe(6)
    expect(series.maxDensity).toBe(4.4)
  })

  it('falls back to 1 for both maxima so the chart never divides by zero', () => {
    const allZero = buildLoadSeries(
      makeData([
        makeChapter('c1', '第1章'),
        makeChapter('c2', '第2章'),
      ]),
    )
    expect(allZero.maxNew).toBe(1)
    expect(allZero.maxDensity).toBe(1)

    const empty = buildLoadSeries(makeData([]))
    expect(empty.chapters).toEqual([])
    expect(empty.maxNew).toBe(1)
    expect(empty.maxDensity).toBe(1)
  })

  it('returns no chapters for a missing payload', () => {
    expect(buildLoadSeries(null).chapters).toEqual([])
    expect(buildLoadSeries(undefined).chapters).toEqual([])
  })

  it('marks chapters without body so the view can gray them out', () => {
    const data = makeData([
      makeChapter('c1', '第1章 雨夜', { new_count: 3, density: 4.4, mentions: 9, chars: 2100 }),
      makeChapter('c2', '第2章 未写', { has_body: false, chars: 0 }),
    ])

    const series = buildLoadSeries(data)

    expect(series.chapters.map((chapter) => chapter.hasBody)).toEqual([true, false])
    // 没写正文的章仍占一列（灰显），不能从轴上消失。
    expect(series.chapters[1].x).toBe(COL_W)
    expect(series.chapters[1].newCount).toBe(0)
    expect(series.chapters[1].density).toBe(0)
  })

  it('carries the numbers the tooltip shows', () => {
    const series = buildLoadSeries(
      makeData([
        makeChapter('c1', '第1章', { new_count: 3, mentions: 14, chars: 3200, density: 4.4 }),
      ]),
    )

    expect(series.chapters[0]).toMatchObject({
      newCount: 3,
      mentions: 14,
      chars: 3200,
      density: 4.4,
      volumeLabel: '第一卷',
    })
  })

  it('keeps the volume label so identical chapter numbers across volumes are distinguishable', () => {
    const data = makeData([
      makeChapter('v1c1', '第1章 雨夜', { volume_label: '第一卷' }),
      makeChapter('v2c1', '第1章 退潮', { volume_label: '第二卷' }),
    ])

    expect(buildLoadSeries(data).chapters.map((chapter) => chapter.volumeLabel)).toEqual([
      '第一卷',
      '第二卷',
    ])
  })

  it('scales by the chapters that actually have body', () => {
    // 后端不会给无正文章非零值；万一给了，也不能把它算进柱高分母，
    // 否则有正文的柱会被压扁。
    const data = makeData([
      makeChapter('c1', '第1章', { new_count: 2, density: 3 }),
      makeChapter('c2', '第2章 未写', { has_body: false, new_count: 99, density: 99 }),
    ])

    const series = buildLoadSeries(data)
    expect(series.maxNew).toBe(2)
    expect(series.maxDensity).toBe(3)
  })
})
