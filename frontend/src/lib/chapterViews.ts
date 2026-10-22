import type { Foreshadow, VolumeNode } from '../api/client'

export interface RhythmChapter {
  id: string
  label: string
  volumeName: string
  volumeSeq: number
  chapterSeq: number
  targetWords: number | null
  conflict: number | null
  dialogue: number | null
  hook: number | null
  lines: string[]
}

export interface VolumeBand {
  id: string
  name: string
  start: number
  end: number
}

export interface RhythmSeries {
  chapters: RhythmChapter[]
  bands: VolumeBand[]
  maxTargetWords: number
  missing: {
    targetWords: number
    conflict: number
    dialogue: number
    hook: number
  }
}

export function buildRhythmSeries(volumes: VolumeNode[]): RhythmSeries {
  const chapters: RhythmChapter[] = []
  const bands: VolumeBand[] = []
  for (const volume of volumes) {
    const start = chapters.length
    for (const chapter of volume.chapters) {
      chapters.push({
        id: chapter.id,
        label: `第${chapter.seq + 1}章 ${chapter.title}`,
        volumeName: volume.name,
        volumeSeq: volume.seq,
        chapterSeq: chapter.seq,
        targetWords: chapter.target_words,
        conflict: chapter.conflict_level,
        dialogue: chapter.dialogue_ratio,
        hook: chapter.hook_strength,
        lines: chapter.lines,
      })
    }
    bands.push({ id: volume.id, name: volume.name, start, end: chapters.length })
  }
  const maxTargetWords = chapters.reduce(
    (max, chapter) => Math.max(max, chapter.targetWords ?? 0),
    1,
  )
  return {
    chapters,
    bands,
    maxTargetWords,
    missing: {
      targetWords: chapters.filter((chapter) => chapter.targetWords == null).length,
      conflict: chapters.filter((chapter) => chapter.conflict == null).length,
      dialogue: chapters.filter((chapter) => chapter.dialogue == null).length,
      hook: chapters.filter((chapter) => chapter.hook == null).length,
    },
  }
}

export interface LedgerLocation {
  volumeSeq: number
  volumeName: string
  chapterSeq: number
  chapterTitle: string
  sceneId: string
  sceneSeq: number
  shortLabel: string
  fullLabel: string
}

export type LedgerFilter =
  | 'all'
  | 'missing_plant'
  | 'missing_pay'
  | 'unpaid'
  | 'dropped'

export interface LedgerRow {
  id: string
  name: string
  note: string
  status: string
  /** 位置字段反映的事实；显式 `dropped` 例外。界面显示的是这个。 */
  effectiveStatus: string
  statusLabel: string
  statusIsDerived: boolean
  /** 存量数据里的旧词表值（`confirmed`），界面要标出来。 */
  statusIsLegacy: boolean
  plant: LedgerLocation | null
  pay: LedgerLocation | null
  actualPay: LedgerLocation | null
  missingPlant: boolean
  missingPay: boolean
  unpaid: boolean
  sameScene: boolean
}

function locationOf(
  volume: VolumeNode,
  chapterSeq: number,
  chapterTitle: string,
  sceneId: string,
  sceneSeq: number,
): LedgerLocation {
  const volumeNo = volume.seq + 1
  const chapterNo = chapterSeq + 1
  const sceneNo = sceneSeq + 1
  return {
    volumeSeq: volume.seq,
    volumeName: volume.name,
    chapterSeq,
    chapterTitle,
    sceneId,
    sceneSeq,
    shortLabel: `第${volumeNo}卷·第${chapterNo}章·场景${sceneNo}`,
    fullLabel: `第${volumeNo}卷《${volume.name}》·第${chapterNo}章《${chapterTitle}》·场景${sceneNo}`,
  }
}

function sceneIndex(volumes: VolumeNode[]): Map<string, LedgerLocation> {
  const index = new Map<string, LedgerLocation>()
  for (const volume of volumes) {
    for (const chapter of volume.chapters) {
      for (const scene of chapter.scenes) {
        index.set(
          scene.id,
          locationOf(volume, chapter.seq, chapter.title, scene.id, scene.seq),
        )
      }
    }
  }
  return index
}

function compareNames(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0
}

function compareLedgerRows(a: LedgerRow, b: LedgerRow): number {
  if (a.missingPlant !== b.missingPlant) return a.missingPlant ? -1 : 1
  if (a.plant && b.plant) {
    if (a.plant.volumeSeq !== b.plant.volumeSeq) {
      return a.plant.volumeSeq - b.plant.volumeSeq
    }
    if (a.plant.chapterSeq !== b.plant.chapterSeq) {
      return a.plant.chapterSeq - b.plant.chapterSeq
    }
    if (a.plant.sceneSeq !== b.plant.sceneSeq) {
      return a.plant.sceneSeq - b.plant.sceneSeq
    }
  }
  return compareNames(a.name, b.name)
}

export function buildForeshadowLedger(
  volumes: VolumeNode[],
  foreshadows: Foreshadow[],
): LedgerRow[] {
  const index = sceneIndex(volumes)
  const rows = foreshadows.map((foreshadow) => {
    const plant = foreshadow.plant_scene_id
      ? index.get(foreshadow.plant_scene_id) ?? null
      : null
    const pay = foreshadow.plan_pay_scene_id
      ? index.get(foreshadow.plan_pay_scene_id) ?? null
      : null
    const actualPay = foreshadow.actual_pay_scene_id
      ? index.get(foreshadow.actual_pay_scene_id) ?? null
      : null
    const effectiveStatus = foreshadow.effective_status ?? foreshadow.status
    return {
      id: foreshadow.id,
      name: foreshadow.name,
      note: foreshadow.note,
      status: foreshadow.status,
      effectiveStatus,
      statusLabel: foreshadow.status_label ?? effectiveStatus,
      statusIsDerived: foreshadow.status_is_derived ?? false,
      statusIsLegacy: foreshadow.status_is_legacy ?? false,
      plant,
      pay,
      actualPay,
      missingPlant: plant === null,
      missingPay: pay === null,
      // 未回收：还没收，也不是作者放弃的，且确实埋设或计划回收过。
      // 完全没安排的伏笔不计入 —— 与成品报告的 `is_unrecovered` 同一口径。
      // 位置与状态**都要看**：`effective_status` 缺失时（旧响应 / 测试夹具）
      // 只看状态会漏掉「实际回收位置已经有了」这个事实。
      unpaid:
        actualPay === null &&
        effectiveStatus !== 'paid' &&
        effectiveStatus !== 'dropped' &&
        (plant !== null || pay !== null),
      sameScene: plant !== null && pay !== null && plant.sceneId === pay.sceneId,
    }
  })
  return rows.sort(compareLedgerRows)
}

export function filterLedger(rows: LedgerRow[], filter: LedgerFilter): LedgerRow[] {
  if (filter === 'missing_plant') return rows.filter((row) => row.missingPlant)
  if (filter === 'missing_pay') return rows.filter((row) => row.missingPay)
  if (filter === 'unpaid') return rows.filter((row) => row.unpaid)
  if (filter === 'dropped') {
    return rows.filter((row) => row.effectiveStatus === 'dropped')
  }
  return rows
}

export interface SwimlaneChapter {
  id: string
  label: string
  volumeSeq: number
  chapterSeq: number
  volumeName: string
}

export interface SwimlaneRow {
  name: string
  cells: boolean[]
  count: number
}

export interface SwimlaneModel {
  chapters: SwimlaneChapter[]
  bands: VolumeBand[]
  rows: SwimlaneRow[]
}

export function buildSwimlanes(volumes: VolumeNode[]): SwimlaneModel {
  const chapters: SwimlaneChapter[] = []
  const bands: VolumeBand[] = []
  const rowsByName = new Map<string, SwimlaneRow>()
  for (const volume of volumes) {
    const start = chapters.length
    for (const chapter of volume.chapters) {
      const column = chapters.length
      chapters.push({
        id: chapter.id,
        label: `第${chapter.seq + 1}章 ${chapter.title}`,
        volumeSeq: volume.seq,
        chapterSeq: chapter.seq,
        volumeName: volume.name,
      })
      const seen = new Set<string>()
      const names = Array.isArray(chapter.lines) ? chapter.lines : []
      for (const raw of names) {
        const name = String(raw).trim()
        if (!name || seen.has(name)) continue
        seen.add(name)
        let row = rowsByName.get(name)
        if (row === undefined) {
          row = {
            name,
            cells: Array.from({ length: chapters.length }, () => false),
            count: 0,
          }
          rowsByName.set(name, row)
        }
        while (row.cells.length < chapters.length) row.cells.push(false)
        row.cells[column] = true
        row.count += 1
      }
    }
    bands.push({ id: volume.id, name: volume.name, start, end: chapters.length })
  }
  const rows = Array.from(rowsByName.values())
  for (const row of rows) {
    while (row.cells.length < chapters.length) row.cells.push(false)
  }
  rows.sort((a, b) => {
    const firstA = a.cells.indexOf(true)
    const firstB = b.cells.indexOf(true)
    if (firstA !== firstB) return firstA - firstB
    return compareNames(a.name, b.name)
  })
  return { chapters, bands, rows }
}
