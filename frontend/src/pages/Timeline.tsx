import { useEffect, useMemo, useRef, useState } from 'react'
import { api, type SettingEntry, type TimelineEvent } from '../api/client'
import { useCurrentProject } from '../state/ProjectContext'
import { Badge } from '../ui/Badge'
import { Button, IconButton } from '../ui/Button'
import { Card } from '../ui/Card'
import { EmptyState } from '../ui/EmptyState'
import { Field, Input, Select, Textarea } from '../ui/Field'
import { Icon } from '../ui/icons'

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
  // 迟到响应不许覆盖新项目的事件：切项目现在是常驻入口。
  const dataToken = useRef(0)

  useEffect(() => {
    if (!projectId) return
    const token = ++dataToken.current
    setNotice('')
    setDraft(EMPTY)
    setEditingId(null)
    setEntries([])
    setEvents([])
    api
      .listEntries(projectId)
      .then((rows) => {
        if (dataToken.current !== token) return
        setEntries(rows)
      })
      .catch((e) => {
        if (dataToken.current !== token) return
        setNotice((e as Error).message)
      })
    api
      .listTimeline(projectId)
      .then((rows) => {
        if (dataToken.current !== token) return
        setEvents(rows)
      })
      .catch((e) => {
        if (dataToken.current !== token) return
        setNotice((e as Error).message)
      })
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
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="font-serif text-[22px] font-semibold text-ink">时间线</h2>
        <Button variant="primary" onClick={startCreate}>
          新建事件
        </Button>
        <span className="text-[12px] text-muted">按故事内时序排列，顺序由上下移动决定。</span>
      </div>

      {notice && <p className="text-[13px] text-muted">{notice}</p>}

      <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <section className="relative space-y-3 pl-5">
          <span className="absolute bottom-2 left-[5px] top-2 w-px bg-line" aria-hidden="true" />
          {events.map((event, index) => (
            <article
              key={event.id}
              className="relative rounded-card border border-line bg-surface p-3.5"
            >
              <span
                className="absolute -left-[18px] top-5 h-2 w-2 rounded-full border border-line-strong bg-surface"
                aria-hidden="true"
              />
              <div className="flex flex-wrap items-center gap-2.5">
                <span className="text-[11px] tabular-nums text-faint">#{index + 1}</span>
                {event.story_time && <Badge tone="accent">{event.story_time}</Badge>}
                <span className="text-[14px] font-semibold text-ink">{event.title}</span>
                {event.location_id && (
                  <span className="text-[12px] text-muted">@ {nameOf(event.location_id)}</span>
                )}
                <div className="ml-auto flex items-center gap-1">
                  <IconButton
                    label="上移"
                    disabled={index === 0}
                    onClick={() => move(event, 'up')}
                    className="disabled:opacity-30"
                  >
                    <Icon name="chevron" className="-rotate-90" />
                  </IconButton>
                  <IconButton
                    label="下移"
                    disabled={index === events.length - 1}
                    onClick={() => move(event, 'down')}
                    className="disabled:opacity-30"
                  >
                    <Icon name="chevron" className="rotate-90" />
                  </IconButton>
                  <Button size="sm" variant="ghost" onClick={() => startEdit(event)}>
                    编辑
                  </Button>
                  <Button size="sm" variant="warn" onClick={() => remove(event)}>
                    删除
                  </Button>
                </div>
              </div>
              {event.participants.length > 0 && (
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  <span className="text-[11.5px] text-muted">参与者</span>
                  {event.participants.map((id) => (
                    <Badge key={id}>{nameOf(id)}</Badge>
                  ))}
                </div>
              )}
              {event.description && (
                <p className="mt-2 whitespace-pre-wrap text-[13px] leading-[1.7] text-ink-2">
                  {event.description}
                </p>
              )}
            </article>
          ))}
          {events.length === 0 && (
            <EmptyState
              title="还没有事件"
              hint="时间线是故事内时序，不是写作顺序；顺序由这里的上下移动决定。"
            />
          )}
        </section>

        <Card title={editingId ? '编辑事件' : '新建事件'}>
          <div className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="标题">
                <Input
                  placeholder="标题"
                  value={draft.title}
                  onChange={(e) => setDraft({ ...draft, title: e.target.value })}
                />
              </Field>
              <Field label="故事内时间">
                <Input
                  placeholder="如「第三年·春」"
                  value={draft.story_time}
                  onChange={(e) => setDraft({ ...draft, story_time: e.target.value })}
                />
              </Field>
            </div>
            <Field label="地点">
              <Select
                aria-label="地点"
                value={draft.location_id}
                onChange={(e) => setDraft({ ...draft, location_id: e.target.value })}
                options={[
                  { value: '', label: '（无地点）' },
                  ...entries.map((entry) => ({ value: entry.id, label: entry.name })),
                ]}
              />
            </Field>
            <Field label="事件描述">
              <Textarea
                placeholder="事件描述"
                value={draft.description}
                onChange={(e) => setDraft({ ...draft, description: e.target.value })}
              />
            </Field>
            <div className="space-y-2">
              <div className="text-[11.5px] text-muted">参与者（只列人物）</div>
              <div className="flex flex-wrap gap-1.5">
                {characters.map((character) => {
                  const on = draft.participants.includes(character.id)
                  return (
                    <button
                      key={character.id}
                      type="button"
                      onClick={() => toggleParticipant(character.id)}
                      className={`h-7 rounded-tag border px-2.5 text-[12px] transition-colors duration-[120ms] ${
                        on
                          ? 'border-accent bg-accent-soft text-accent-ink'
                          : 'border-line bg-surface text-ink-2 hover:bg-sunken'
                      }`}
                    >
                      {character.name}
                    </button>
                  )
                })}
                {characters.length === 0 && (
                  <span className="text-[11.5px] text-muted">还没有人物，先去世界观里建一个。</span>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="primary" onClick={save}>
                {editingId ? '保存' : '新建'}
              </Button>
              {editingId && (
                <Button variant="secondary" onClick={startCreate}>
                  取消编辑
                </Button>
              )}
            </div>
            <p className="text-[11.5px] text-muted">
              时间线是故事内时序，不是写作顺序；顺序由列表里的上移 / 下移决定。
            </p>
          </div>
        </Card>
      </div>
    </div>
  )
}
