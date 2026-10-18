export type DiffKind = 'same' | 'add' | 'remove'

export interface DiffRow {
  kind: DiffKind
  text: string
  oldLine: number | null
  newLine: number | null
}

const MAX_DIFF_LINES = 4000

function toLines(text: string): string[] {
  const normalized = text.replace(/\r\n/g, '\n')
  if (normalized === '') return []
  const lines = normalized.split('\n')
  if (lines[lines.length - 1] === '') lines.pop()
  return lines
}

export function diffLines(oldText: string, newText: string): DiffRow[] {
  const oldLines = toLines(oldText)
  const newLines = toLines(newText)

  if (oldLines.length + newLines.length > MAX_DIFF_LINES) {
    return [
      ...oldLines.map((text, index) => ({
        kind: 'remove' as const,
        text,
        oldLine: index + 1,
        newLine: null,
      })),
      ...newLines.map((text, index) => ({
        kind: 'add' as const,
        text,
        oldLine: null,
        newLine: index + 1,
      })),
    ]
  }

  const table: number[][] = Array.from({ length: oldLines.length + 1 }, () =>
    new Array<number>(newLines.length + 1).fill(0),
  )
  for (let i = oldLines.length - 1; i >= 0; i -= 1) {
    for (let j = newLines.length - 1; j >= 0; j -= 1) {
      table[i][j] =
        oldLines[i] === newLines[j]
          ? table[i + 1][j + 1] + 1
          : Math.max(table[i + 1][j], table[i][j + 1])
    }
  }

  const rows: DiffRow[] = []
  let i = 0
  let j = 0
  while (i < oldLines.length && j < newLines.length) {
    if (oldLines[i] === newLines[j]) {
      rows.push({ kind: 'same', text: oldLines[i], oldLine: i + 1, newLine: j + 1 })
      i += 1
      j += 1
    } else if (table[i + 1][j] >= table[i][j + 1]) {
      rows.push({ kind: 'remove', text: oldLines[i], oldLine: i + 1, newLine: null })
      i += 1
    } else {
      rows.push({ kind: 'add', text: newLines[j], oldLine: null, newLine: j + 1 })
      j += 1
    }
  }
  while (i < oldLines.length) {
    rows.push({ kind: 'remove', text: oldLines[i], oldLine: i + 1, newLine: null })
    i += 1
  }
  while (j < newLines.length) {
    rows.push({ kind: 'add', text: newLines[j], oldLine: null, newLine: j + 1 })
    j += 1
  }
  return rows
}
