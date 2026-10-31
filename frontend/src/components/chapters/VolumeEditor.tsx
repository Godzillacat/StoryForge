import { useEffect, useState } from 'react'
import type { ChapterStatusOption, VolumeNode } from '../../api/client'
import { Button } from '../../ui/Button'
import { Card } from '../../ui/Card'
import { Field, Input, Select, Textarea } from '../../ui/Field'

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
    <Card className="space-y-3 text-[13.5px]">
      <h3 className="text-[13.5px] font-medium text-ink-2">卷</h3>
      <Field label="卷名">
        <Input value={draft.name} onChange={(e) => set({ name: e.target.value })} />
      </Field>
      <Field label="本卷要做什么">
        <Textarea className="min-h-[80px]"
                  value={draft.purpose} onChange={(e) => set({ purpose: e.target.value })} />
      </Field>
      <Field label="摘要">
        <Textarea className="min-h-[80px]"
                  value={draft.summary} onChange={(e) => set({ summary: e.target.value })} />
      </Field>
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-muted">对应第几幕</label>
        <div className="w-24">
          <Input value={draft.actSeq} onChange={(e) => set({ actSeq: e.target.value })} placeholder="快照，可空" />
        </div>
        <label className="text-muted">目标字数</label>
        <div className="w-32">
          <Input value={draft.targetWords} onChange={(e) => set({ targetWords: e.target.value })} />
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
                  name: draft.name.trim(),
                  purpose: draft.purpose,
                  summary: draft.summary,
                  act_seq: draft.actSeq.trim() ? Number(draft.actSeq) : null,
                  target_words: draft.targetWords.trim() ? Number(draft.targetWords) : null,
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
