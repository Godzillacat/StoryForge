import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { expect, it } from 'vitest'
import { Dialog } from './Dialog'

function Host() {
  const [name, setName] = useState('')
  return (
    <Dialog open title="新建项目" onClose={() => undefined}>
      <input
        aria-label="项目名称"
        autoFocus
        value={name}
        onChange={(event) => setName(event.target.value)}
      />
    </Dialog>
  )
}

it('输入时焦点留在输入框，不被对话框容器抢走', () => {
  render(<Host />)
  const input = screen.getByLabelText('项目名称') as HTMLInputElement
  expect(document.activeElement).toBe(input)

  fireEvent.change(input, { target: { value: '南' } })
  expect(document.activeElement).toBe(input)

  fireEvent.change(input, { target: { value: '南滨' } })
  expect(document.activeElement).toBe(input)
})
