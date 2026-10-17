import { useEffect, useState } from 'react'
import type { ChapterStatusOption, SceneNode } from '../../api/client'

export default function SceneEditor({
  scene,
  statuses,
  busy,
  onSave,
  onDelete,
}: {
  scene: SceneNode
  statuses: ChapterStatusOption[]
  busy: boolean
  onSave: (fields: Record<string, unknown>) => Promise<void>
  onDelete: () => Promise<void>
}) {
  const [draft, setDraft] = useState({
    goal: '',
    conflict: '',
    turn: '',
    storyTime: '',
    pov: '',
    minWords: '',
    maxWords: '',
    status: 'planned',
  })

  useEffect(() => {
    setDraft({
      goal: scene.goal,
      conflict: scene.conflict,
      turn: scene.turn,
      storyTime: scene.story_time,
      pov: scene.pov,
      minWords: scene.target_words_min == null ? '' : String(scene.target_words_min),
      maxWords: scene.target_words_max == null ? '' : String(scene.target_words_max),
      status: scene.status,
    })
  }, [scene.id])

  const set = (patch: Partial<typeof draft>) => setDraft({ ...draft, ...patch })

  return (
    <section className="space-y-3 rounded border border-slate-800 p-4 text-sm">
      <h3 className="text-sm font-medium text-slate-300">场景</h3>
      <label className="block">
        <span className="text-slate-500">场景目标</span>
        <textarea className="mt-1 h-20 w-full rounded border border-slate-700 bg-slate-900 p-3"
                  value={draft.goal} onChange={(e) => set({ goal: e.target.value })} />
      </label>
      <label className="block">
        <span className="text-slate-500">冲突</span>
        <textarea className="mt-1 h-20 w-full rounded border border-slate-700 bg-slate-900 p-3"
                  value={draft.conflict} onChange={(e) => set({ conflict: e.target.value })} />
      </label>
      <label className="block">
        <span className="text-slate-500">转折</span>
        <textarea className="mt-1 h-20 w-full rounded border border-slate-700 bg-slate-900 p-3"
                  value={draft.turn} onChange={(e) => set({ turn: e.target.value })} />
      </label>
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-slate-500">故事内时间</label>
        <input className="w-44 rounded border border-slate-700 bg-slate-900 px-3 py-2"
               value={draft.storyTime} onChange={(e) => set({ storyTime: e.target.value })} />
        <label className="text-slate-500">视角</label>
        <input className="w-40 rounded border border-slate-700 bg-slate-900 px-3 py-2"
               value={draft.pov} onChange={(e) => set({ pov: e.target.value })} />
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-slate-500">字数下限</label>
        <input className="w-24 rounded border border-slate-700 bg-slate-900 px-3 py-2"
               value={draft.minWords} onChange={(e) => set({ minWords: e.target.value })} />
        <label className="text-slate-500">字数上限</label>
        <input className="w-24 rounded border border-slate-700 bg-slate-900 px-3 py-2"
               value={draft.maxWords} onChange={(e) => set({ maxWords: e.target.value })} />
        <label className="text-slate-500">状态</label>
        <select className="rounded border border-slate-700 bg-slate-900 px-2 py-1"
                value={draft.status} onChange={(e) => set({ status: e.target.value })}>
          {statuses.map((status) => (
            <option key={status.key} value={status.key}>{status.label}</option>
          ))}
        </select>
      </div>
      <div className="flex items-center gap-2">
        <button className="rounded bg-indigo-600 px-4 py-2 disabled:opacity-50" disabled={busy}
                onClick={() => onSave({
                  goal: draft.goal,
                  conflict: draft.conflict,
                  turn: draft.turn,
                  story_time: draft.storyTime,
                  pov: draft.pov,
                  target_words_min: draft.minWords.trim() ? Number(draft.minWords) : null,
                  target_words_max: draft.maxWords.trim() ? Number(draft.maxWords) : null,
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
