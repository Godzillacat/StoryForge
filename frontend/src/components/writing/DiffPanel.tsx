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
    <section className="space-y-2 rounded border border-slate-800 p-3">
      <h3 className="text-sm font-medium text-slate-300">
        旧稿与新稿对比（+{added} / -{removed}）
      </h3>
      <div className="max-h-80 overflow-auto rounded bg-slate-950 font-mono text-xs leading-6">
        {rows.map((row, index) => (
          <div
            key={index}
            className={
              row.kind === 'add'
                ? 'bg-emerald-950/40 text-emerald-200'
                : row.kind === 'remove'
                  ? 'bg-rose-950/40 text-rose-200'
                  : 'text-slate-400'
            }
          >
            <span className="inline-block w-10 select-none pr-2 text-right text-slate-600">
              {row.kind === 'add' ? '+' : row.kind === 'remove' ? '-' : ' '}
            </span>
            <span className="whitespace-pre-wrap break-words">{row.text || ' '}</span>
          </div>
        ))}
      </div>
    </section>
  )
}
