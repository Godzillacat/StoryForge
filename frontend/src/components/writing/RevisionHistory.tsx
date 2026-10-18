import type { RevisionSummary } from '../../api/client'

const SOURCE_LABELS: Record<string, string> = {
  ai: 'AI 采纳',
  author: '作者保存',
  restore: '恢复',
}

interface Props {
  revisions: RevisionSummary[]
  busy: boolean
  onOpen: (revisionId: string) => void
  onRestore: (revisionId: string) => void
}

export default function RevisionHistory({ revisions, busy, onOpen, onRestore }: Props) {
  if (revisions.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        还没有修订。保存正文或采纳草稿后会在这里留下快照。
      </p>
    )
  }

  return (
    <section className="space-y-2 text-sm">
      <h3 className="font-medium text-slate-300">修订历史</h3>
      <ul className="space-y-2">
        {revisions.map((revision) => (
          <li key={revision.id} className="rounded border border-slate-800 p-2">
            <div className="flex items-center justify-between gap-2">
              <button
                type="button"
                onClick={() => onOpen(revision.id)}
                className="text-left text-slate-300 hover:text-white"
              >
                {SOURCE_LABELS[revision.source] ?? revision.source} · {revision.chars} 字
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => onRestore(revision.id)}
                className="rounded border border-slate-700 px-2 py-0.5 text-xs text-slate-400 hover:text-white disabled:opacity-50"
              >
                恢复
              </button>
            </div>
            <p className="mt-1 text-xs text-slate-500">
              {new Date(revision.created_at).toLocaleString()}
            </p>
            <p className="mt-1 line-clamp-2 text-xs text-slate-500">{revision.preview}</p>
          </li>
        ))}
      </ul>
    </section>
  )
}
