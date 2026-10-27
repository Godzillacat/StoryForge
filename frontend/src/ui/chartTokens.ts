import { PALETTE } from './palette'

/**
 * 图表的全部用色。图表里不得出现裸十六进制 —— 改色只改这里。
 *
 * 取值一律来自 `PALETTE`：纸底上的对比度由 `contrast.test.ts` 守着，
 * 图表因此不需要第二套校验。`chartTokens.test.ts` 会断言这一点。
 *
 * 只管颜色，不管几何：两张图的版式本来就不同（一张是四行堆叠的小多图、
 * 一张是单一绘图区，列宽 44 与 56），几何常量留在各自文件里。
 */
export const CHART = {
  /** 主序列：实线、柱。 */
  series: PALETTE.accent,
  /** 并置在同一绘图区里的第二条序列（设定投放的密度线）。 */
  seriesAlt: PALETTE.warn,
  /** 虚线：节奏图的「钩子」。既有的次级编码，不靠颜色区分。 */
  dashed: PALETTE.lineStrong,
  /** 绘图区底。网格与卷带都以它为基准取更深的色。 */
  plot: PALETTE.surface,
  /** 网格（spec §6.1 把 sunken 指定给图表网格）。次级刻度靠 opacity 再压淡。 */
  grid: PALETTE.sunken,
  /** 卷带底：比绘图区底略深，让卷的范围看得出来。 */
  band: PALETTE.paper,
  /** 数据点的描边：与绘图区底同色，让点从线上「咬」出来。 */
  pointStroke: PALETTE.surface,
  /** 占位块（未写正文的章）。 */
  placeholder: PALETTE.paper,
  placeholderStroke: PALETTE.lineStrong,
  /** 行名（「目标字数」等）。 */
  axisLabel: PALETTE.muted,
  /** 章号、章名等刻度标签。 */
  axisTick: PALETTE.faint,
} as const
