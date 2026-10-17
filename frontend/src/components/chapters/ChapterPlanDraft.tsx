import { useState } from 'react'
import type { PlanChapter, PlanVolume } from '../../api/client'

const EMPTY_CHAPTER: PlanChapter = {
  title: '',
  pov: '',
  target_words: null,
  emotional_tone: '',
  lines: [],
  hook: '',
  summary: '',
  conflict_level: null,
  dialogue_ratio: null,
  hook_strength: null,
  status: 'planned',
}

export default function ChapterPlanDraft({
  volumes: initial,
  warnings,
  openQuestions,
  busy,
  onWrite,
  onClose,
}: {
  volumes: PlanVolume[]
  warnings: string[]
  openQuestions: string[]
  busy: boolean
  onWrite: (volumes: PlanVolume[], mode: 'replace' | 'append') => Promise<void>
  onClose: () => void
}) {
  const [volumes, setVolumes] = useState<PlanVolume[]>(initial)
  const [mode, setMode] = useState<'replace' | 'append'>('replace')

  const updateVolume = (index: number, patch: Partial<PlanVolume>) =>
    setVolumes((prev) => prev.map((item, i) => (i === index ? { ...item, ...patch } : item)))
  const updateChapter = (vIndex: number, cIndex: number, patch: Partial<PlanChapter>) =>
    setVolumes((prev) => prev.map((volume, i) =>
      i === vIndex
        ? { ...volume, chapters: volume.chapters.map((c, j) => (j === cIndex ? { ...c, ...patch } : c)) }
        : volume,
    ))

  function write() {
    if (volumes.length === 0) return
    const message = mode === 'replace'
      ? '写入会删除本项目现有的卷、章、场景（伏笔名保留）。确定替换？'
      : '把这份草稿追加到现有结构之后？'
    if (!window.confirm(message)) return
    void onWrite(volumes, mode)
  }

  return (
    <section className="space-y-3 rounded border border-indigo-800 bg-slate-950/60 p-4 text-sm">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="font-medium text-indigo-300">章纲草稿（逐项可改）</h3>
        <button className="text-xs text-indigo-400" onClick={() => setVolumes([...volumes, {
          name: '新卷', purpose: '', summary: '', act_seq: null, target_words: null,
          status: 'planned', chapters: [{ ...EMPTY_CHAPTER, title: '新章' }],
        }])}>+卷</button>
        <button className="text-xs text-slate-400" onClick={onClose}>收起</button>
      </div>
      {warnings.map((warning) => (
        <p key={warning} className="text-xs text-amber-300">{warning}</p>
      ))}
      {openQuestions.map((question) => (
        <p key={question} className="text-xs text-slate-400">待确认：{question}</p>
      ))}

      {volumes.map((volume, vIndex) => (
        <div key={vIndex} className="space-y-2 rounded border border-slate-800 p-3">
          <div className="flex flex-wrap items-center gap-2">
            <input className="w-44 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                   value={volume.name} onChange={(e) => updateVolume(vIndex, { name: e.target.value })} />
            <input className="flex-1 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                   placeholder="本卷要做什么" value={volume.purpose}
                   onChange={(e) => updateVolume(vIndex, { purpose: e.target.value })} />
            <input className="w-24 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                   placeholder="幕序号" value={volume.act_seq ?? ''}
                   onChange={(e) => updateVolume(vIndex, {
                     act_seq: e.target.value.trim() ? Number(e.target.value) : null,
                   })} />
            <button className="text-xs text-slate-500" onClick={() => setVolumes(volumes.filter((_, i) => i !== vIndex))}>
              删卷
            </button>
            <button className="text-xs text-indigo-400" onClick={() => updateVolume(vIndex, {
              chapters: [...volume.chapters, { ...EMPTY_CHAPTER, title: '新章' }],
            })}>+章</button>
          </div>
          {volume.chapters.map((chapter, cIndex) => (
            <div key={cIndex} className="ml-4 space-y-1 rounded border border-slate-800 p-2">
              <div className="flex flex-wrap items-center gap-2">
                <input className="w-40 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                       value={chapter.title} onChange={(e) => updateChapter(vIndex, cIndex, { title: e.target.value })} />
                <input className="w-28 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                       placeholder="视角" value={chapter.pov}
                       onChange={(e) => updateChapter(vIndex, cIndex, { pov: e.target.value })} />
                <input className="w-24 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                       placeholder="目标字数" value={chapter.target_words ?? ''}
                       onChange={(e) => updateChapter(vIndex, cIndex, {
                         target_words: e.target.value.trim() ? Number(e.target.value) : null,
                       })} />
                <input className="w-24 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                       placeholder="冲突 1-5" value={chapter.conflict_level ?? ''}
                       onChange={(e) => updateChapter(vIndex, cIndex, {
                         conflict_level: e.target.value.trim() ? Number(e.target.value) : null,
                       })} />
                <input className="w-20 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                       placeholder="对话占比" value={chapter.dialogue_ratio ?? ''}
                       onChange={(e) => updateChapter(vIndex, cIndex, {
                         dialogue_ratio: e.target.value.trim() ? Number(e.target.value) : null,
                       })} />
                <input className="w-20 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                       placeholder="钩子强度" value={chapter.hook_strength ?? ''}
                       onChange={(e) => updateChapter(vIndex, cIndex, {
                         hook_strength: e.target.value.trim() ? Number(e.target.value) : null,
                       })} />
                <button className="text-xs text-slate-500"
                        onClick={() => updateVolume(vIndex, {
                          chapters: volume.chapters.filter((_, i) => i !== cIndex),
                        })}>删章</button>
              </div>
              <input className="w-full rounded border border-slate-700 bg-slate-900 px-2 py-1"
                     placeholder="情绪基调" value={chapter.emotional_tone}
                     onChange={(e) => updateChapter(vIndex, cIndex, { emotional_tone: e.target.value })} />
              <input className="w-full rounded border border-slate-700 bg-slate-900 px-2 py-1"
                     placeholder="推进的线（顿号分隔）" value={chapter.lines.join('、')}
                     onChange={(e) => updateChapter(vIndex, cIndex, {
                       lines: e.target.value.split(/[、,，]/).map((v) => v.trim()).filter(Boolean),
                     })} />
              <input className="w-full rounded border border-slate-700 bg-slate-900 px-2 py-1"
                     placeholder="章末钩子" value={chapter.hook}
                     onChange={(e) => updateChapter(vIndex, cIndex, { hook: e.target.value })} />
              <textarea className="h-14 w-full rounded border border-slate-700 bg-slate-900 p-2 text-xs"
                        placeholder="本章摘要" value={chapter.summary}
                        onChange={(e) => updateChapter(vIndex, cIndex, { summary: e.target.value })} />
            </div>
          ))}
        </div>
      ))}

      <div className="flex items-center gap-3">
        <select className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs"
                value={mode} onChange={(e) => setMode(e.target.value as 'replace' | 'append')}>
          <option value="replace">替换现有结构</option>
          <option value="append">追加到末尾</option>
        </select>
        <button className="rounded bg-indigo-600 px-4 py-2 disabled:opacity-50" disabled={busy}
                onClick={write}>
          写入项目
        </button>
      </div>
    </section>
  )
}
