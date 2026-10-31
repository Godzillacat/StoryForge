import { expect, it } from 'vitest'
import { runProjectGuard, setProjectGuard } from './projectGuard'

it('没人登记守卫时放行', () => {
  expect(runProjectGuard()).toBe(true)
})

it('守卫说否则拦住', () => {
  setProjectGuard(() => false)
  expect(runProjectGuard()).toBe(false)
})

it('清掉守卫后恢复放行', () => {
  setProjectGuard(null)
  expect(runProjectGuard()).toBe(true)
})
