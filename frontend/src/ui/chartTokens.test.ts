import { expect, it } from 'vitest'
import { CHART } from './chartTokens'
import { PALETTE } from './palette'

/** WCAG 相对亮度：用来断言「网格在绘图区底上看得见」这类关系。 */
function luminance(hex: string): number {
  const channel = (offset: number) => {
    const value = parseInt(hex.slice(offset, offset + 2), 16) / 255
    return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * channel(1) + 0.7152 * channel(3) + 0.0722 * channel(5)
}

it('图表用色全部来自 PALETTE（挡住裸十六进制）', () => {
  const allowed = new Set<string>(Object.values(PALETTE))
  for (const [name, value] of Object.entries(CHART)) {
    expect(allowed, `${name} = ${value} 不在 PALETTE 里`).toContain(value)
  }
})

it('并置在同一绘图区的两条序列色不相同', () => {
  expect(CHART.series).not.toBe(CHART.seriesAlt)
})

it('逻辑链的三条序列色两两可分辨', () => {
  const chain = [CHART.cause, CHART.turn, CHART.reveal]
  expect(new Set(chain).size).toBe(3)
})

it('网格与卷带都比绘图区底深，否则在浅色底上看不见', () => {
  expect(luminance(CHART.grid)).toBeLessThan(luminance(CHART.plot))
  expect(luminance(CHART.band)).toBeLessThan(luminance(CHART.plot))
})

it('逻辑链的三条序列色在纸底上达到 AA', () => {
  const paper = luminance(PALETTE.paper)
  for (const hex of [CHART.cause, CHART.turn, CHART.reveal]) {
    const ratio = (Math.max(luminance(hex), paper) + 0.05) / (Math.min(luminance(hex), paper) + 0.05)
    expect(ratio, `${hex} 对纸底的对比度不足`).toBeGreaterThanOrEqual(4.5)
  }
})
