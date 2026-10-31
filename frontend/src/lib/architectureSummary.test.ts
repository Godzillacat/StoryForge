import { expect, it } from 'vitest'
import type { ArchitectureOption } from '../api/client'
import { comparisonSummary } from './architectureSummary'

const option = (tool: string, fit_score: number, length_plan?: string, rhythm_shape?: string): ArchitectureOption => ({
  tool,
  reason: '',
  fit_score,
  risks: [],
  length_plan,
  rhythm_shape,
})

it('点出字段差异与适配度最高的一套', () => {
  const text = comparisonSummary([
    option('三幕', 0.86, '均分', '前缓后紧'),
    option('四幕', 0.78, '均分', '递进'),
  ])
  expect(text).toContain('节奏形态')
  expect(text).toContain('「三幕」（0.86）')
})

it('字段接近时明说接近', () => {
  const text = comparisonSummary([option('甲', 0.8, '均分', '递进'), option('乙', 0.7, '均分', '递进')])
  expect(text).toContain('接近')
  expect(text).toContain('「甲」（0.8）')
})

it('不足两套时不给摘要', () => {
  expect(comparisonSummary([option('甲', 0.8)])).toBe('')
})
