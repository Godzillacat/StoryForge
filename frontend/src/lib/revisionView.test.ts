import { expect, it } from 'vitest'
import { countSelected, isSelectable } from './revisionView'

it('锁定或现值已变化的行不可勾选', () => {
  expect(isSelectable({ locked: true } as never)).toBe(false)
  expect(isSelectable({ locked: false } as never)).toBe(true)
  // 「已变化」与锁定同样不可选：套用旧建议会盖掉作者刚改的内容。
  expect(isSelectable({ locked: false, stale: true } as never)).toBe(false)
})

it('只数可勾选且已勾选的行', () => {
  expect(
    countSelected([{ locked: false }, { locked: true }, { stale: true }] as never, new Set([0, 1, 2])),
  ).toBe(1)
})
