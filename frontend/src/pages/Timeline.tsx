import { useEffect, useMemo, useState } from 'react'
import { api, type SettingEntry, type TimelineEvent } from '../api/client'
import { useCurrentProject } from '../state/ProjectContext'

interface Draft {
  title: string
  story_time: string
  description: string
  participants: string[]
  location_id: string
}

const EMPTY: Draft = {
  title: '',
  story_time: '',
  description: '',
  participants: [],
  location_id: '',
}

export default function Timeline() {
  // 当前项目由外壳持有；切换入口在侧栏。
  const { projectId } = useCurrentProject()
  const [entries, setEntries] = useState<SettingEntry[]>([])
  const [events, setEvents] = useState<TimelineEvent[]>([])
  const [draft, setDraft] = useState<Draft>(EMPTY)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [notice, setNotice] = useState('')

  useEffect(() => {
    if (!projectId) return
    setNotice('')
    setDraft(EMPTY)
    setEditingId(null)
    setEntries([])
    setEvents([])
    api.listEntries(projectId).then(setEntries).catch((e) => setNotice((e as Error).message))
    api.listTimeline(projectId).then(setEvents).catch((e) => setNotice((e as Error).message))
  }, [projectId])

  const byId = useMemo(() => new Map(entries.map((e) => [e.id, e])), [entries])
  const characters = entries.filter((e) => e.type === 'character')

  function nameOf(id: string) {
    return byId.get(id)?.name ?? '（已删除）'
  }

  async function refresh() {
    setEntries(await api.listEntries(projectId))
    setEvents(await api.listTimeline(projectId))
  }

  function startCreate() {
    setEditingId(null)
    setDraft(EMPTY)
    setNotice('')
  }

  function startEdit(event: TimelineEvent) {
    setEditingId(event.id)
    setDraft({
      title: event.title,
      story_time: event.story_time,
      description: event.description,
      participants: event.participants,
      location_id: event.location_id ?? '',
    })
    setNotice('')
  }

  async function save() {
    if (!draft.title.trim()) {
      setNotice('先给事件起个标题')
      return
    }
    const body = {
      title: draft.title.trim(),
      story_time: draft.story_time,
      description: draft.description,
      participants: draft.participants,
      location_id: draft.location_id || null,
    }
    try {
      if (editingId) await api.updateTimelineEvent(editingId, body)
      else await api.createTimelineEvent(projectId, body)
      await refresh()
      setDraft(EMPTY)
      setEditingId(null)
      setNotice(editingId ? '已保存' : '已新建')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function move(event: TimelineEvent, direction: 'up' | 'down') {
    try {
      await api.moveTimelineEvent(event.id, direction)
      await refresh()
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function remove(event: TimelineEvent) {
    if (!window.confirm(`删除事件「${event.title}」？`)) return
    try {
      await api.deleteTimelineEvent(event.id)
      if (editingId === event.id) {
        setEditingId(null)
        setDraft(EMPTY)
      }
      await refresh()
      setNotice('已删除')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  function toggleParticipant(id: string) {
    setDraft((prev) => ({
      ...prev,
      participants: prev.participants.includes(id)
        ? prev.participants.filter((item) => item !== id)
        : [...prev.participants, id],
    }))
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-xl font-semibold">时间线</h2>
        <button className="rounded border border-slate-700 px-3 py-2 text-sm" onClick={startCreate}>
          新建事件
        </button>
      </div>

      {notice && <p className="text-sm text-slate-400">{notice}</p>}

      <section className="space-y-3 rounded border border-slate-800 p-4 text-sm">
        <h3 className="text-sm font-medium text-slate-300">
          {editingId ? '编辑事件' : '新建事件'}
        </h3>
        <div className="flex flex-wrap items-center gap-2">
          <input
            className="w-52 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
            placeholder="标题"
            value={draft.title}
            onChange={(e) => setDraft({ ...draft, title: e.target.value })}
          />
          <input
            className="w-44 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
            placeholder="故事内时间，如「第三年·春」"
            value={draft.story_time}
            onChange={(e) => setDraft({ ...draft, story_time: e.target.value })}
          />
          <select
            className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
            value={draft.location_id}
            onChange={(e) => setDraft({ ...draft, location_id: e.target.value })}
          >
            <option value="">（无地点）</option>
            {entries.map((entry) => (
              <option key={entry.id} value={entry.id}>
                {entry.name}
              </option>
            ))}
          </select>
        </div>
        <textarea
          className="h-20 w-full rounded border border-slate-700 bg-slate-900 p-3 text-sm"
          placeholder="事件描述"
          value={draft.description}
          onChange={(e) => setDraft({ ...draft, description: e.target.value })}
        />
        <div className="space-y-2">
          <div className="text-slate-400">参与者（只列人物）</div>
          <div className="flex flex-wrap gap-2">
            {characters.map((character) => {
              const on = draft.participants.includes(character.id)
              return (
                <button
                  key={character.id}
                  onClick={() => toggleParticipant(character.id)}
                  className={`rounded border px-3 py-1 text-xs ${
                    on ? 'border-indigo-500 bg-slate-800' : 'border-slate-700'
                  }`}
                >
                  {character.name}
                </button>
              )
            })}
            {characters.length === 0 && (
              <span className="text-xs text-slate-500">还没有人物，先去世界观里建一个。</span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button className="rounded bg-indigo-600 px-4 py-2 text-sm" onClick={save}>
            {editingId ? '保存' : '新建'}
          </button>
          {editingId && (
            <button
              className="rounded border border-slate-700 px-4 py-2 text-sm"
              onClick={startCreate}
            >
              取消编辑
            </button>
          )}
        </div>
        <p className="text-xs text-slate-500">
          时间线是故事内时序，不是写作顺序；顺序由列表里的上移 / 下移决定。
        </p>
      </section>

      <div className="space-y-2">
        {events.map((event, index) => (
          <article key={event.id} className="rounded border border-slate-800 p-4 text-sm">
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-xs text-slate-500">#{index + 1}</span>
              {event.story_time && (
                <span className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-300">
                  {event.story_time}
                </span>
              )}
              <span className="font-medium">{event.title}</span>
              {event.location_id && (
                <span className="text-xs text-slate-500">@ {nameOf(event.location_id)}</span>
              )}
              <button
                className="text-xs text-indigo-400 disabled:opacity-30"
                disabled={index === 0}
                onClick={() => move(event, 'up')}
              >
                上移
              </button>
              <button
                className="text-xs text-indigo-400 disabled:opacity-30"
                disabled={index === events.length - 1}
                onClick={() => move(event, 'down')}
              >
                下移
              </button>
              <button className="text-xs text-indigo-400" onClick={() => startEdit(event)}>
                编辑
              </button>
              <button className="text-xs text-amber-400" onClick={() => remove(event)}>
                删除
              </button>
            </div>
            {event.participants.length > 0 && (
              <p className="mt-1 text-xs text-slate-500">
                参与者：{event.participants.map(nameOf).join('、')}
              </p>
            )}
            {event.description && (
              <p className="mt-1 whitespace-pre-wrap text-slate-300">{event.description}</p>
            )}
          </article>
        ))}
        {events.length === 0 && (
          <p className="text-sm text-slate-500">
            还没有事件。时间线是故事内时序，不是写作顺序；顺序由这里的上下移动决定。
          </p>
        )}
      </div>
    </div>
  )
}
