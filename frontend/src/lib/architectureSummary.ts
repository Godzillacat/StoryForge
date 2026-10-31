import type { ArchitectureOption } from '../api/client'

/**
 * 三套方案的对比摘要：只说「哪里不一样」与「适配度最高的是哪套」，
 * 不做推荐裁决 —— 选哪套是作者的事。
 */
export function comparisonSummary(options: ArchitectureOption[]): string {
  if (options.length < 2) return ''
  const best = options.reduce((a, b) => (b.fit_score > a.fit_score ? b : a))
  const differs = (pick: (option: ArchitectureOption) => string) =>
    new Set(options.map((option) => pick(option).trim() || '—')).size > 1

  const differences: string[] = []
  if (differs((option) => option.length_plan ?? '')) differences.push('篇幅分配')
  if (differs((option) => option.rhythm_shape ?? '')) differences.push('节奏形态')

  const head = differences.length
    ? `三套方案在${differences.join('、')}上不同`
    : '三套方案在篇幅与节奏上接近'
  return `${head}；适配度最高的是「${best.tool}」（${best.fit_score}）。`
}
