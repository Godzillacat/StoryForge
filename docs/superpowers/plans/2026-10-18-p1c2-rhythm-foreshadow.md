# P1c-2 节奏 / 伏笔 / 剧情线视图 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `/chapters` 页内加三个只读视图：节奏曲线、伏笔账本、剧情线泳道，全部由现有树与伏笔接口派生。

**Architecture:** 纯前端投影。`frontend/src/lib/chapterViews.ts` 负责扁平化、连接、排序与分组，vitest 覆盖；三个组件只渲染；`Chapters.tsx` 加页签、加载态、统一请求代际与「跳回结构设计」。

**Tech Stack:** React 19 + TypeScript 6 + Vite 7 + Tailwind 3 + vitest；手写 SVG，不引入图表库。

**Spec:** `docs/superpowers/specs/2026-10-18-p1c2-rhythm-foreshadow-design.md`

## Global Constraints

- **纯前端**：不改后端、不建表、不迁移、不加依赖、不调用模型、不消耗模型额度。
- 数据只来自现有 `GET /api/projects/{id}/chapters/tree`、`GET /api/projects/{id}/foreshadows`、`GET /api/chapter-types`。
- **`null` = 未评，`0` = 有效值**；曲线在 `null` 处断开，不插值、不转 0。
- 显示给作者的章号一律是**卷内序号 `seq + 1`**；位置标签形如 `第1卷·第2章·场景1`。
- 节奏图里的「字数」只显示 `target_words`，文案必须写「目标字数」，不得冒充实际字数。
- 伏笔状态列表头写「规划状态」，沿用 `planned / confirmed` 的中文标签；生命周期状态属 P4。
- 三个视图都是**只读**；点击位置只做「切回结构设计并选中」。
- 项目约定：纯逻辑用 vitest 覆盖，UI 不写自动化测试。
- 所有 UI 文案用中文；标识符用英文。
- 提交信息用中文，前缀沿用 `feat(frontend):` / `docs:`。

---

## File Structure

| 文件 | 责任 |
|---|---|
| `frontend/src/lib/chapterViews.ts` | 纯投影：节奏序列、伏笔账本、泳道；不依赖 React |
| `frontend/src/lib/chapterViews.test.ts` | 上述纯函数的所有测试 |
| `frontend/src/components/chapters/RhythmCurve.tsx` | 四行小多图 SVG 与点击/悬停 |
| `frontend/src/components/chapters/ForeshadowLedger.tsx` | 只读账本表格、筛选、位置跳转 |
| `frontend/src/components/chapters/Swimlanes.tsx` | 线 × 章泳道表 |
| `frontend/src/pages/Chapters.tsx` | 页签、加载态、请求代际、跳转接线 |
| `docs/superpowers/plans/2026-10-18-p1c2-walkthrough.md` | 手工走查清单与结果 |
| `CLAUDE.md` | 路线图、阶段记录、变更记录 |

---

### Task 1: 纯投影函数与测试

**Files:**
- Create: `frontend/src/lib/chapterViews.ts`
- Test: `frontend/src/lib/chapterViews.test.ts`

**Interfaces:**
- Consumes: `VolumeNode` / `ChapterNode` / `SceneNode` / `Foreshadow`（`frontend/src/api/client.ts`）。
- Produces:
  - `buildRhythmSeries(volumes: VolumeNode[]): RhythmSeries`
  - `buildForeshadowLedger(volumes: VolumeNode[], foreshadows: Foreshadow[]): LedgerRow[]`
  - `filterLedger(rows: LedgerRow[], filter: LedgerFilter): LedgerRow[]`
  - `buildSwimlanes(volumes: VolumeNode[]): SwimlaneModel`
  - 类型：`RhythmChapter` / `VolumeBand` / `RhythmSeries` / `LedgerLocation` / `LedgerFilter` / `LedgerRow` / `SwimlaneChapter` / `SwimlaneRow` / `SwimlaneModel`

- [ ] **Step 1: 写失败测试**

Create `frontend/src/lib/chapterViews.test.ts`:

```ts
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
    foreshadows: { plants: [], pays: [] },
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
    makeForeshadow('f1', '跨卷伏笔', {
      plant_scene_id: 's3',
      plan_pay_scene_id: 's4',
    }),
    makeForeshadow('f2', '缺埋设乙', { plan_pay_scene_id: 's1' }),
    makeForeshadow('f3', '缺回收甲', { plant_scene_id: 's1' }),
    makeForeshadow('f4', '同场丙', {
      plant_scene_id: 's2',
      plan_pay_scene_id: 's2',
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
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```bash
cd "D:/Practical Project/AIProject/Experiment/StoryForge/frontend" && pnpm vitest run src/lib/chapterViews.test.ts
```

Expected: FAIL，模块 `./chapterViews` 不存在或导出的函数未定义。

- [ ] **Step 3: 写实现**

Create `frontend/src/lib/chapterViews.ts`:

```ts
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

export type LedgerFilter = 'all' | 'missing_plant' | 'missing_pay'

export interface LedgerRow {
  id: string
  name: string
  note: string
  status: string
  plant: LedgerLocation | null
  pay: LedgerLocation | null
  missingPlant: boolean
  missingPay: boolean
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
    return {
      id: foreshadow.id,
      name: foreshadow.name,
      note: foreshadow.note,
      status: foreshadow.status,
      plant,
      pay,
      missingPlant: plant === null,
      missingPay: pay === null,
      sameScene: plant !== null && pay !== null && plant.sceneId === pay.sceneId,
    }
  })
  return rows.sort(compareLedgerRows)
}

export function filterLedger(rows: LedgerRow[], filter: LedgerFilter): LedgerRow[] {
  if (filter === 'missing_plant') return rows.filter((row) => row.missingPlant)
  if (filter === 'missing_pay') return rows.filter((row) => row.missingPay)
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
```

- [ ] **Step 4: 跑测试确认通过**

Run:

```bash
cd "D:/Practical Project/AIProject/Experiment/StoryForge/frontend" && pnpm vitest run src/lib/chapterViews.test.ts
```

Expected: PASS（10 个新用例）。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/lib/chapterViews.ts frontend/src/lib/chapterViews.test.ts
git commit -m "feat(frontend): 章节视图纯投影函数与测试"
```

---

### Task 2: 节奏曲线组件

**Files:**
- Create: `frontend/src/components/chapters/RhythmCurve.tsx`

**Interfaces:**
- Consumes: `buildRhythmSeries(volumes)`；`VolumeNode`。
- Produces: `<RhythmCurve volumes={VolumeNode[]} onSelectChapter={(id: string) => void} />`。

- [ ] **Step 0: 按 dataviz 技能核对图表规范**

调用 `dataviz` 技能，核对深色底上三条序列的配色、虚线区分、坐标轴与标记。若技能给出更合适的色值或线宽，按技能调整下面代码里的 `#818cf8` / `#34d399` / `#fbbf24` 与网格色；**四行小多图、`null` 断线、`0` 保留、点击跳转的结构不变**。

- [ ] **Step 1: 写组件**

Create `frontend/src/components/chapters/RhythmCurve.tsx`:

```tsx
import type { VolumeNode } from '../../api/client'
import { buildRhythmSeries } from '../../lib/chapterViews'

const COL_WIDTH = 44
const LABEL_WIDTH = 88
const RIGHT_PAD = 16
const TOP = 32
const ROW_HEIGHT = 88
const ROW_GAP = 12
const DIALOGUE_HEIGHT = 64

export default function RhythmCurve({
  volumes,
  onSelectChapter,
}: {
  volumes: VolumeNode[]
  onSelectChapter: (id: string) => void
}) {
  const series = buildRhythmSeries(volumes)
  if (series.chapters.length === 0) {
    return (
      <p className="rounded border border-slate-800 p-4 text-sm text-slate-500">
        还没有卷章。去「结构设计」建卷，或先用 AI 排卷章。
      </p>
    )
  }

  const width = LABEL_WIDTH + series.chapters.length * COL_WIDTH + RIGHT_PAD
  const targetTop = TOP
  const targetBottom = targetTop + ROW_HEIGHT
  const conflictTop = targetBottom + ROW_GAP
  const conflictBottom = conflictTop + ROW_HEIGHT
  const hookTop = conflictBottom + ROW_GAP
  const hookBottom = hookTop + ROW_HEIGHT
  const dialogueTop = hookBottom + ROW_GAP
  const dialogueBottom = dialogueTop + DIALOGUE_HEIGHT
  const height = dialogueBottom + 28
  const x = (index: number) => LABEL_WIDTH + index * COL_WIDTH + COL_WIDTH / 2
  const levelY = (value: number, top: number, bottom: number) =>
    bottom - 8 - ((value - 1) / 4) * (bottom - top - 16)
  const ratioY = (value: number) =>
    dialogueBottom - 8 - value * (DIALOGUE_HEIGHT - 16)
  const path = (
    values: (number | null)[],
    yFor: (value: number) => number,
  ) => {
    let result = ''
    let open = false
    values.forEach((value, index) => {
      if (value == null) {
        open = false
        return
      }
      result += `${open ? 'L' : 'M'}${x(index)} ${yFor(value)} `
      open = true
    })
    return result.trim()
  }
  const hasAny = series.chapters.some(
    (chapter) =>
      chapter.targetWords != null ||
      chapter.conflict != null ||
      chapter.dialogue != null ||
      chapter.hook != null,
  )
  const barWidth = COL_WIDTH * 0.5
  const conflictValues = series.chapters.map((chapter) => chapter.conflict)
  const hookValues = series.chapters.map((chapter) => chapter.hook)
  const dialogueValues = series.chapters.map((chapter) => chapter.dialogue)
  const volumeOpacity = (index: number) => (index % 2 === 0 ? 0.55 : 0.2)

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-sm font-medium text-slate-300">节奏曲线</h3>
        <p className="text-xs text-slate-500">
          目标字数（P1 尚无正文，不是实际字数）· 点任意一章可回到结构设计
        </p>
      </div>
      {!hasAny && (
        <p className="rounded border border-amber-900/60 bg-amber-950/30 p-3 text-sm text-amber-300">
          章还没填节奏指标，去结构设计里补。
        </p>
      )}
      <p className="text-xs text-slate-500">
        冲突未评 {series.missing.conflict} 章 · 钩子未评 {series.missing.hook} 章 ·
        对话未评 {series.missing.dialogue} 章 · 目标字数未填{' '}
        {series.missing.targetWords} 章
      </p>
      <div className="overflow-x-auto rounded border border-slate-800 bg-slate-950 p-3">
        <svg width={width} height={height} role="img" aria-label="节奏曲线">
          {series.bands.map((band, index) =>
            band.end > band.start ? (
              <g key={band.id}>
                <rect
                  x={LABEL_WIDTH + band.start * COL_WIDTH}
                  y={TOP - 8}
                  width={(band.end - band.start) * COL_WIDTH}
                  height={dialogueBottom - TOP + 8}
                  fill="#0f172a"
                  opacity={volumeOpacity(index)}
                />
                <text
                  x={LABEL_WIDTH + ((band.start + band.end) / 2) * COL_WIDTH}
                  y={TOP - 14}
                  textAnchor="middle"
                  fill="#94a3b8"
                  fontSize={11}
                >
                  {band.name}
                </text>
              </g>
            ) : null,
          )}
          {[targetTop, conflictTop, hookTop, dialogueTop].map((top) => (
            <line
              key={top}
              x1={LABEL_WIDTH}
              x2={width - RIGHT_PAD}
              y1={top}
              y2={top}
              stroke="#1e293b"
            />
          ))}
          <text x={0} y={targetTop + 16} fill="#94a3b8" fontSize={11}>
            目标字数
          </text>
          <text x={0} y={conflictTop + 16} fill="#94a3b8" fontSize={11}>
            冲突强度
          </text>
          <text x={0} y={hookTop + 16} fill="#94a3b8" fontSize={11}>
            钩子强度
          </text>
          <text x={0} y={dialogueTop + 16} fill="#94a3b8" fontSize={11}>
            对话占比
          </text>
          {[1, 3, 5].map((level) => (
            <g key={`grid-${level}`}>
              <line
                x1={LABEL_WIDTH}
                x2={width - RIGHT_PAD}
                y1={levelY(level, conflictTop, conflictBottom)}
                y2={levelY(level, conflictTop, conflictBottom)}
                stroke="#1e293b"
                opacity={0.6}
              />
              <line
                x1={LABEL_WIDTH}
                x2={width - RIGHT_PAD}
                y1={levelY(level, hookTop, hookBottom)}
                y2={levelY(level, hookTop, hookBottom)}
                stroke="#1e293b"
                opacity={0.6}
              />
            </g>
          ))}
          {series.chapters.map((chapter, index) =>
            chapter.targetWords == null ? null : (
              <rect
                key={`bar-${chapter.id}`}
                x={x(index) - barWidth / 2}
                y={
                  targetBottom -
                  (chapter.targetWords / series.maxTargetWords) *
                    (ROW_HEIGHT - 16) -
                  8
                }
                width={barWidth}
                height={
                  (chapter.targetWords / series.maxTargetWords) *
                  (ROW_HEIGHT - 16)
                }
                fill="#6366f1"
                opacity={0.8}
              />
            ),
          )}
          <path
            d={path(conflictValues, (value) =>
              levelY(value, conflictTop, conflictBottom),
            )}
            fill="none"
            stroke="#818cf8"
            strokeWidth={2}
          />
          <path
            d={path(hookValues, (value) =>
              levelY(value, hookTop, hookBottom),
            )}
            fill="none"
            stroke="#34d399"
            strokeWidth={2}
            strokeDasharray="5 4"
          />
          <path
            d={path(dialogueValues, ratioY)}
            fill="none"
            stroke="#fbbf24"
            strokeWidth={2}
          />
          {series.chapters.map((chapter, index) => (
            <g key={`dots-${chapter.id}`}>
              {chapter.conflict != null && (
                <circle
                  cx={x(index)}
                  cy={levelY(chapter.conflict, conflictTop, conflictBottom)}
                  r={2.5}
                  fill="#818cf8"
                />
              )}
              {chapter.hook != null && (
                <circle
                  cx={x(index)}
                  cy={levelY(chapter.hook, hookTop, hookBottom)}
                  r={2.5}
                  fill="#34d399"
                />
              )}
              {chapter.dialogue != null && (
                <circle
                  cx={x(index)}
                  cy={ratioY(chapter.dialogue)}
                  r={2.5}
                  fill="#fbbf24"
                />
              )}
            </g>
          ))}
          {series.chapters.map((chapter, index) => (
            <text
              key={`x-${chapter.id}`}
              x={x(index)}
              y={height - 8}
              textAnchor="middle"
              fill="#64748b"
              fontSize={10}
            >
              {chapter.chapterSeq + 1}
            </text>
          ))}
          {series.chapters.map((chapter, index) => (
            <rect
              key={`hit-${chapter.id}`}
              x={LABEL_WIDTH + index * COL_WIDTH}
              y={TOP - 8}
              width={COL_WIDTH}
              height={dialogueBottom - TOP + 8}
              fill="transparent"
              role="button"
              tabIndex={0}
              className="cursor-pointer outline-none focus:fill-slate-800/40"
              onClick={() => onSelectChapter(chapter.id)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault()
                  onSelectChapter(chapter.id)
                }
              }}
            >
              <title>
                {`${chapter.label}（${chapter.volumeName}）
目标字数：${chapter.targetWords ?? '未填'}
冲突：${chapter.conflict ?? '未评'} · 钩子：${chapter.hook ?? '未评'} · 对话占比：${
                  chapter.dialogue == null
                    ? '未评'
                    : `${Math.round(chapter.dialogue * 100)}%`
                }
推进线：${chapter.lines.join('、') || '未填'}`}
              </title>
            </rect>
          ))}
        </svg>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 类型检查与回归测试**

Run:

```bash
cd "D:/Practical Project/AIProject/Experiment/StoryForge/frontend" && pnpm vitest run && pnpm build
```

Expected: 10 个新用例 + 既有 8 个通过；`tsc -b` 与 `vite build` 干净。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/chapters/RhythmCurve.tsx
git commit -m "feat(frontend): 节奏曲线视图"
```

---

### Task 3: 伏笔账本组件

**Files:**
- Create: `frontend/src/components/chapters/ForeshadowLedger.tsx`

**Interfaces:**
- Consumes: `buildForeshadowLedger` / `filterLedger`；`VolumeNode[]`、`Foreshadow[]`、`ChapterStatusOption[]`。
- Produces: `<ForeshadowLedger volumes foreshadows statuses onSelectScene={(id: string) => void} />`。

- [ ] **Step 1: 写组件**

Create `frontend/src/components/chapters/ForeshadowLedger.tsx`:

```tsx
import { useState } from 'react'
import type {
  ChapterStatusOption,
  Foreshadow,
  VolumeNode,
} from '../../api/client'
import {
  buildForeshadowLedger,
  filterLedger,
  type LedgerFilter,
  type LedgerLocation,
  type LedgerRow,
} from '../../lib/chapterViews'

const FILTERS: { key: LedgerFilter; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'missing_plant', label: '缺埋设' },
  { key: 'missing_pay', label: '缺计划回收' },
]

function hints(row: LedgerRow): string {
  const out: string[] = []
  if (row.missingPlant) out.push('缺埋设')
  if (row.missingPay) out.push('缺计划回收')
  if (row.sameScene) out.push('埋设与回收同一场')
  return out.join(' ')
}

function LocationCell({
  location,
  onSelect,
}: {
  location: LedgerLocation | null
  onSelect: (id: string) => void
}) {
  if (!location) return <span className="text-amber-300">未安排</span>
  return (
    <button
      className="text-left text-indigo-300 hover:underline"
      title={location.fullLabel}
      onClick={() => onSelect(location.sceneId)}
    >
      {location.shortLabel}
    </button>
  )
}

export default function ForeshadowLedger({
  volumes,
  foreshadows,
  statuses,
  onSelectScene,
}: {
  volumes: VolumeNode[]
  foreshadows: Foreshadow[]
  statuses: ChapterStatusOption[]
  onSelectScene: (id: string) => void
}) {
  const [filter, setFilter] = useState<LedgerFilter>('all')
  const rows = buildForeshadowLedger(volumes, foreshadows)
  if (foreshadows.length === 0) {
    return (
      <p className="rounded border border-slate-800 p-4 text-sm text-slate-500">
        还没有伏笔。在结构设计的场景编辑器里挂上伏笔后，这里会按故事顺序列出。
      </p>
    )
  }
  const visible = filterLedger(rows, filter)
  const labelByKey = new Map(
    statuses.map((status): [string, string] => [status.key, status.label]),
  )
  const missingPlant = rows.filter((row) => row.missingPlant).length
  const missingPay = rows.filter((row) => row.missingPay).length

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-sm font-medium text-slate-300">伏笔账本</h3>
        <p className="text-xs text-slate-500">
          共 {rows.length} 条 · 缺埋设 {missingPlant} · 缺计划回收 {missingPay}
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        {FILTERS.map((item) => (
          <button
            key={item.key}
            className={`rounded border px-3 py-1 text-sm ${
              filter === item.key
                ? 'border-indigo-500 bg-slate-800 text-white'
                : 'border-slate-700 text-slate-400 hover:bg-slate-900'
            }`}
            onClick={() => setFilter(item.key)}
          >
            {item.label}
          </button>
        ))}
      </div>
      <div className="overflow-x-auto rounded border border-slate-800">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-900 text-xs text-slate-400">
            <tr>
              <th className="px-3 py-2">名称</th>
              <th className="px-3 py-2">备注</th>
              <th className="px-3 py-2">埋设位置</th>
              <th className="px-3 py-2">计划回收位置</th>
              <th className="px-3 py-2">规划状态</th>
              <th className="px-3 py-2">提示</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((row) => (
              <tr key={row.id} className="border-t border-slate-800 align-top">
                <td className="px-3 py-2 font-medium">{row.name}</td>
                <td className="px-3 py-2 text-slate-400">
                  <span
                    className="block max-w-[16rem] truncate"
                    title={row.note}
                  >
                    {row.note || '—'}
                  </span>
                </td>
                <td className="px-3 py-2">
                  <LocationCell location={row.plant} onSelect={onSelectScene} />
                </td>
                <td className="px-3 py-2">
                  <LocationCell location={row.pay} onSelect={onSelectScene} />
                </td>
                <td className="px-3 py-2 text-slate-400">
                  {labelByKey.get(row.status) ?? row.status}
                </td>
                <td className="px-3 py-2 text-xs text-amber-300">
                  {hints(row)}
                </td>
              </tr>
            ))}
            {visible.length === 0 && (
              <tr>
                <td
                  colSpan={6}
                  className="px-3 py-4 text-center text-sm text-slate-500"
                >
                  这个筛选下没有伏笔。
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-slate-500">
        规划状态只有「规划中 / 已确认」；已埋设、已回收等生命周期状态属
        P4。本页只读，埋设与回收的挂接在结构设计的场景编辑器里改。
      </p>
    </div>
  )
}
```

- [ ] **Step 2: 类型检查与回归测试**

Run:

```bash
cd "D:/Practical Project/AIProject/Experiment/StoryForge/frontend" && pnpm vitest run && pnpm build
```

Expected: 全部通过，构建干净。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/chapters/ForeshadowLedger.tsx
git commit -m "feat(frontend): 伏笔账本视图"
```

---

### Task 4: 剧情线泳道组件

**Files:**
- Create: `frontend/src/components/chapters/Swimlanes.tsx`

**Interfaces:**
- Consumes: `buildSwimlanes(volumes)`。
- Produces: `<Swimlanes volumes={VolumeNode[]} onSelectChapter={(id: string) => void} />`。

- [ ] **Step 1: 写组件**

Create `frontend/src/components/chapters/Swimlanes.tsx`:

```tsx
import type { VolumeNode } from '../../api/client'
import { buildSwimlanes } from '../../lib/chapterViews'

export default function Swimlanes({
  volumes,
  onSelectChapter,
}: {
  volumes: VolumeNode[]
  onSelectChapter: (id: string) => void
}) {
  const model = buildSwimlanes(volumes)
  if (model.chapters.length === 0) {
    return (
      <p className="rounded border border-slate-800 p-4 text-sm text-slate-500">
        还没有卷章。去「结构设计」建卷，或先用 AI 排卷章。
      </p>
    )
  }
  if (model.rows.length === 0) {
    return (
      <p className="rounded border border-slate-800 p-4 text-sm text-slate-500">
        章还没填推进的线。在结构设计里编辑章，填「推进的线」后这里会按线分组。
      </p>
    )
  }

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-sm font-medium text-slate-300">剧情线</h3>
        <p className="text-xs text-slate-500">
          行是章里的「推进的线」，列是故事顺序的章；点格子回到该章。
        </p>
      </div>
      <div className="overflow-x-auto rounded border border-slate-800">
        <table className="text-left text-sm">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 bg-slate-900 px-3 py-2 text-xs text-slate-400">
                线
              </th>
              {model.bands
                .filter((band) => band.end > band.start)
                .map((band) => (
                  <th
                    key={band.id}
                    colSpan={band.end - band.start}
                    className="border-l border-slate-800 px-2 py-2 text-center text-xs text-slate-300"
                  >
                    {band.name}
                  </th>
                ))}
            </tr>
            <tr>
              <th className="sticky left-0 z-10 bg-slate-900 px-3 py-1 text-xs text-slate-500">
                章
              </th>
              {model.chapters.map((chapter) => (
                <th
                  key={chapter.id}
                  title={`${chapter.label}（${chapter.volumeName}）`}
                  className="border-l border-slate-800 px-1 py-1 text-center text-xs font-normal text-slate-500"
                >
                  {chapter.chapterSeq + 1}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {model.rows.map((row) => (
              <tr key={row.name} className="border-t border-slate-800">
                <th className="sticky left-0 z-10 whitespace-nowrap bg-slate-950 px-3 py-2 text-left text-xs font-medium text-slate-300">
                  {row.name}{' '}
                  <span className="text-slate-500">({row.count})</span>
                </th>
                {model.chapters.map((chapter, index) => (
                  <td
                    key={chapter.id}
                    className="border-l border-slate-800 px-1 py-1 text-center"
                  >
                    {row.cells[index] ? (
                      <button
                        className="mx-auto block h-4 w-6 rounded-sm bg-indigo-500 hover:bg-indigo-400"
                        title={`${chapter.label}（${chapter.volumeName}）`}
                        aria-label={`${chapter.label}：${row.name}`}
                        onClick={() => onSelectChapter(chapter.id)}
                      />
                    ) : (
                      <span className="block h-4 w-6" />
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 类型检查与回归测试**

Run:

```bash
cd "D:/Practical Project/AIProject/Experiment/StoryForge/frontend" && pnpm vitest run && pnpm build
```

Expected: 全部通过，构建干净。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/chapters/Swimlanes.tsx
git commit -m "feat(frontend): 剧情线泳道视图"
```

---

### Task 5: 章节页页签、加载态与跳转

**Files:**
- Modify: `frontend/src/pages/Chapters.tsx`

**Interfaces:**
- Consumes: `RhythmCurve` / `ForeshadowLedger` / `Swimlanes`；`Selection`。
- Produces: 四页签页面；`openInStructure(selection: Selection)`；统一 `dataRequestRef` 代际。

- [ ] **Step 1: 加导入、类型与状态**

在 imports 末尾加：

```tsx
import ForeshadowLedger from '../components/chapters/ForeshadowLedger'
import RhythmCurve from '../components/chapters/RhythmCurve'
import Swimlanes from '../components/chapters/Swimlanes'
```

在 `Chapters` 组件之前加：

```tsx
type ViewTab = 'structure' | 'rhythm' | 'foreshadows' | 'lanes'

const TABS: { key: ViewTab; label: string }[] = [
  { key: 'structure', label: '结构设计' },
  { key: 'rhythm', label: '节奏曲线' },
  { key: 'foreshadows', label: '伏笔账本' },
  { key: 'lanes', label: '剧情线' },
]
```

在组件状态区加：

```tsx
const [view, setView] = useState<ViewTab>('structure')
// 数据属于哪个项目：用它与 projectId 的差异推导加载态，
// 避免切项目时先闪一帧上一个项目的数据。
const [dataProjectId, setDataProjectId] = useState('')
```

把 `entriesRequestRef` 改名为 `dataRequestRef`（声明、effect、refresh、cleanup 全部同名替换），并把注释改为：

```tsx
// 每次项目级请求自增；迟到的旧项目响应凭 token 失效，
// 不能覆盖当前项目的树、条目或伏笔。
const dataRequestRef = useRef(0)
```

- [ ] **Step 2: 替换项目装载 effect**

把现有 `useEffect(() => { ... }, [projectId])` 整块替换为：

```tsx
useEffect(() => {
  if (!projectId) return
  setSelected(null)
  setNotice('')
  setVolumes([])
  setEntries([])
  setEntriesProjectId('')
  setForeshadows([])
  setDataProjectId('')
  runToken.current++
  setChapterPlan(null)
  setScenePlan(null)
  setPlanning(false)
  const token = ++dataRequestRef.current
  Promise.allSettled([
    api.getChapterTree(projectId),
    api.listForeshadows(projectId),
  ]).then(([treeResult, foreshadowResult]) => {
    if (dataRequestRef.current !== token) return
    const errors: string[] = []
    if (treeResult.status === 'fulfilled') {
      setVolumes(treeResult.value.volumes)
    } else {
      errors.push((treeResult.reason as Error).message)
    }
    if (foreshadowResult.status === 'fulfilled') {
      setForeshadows(foreshadowResult.value)
    } else {
      errors.push((foreshadowResult.reason as Error).message)
    }
    if (errors.length > 0) setNotice(errors.join('；'))
    // 两份都已有结果就结束加载态：部分失败时显示已有数据 + 页头提示。
    setDataProjectId(projectId)
  })
  api
    .listEntries(projectId)
    .then((list) => {
      if (dataRequestRef.current !== token) return
      setEntries(list)
      setEntriesProjectId(projectId)
    })
    .catch((error) => {
      if (dataRequestRef.current === token) setNotice((error as Error).message)
    })
  return () => {
    // 切项目或卸载时让在途响应过期。
    dataRequestRef.current += 1
  }
}, [projectId])
```

- [ ] **Step 3: 更新 `refresh` 与加 `openInStructure` / `viewsLoading`**

把 `refresh()` 里的 `entriesRequestRef` 全部改为 `dataRequestRef`，其余不变。

在 `deleteSelected` 之后、`return (` 之前加：

```tsx
function openInStructure(selection: Selection) {
  const chapters = volumes.flatMap((volume) => volume.chapters)
  const found =
    selection.kind === 'volume'
      ? volumes.some((volume) => volume.id === selection.id)
      : selection.kind === 'chapter'
        ? chapters.some((chapter) => chapter.id === selection.id)
        : chapters.some((chapter) =>
            chapter.scenes.some((scene) => scene.id === selection.id),
          )
  if (!found) {
    setNotice('这一项已不在当前结构里。')
    return
  }
  setSelected(selection)
  setView('structure')
}

const viewsLoading = Boolean(projectId) && dataProjectId !== projectId
```

- [ ] **Step 4: 改返回值**

把现有 `return ( ... )` 整块替换为下面这份。原有编辑器与草稿的 props 逐字保留：

```tsx
return (
  <div className="space-y-6">
    <div className="flex flex-wrap items-center gap-3">
      <h2 className="text-xl font-semibold">章节设计</h2>
      <select
        className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
        value={projectId}
        onChange={(e) => {
          setDataProjectId('')
          setProjectId(e.target.value)
        }}
      >
        {projects.map((project) => (
          <option key={project.id} value={project.id}>
            {project.name}
          </option>
        ))}
      </select>
      {view === 'structure' && (
        <button
          className="rounded bg-indigo-600 px-4 py-2 text-sm disabled:opacity-50"
          disabled={!projectId || planning}
          onClick={runChapterPlan}
        >
          {planning ? '生成中…' : 'AI 排卷章'}
        </button>
      )}
      {notice && <span className="text-sm text-slate-400">{notice}</span>}
    </div>

    <div className="flex flex-wrap gap-2 border-b border-slate-800 pb-2">
      {TABS.map((tab) => (
        <button
          key={tab.key}
          className={`rounded px-3 py-1.5 text-sm ${
            view === tab.key
              ? 'bg-slate-800 text-white'
              : 'text-slate-400 hover:bg-slate-900'
          }`}
          onClick={() => setView(tab.key)}
        >
          {tab.label}
        </button>
      ))}
    </div>

    {view === 'structure' && (
      <>
        {chapterPlan && (
          <>
            <ChapterPlanDraft
              key={chapterPlan.run.id}
              volumes={chapterPlan.volumes}
              statuses={statuses}
              warnings={chapterPlan.warnings}
              openQuestions={chapterPlan.open_questions}
              busy={planning}
              onWrite={writeChapterPlan}
              onClose={() => setChapterPlan(null)}
            />
            <RunTrace run={chapterPlan.run} />
          </>
        )}
        {scenePlan && (
          <>
            <ScenePlanDraft
              key={scenePlan.data.run.id}
              chapterTitle={scenePlan.chapterTitle}
              scenes={scenePlan.data.scenes}
              warnings={scenePlan.data.warnings}
              openQuestions={scenePlan.data.open_questions}
              busy={planning}
              onWrite={writeScenePlan}
              onClose={() => setScenePlan(null)}
            />
            <RunTrace run={scenePlan.data.run} />
          </>
        )}

        <div className="grid gap-6 lg:grid-cols-[300px_1fr]">
          <ChapterTree
            volumes={volumes}
            selected={selected}
            onSelect={setSelected}
            onAddVolume={addVolume}
            onAddChapter={addChapter}
            onAddScene={addScene}
            onMove={move}
          />

          <div className="space-y-4">
            {activeChapter && (
              <div className="flex justify-end">
                <button
                  className="rounded border border-emerald-700 px-3 py-1.5 text-sm text-emerald-300 disabled:opacity-50"
                  disabled={planning}
                  onClick={() => runScenePlan(activeChapter)}
                >
                  AI 写场景卡
                </button>
              </div>
            )}
            {!selected && (
              <p className="rounded border border-slate-800 p-4 text-sm text-slate-500">
                从左边选一卷、一章或一个场景开始编辑；也可以先手工建卷。
              </p>
            )}
            {volume && (
              <VolumeEditor
                key={volume.id}
                volume={volume}
                statuses={statuses}
                busy={busy}
                onSave={async (fields) =>
                  run(async () => {
                    await api.updateVolume(volume.id, fields)
                    await refresh()
                    setNotice('已保存')
                  })
                }
                onDelete={deleteSelected}
              />
            )}
            {chapter && (
              <ChapterEditor
                key={chapter.id}
                chapter={chapter}
                statuses={statuses}
                busy={busy}
                onSave={async (fields) =>
                  run(async () => {
                    await api.updateChapter(chapter.id, fields)
                    await refresh()
                    setNotice('已保存')
                  })
                }
                onDelete={deleteSelected}
              />
            )}
            {scene && (
              <SceneEditor
                key={scene.id}
                scene={scene}
                statuses={statuses}
                entries={entries}
                entriesReady={entriesProjectId === projectId}
                foreshadows={foreshadows}
                busy={busy}
                onSave={async (fields) =>
                  run(async () => {
                    await api.updateScene(scene.id, fields)
                    await refresh()
                    setNotice('已保存')
                  })
                }
                onDelete={deleteSelected}
              />
            )}
          </div>
        </div>
      </>
    )}

    {view !== 'structure' && (
      <section className="space-y-4">
        {!projectId ? (
          <p className="rounded border border-slate-800 p-4 text-sm text-slate-500">
            先选一个项目。
          </p>
        ) : viewsLoading ? (
          <p className="rounded border border-slate-800 p-4 text-sm text-slate-500">
            正在读取章节结构…
          </p>
        ) : (
          <>
            {view === 'rhythm' && (
              <RhythmCurve
                volumes={volumes}
                onSelectChapter={(id) =>
                  openInStructure({ kind: 'chapter', id })
                }
              />
            )}
            {view === 'foreshadows' && (
              <ForeshadowLedger
                volumes={volumes}
                foreshadows={foreshadows}
                statuses={statuses}
                onSelectScene={(id) => openInStructure({ kind: 'scene', id })}
              />
            )}
            {view === 'lanes' && (
              <Swimlanes
                volumes={volumes}
                onSelectChapter={(id) =>
                  openInStructure({ kind: 'chapter', id })
                }
              />
            )}
          </>
        )}
      </section>
    )}
  </div>
)
```

- [ ] **Step 5: 类型检查与回归测试**

Run:

```bash
cd "D:/Practical Project/AIProject/Experiment/StoryForge/frontend" && pnpm vitest run && pnpm build
```

Expected: 18 个前端测试通过；`tsc -b` 与 `vite build` 干净。UI 不写自动化测试（项目约定），交互在 Task 6 手工走查。

- [ ] **Step 6: 提交**

```bash
git add frontend/src/pages/Chapters.tsx
git commit -m "feat(frontend): 章节页接入节奏、伏笔与剧情线视图"
```

---

### Task 6: 手工走查与阶段文档

**Files:**
- Create: `docs/superpowers/plans/2026-10-18-p1c2-walkthrough.md`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: 已启动的后端 / 前端与 Task 1–5 的视图。

- [ ] **Step 1: 起临时环境并播种**

把脚本写到 `<worktree-root>/.superpowers/sdd/2026-10-18-p1c2-rhythm-foreshadow/seed_p1c2.py`（目录与计划同名，由 SDD 工作区脚本创建）：

```python
"""P1c-2 走查夹具：只通过 HTTP API 写入临时数据目录。"""

import httpx

BASE = "http://127.0.0.1:8756"


def main() -> None:
    client = httpx.Client(base_url=BASE, timeout=30)

    def post(path: str, body: dict) -> dict:
        response = client.post(path, json=body)
        response.raise_for_status()
        return response.json()

    project = post("/api/projects", {"name": "P1c2 走查"})
    pid = project["id"]
    v1 = post(f"/api/projects/{pid}/volumes", {"name": "第一卷", "purpose": "起"})
    v2 = post(f"/api/projects/{pid}/volumes", {"name": "第二卷", "purpose": "落"})

    def chapter(volume_id: str, title: str, **fields) -> dict:
        return post(f"/api/volumes/{volume_id}/chapters", {"title": title, **fields})

    c1 = chapter(
        v1["id"],
        "开端",
        target_words=3000,
        conflict_level=2,
        dialogue_ratio=0.4,
        hook_strength=3,
        lines=["主线", "暗线"],
    )
    c2 = chapter(v1["id"], "转折", dialogue_ratio=0.0, lines=["暗线", " 主线 "])
    c3 = chapter(
        v2["id"],
        "再起",
        target_words=5000,
        conflict_level=5,
        dialogue_ratio=1.0,
        hook_strength=4,
        lines=["副线"],
    )
    c4 = chapter(
        v2["id"],
        "收束",
        conflict_level=3,
        dialogue_ratio=0.5,
        hook_strength=2,
    )
    chapter(v2["id"], "尾声")

    def scene(chapter_id: str, **fields) -> dict:
        return post(f"/api/chapters/{chapter_id}/scenes", {"goal": "场景目标", **fields})

    s1 = scene(c1["id"], foreshadow_plants=["旧城信标"])
    scene(c1["id"], foreshadow_plants=["雨夜来客"], foreshadow_pays=["旧城信标"])
    s3 = scene(c2["id"])
    scene(c3["id"])

    orphan = post(
        f"/api/projects/{pid}/foreshadows",
        {"name": "失踪的档案", "note": "计划回收但还没有埋设"},
    )
    response = client.patch(
        f"/api/foreshadows/{orphan['id']}",
        json={"plan_pay_scene_id": s3["id"]},
    )
    response.raise_for_status()

    print(f"project={pid}")
    print(f"c1={c1['id']} c2={c2['id']} c3={c3['id']} c4={c4['id']}")
    print(f"s1={s1['id']} s3={s3['id']}")


if __name__ == "__main__":
    main()
```

起服务（两个后台进程）：

```bash
mkdir -p "$LOCALAPPDATA/StoryForge-p1c2-walkthrough"
STORYFORGE_DATA_DIR="$LOCALAPPDATA/StoryForge-p1c2-walkthrough" uv run --directory backend uvicorn app.main:app --port 8756
```

```bash
cd "D:/Practical Project/AIProject/Experiment/StoryForge/frontend" && pnpm dev --port 5173
```

等 `/api/health` 返回后播种：

```bash
curl -s http://127.0.0.1:8756/api/health
uv run --directory backend python "<worktree-root>/.superpowers/sdd/2026-10-18-p1c2-rhythm-foreshadow/seed_p1c2.py"
```

- [ ] **Step 2: 浏览器走查并写清单**

用 `playwright-cli` 技能打开 `http://127.0.0.1:5173/chapters`，按下面清单逐项执行，并把结果写入 `docs/superpowers/plans/2026-10-18-p1c2-walkthrough.md`：

```markdown
# P1c-2 手工走查清单

> 2026-10-18。环境：临时数据目录 `$LOCALAPPDATA/StoryForge-p1c2-walkthrough`，后端 8756、前端 5173。
> 数据由 `seed_p1c2.py` 通过 HTTP API 播种；未调用模型，未写作者库。

## 夹具

- 项目「P1c2 走查」：2 卷 5 章；c2 冲突/钩子为空、对话占比 0；c3 目标字数 5000、冲突 5；c5 全空。
- 4 个场景（c1 两场、c2 一场、c3 一场）。
- 3 条伏笔：旧城信标（埋 c1s1、计划回收 c1s2）、失踪的档案（无埋设、计划回收 c2s1）、雨夜来客（埋 c1s2、无计划回收）。
- 线名：c1 [主线, 暗线]、c2 [暗线, " 主线 "]、c3 [副线]、c4 无、c5 无。

## 检查项

- [ ] 四个页签可见；结构设计页签与改动前一致；视图页签隐藏树、编辑器与 AI 按钮。
- [ ] 节奏曲线：5 列、2 个卷分带；c2 冲突/钩子断线；c2 对话占比 0%；c1 3000 / c3 5000 柱高比例正确；未评计数正确。
- [ ] 节奏曲线点击 c3 → 切回结构设计并选中 c3。
- [ ] 伏笔账本：3 行；失踪的档案置顶；旧城信标两端标签正确；雨夜来客缺计划回收；筛选「缺埋设 / 缺计划回收」结果正确；状态显示规划中。
- [ ] 账本点击旧城信标的埋设位置 → 切回结构设计并选中 c1s1。
- [ ] 剧情线：行 主线/暗线/副线；c2 的「 主线 」与重复暗线没有产生多余行/格；c4、c5 列仍存在；点击格子选中对应章。
- [ ] 空态：用仪表盘新建（或 `POST /api/projects`）一个无卷章项目，三个视图都显示各自空态；再建一个只有卷章、没有伏笔的项目，账本显示空态。
- [ ] 控制台 0 报错。
- [ ] 切项目快速来回，视图不显示上一个项目的数据。

## 结果

逐项勾选上面的检查项，并在下面记录实际观察；失败项写清复现步骤与截图路径（如适用）。

- 通过项：
- 失败项：
```

- [ ] **Step 3: 停服务、删临时目录**

停止两个后台进程，然后：

```bash
rm -rf "$LOCALAPPDATA/StoryForge-p1c2-walkthrough"
```

确认没有写作者真实库，也没有产生模型调用。

- [ ] **Step 4: 更新 CLAUDE.md**

路线图行改为：

```markdown
| **P1c-2 节奏 / 伏笔 / 剧情线视图** | 节奏曲线、伏笔账本、剧情线泳道（纯前端只读） | ✅ 完成（2026-10-18 通过临时数据目录走查；遗留见下方阶段记录） |
```

在 P1c-1 阶段记录之后追加：

```markdown
**2026-10-18 · P1c-2 节奏 / 伏笔 / 剧情线视图（实施完成）**

设计 `docs/superpowers/specs/2026-10-18-p1c2-rhythm-foreshadow-design.md`；实施计划 `docs/superpowers/plans/2026-10-18-p1c2-rhythm-foreshadow.md`。纯前端只读视图：不建表、不迁移、不加后端接口、不加图表库、不调用模型。

产出：`/chapters` 页签（结构设计 / 节奏曲线 / 伏笔账本 / 剧情线）；共享 x 轴的四行节奏小多图（目标字数、冲突、钩子、对话占比），`null` 断线、`0` 保留；伏笔账本把埋设/计划回收解析到卷 / 章 / 场景，缺埋设置顶并可筛选；剧情线按 `chapter.lines` 分组的泳道；点击视图里的位置切回结构设计并选中对应章 / 场景。顺带把树 / 条目 / 伏笔的请求代际统一，视图在数据就绪前显示加载态。

验证：

| 项 | 结果 |
|---|---|
| 后端测试 | **339 passed**（本段未改后端） |
| 前端测试 | **18 passed**（既有 8 + 新增 10） |
| 前端构建 | `pnpm build` 干净 |
| 手工走查 | 通过；清单见 `docs/superpowers/plans/2026-10-18-p1c2-walkthrough.md` |
| 真实模型 / 额度 | 未调用，额度未变 |
| 作者真实库 | 未写入；走查使用临时 `STORYFORGE_DATA_DIR` 并已删除 |

裁定与遗留：账本只读；伏笔名称 / 备注 / 规划状态仍只有后端接口、没有编辑界面（P1c-1 遗留，本段不补）；仪表盘摘要与伏笔回收率留到 P2/P4，因为现在只能反映计划；FTS5 仍顺延到 P2 之前。
```

在 §8 变更记录末尾追加：

```markdown
| 2026-10-18 | P1c-2 含**剧情线泳道**，修正 CLAUDE.md 的 P1c-2 行 | 产品设计文档 §4.5 与 P1c-1 spec §1.3 都把泳道归到 P1c-2；CLAUDE.md 漏记 |
| 2026-10-18 | P1c-2 用**前端纯投影**，不加后端接口、不加图表库 | 树 / 伏笔接口已返回全部数据；符合「只画视图」与「不用重型依赖」 |
| 2026-10-18 | 节奏图 `null` = 未评、`0` = 有效值，断线不插值 | `0` 是合法的对话占比；插值会伪造数据 |
| 2026-10-18 | 节奏图的「字数」用 `target_words` 并标「目标字数」 | P1 尚无正文，实际字数等 P2 |
| 2026-10-18 | 伏笔状态列标「规划状态」，沿用章节状态词表；生命周期状态留 P4 | P1c 只有 planned / confirmed；不把规划状态伪装成回收状态 |
| 2026-10-18 | 账本只读；伏笔名称 / 备注 / 规划状态暂无编辑界面，记为遗留 | 视图不扩编辑面；现有界面缺口如实记录 |
| 2026-10-18 | 树 / 条目 / 伏笔统一请求代际 token；视图在数据就绪前显示加载态 | 切项目时旧响应会覆盖新项目；视图会直接暴露这个问题 |
| 2026-10-18 | 泳道按线名 trim 后精确匹配、章内去重、首次出现排序 | 线名是自由文本，静默同义归并比不合并更危险 |
| 2026-10-18 | 账本缺埋设置顶，其余按埋设的故事顺序；提供缺埋设 / 缺回收筛选 | 未安排的伏笔最需要作者处理 |
| 2026-10-18 | 仪表盘节奏摘要与伏笔回收率不在 P1c-2 | 回收率要等 P2/P4 有实际回收状态，否则只能反映计划 |
```

- [ ] **Step 5: 最终验证**

Run:

```bash
uv run --directory backend pytest -q
cd "D:/Practical Project/AIProject/Experiment/StoryForge/frontend" && pnpm vitest run && pnpm build
```

Expected: 后端 339 passed；前端 18 passed；构建干净。

- [ ] **Step 6: 提交**

```bash
git add docs/superpowers/plans/2026-10-18-p1c2-walkthrough.md CLAUDE.md
git commit -m "docs: 归档 P1c-2 走查并同步阶段记录"
```

---

## Final Verification

- [ ] `uv run --directory backend pytest -q` → 339 passed。
- [ ] `cd frontend && pnpm vitest run` → 18 passed。
- [ ] `cd frontend && pnpm build` → 干净。
- [ ] `git status --porcelain` → 只剩本计划预期的提交内容（无未跟踪的临时数据）。
- [ ] 确认 `STORYFORGE_DATA_DIR` 临时目录已删除，作者真实库未被写入。
