import { describe, expect, it } from 'vitest'
import { contrastRatio } from './contrast'
import { PALETTE } from '../ui/palette'

describe('对比度', () => {
  it('纸色底上的文字达到 AA', () => {
    expect(contrastRatio(PALETTE.ink, PALETTE.paper)).toBeGreaterThanOrEqual(7)
    expect(contrastRatio(PALETTE.ink2, PALETTE.paper)).toBeGreaterThanOrEqual(4.5)
    expect(contrastRatio(PALETTE.muted, PALETTE.paper)).toBeGreaterThanOrEqual(4.5)
    expect(contrastRatio(PALETTE.accent, PALETTE.paper)).toBeGreaterThanOrEqual(4.5)
    expect(contrastRatio(PALETTE.warn, PALETTE.paper)).toBeGreaterThanOrEqual(4.5)
    expect(contrastRatio(PALETTE.danger, PALETTE.paper)).toBeGreaterThanOrEqual(4.5)
  })
  it('主按钮白字在墨绿上达到 AA', () => {
    expect(contrastRatio('#FFFFFF', PALETTE.accent)).toBeGreaterThanOrEqual(4.5)
  })
})
