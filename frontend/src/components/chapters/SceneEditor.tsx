import { useEffect, useState } from 'react'
import type {
  ChapterStatusOption,
  Foreshadow,
  SceneNode,
  SettingEntry,
} from '../../api/client'
import { Button } from '../../ui/Button'
import { Card } from '../../ui/Card'
import { Field, Input, Select, Textarea } from '../../ui/Field'

export default function SceneEditor({
  scene,
  statuses,
  entries,
  entriesReady,
  foreshadows,
  busy,
  onSave,
  onDelete,
}: {
  scene: SceneNode
  statuses: ChapterStatusOption[]
  entries: SettingEntry[]
  entriesReady: boolean
  foreshadows: Foreshadow[]
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
    characterIds: [] as string[],
    locationId: '',
    plantNames: [] as string[],
    payNames: [] as string[],
  })
  const [plantInput, setPlantInput] = useState('')
  const [payInput, setPayInput] = useState('')

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
      characterIds: scene.characters,
      locationId: scene.location_id ?? '',
      plantNames: scene.foreshadows.plants.map((item) => item.name),
      payNames: scene.foreshadows.pays.map((item) => item.name),
    })
    setPlantInput('')
    setPayInput('')
  }, [scene.id])

  const set = (patch: Partial<typeof draft>) => setDraft({ ...draft, ...patch })
  const characters = entries.filter((entry) => entry.type === 'character')
  const nameOf = (id: string) => entries.find((entry) => entry.id === id)?.name ?? '（已删除）'
  const resolvedNameOf = (id: string) => entries.find((entry) => entry.id === id)?.name

  function toggleCharacter(id: string) {
    set({
      characterIds: draft.characterIds.includes(id)
        ? draft.characterIds.filter((item) => item !== id)
        : [...draft.characterIds, id],
    })
  }

  function addName(kind: 'plant' | 'pay') {
    const raw = kind === 'plant' ? plantInput : payInput
    const name = raw.trim()
    if (!name) return
    if (kind === 'plant') {
      if (!draft.plantNames.includes(name)) set({ plantNames: [...draft.plantNames, name] })
      setPlantInput('')
    } else {
      if (!draft.payNames.includes(name)) set({ payNames: [...draft.payNames, name] })
      setPayInput('')
    }
  }

  function removeName(kind: 'plant' | 'pay', name: string) {
    if (kind === 'plant') {
      set({ plantNames: draft.plantNames.filter((item) => item !== name) })
    } else {
      set({ payNames: draft.payNames.filter((item) => item !== name) })
    }
  }

  return (
    <Card className="space-y-3 text-[13.5px]">
      <h3 className="text-[13.5px] font-medium text-ink-2">场景</h3>
      <Field label="场景目标">
        <Textarea className="min-h-[80px]"
                  value={draft.goal} onChange={(e) => set({ goal: e.target.value })} />
      </Field>
      <Field label="冲突">
        <Textarea className="min-h-[80px]"
                  value={draft.conflict} onChange={(e) => set({ conflict: e.target.value })} />
      </Field>
      <Field label="转折">
        <Textarea className="min-h-[80px]"
                  value={draft.turn} onChange={(e) => set({ turn: e.target.value })} />
      </Field>

      <div className="space-y-2">
        <div className="text-muted">出场人物（只列人物）</div>
        <div className="flex flex-wrap gap-2">
          {characters.map((character) => {
            const on = draft.characterIds.includes(character.id)
            return (
              <button key={character.id} onClick={() => toggleCharacter(character.id)}
                      className={`rounded-control border px-3 py-1 text-[11.5px] ${
                        on ? 'border-accent bg-accent-soft' : 'border-line-strong'
                      }`}>
                {character.name}
              </button>
            )
          })}
          {characters.length === 0 && (
            <span className="text-[11.5px] text-muted">还没有人物，先去世界观里建一个。</span>
          )}
        </div>
        {draft.characterIds.length > 0 && (
          <div className="flex flex-wrap items-center gap-1 text-[11.5px] text-muted">
            <span>已选：</span>
            {draft.characterIds.map((id) => (
              <span key={id} className="rounded-tag bg-accent-soft px-2 py-1">
                {nameOf(id)}
                <button className="ml-2 text-warn"
                        onClick={() => set({
                          characterIds: draft.characterIds.filter((item) => item !== id),
                        })}>
                  ×
                </button>
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <label className="text-muted">地点</label>
        <div className="w-40">
          <Select options={[{ value: '', label: '（无地点）' }, ...entries.map((entry) => ({ value: entry.id, label: entry.name }))]}
                  value={draft.locationId} onChange={(e) => set({ locationId: e.target.value })} />
        </div>
        <label className="text-muted">故事内时间</label>
        <div className="w-44">
          <Input value={draft.storyTime} onChange={(e) => set({ storyTime: e.target.value })} />
        </div>
        <label className="text-muted">视角</label>
        <div className="w-40">
          <Input value={draft.pov} onChange={(e) => set({ pov: e.target.value })} />
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <label className="text-muted">字数下限</label>
        <div className="w-24">
          <Input value={draft.minWords} onChange={(e) => set({ minWords: e.target.value })} />
        </div>
        <label className="text-muted">字数上限</label>
        <div className="w-24">
          <Input value={draft.maxWords} onChange={(e) => set({ maxWords: e.target.value })} />
        </div>
        <label className="text-muted">状态</label>
        <div className="w-32">
          <Select options={statuses.map((status) => ({ value: status.key, label: status.label }))}
                  value={draft.status} onChange={(e) => set({ status: e.target.value })} />
        </div>
      </div>

      <datalist id="foreshadow-names">
        {foreshadows.map((row) => <option key={row.id} value={row.name} />)}
      </datalist>

      {(['plant', 'pay'] as const).map((kind) => {
        const names = kind === 'plant' ? draft.plantNames : draft.payNames
        const input = kind === 'plant' ? plantInput : payInput
        const setInput = kind === 'plant' ? setPlantInput : setPayInput
        return (
          <div key={kind} className="space-y-1">
            <div className="text-muted">{kind === 'plant' ? '埋设的伏笔' : '回收的伏笔'}</div>
            <div className="flex flex-wrap gap-2">
              {names.map((name) => (
                <span key={name} className="rounded-tag bg-accent-soft px-2 py-1 text-[11.5px]">
                  {name}
                  <button className="ml-2 text-warn" onClick={() => removeName(kind, name)}>
                    ×
                  </button>
                </span>
              ))}
            </div>
            <div className="flex items-center gap-2">
              <div className="w-64">
                <Input list="foreshadow-names" placeholder="已有伏笔名或新名字"
                       value={input} onChange={(e) => setInput(e.target.value)}
                       onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addName(kind) } }} />
              </div>
              <Button variant="accent" size="sm" onClick={() => addName(kind)}>
                添加
              </Button>
            </div>
          </div>
        )
      })}

      <div className="flex items-center gap-2">
        <Button variant="primary" disabled={busy}
                onClick={() => {
                  const fields: Record<string, unknown> = {
                    goal: draft.goal,
                    conflict: draft.conflict,
                    turn: draft.turn,
                    story_time: draft.storyTime,
                    pov: draft.pov,
                    target_words_min: draft.minWords.trim() ? Number(draft.minWords) : null,
                    target_words_max: draft.maxWords.trim() ? Number(draft.maxWords) : null,
                    status: draft.status,
                    foreshadow_plants: draft.plantNames,
                    foreshadow_pays: draft.payNames,
                  }
                  // 只有条目确实属于当前项目且已加载时，才敢把 ID 映射成名称。
                  // 否则整键省略：后端 exclude_unset 会保留库里的原值，而明确
                  // 发送空值等于静默清空场景的人物与地点。
                  if (entriesReady) {
                    // 世界观里已删除的条目只剩一个解析不到名称的 ID；丢弃它，
                    // 免得一个残影让每次保存都被后端拒绝。
                    fields.characters = draft.characterIds
                      .map(resolvedNameOf)
                      .filter((name): name is string => Boolean(name))
                    fields.location = draft.locationId
                      ? resolvedNameOf(draft.locationId) ?? ''
                      : ''
                  }
                  onSave(fields)
                }}>
          保存
        </Button>
        <Button variant="danger" disabled={busy} onClick={onDelete}>
          删除
        </Button>
      </div>
      <p className="text-[11.5px] text-muted">
        人物、地点、伏笔都按名称保存；名称找不到或与另一个场景冲突时，后端会列出原因。
      </p>
    </Card>
  )
}
