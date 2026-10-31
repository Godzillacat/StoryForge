import { useEffect, useState } from 'react'
import type { ChapterNode, ChapterStatusOption } from '../../api/client'
import { Button } from '../../ui/Button'
import { Card } from '../../ui/Card'
import { Field, Input, Select, Textarea } from '../../ui/Field'

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
  }, [chapter.id])

  const set = (patch: Partial<typeof draft>) => setDraft({ ...draft, ...patch })
  const levels = ['', '1', '2', '3', '4', '5']

  return (
    <Card className="space-y-3 text-[13.5px]">
      <h3 className="text-[13.5px] font-medium text-ink-2">章</h3>
      <Field label="标题">
        <Input value={draft.title} onChange={(e) => set({ title: e.target.value })} />
      </Field>
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-muted">视角</label>
        <div className="w-40">
          <Input value={draft.pov} onChange={(e) => set({ pov: e.target.value })} />
        </div>
        <label className="text-muted">目标字数</label>
        <div className="w-32">
          <Input value={draft.targetWords} onChange={(e) => set({ targetWords: e.target.value })} />
        </div>
      </div>
      <Field label="情绪基调">
        <Input value={draft.emotionalTone} onChange={(e) => set({ emotionalTone: e.target.value })} />
      </Field>
      <Field label="推进的线（顿号分隔）">
        <Input value={draft.lines} onChange={(e) => set({ lines: e.target.value })} />
      </Field>
      <Field label="章末钩子">
        <Input value={draft.hook} onChange={(e) => set({ hook: e.target.value })} />
      </Field>
      <Field label="本章摘要">
        <Textarea className="min-h-[96px]"
                  value={draft.summary} onChange={(e) => set({ summary: e.target.value })} />
      </Field>
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-muted">冲突强度</label>
        <div className="w-24">
          <Select options={levels.map((value) => ({ value, label: value || '未评' }))}
                  value={draft.conflictLevel} onChange={(e) => set({ conflictLevel: e.target.value })} />
        </div>
        <label className="text-muted">对话占比（%）</label>
        <div className="w-24">
          <Input value={draft.dialogueRatio} onChange={(e) => set({ dialogueRatio: e.target.value })} />
        </div>
        <label className="text-muted">钩子强度</label>
        <div className="w-24">
          <Select options={levels.map((value) => ({ value, label: value || '未评' }))}
                  value={draft.hookStrength} onChange={(e) => set({ hookStrength: e.target.value })} />
        </div>
        <label className="text-muted">状态</label>
        <div className="w-32">
          <Select options={statuses.map((status) => ({ value: status.key, label: status.label }))}
                  value={draft.status} onChange={(e) => set({ status: e.target.value })} />
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Button variant="primary" disabled={busy}
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
        </Button>
        <Button variant="danger" disabled={busy} onClick={onDelete}>
          删除
        </Button>
      </div>
    </Card>
  )
}
