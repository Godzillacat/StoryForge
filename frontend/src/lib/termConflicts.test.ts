import { expect, it } from 'vitest'
import type { TermRow } from '../api/client'
import { ambiguousForms } from './termConflicts'

const row = (form: string, entry_name: string, entry_id = entry_name): TermRow => ({
  entry_id,
  entry_name,
  type: 'character',
  form,
  is_primary: false,
})

it('同一写法被两个条目共用时标记出来', () => {
  const result = ambiguousForms([row('老师', '甲'), row('老师', '乙'), row('沈砚', '甲')])
  expect([...result.entries()]).toEqual([['老师', ['甲', '乙']]])
})

it('同一条目内的重复别名不算冲突', () => {
  expect(ambiguousForms([row('阿明', '甲'), row('阿明', '甲')]).size).toBe(0)
})

it('没有冲突时返回空表', () => {
  expect(ambiguousForms([row('沈砚', '甲'), row('南滨', '乙')]).size).toBe(0)
})
