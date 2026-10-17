import { useState } from 'react'
import type { PlanScene } from '../../api/client'

const EMPTY_SCENE: PlanScene = {
  goal: '', conflict: '', turn: '', characters: [], location: '', story_time: '', pov: '',
  target_words_min: null, target_words_max: null, foreshadow_plants: [], foreshadow_pays: [],
}

export default function ScenePlanDraft({
  chapterTitle,
  scenes: initial,
  warnings,
  openQuestions,
  busy,
  onWrite,
  onClose,
}: {
  chapterTitle: string
  scenes: PlanScene[]
  warnings: string[]
  openQuestions: string[]
  busy: boolean
  onWrite: (scenes: PlanScene[], mode: 'replace' | 'append') => Promise<void>
  onClose: () => void
}) {
  const [scenes, setScenes] = useState<PlanScene[]>(initial)
  const [mode, setMode] = useState<'replace' | 'append'>('replace')

  const update = (index: number, patch: Partial<PlanScene>) =>
    setScenes((prev) => prev.map((item, i) => (i === index ? { ...item, ...patch } : item)))

  function write() {
    if (scenes.length === 0) return
    const message = mode === 'replace'
      ? '写入会删除本章现有场景（伏笔名保留）。确定替换？'
      : '把这份场景草稿追加到本章末尾？'
    if (!window.confirm(message)) return
    void onWrite(scenes, mode)
  }

  return (
    <section className="space-y-3 rounded border border-emerald-800 bg-slate-950/60 p-4 text-sm">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="font-medium text-emerald-300">场景草稿 · {chapterTitle}（逐项可改）</h3>
        <button className="text-xs text-emerald-400"
                onClick={() => setScenes([...scenes, { ...EMPTY_SCENE }])}>+场景</button>
        <button className="text-xs text-slate-400" onClick={onClose}>收起</button>
      </div>
      {warnings.map((warning) => <p key={warning} className="text-xs text-amber-300">{warning}</p>)}
      {openQuestions.map((question) => <p key={question} className="text-xs text-slate-400">待确认：{question}</p>)}

      {scenes.map((scene, index) => (
        <div key={index} className="space-y-1 rounded border border-slate-800 p-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-slate-500">场景 {index + 1}</span>
            <input className="flex-1 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                   placeholder="场景目标" value={scene.goal}
                   onChange={(e) => update(index, { goal: e.target.value })} />
            <button className="text-xs text-slate-500"
                    onClick={() => setScenes(scenes.filter((_, i) => i !== index))}>删除</button>
          </div>
          <input className="w-full rounded border border-slate-700 bg-slate-900 px-2 py-1"
                 placeholder="冲突" value={scene.conflict}
                 onChange={(e) => update(index, { conflict: e.target.value })} />
          <input className="w-full rounded border border-slate-700 bg-slate-900 px-2 py-1"
                 placeholder="转折" value={scene.turn}
                 onChange={(e) => update(index, { turn: e.target.value })} />
          <div className="flex flex-wrap gap-2">
            <input className="w-52 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                   placeholder="人物（顿号分隔，用标准名）" value={scene.characters.join('、')}
                   onChange={(e) => update(index, {
                     characters: e.target.value.split(/[、,，]/).map((v) => v.trim()).filter(Boolean),
                   })} />
            <input className="w-40 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                   placeholder="地点（标准名）" value={scene.location}
                   onChange={(e) => update(index, { location: e.target.value })} />
            <input className="w-36 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                   placeholder="故事内时间" value={scene.story_time}
                   onChange={(e) => update(index, { story_time: e.target.value })} />
            <input className="w-28 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                   placeholder="视角" value={scene.pov}
                   onChange={(e) => update(index, { pov: e.target.value })} />
            <input className="w-24 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                   placeholder="字数下限" value={scene.target_words_min ?? ''}
                   onChange={(e) => update(index, {
                     target_words_min: e.target.value.trim() ? Number(e.target.value) : null,
                   })} />
            <input className="w-24 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                   placeholder="字数上限" value={scene.target_words_max ?? ''}
                   onChange={(e) => update(index, {
                     target_words_max: e.target.value.trim() ? Number(e.target.value) : null,
                   })} />
          </div>
          <div className="flex flex-wrap gap-2">
            <input className="w-40 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                   placeholder="埋设伏笔（顿号分隔）" value={scene.foreshadow_plants.join('、')}
                   onChange={(e) => update(index, {
                     foreshadow_plants: e.target.value.split(/[、,，]/).map((v) => v.trim()).filter(Boolean),
                   })} />
            <input className="w-40 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                   placeholder="回收伏笔（顿号分隔）" value={scene.foreshadow_pays.join('、')}
                   onChange={(e) => update(index, {
                     foreshadow_pays: e.target.value.split(/[、,，]/).map((v) => v.trim()).filter(Boolean),
                   })} />
          </div>
        </div>
      ))}

      <div className="flex items-center gap-3">
        <select className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs"
                value={mode} onChange={(e) => setMode(e.target.value as 'replace' | 'append')}>
          <option value="replace">替换本章场景</option>
          <option value="append">追加到本章末尾</option>
        </select>
        <button className="rounded bg-emerald-600 px-4 py-2 disabled:opacity-50" disabled={busy}
                onClick={write}>
          写入本章
        </button>
      </div>
    </section>
  )
}
