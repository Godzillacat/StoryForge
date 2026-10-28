import type { RevisionSummary } from '../../api/client'
import { Button } from '../../ui/Button'

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
      <p className="text-[13.5px] text-muted">
        还没有修订。保存正文或采纳草稿后会在这里留下快照。
      </p>
    )
  }

  return (
    <section className="space-y-2 text-[13.5px]">
      <h3 className="font-medium text-ink-2">修订历史</h3>
      <ul className="space-y-2">
        {revisions.map((revision) => (
          <li key={revision.id} className="rounded-control border border-line p-2">
            <div className="flex items-center justify-between gap-2">
              <button
                type="button"
                onClick={() => onOpen(revision.id)}
                className="text-left text-ink-2 hover:text-ink"
              >
                {SOURCE_LABELS[revision.source] ?? revision.source} · {revision.chars} 字
              </button>
              <Button
                size="sm"
                disabled={busy}
                onClick={() => onRestore(revision.id)}
              >
                恢复
              </Button>
            </div>
            <p className="mt-1 text-[11.5px] text-muted">
              {new Date(revision.created_at).toLocaleString()}
            </p>
            <p className="mt-1 line-clamp-2 text-[11.5px] text-muted">{revision.preview}</p>
          </li>
        ))}
      </ul>
    </section>
  )
}
