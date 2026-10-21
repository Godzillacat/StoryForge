import { useState } from 'react'
import type { BatchJob } from '../../api/client'

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
    <section className="space-y-3 text-sm">
      <h3 className="font-medium text-slate-300">批量生成</h3>
      <p className="text-xs text-slate-500">
        只生成 AI 草稿，不覆盖已采纳正文；已有正文或草稿的场景会跳过。
      </p>

      <div className="flex flex-wrap items-center gap-2">
        <select
          value={scope}
          disabled={loading || busy || active}
          onChange={(event) => setScope(event.target.value as 'chapter' | 'volume')}
          className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs"
        >
          <option value="chapter" disabled={!chapterId}>
            当前章：{chapterLabel || '（未选）'}
          </option>
          <option value="volume" disabled={!volumeId}>
            当前卷：{volumeLabel || '（未选）'}
          </option>
        </select>
        <button
          type="button"
          disabled={loading || busy || active || !canStart || !scopeId}
          onClick={() => onStart(scope, scopeId)}
          className="rounded border border-slate-700 px-2 py-1 text-xs text-slate-300 hover:text-white disabled:opacity-50"
        >
          {loading ? '创建中…' : '开始批量生成'}
        </button>
      </div>

      {job && (
        <div className="space-y-2 rounded border border-slate-800 p-2 text-xs">
          <div className="flex items-center justify-between gap-2">
            <span className="text-slate-300">
              {job.scope_type === 'chapter' ? '当前章' : '当前卷'} ·{' '}
              {STATUS_LABELS[job.status] ?? job.status}
            </span>
            <span className="text-slate-500">
              {job.cursor} / {job.total}
            </span>
          </div>

          {job.failures.length > 0 && (
            <div className="space-y-1">
              <p className="text-amber-300">失败 {job.failures.length} 场：</p>
              <ul className="list-inside list-disc text-amber-200">
                {job.failures.map((failure, index) => (
                  <li key={`${failure.scene_id}-${index}`}>{failure.message}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex flex-wrap gap-1">
            {active && (
              <button
                type="button"
                disabled={busy}
                onClick={onPause}
                className="rounded border border-slate-700 px-2 py-0.5 text-slate-300 hover:text-white disabled:opacity-50"
              >
                暂停
              </button>
            )}
            {(job.status === 'paused' || job.status === 'failed') && (
              <button
                type="button"
                disabled={busy}
                onClick={onResume}
                className="rounded border border-slate-700 px-2 py-0.5 text-slate-300 hover:text-white disabled:opacity-50"
              >
                继续
              </button>
            )}
            {job.failures.length > 0 && (
              <button
                type="button"
                disabled={busy}
                onClick={onRetryFailed}
                className="rounded border border-amber-800 px-2 py-0.5 text-amber-300 hover:text-amber-200 disabled:opacity-50"
              >
                重试失败
              </button>
            )}
            {active && (
              <button
                type="button"
                disabled={busy}
                onClick={onCancel}
                className="rounded border border-slate-700 px-2 py-0.5 text-slate-400 hover:text-white disabled:opacity-50"
              >
                取消
              </button>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
