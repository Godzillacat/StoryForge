import type { CharacterDriftData, CharacterDriftTotals } from '../api/client'

/** 表格的一列：一章。表头只放得下几个字，全文进悬停提示。 */
export interface DriftChapter {
  id: string
  label: string
  /** 卷名：两卷都可能有「第1章 雨夜」，悬停提示靠它区分。没有就是空串。 */
  volumeLabel: string
}

/**
 * 表格的一格。`null`（不在这个类型里）表示**没有记录**，与「记录过但没变」
 * 是两件事 —— 后者是 `changed: false` 的正常格子。
 */
export interface DriftCell {
  chapterId: string
  label: string
  note: string
  changed: boolean
}

export interface DriftRow {
  entryId: string
  name: string
  /** 与 `chapters` 等长、按下标对齐；没记录的章是 `null`。 */
  cells: (DriftCell | null)[]
  // 变化次数与记录条数都由后端算好：判定规则（与上一条记录比）不在这里重写。
  changes: number
  recorded: number
}

export interface DriftGrid {
  chapters: DriftChapter[]
  rows: DriftRow[]
  /** 顶部汇总用；后端算，前端原样透传。 */
  totals: CharacterDriftTotals
}

const EMPTY_TOTALS: CharacterDriftTotals = { characters: 0, changes: 0, sparse: 0 }

/**
 * 布局纯函数：接口数据 → 按章对齐的网格。
 *
 * 服务端的 `cells` 只含有记录的章，所以必须按 `chapter_id` 找列位置，
 * **不能按下标铺** —— 中间空几章时那样会把后面的状态错到前面列上，
 * 显示成「第2章就变了」。缺的格填 `null`，界面才画得出空白。
 */
export function buildDriftGrid(
  data: CharacterDriftData | null | undefined,
): DriftGrid {
  const chapters: DriftChapter[] = (data?.chapters ?? []).map((chapter) => ({
    id: chapter.id,
    label: chapter.label,
    volumeLabel: chapter.volume_label ?? '',
  }))
  const indexById = new Map(chapters.map((chapter, index) => [chapter.id, index]))

  const rows: DriftRow[] = (data?.characters ?? []).map((row) => {
    const cells: (DriftCell | null)[] = chapters.map(() => null)
    for (const cell of row.cells) {
      const index = indexById.get(cell.chapter_id)
      // 章不在 `chapters` 里（章被删、状态行残留）：这一列不存在，宁可不画，
      // 也不能挤到别的列上去。
      if (index === undefined) continue
      // (chapter_id, entry_id) 在库里唯一，正常不会重复；真重复就保留先到的那条。
      if (cells[index]) continue
      cells[index] = {
        chapterId: cell.chapter_id,
        // 标签以章表为准：章改过标题后，状态行里存的是旧标题。
        label: chapters[index].label,
        note: cell.note,
        changed: cell.changed === true,
      }
    }
    return {
      entryId: row.entry_id,
      name: row.name,
      cells,
      changes: row.changes,
      recorded: row.recorded,
    }
  })

  return { chapters, rows, totals: data?.totals ?? EMPTY_TOTALS }
}
