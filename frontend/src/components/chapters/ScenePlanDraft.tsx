import { useState } from 'react'
import type { PlanScene } from '../../api/client'
import { Button } from '../../ui/Button'
import { Card } from '../../ui/Card'
import { Input, Select } from '../../ui/Field'

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
    <Card className="space-y-3 text-[13.5px]">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="font-medium text-accent-ink">场景草稿 · {chapterTitle}（逐项可改）</h3>
        <Button variant="accent" size="sm"
                onClick={() => setScenes([...scenes, { ...EMPTY_SCENE }])}>+场景</Button>
        <Button variant="ghost" size="sm" onClick={onClose}>收起</Button>
      </div>
      {warnings.map((warning) => <p key={warning} className="text-[11.5px] text-warn">{warning}</p>)}
      {openQuestions.map((question) => <p key={question} className="text-[11.5px] text-muted">待确认：{question}</p>)}

      {scenes.map((scene, index) => (
        <div key={index} className="space-y-1 rounded-card border border-line p-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[11.5px] text-muted">场景 {index + 1}</span>
            <div className="flex-1">
              <Input placeholder="场景目标" value={scene.goal}
                     onChange={(e) => update(index, { goal: e.target.value })} />
            </div>
            <Button variant="ghost" size="sm"
                    onClick={() => setScenes(scenes.filter((_, i) => i !== index))}>删除</Button>
          </div>
          <Input placeholder="冲突" value={scene.conflict}
                 onChange={(e) => update(index, { conflict: e.target.value })} />
          <Input placeholder="转折" value={scene.turn}
                 onChange={(e) => update(index, { turn: e.target.value })} />
          <div className="flex flex-wrap gap-2">
            <div className="w-52">
              <Input placeholder="人物（顿号分隔，用标准名）" value={scene.characters.join('、')}
                     onChange={(e) => update(index, {
                       characters: e.target.value.split(/[、,，]/).map((v) => v.trim()).filter(Boolean),
                     })} />
            </div>
            <div className="w-40">
              <Input placeholder="地点（标准名）" value={scene.location}
                     onChange={(e) => update(index, { location: e.target.value })} />
            </div>
            <div className="w-36">
              <Input placeholder="故事内时间" value={scene.story_time}
                     onChange={(e) => update(index, { story_time: e.target.value })} />
            </div>
            <div className="w-28">
              <Input placeholder="视角" value={scene.pov}
                     onChange={(e) => update(index, { pov: e.target.value })} />
            </div>
            <div className="w-24">
              <Input placeholder="字数下限" value={scene.target_words_min ?? ''}
                     onChange={(e) => update(index, {
                       target_words_min: e.target.value.trim() ? Number(e.target.value) : null,
                     })} />
            </div>
            <div className="w-24">
              <Input placeholder="字数上限" value={scene.target_words_max ?? ''}
                     onChange={(e) => update(index, {
                       target_words_max: e.target.value.trim() ? Number(e.target.value) : null,
                     })} />
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <div className="w-40">
              <Input placeholder="埋设伏笔（顿号分隔）" value={scene.foreshadow_plants.join('、')}
                     onChange={(e) => update(index, {
                       foreshadow_plants: e.target.value.split(/[、,，]/).map((v) => v.trim()).filter(Boolean),
                     })} />
            </div>
            <div className="w-40">
              <Input placeholder="回收伏笔（顿号分隔）" value={scene.foreshadow_pays.join('、')}
                     onChange={(e) => update(index, {
                       foreshadow_pays: e.target.value.split(/[、,，]/).map((v) => v.trim()).filter(Boolean),
                     })} />
            </div>
          </div>
        </div>
      ))}

      <div className="flex items-center gap-3">
        <div className="w-44">
          <Select options={[{ value: 'replace', label: '替换本章场景' }, { value: 'append', label: '追加到本章末尾' }]}
                  value={mode} onChange={(e) => setMode(e.target.value as 'replace' | 'append')} />
        </div>
        <Button variant="primary" disabled={busy} onClick={write}>
          写入本章
        </Button>
      </div>
    </Card>
  )
}
