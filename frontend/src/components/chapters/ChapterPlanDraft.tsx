import { useState } from 'react'
import type { ChapterStatusOption, PlanChapter, PlanVolume } from '../../api/client'
import { Button } from '../../ui/Button'
import { Card } from '../../ui/Card'
import { Input, Select, Textarea } from '../../ui/Field'

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
  statuses,
  warnings,
  openQuestions,
  busy,
  onWrite,
  onClose,
}: {
  volumes: PlanVolume[]
  statuses: ChapterStatusOption[]
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
    <Card className="space-y-3 text-[13.5px]">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="font-medium text-accent-ink">章纲草稿（逐项可改）</h3>
        <Button variant="accent" size="sm" onClick={() => setVolumes([...volumes, {
          name: '新卷', purpose: '', summary: '', act_seq: null, target_words: null,
          status: 'planned', chapters: [{ ...EMPTY_CHAPTER, title: '新章' }],
        }])}>+卷</Button>
        <Button variant="ghost" size="sm" onClick={onClose}>收起</Button>
      </div>
      {warnings.map((warning) => (
        <p key={warning} className="text-[11.5px] text-warn">{warning}</p>
      ))}
      {openQuestions.map((question) => (
        <p key={question} className="text-[11.5px] text-muted">待确认：{question}</p>
      ))}

      {volumes.map((volume, vIndex) => (
        <div key={vIndex} className="space-y-2 rounded-card border border-line p-3">
          <div className="flex flex-wrap items-center gap-2">
            <div className="w-44">
              <Input value={volume.name} onChange={(e) => updateVolume(vIndex, { name: e.target.value })} />
            </div>
            <div className="flex-1">
              <Input placeholder="本卷要做什么" value={volume.purpose}
                     onChange={(e) => updateVolume(vIndex, { purpose: e.target.value })} />
            </div>
            <div className="w-24">
              <Input placeholder="幕序号" value={volume.act_seq ?? ''}
                     onChange={(e) => updateVolume(vIndex, {
                       act_seq: e.target.value.trim() ? Number(e.target.value) : null,
                     })} />
            </div>
            <div className="w-24">
              <Input type="number" placeholder="目标字数" value={volume.target_words ?? ''}
                     onChange={(e) => updateVolume(vIndex, {
                       target_words: e.target.value.trim() ? Number(e.target.value) : null,
                     })} />
            </div>
            <div className="w-32">
              <Select options={statuses.map((status) => ({ value: status.key, label: status.label }))}
                      value={volume.status} onChange={(e) => updateVolume(vIndex, { status: e.target.value })} />
            </div>
            <Button variant="ghost" size="sm" onClick={() => setVolumes(volumes.filter((_, i) => i !== vIndex))}>
              删卷
            </Button>
            <Button variant="accent" size="sm" onClick={() => updateVolume(vIndex, {
              chapters: [...volume.chapters, { ...EMPTY_CHAPTER, title: '新章' }],
            })}>+章</Button>
          </div>
          <Textarea placeholder="本卷摘要" value={volume.summary}
                    onChange={(e) => updateVolume(vIndex, { summary: e.target.value })} />
          {volume.chapters.map((chapter, cIndex) => (
            <div key={cIndex} className="ml-4 space-y-1 rounded-card border border-line p-2">
              <div className="flex flex-wrap items-center gap-2">
                <div className="w-40">
                  <Input value={chapter.title} onChange={(e) => updateChapter(vIndex, cIndex, { title: e.target.value })} />
                </div>
                <div className="w-28">
                  <Input placeholder="视角" value={chapter.pov}
                         onChange={(e) => updateChapter(vIndex, cIndex, { pov: e.target.value })} />
                </div>
                <div className="w-24">
                  <Input placeholder="目标字数" value={chapter.target_words ?? ''}
                         onChange={(e) => updateChapter(vIndex, cIndex, {
                           target_words: e.target.value.trim() ? Number(e.target.value) : null,
                         })} />
                </div>
                <div className="w-24">
                  <Input placeholder="冲突 1-5" value={chapter.conflict_level ?? ''}
                         onChange={(e) => updateChapter(vIndex, cIndex, {
                           conflict_level: e.target.value.trim() ? Number(e.target.value) : null,
                         })} />
                </div>
                {/* 界面按百分比编辑；草稿内部与写入载荷仍是 0–1，和章编辑器一致。 */}
                <div className="w-20">
                  <Input placeholder="对话占比（%）"
                         value={chapter.dialogue_ratio == null ? '' : String(Math.round(chapter.dialogue_ratio * 100))}
                         onChange={(e) => updateChapter(vIndex, cIndex, {
                           dialogue_ratio: e.target.value.trim() ? Number(e.target.value) / 100 : null,
                         })} />
                </div>
                <div className="w-20">
                  <Input placeholder="钩子强度" value={chapter.hook_strength ?? ''}
                         onChange={(e) => updateChapter(vIndex, cIndex, {
                           hook_strength: e.target.value.trim() ? Number(e.target.value) : null,
                         })} />
                </div>
                <div className="w-32">
                  <Select options={statuses.map((status) => ({ value: status.key, label: status.label }))}
                          value={chapter.status}
                          onChange={(e) => updateChapter(vIndex, cIndex, { status: e.target.value })} />
                </div>
                <Button variant="ghost" size="sm"
                        onClick={() => updateVolume(vIndex, {
                          chapters: volume.chapters.filter((_, i) => i !== cIndex),
                        })}>删章</Button>
              </div>
              <Input placeholder="情绪基调" value={chapter.emotional_tone}
                     onChange={(e) => updateChapter(vIndex, cIndex, { emotional_tone: e.target.value })} />
              <Input placeholder="推进的线（顿号分隔）" value={chapter.lines.join('、')}
                     onChange={(e) => updateChapter(vIndex, cIndex, {
                       lines: e.target.value.split(/[、,，]/).map((v) => v.trim()).filter(Boolean),
                     })} />
              <Input placeholder="章末钩子" value={chapter.hook}
                     onChange={(e) => updateChapter(vIndex, cIndex, { hook: e.target.value })} />
              <Textarea placeholder="本章摘要" value={chapter.summary}
                        onChange={(e) => updateChapter(vIndex, cIndex, { summary: e.target.value })} />
            </div>
          ))}
        </div>
      ))}

      <div className="flex items-center gap-3">
        <div className="w-44">
          <Select options={[{ value: 'replace', label: '替换现有结构' }, { value: 'append', label: '追加到末尾' }]}
                  value={mode} onChange={(e) => setMode(e.target.value as 'replace' | 'append')} />
        </div>
        <Button variant="primary" disabled={busy} onClick={write}>
          写入项目
        </Button>
      </div>
    </Card>
  )
}
