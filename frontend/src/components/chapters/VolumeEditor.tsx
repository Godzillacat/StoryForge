import { useEffect, useState } from 'react'
import type { ChapterStatusOption, VolumeNode } from '../../api/client'

export default function VolumeEditor({
  volume,
  statuses,
  busy,
  onSave,
  onDelete,
}: {
  volume: VolumeNode
  statuses: ChapterStatusOption[]
  busy: boolean
  onSave: (fields: Record<string, unknown>) => Promise<void>
  onDelete: () => Promise<void>
}) {
  const [draft, setDraft] = useState({
    name: '',
    purpose: '',
    summary: '',
    actSeq: '',
    targetWords: '',
    status: 'planned',
  })

  useEffect(() => {
    setDraft({
      name: volume.name,
      purpose: volume.purpose,
      summary: volume.summary,
      actSeq: volume.act_seq == null ? '' : String(volume.act_seq),
      targetWords: volume.target_words == null ? '' : String(volume.target_words),
      status: volume.status,
    })
  }, [volume.id])

  const set = (patch: Partial<typeof draft>) => setDraft({ ...draft, ...patch })

  return (
    <section className="space-y-3 rounded border border-slate-800 p-4 text-sm">
      <h3 className="text-sm font-medium text-slate-300">卷</h3>
      <label className="block">
        <span className="text-slate-500">卷名</span>
        <input className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-3 py-2"
               value={draft.name} onChange={(e) => set({ name: e.target.value })} />
      </label>
      <label className="block">
        <span className="text-slate-500">本卷要做什么</span>
        <textarea className="mt-1 h-20 w-full rounded border border-slate-700 bg-slate-900 p-3"
                  value={draft.purpose} onChange={(e) => set({ purpose: e.target.value })} />
      </label>
      <label className="block">
        <span className="text-slate-500">摘要</span>
        <textarea className="mt-1 h-20 w-full rounded border border-slate-700 bg-slate-900 p-3"
                  value={draft.summary} onChange={(e) => set({ summary: e.target.value })} />
      </label>
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-slate-500">对应第几幕</label>
        <input className="w-24 rounded border border-slate-700 bg-slate-900 px-3 py-2"
               value={draft.actSeq} onChange={(e) => set({ actSeq: e.target.value })} placeholder="快照，可空" />
        <label className="text-slate-500">目标字数</label>
        <input className="w-32 rounded border border-slate-700 bg-slate-900 px-3 py-2"
               value={draft.targetWords} onChange={(e) => set({ targetWords: e.target.value })} />
        <label className="text-slate-500">状态</label>
        <select className="rounded border border-slate-700 bg-slate-900 px-3 py-2"
                value={draft.status} onChange={(e) => set({ status: e.target.value })}>
          {statuses.map((status) => (
            <option key={status.key} value={status.key}>{status.label}</option>
          ))}
        </select>
      </div>
      <div className="flex items-center gap-2">
        <button className="rounded bg-indigo-600 px-4 py-2 disabled:opacity-50" disabled={busy}
                onClick={() => onSave({
                  name: draft.name.trim(),
                  purpose: draft.purpose,
                  summary: draft.summary,
                  act_seq: draft.actSeq.trim() ? Number(draft.actSeq) : null,
                  target_words: draft.targetWords.trim() ? Number(draft.targetWords) : null,
                  status: draft.status,
                })}>
          保存
        </button>
        <button className="rounded border border-amber-700 px-4 py-2 text-amber-400" disabled={busy}
                onClick={onDelete}>
          删除
        </button>
      </div>
    </section>
  )
}
