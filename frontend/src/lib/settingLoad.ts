import type { SettingLoadData } from '../api/client'

// 一章一列：宽度固定，x 由序号算出 —— 组件不另抄一份间距公式。
export const COL_W = 56

/** 曲线上的一列：柱（新设定数）与折线点（密度）共用同一个 x。 */
export interface LoadPoint {
  id: string
  label: string
  x: number
  // 章号按卷各自从 1 起，跨卷会重名；悬停提示靠它区分。
  volumeLabel: string
  newCount: number
  density: number
  /** false = 这一章还没写正文，只能灰显，不能画成 0 柱。 */
  hasBody: boolean
  // 悬停提示要用的两个数：布局只透传，不解释。
  mentions: number
  chars: number
}

export interface LoadSeries {
  chapters: LoadPoint[]
  /** 柱高分母：没有可画的柱时为 1，避免除零。 */
  maxNew: number
  /** 折线分母：全为 0 时为 1，同上。 */
  maxDensity: number
}

/**
 * 分母取实有最大值；全都为 0 时退回 1。
 *
 * 不能写成 `Math.max(1, max)` —— 密度小于 1 是常态（每千字不足一次提及），
 * 那样会把整条折线压成贴地的直线。只有真的取不到正数时才兜底。
 */
function axisMax(values: number[]): number {
  const max = values.reduce((best, value) => (value > best ? value : best), 0)
  return max > 0 ? max : 1
}

/**
 * 布局纯函数：接口数据 → 一列一章的曲线坐标。
 *
 * 只排位置、透传数字，不判断投放好坏（判定在后端，也不在这里）。
 * `maxNew` / `maxDensity` 只在**有正文的章**里取：没有正文的章不参与
 * 新/旧判定，若把它的值算进分母，有正文的柱会被压扁。
 */
export function buildLoadSeries(
  data: SettingLoadData | null | undefined,
): LoadSeries {
  const chapters: LoadPoint[] = (data?.chapters ?? []).map((chapter, index) => ({
    id: chapter.id,
    label: chapter.label,
    x: index * COL_W,
    volumeLabel: chapter.volume_label,
    newCount: chapter.new_count,
    density: chapter.density,
    hasBody: chapter.has_body === true,
    mentions: chapter.mentions,
    chars: chapter.chars,
  }))
  const withBody = chapters.filter((chapter) => chapter.hasBody)
  return {
    chapters,
    maxNew: axisMax(withBody.map((chapter) => chapter.newCount)),
    maxDensity: axisMax(withBody.map((chapter) => chapter.density)),
  }
}
