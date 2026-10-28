import { diffLines } from '../../lib/diff'

interface Props {
  oldText: string
  newText: string
}

export default function DiffPanel({ oldText, newText }: Props) {
  const rows = diffLines(oldText, newText)
  const added = rows.filter((row) => row.kind === 'add').length
  const removed = rows.filter((row) => row.kind === 'remove').length

  return (
    <section className="space-y-2 rounded-card border border-line p-3">
      <h3 className="text-[13.5px] font-medium text-ink-2">
        旧稿与新稿对比（+{added} / -{removed}）
      </h3>
      <div className="max-h-80 overflow-auto rounded-control bg-sunken font-mono text-[11.5px] leading-6">
        {rows.map((row, index) => (
          <div
            key={index}
            className={
              row.kind === 'add'
                ? 'bg-accent-soft text-accent-ink'
                : row.kind === 'remove'
                  ? 'bg-danger/10 text-danger'
                  : 'text-muted'
            }
          >
            <span className="inline-block w-10 select-none pr-2 text-right text-faint">
              {row.kind === 'add' ? '+' : row.kind === 'remove' ? '-' : ' '}
            </span>
            <span className="whitespace-pre-wrap break-words">{row.text || ' '}</span>
          </div>
        ))}
      </div>
    </section>
  )
}
