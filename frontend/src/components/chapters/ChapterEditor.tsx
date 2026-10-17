import { useEffect, useState } from 'react'
import type { ChapterNode, ChapterStatusOption } from '../../api/client'

export default function ChapterEditor({
  chapter,
  statuses,
  busy,
  onSave,
  onDelete,
}: {
  chapter: ChapterNode
  statuses: ChapterStatusOption[]
  busy: boolean
  onSave: (fields: Record<string, unknown>) => Promise<void>
  onDelete: () => Promise<void>
}) {
  const [draft, setDraft] = useState({
    title: '',
    pov: '',
    targetWords: '',
    emotionalTone: '',
    lines: '',
    hook: '',
    summary: '',
    conflictLevel: '',
    dialogueRatio: '',
    hookStrength: '',
    status: 'planned',
  })

  useEffect(() => {
    setDraft({
      title: chapter.title,
      pov: chapter.pov,
      targetWords: chapter.target_words == null ? '' : String(chapter.target_words),
      emotionalTone: chapter.emotional_tone,
      lines: chapter.lines.join('、'),
      hook: chapter.hook,
      summary: chapter.summary,
      conflictLevel: chapter.conflict_level == null ? '' : String(chapter.conflict_level),
      dialogueRatio:
        chapter.dialogue_ratio == null ? '' : String(Math.round(chapter.dialogue_ratio * 100)),
      hookStrength: chapter.hook_strength == null ? '' : String(chapter.hook_strength),
      status: chapter.status,
    })
  }, [chapter])

  const set = (patch: Partial<typeof draft>) => setDraft({ ...draft, ...patch })
  const levels = ['', '1', '2', '3', '4', '5']

  return (
    <section className="space-y-3 rounded border border-slate-800 p-4 text-sm">
      <h3 className="text-sm font-medium text-slate-300">章</h3>
      <label className="block">
        <span className="text-slate-500">标题</span>
        <input className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-3 py-2"
               value={draft.title} onChange={(e) => set({ title: e.target.value })} />
      </label>
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-slate-500">视角</label>
        <input className="w-40 rounded border border-slate-700 bg-slate-900 px-3 py-2"
               value={draft.pov} onChange={(e) => set({ pov: e.target.value })} />
        <label className="text-slate-500">目标字数</label>
        <input className="w-32 rounded border border-slate-700 bg-slate-900 px-3 py-2"
               value={draft.targetWords} onChange={(e) => set({ targetWords: e.target.value })} />
      </div>
      <label className="block">
        <span className="text-slate-500">情绪基调</span>
        <input className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-3 py-2"
               value={draft.emotionalTone} onChange={(e) => set({ emotionalTone: e.target.value })} />
      </label>
      <label className="block">
        <span className="text-slate-500">推进的线（顿号分隔）</span>
        <input className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-3 py-2"
               value={draft.lines} onChange={(e) => set({ lines: e.target.value })} />
      </label>
      <label className="block">
        <span className="text-slate-500">章末钩子</span>
        <input className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-3 py-2"
               value={draft.hook} onChange={(e) => set({ hook: e.target.value })} />
      </label>
      <label className="block">
        <span className="text-slate-500">本章摘要</span>
        <textarea className="mt-1 h-24 w-full rounded border border-slate-700 bg-slate-900 p-3"
                  value={draft.summary} onChange={(e) => set({ summary: e.target.value })} />
      </label>
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-slate-500">冲突强度</label>
        <select className="rounded border border-slate-700 bg-slate-900 px-2 py-1"
                value={draft.conflictLevel} onChange={(e) => set({ conflictLevel: e.target.value })}>
          {levels.map((value) => <option key={value} value={value}>{value || '未评'}</option>)}
        </select>
        <label className="text-slate-500">对话占比（%）</label>
        <input className="w-24 rounded border border-slate-700 bg-slate-900 px-2 py-1"
               value={draft.dialogueRatio} onChange={(e) => set({ dialogueRatio: e.target.value })} />
        <label className="text-slate-500">钩子强度</label>
        <select className="rounded border border-slate-700 bg-slate-900 px-2 py-1"
                value={draft.hookStrength} onChange={(e) => set({ hookStrength: e.target.value })}>
          {levels.map((value) => <option key={value} value={value}>{value || '未评'}</option>)}
        </select>
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
                  title: draft.title.trim(),
                  pov: draft.pov,
                  target_words: draft.targetWords.trim() ? Number(draft.targetWords) : null,
                  emotional_tone: draft.emotionalTone,
                  lines: draft.lines.split(/[、,，]/).map((item) => item.trim()).filter(Boolean),
                  hook: draft.hook,
                  summary: draft.summary,
                  conflict_level: draft.conflictLevel ? Number(draft.conflictLevel) : null,
                  dialogue_ratio: draft.dialogueRatio.trim() ? Number(draft.dialogueRatio) / 100 : null,
                  hook_strength: draft.hookStrength ? Number(draft.hookStrength) : null,
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
