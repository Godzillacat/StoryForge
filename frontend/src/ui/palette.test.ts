import { expect, it } from 'vitest'
import configText from '../../tailwind.config.js?raw'
import { PALETTE } from './palette'

// Tailwind 配置是纯 JS，没法 import 到 TS 的常量；这里用原文比对守住「不许漂移」。
it('tailwind.config.js 里的颜色值都来自 PALETTE', () => {
  for (const value of Object.values(PALETTE)) {
    expect(configText.toLowerCase()).toContain(value.toLowerCase())
  }
})
