import { expect, it } from 'vitest'
import { cn } from './cn'

it('拼接并丢弃假值', () => {
  expect(cn('a', false, undefined, 'b', null)).toBe('a b')
})

it('去掉首尾与重复空白', () => {
  expect(cn('  a  ', '', ' b ')).toBe('a b')
})
