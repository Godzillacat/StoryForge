import { describe, expect, it } from 'vitest'
import type { Foreshadow, SceneNode, VolumeNode } from '../api/client'
import {
  buildForeshadowLedger,
  buildRhythmSeries,
  buildSwimlanes,
  filterLedger,
} from './chapterViews'

function makeChapter(
  id: string,
  seq: number,
  title: string,
  overrides: Partial<VolumeNode['chapters'][number]> = {},
): VolumeNode['chapters'][number] {
  return {
    id,
    volume_id: 'v',
    seq,
    title,
    pov: '',
    target_words: null,
    emotional_tone: '',
    lines: [],
    hook: '',
    summary: '',
    conflict_level: null,
    dialogue_ratio: null,
    hook_strength: null,
    status: 'planned',
    source_run_id: null,
    scenes: [],
    ...overrides,
  }
}

function makeScene(
  id: string,
  chapterId: string,
  seq: number,
  overrides: Partial<SceneNode> = {},
): SceneNode {
  return {
    id,
    chapter_id: chapterId,
    seq,
    goal: '',
    conflict: '',
    turn: '',
    characters: [],
    location_id: null,
    story_time: '',
    pov: '',
    target_words_min: null,
    target_words_max: null,
    status: 'planned',
    source_run_id: null,
    has_body: false,
    foreshadows: { plants: [], pays: [], actual_pays: [] },
    ...overrides,
  }
}

function makeVolume(
  id: string,
  seq: number,
  name: string,
  chapters: VolumeNode['chapters'],
): VolumeNode {
  return {
    id,
    project_id: 'p',
    seq,
    name,
    purpose: '',
    summary: '',
    act_seq: null,
    target_words: null,
    status: 'planned',
    source_run_id: null,
    chapters,
  }
}

function makeForeshadow(
  id: string,
  name: string,
  overrides: Partial<Foreshadow> = {},
): Foreshadow {
  return {
    id,
    project_id: 'p',
    name,
    note: '',
    plant_scene_id: null,
    plan_pay_scene_id: null,
    actual_pay_scene_id: null,
    status: 'planned',
    source_run_id: null,
    ...overrides,
  }
}

function rhythmVolumes(): VolumeNode[] {
  return [
    makeVolume('v1', 0, '第一卷', [
      makeChapter('c1', 0, '开端', {
        target_words: 3000,
        conflict_level: 2,
        dialogue_ratio: 0.4,
        hook_strength: 3,
        lines: ['主线'],
      }),
      makeChapter('c2', 1, '转折', {
        target_words: null,
        conflict_level: null,
        dialogue_ratio: 0,
        hook_strength: null,
      }),
    ]),
    makeVolume('v2', 1, '第二卷', [
      makeChapter('c3', 0, '再起', {
        target_words: 5000,
        conflict_level: 5,
        dialogue_ratio: 1,
        hook_strength: 4,
      }),
    ]),
  ]
}

describe('buildRhythmSeries', () => {
  it('按卷序与章序扁平化，并给出卷分带', () => {
    const series = buildRhythmSeries(rhythmVolumes())
    expect(series.chapters.map((chapter) => chapter.id)).toEqual(['c1', 'c2', 'c3'])
    expect(series.chapters[0]).toMatchObject({
      label: '第1章 开端',
      volumeName: '第一卷',
      volumeSeq: 0,
      chapterSeq: 0,
    })
    expect(series.chapters[2].label).toBe('第1章 再起')
    expect(series.bands).toEqual([
      { id: 'v1', name: '第一卷', start: 0, end: 2 },
      { id: 'v2', name: '第二卷', start: 2, end: 3 },
    ])
  })

  it('null 保留为未评，0 是有效值', () => {
    const series = buildRhythmSeries(rhythmVolumes())
    expect(series.chapters[1].dialogue).toBe(0)
    expect(series.chapters[1].conflict).toBeNull()
    expect(series.missing).toEqual({
      targetWords: 1,
      conflict: 1,
      dialogue: 0,
      hook: 1,
    })
  })

  it('目标字数最大值至少为 1', () => {
    expect(buildRhythmSeries(rhythmVolumes()).maxTargetWords).toBe(5000)
    expect(buildRhythmSeries([]).maxTargetWords).toBe(1)
    expect(buildRhythmSeries([makeVolume('v', 0, '空卷', [])]).maxTargetWords).toBe(1)
  })
})

function ledgerVolumes(): VolumeNode[] {
  const c1 = makeChapter('c1', 0, '开端', {
    scenes: [makeScene('s1', 'c1', 0), makeScene('s2', 'c1', 1)],
  })
  const c2 = makeChapter('c2', 1, '转折', {
    scenes: [makeScene('s3', 'c2', 0)],
  })
  const c3 = makeChapter('c3', 0, '再起', {
    scenes: [makeScene('s4', 'c3', 0)],
  })
  return [
    makeVolume('v1', 0, '第一卷', [c1, c2]),
    makeVolume('v2', 1, '第二卷', [c3]),
  ]
}

function ledgerForeshadows(): Foreshadow[] {
  return [
    makeForeshadow('f2', '缺埋设乙', { plan_pay_scene_id: 's1' }),
    makeForeshadow('f3', '缺回收甲', { plant_scene_id: 's1' }),
    makeForeshadow('f4', '同场丙', {
      plant_scene_id: 's2',
      plan_pay_scene_id: 's2',
      actual_pay_scene_id: 's2',
    }),
    makeForeshadow('f1', '跨卷伏笔', {
      plant_scene_id: 's3',
      plan_pay_scene_id: 's4',
      actual_pay_scene_id: 's4',
    }),
    makeForeshadow('f5', '坏外键丁', { plant_scene_id: 'gone' }),
  ]
}

describe('buildForeshadowLedger', () => {
  it('把两端解析成卷 / 章 / 场景，并按规则排序', () => {
    const rows = buildForeshadowLedger(ledgerVolumes(), ledgerForeshadows())
    expect(rows.map((row) => row.id)).toEqual(['f5', 'f2', 'f3', 'f4', 'f1'])
    const f1 = rows.find((row) => row.id === 'f1')!
    expect(f1.plant?.shortLabel).toBe('第1卷·第2章·场景1')
    expect(f1.pay?.shortLabel).toBe('第2卷·第1章·场景1')
    expect(f1.plant?.fullLabel).toBe('第1卷《第一卷》·第2章《转折》·场景1')
  })

  it('缺失与同场标记', () => {
    const rows = buildForeshadowLedger(ledgerVolumes(), ledgerForeshadows())
    const byId = new Map(rows.map((row) => [row.id, row]))
    expect(byId.get('f2')!.missingPlant).toBe(true)
    expect(byId.get('f2')!.plant).toBeNull()
    expect(byId.get('f2')!.missingPay).toBe(false)
    expect(byId.get('f3')!.missingPay).toBe(true)
    expect(byId.get('f4')!.sameScene).toBe(true)
    expect(byId.get('f4')!.actualPay?.shortLabel).toBe('第1卷·第1章·场景2')
    expect(byId.get('f2')!.unpaid).toBe(true)
    expect(byId.get('f4')!.unpaid).toBe(false)
    expect(byId.get('f5')!.missingPlant).toBe(true)
    expect(byId.get('f1')!.missingPlant).toBe(false)
    expect(byId.get('f1')!.missingPay).toBe(false)
  })

  it('筛选按字面语义', () => {
    const rows = buildForeshadowLedger(ledgerVolumes(), ledgerForeshadows())
    expect(filterLedger(rows, 'all')).toHaveLength(5)
    expect(filterLedger(rows, 'missing_plant').map((row) => row.id)).toEqual([
      'f5',
      'f2',
    ])
    expect(filterLedger(rows, 'missing_pay').map((row) => row.id)).toEqual([
      'f5',
      'f3',
    ])
    expect(filterLedger(rows, 'unpaid').map((row) => row.id)).toEqual([
      'f2',
      'f3',
    ])
  })

  it('空伏笔返回空表', () => {
    expect(buildForeshadowLedger(ledgerVolumes(), [])).toEqual([])
  })
})

function swimlaneVolumes(): VolumeNode[] {
  return [
    makeVolume('v1', 0, '第一卷', [
      makeChapter('c1', 0, '开端', { lines: ['主线', '暗线', ' 主线 '] }),
      makeChapter('c2', 1, '转折', { lines: ['暗线'] }),
    ]),
    makeVolume('v2', 1, '第二卷', [
      makeChapter('c3', 0, '再起', { lines: ['副线'] }),
      makeChapter('c4', 1, '收束', { lines: [] }),
    ]),
  ]
}

describe('buildSwimlanes', () => {
  it('按首次出现排序、章内去重、保留无线章', () => {
    const model = buildSwimlanes(swimlaneVolumes())
    expect(model.chapters.map((chapter) => chapter.id)).toEqual([
      'c1',
      'c2',
      'c3',
      'c4',
    ])
    expect(model.chapters[2].chapterSeq).toBe(0)
    expect(model.rows.map((row) => row.name)).toEqual(['主线', '暗线', '副线'])
    expect(model.rows[0].cells).toEqual([true, false, false, false])
    expect(model.rows[0].count).toBe(1)
    expect(model.rows[1].cells).toEqual([true, true, false, false])
    expect(model.rows[1].count).toBe(2)
    expect(model.rows[2].cells).toEqual([false, false, true, false])
    expect(model.bands).toEqual([
      { id: 'v1', name: '第一卷', start: 0, end: 2 },
      { id: 'v2', name: '第二卷', start: 2, end: 4 },
    ])
  })

  it('无线时行为空，不抛错', () => {
    const model = buildSwimlanes([
      makeVolume('v', 0, '第一卷', [makeChapter('c', 0, '无')]),
    ])
    expect(model.rows).toEqual([])
    expect(model.chapters).toHaveLength(1)
  })

  it('空树不抛错', () => {
    expect(buildSwimlanes([])).toEqual({ chapters: [], bands: [], rows: [] })
  })
})
