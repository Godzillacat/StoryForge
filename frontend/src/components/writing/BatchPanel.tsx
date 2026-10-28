import { useState } from 'react'
import type { BatchJob } from '../../api/client'
import { Button } from '../../ui/Button'

interface Props {
  job: BatchJob | null
  loading: boolean
  busy: boolean
  canStart: boolean
  chapterId: string
  chapterLabel: string
  volumeId: string
  volumeLabel: string
  onStart: (scopeType: 'chapter' | 'volume', scopeId: string) => void
  onPause: () => void
  onResume: () => void
  onCancel: () => void
  onRetryFailed: () => void
}

const STATUS_LABELS: Record<string, string> = {
  running: '生成中',
  paused: '已暂停',
  completed: '已完成',
  cancelled: '已取消',
  failed: '失败',
}

export default function BatchPanel({
  job,
  loading,
  busy,
  canStart,
  chapterId,
  chapterLabel,
  volumeId,
  volumeLabel,
  onStart,
  onPause,
  onResume,
  onCancel,
  onRetryFailed,
}: Props) {
  const [scope, setScope] = useState<'chapter' | 'volume'>('chapter')
  const scopeId = scope === 'chapter' ? chapterId : volumeId
  const active = job?.status === 'running'

  return (
    <section className="space-y-3 text-[13.5px]">
      <h3 className="font-medium text-ink-2">批量生成</h3>
      <p className="text-[11.5px] text-muted">
        只生成 AI 草稿，不覆盖已采纳正文；已有正文或草稿的场景会跳过。
      </p>

      <div className="flex flex-wrap items-center gap-2">
        <select
          value={scope}
          disabled={loading || busy || active}
          onChange={(event) => setScope(event.target.value as 'chapter' | 'volume')}
          className="rounded-control border border-line-strong bg-surface px-2 py-1 text-[11.5px] text-ink"
        >
          <option value="chapter" disabled={!chapterId}>
            当前章：{chapterLabel || '（未选）'}
          </option>
          <option value="volume" disabled={!volumeId}>
            当前卷：{volumeLabel || '（未选）'}
          </option>
        </select>
        <Button
          size="sm"
          disabled={loading || busy || active || !canStart || !scopeId}
          onClick={() => onStart(scope, scopeId)}
        >
          {loading ? '创建中…' : '开始批量生成'}
        </Button>
      </div>

      {job && (
        <div className="space-y-2 rounded-control border border-line p-2 text-[11.5px]">
          <div className="flex items-center justify-between gap-2">
            <span className="text-ink-2">
              {job.scope_type === 'chapter' ? '当前章' : '当前卷'} ·{' '}
              {STATUS_LABELS[job.status] ?? job.status}
            </span>
            <span className="text-muted">
              {job.cursor} / {job.total}
            </span>
          </div>

          {job.failures.length > 0 && (
            <div className="space-y-1">
              <p className="text-warn">失败 {job.failures.length} 场：</p>
              <ul className="list-inside list-disc text-warn">
                {job.failures.map((failure, index) => (
                  <li key={`${failure.scene_id}-${index}`}>{failure.message}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex flex-wrap gap-1">
            {active && (
              <Button
                size="sm"
                disabled={busy}
                onClick={onPause}
              >
                暂停
              </Button>
            )}
            {(job.status === 'paused' || job.status === 'failed') && (
              <Button
                size="sm"
                disabled={busy}
                onClick={onResume}
              >
                继续
              </Button>
            )}
            {job.failures.length > 0 && (
              <Button
                size="sm"
                variant="warn"
                disabled={busy}
                onClick={onRetryFailed}
              >
                重试失败
              </Button>
            )}
            {active && (
              <Button
                size="sm"
                disabled={busy}
                onClick={onCancel}
              >
                取消
              </Button>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
