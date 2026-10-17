import { useEffect, useState } from 'react'
import type {
  ChapterStatusOption,
  Foreshadow,
  SceneNode,
  SettingEntry,
} from '../../api/client'

export default function SceneEditor({
  scene,
  statuses,
  entries,
  foreshadows,
  busy,
  onSave,
  onDelete,
}: {
  scene: SceneNode
  statuses: ChapterStatusOption[]
  entries: SettingEntry[]
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

      <div className="space-y-2">
        <div className="text-slate-400">出场人物（只列人物）</div>
        <div className="flex flex-wrap gap-2">
          {characters.map((character) => {
            const on = draft.characterIds.includes(character.id)
            return (
              <button key={character.id} onClick={() => toggleCharacter(character.id)}
                      className={`rounded border px-3 py-1 text-xs ${
                        on ? 'border-indigo-500 bg-slate-800' : 'border-slate-700'
                      }`}>
                {character.name}
              </button>
            )
          })}
          {characters.length === 0 && (
            <span className="text-xs text-slate-500">还没有人物，先去世界观里建一个。</span>
          )}
        </div>
        {draft.characterIds.length > 0 && (
          <div className="text-xs text-slate-500">
            已选：{draft.characterIds.map(nameOf).join('、')}
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <label className="text-slate-500">地点</label>
        <select className="rounded border border-slate-700 bg-slate-900 px-3 py-2"
                value={draft.locationId} onChange={(e) => set({ locationId: e.target.value })}>
          <option value="">（无地点）</option>
          {entries.map((entry) => (
            <option key={entry.id} value={entry.id}>{entry.name}</option>
          ))}
        </select>
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

      <datalist id="foreshadow-names">
        {foreshadows.map((row) => <option key={row.id} value={row.name} />)}
      </datalist>

      {(['plant', 'pay'] as const).map((kind) => {
        const names = kind === 'plant' ? draft.plantNames : draft.payNames
        const input = kind === 'plant' ? plantInput : payInput
        const setInput = kind === 'plant' ? setPlantInput : setPayInput
        return (
          <div key={kind} className="space-y-1">
            <div className="text-slate-400">{kind === 'plant' ? '埋设的伏笔' : '回收的伏笔'}</div>
            <div className="flex flex-wrap gap-2">
              {names.map((name) => (
                <span key={name} className="rounded bg-slate-800 px-2 py-1 text-xs">
                  {name}
                  <button className="ml-2 text-amber-400" onClick={() => removeName(kind, name)}>
                    ×
                  </button>
                </span>
              ))}
            </div>
            <div className="flex items-center gap-2">
              <input className="w-64 rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs"
                     list="foreshadow-names" placeholder="已有伏笔名或新名字"
                     value={input} onChange={(e) => setInput(e.target.value)}
                     onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addName(kind) } }} />
              <button className="text-xs text-indigo-400" onClick={() => addName(kind)}>
                添加
              </button>
            </div>
          </div>
        )
      })}

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
                  characters: draft.characterIds.map(nameOf),
                  location: draft.locationId ? nameOf(draft.locationId) : '',
                  foreshadow_plants: draft.plantNames,
                  foreshadow_pays: draft.payNames,
                })}>
          保存
        </button>
        <button className="rounded border border-amber-700 px-4 py-2 text-amber-400" disabled={busy}
                onClick={onDelete}>
          删除
        </button>
      </div>
      <p className="text-xs text-slate-500">
        人物、地点、伏笔都按名称保存；名称找不到或与另一个场景冲突时，后端会列出原因。
      </p>
    </section>
  )
}
