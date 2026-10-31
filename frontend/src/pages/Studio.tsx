import { useEffect, useRef, useState } from 'react'
import {
  api,
  type Agent,
  type AgentVersion,
  type ProviderView,
  type RunView,
  type SlotSpec,
} from '../api/client'
import RunTrace from '../components/RunTrace'
import { useCurrentProject } from '../state/ProjectContext'
import { Badge } from '../ui/Badge'
import { Button, IconButton } from '../ui/Button'
import { Card } from '../ui/Card'
import { EmptyState } from '../ui/EmptyState'
import { Input, Select, Textarea } from '../ui/Field'
import { Icon } from '../ui/icons'
import { Tabs } from '../ui/Tabs'

const PARAM_PROFILES = [
  { value: 'strict', label: '严谨' },
  { value: 'balanced', label: '平衡' },
  { value: 'creative', label: '发散' },
]

const TRIGGER_MODES = [
  { value: 'manual', label: '手动' },
  { value: 'assist', label: '协同' },
  { value: 'auto', label: '自动' },
]

type Tab = 'card' | 'context' | 'versions' | 'debug'

const TABS: { key: Tab; label: string }[] = [
  { key: 'card', label: '角色卡' },
  { key: 'context', label: '上下文与契约' },
  { key: 'versions', label: '版本历史' },
  { key: 'debug', label: '调试台' },
]

export default function Studio() {
  const [agents, setAgents] = useState<Agent[]>([])
  const [providers, setProviders] = useState<ProviderView[]>([])
  const [slots, setSlots] = useState<SlotSpec[]>([])
  // 当前项目由外壳持有：调试台要拿它跑一次真实调用。
  const { projectId } = useCurrentProject()
  const [selected, setSelected] = useState<Agent | null>(null)
  const [versions, setVersions] = useState<AgentVersion[]>([])
  const [run, setRun] = useState<RunView | null>(null)
  const [recentRuns, setRecentRuns] = useState<RunView[]>([])
  const [notice, setNotice] = useState('')
  const [tab, setTab] = useState<Tab>('card')

  const [draft, setDraft] = useState({
    name: '',
    roleLabel: '',
    color: '#6366f1',
    enabled: true,
    prompt: '',
    model: '',
    providerId: '',
    paramProfile: 'balanced',
    slots: [] as string[],
    schemaText: '',
    triggerMode: 'manual',
  })
  const [schemaError, setSchemaError] = useState('')

  useEffect(() => {
    api.listAgents().then(setAgents)
    api.listProviders().then(setProviders)
    api.listSlots().then(setSlots)
  }, [])

  // 重置草稿的时机：换智能体，或当前版本变了（保存了新版本 / 回滚）。
  // 不能只依赖 selected —— 保存 agent 级字段后 refreshAgents 会造出一个新的
  // selected 对象，若那时也整体重置，作者在提示词/模型里未保存的改动会被静默还原。
  const seededKey = useRef<string | null>(null)

  useEffect(() => {
    if (!selected) return

    const key = `${selected.id}:${selected.current_version?.id ?? ''}`
    if (seededKey.current === key) return
    const agentChanged = seededKey.current?.split(':')[0] !== selected.id
    seededKey.current = key

    const version = selected.current_version
    const binding = (version?.model_binding_json ?? {}) as Record<string, unknown>
    setDraft({
      name: selected.name,
      roleLabel: selected.role_label,
      color: selected.color,
      enabled: selected.enabled,
      prompt: version?.system_prompt ?? '',
      model: typeof binding.model === 'string' ? binding.model : '',
      providerId: typeof binding.provider_id === 'string' ? binding.provider_id : '',
      paramProfile: version?.param_profile ?? 'balanced',
      slots: version?.context_slots_json ?? [],
      schemaText: version?.output_schema_json
        ? JSON.stringify(version.output_schema_json, null, 2)
        : '',
      triggerMode: version?.trigger_mode ?? 'manual',
    })
    setSchemaError('')
    if (agentChanged) {
      setNotice('')
      setRun(null)
    }
    api.listVersions(selected.id).then(setVersions)
    api.listRuns(undefined, selected.id).then(setRecentRuns).catch(() => setRecentRuns([]))
  }, [selected])

  async function refreshAgents(agentId?: string) {
    const list = await api.listAgents()
    setAgents(list)
    if (agentId) setSelected(list.find((a) => a.id === agentId) ?? null)
  }

  async function saveAgentFields() {
    if (!selected) return
    try {
      await api.updateAgent(selected.id, {
        name: draft.name,
        role_label: draft.roleLabel,
        color: draft.color,
        enabled: draft.enabled,
      })
      await refreshAgents(selected.id)
      setNotice('已更新角色卡基本信息（不产生新版本）')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function saveVersion() {
    if (!selected) return
    let schema: Record<string, unknown> | null = null
    if (draft.schemaText.trim()) {
      try {
        schema = JSON.parse(draft.schemaText)
      } catch {
        setSchemaError('输出契约不是合法 JSON')
        return
      }
    }
    setSchemaError('')

    // 在既有绑定上改，不要重造：model_binding_json 里还有 timeout_seconds、
    // prices、params 等界面管不到的键，重造会把它们静默抹掉。
    const binding: Record<string, unknown> = {
      ...((selected.current_version?.model_binding_json ?? {}) as Record<string, unknown>),
    }
    if (draft.model.trim()) binding.model = draft.model.trim()
    else delete binding.model
    if (draft.providerId) binding.provider_id = draft.providerId
    else delete binding.provider_id

    try {
      await api.createVersion(selected.id, {
        system_prompt: draft.prompt,
        model_binding_json: binding,
        param_profile: draft.paramProfile,
        context_slots_json: draft.slots,
        output_schema_json: schema,
        trigger_mode: draft.triggerMode,
        note: '手动编辑',
      })
      await refreshAgents(selected.id)
      setNotice('已保存为新版本')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function rollback(versionId: string) {
    if (!selected) return
    try {
      await api.rollback(selected.id, versionId)
      await refreshAgents(selected.id)
      setNotice('已回滚')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function applyPreset() {
    if (!selected) return
    const message = selected.preset?.update_available
      ? '应用预置更新会新建一版并设为当前。旧版本保留，可回退。继续？'
      : '恢复预置会用当前预置新建一版并设为当前。旧版本保留，可回退。继续？'
    if (!window.confirm(message)) return
    try {
      await api.applyPreset(selected.id)
      await refreshAgents(selected.id)
      setNotice('已应用预置')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function runOnce() {
    if (!selected || !projectId) return
    try {
      const response = await api.runAgent(projectId, selected.id)
      setRun(response.run)
      setRecentRuns((prev) => [response.run, ...prev].slice(0, 20))
      setNotice('')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  function toggleSlot(key: string) {
    setDraft((prev) => ({
      ...prev,
      slots: prev.slots.includes(key)
        ? prev.slots.filter((k) => k !== key)
        : [...prev.slots, key],
    }))
  }

  function moveSlot(key: string, delta: number) {
    setDraft((prev) => {
      const index = prev.slots.indexOf(key)
      const next = index + delta
      if (index < 0 || next < 0 || next >= prev.slots.length) return prev
      const slots = [...prev.slots]
      ;[slots[index], slots[next]] = [slots[next], slots[index]]
      return { ...prev, slots }
    })
  }

  const currentVersionNo = selected?.current_version?.version_no

  return (
    <div className="space-y-5">
      <h2 className="font-serif text-[22px] font-semibold text-ink">智能体工作室</h2>

      <div className="grid items-start gap-5 lg:grid-cols-[220px_minmax(0,1fr)]">
        <nav className="space-y-1 lg:sticky lg:top-4">
          {agents.map((agent) => (
            <button
              key={agent.id}
              type="button"
              onClick={() => setSelected(agent)}
              className={`block w-full rounded-control border px-3 py-2 text-left text-[13px] transition-colors duration-[120ms] ${
                selected?.id === agent.id
                  ? 'border-accent bg-accent-soft text-accent-ink'
                  : 'border-transparent text-ink-2 hover:bg-sunken'
              } ${agent.enabled ? '' : 'opacity-50'}`}
            >
              <span className="mr-2 text-muted">{agent.role_label}</span>
              {agent.name}
              {!agent.enabled && <span className="ml-2 text-[11px]">（已停用）</span>}
            </button>
          ))}
        </nav>

        {selected ? (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[12.5px] text-muted">
                任务类型：{selected.task_type}
              </span>
              <Badge tone="accent">当前版本 v{currentVersionNo}</Badge>
            </div>

            <Tabs items={TABS} active={tab} onChange={(key) => setTab(key as Tab)} />

            <div className="flex flex-wrap items-center gap-2">
              <Button variant="primary" onClick={saveVersion}>
                保存为新版本
              </Button>
              <Button onClick={runOnce} disabled={!projectId}>
                单次运行
              </Button>
              {notice && <span className="text-[12.5px] text-muted">{notice}</span>}
            </div>

            <div className={tab === 'card' ? 'space-y-4' : 'hidden'}>
              {selected.preset?.update_available && (
                <div className="flex flex-wrap items-center gap-3 rounded-control border border-warn bg-warn-soft p-3 text-[13px]">
                  <span className="text-warn">预置有更新。</span>
                  <span className="text-[11.5px] text-warn/80">
                    应用会新建一版并设为当前；旧版本保留，可回退。
                  </span>
                  <Button size="sm" variant="warn" onClick={applyPreset}>
                    应用预置更新
                  </Button>
                </div>
              )}
              {!selected.preset?.update_available && selected.preset?.can_restore && (
                <div className="flex flex-wrap items-center gap-3 rounded-control border border-line bg-surface p-3 text-[13px]">
                  <span className="text-ink-2">当前版本不是最新预置。</span>
                  <Button size="sm" onClick={applyPreset}>
                    恢复预置
                  </Button>
                </div>
              )}

              <Card title="角色卡">
                <div className="space-y-3">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-0.5">
                      <span className="mb-1.5 block text-[11.5px] text-muted">名称</span>
                      <Input
                        aria-label="名称"
                        value={draft.name}
                        onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                      />
                    </div>
                    <div className="space-y-0.5">
                      <span className="mb-1.5 block text-[11.5px] text-muted">定位</span>
                      <Input
                        aria-label="定位"
                        value={draft.roleLabel}
                        onChange={(e) => setDraft({ ...draft, roleLabel: e.target.value })}
                      />
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="text-[11.5px] text-muted">颜色</span>
                    <input
                      type="color"
                      aria-label="颜色"
                      className="h-8 w-14 rounded-control border border-line-strong bg-surface"
                      value={draft.color}
                      onChange={(e) => setDraft({ ...draft, color: e.target.value })}
                    />
                    <label className="flex items-center gap-2 text-[12.5px] text-ink-2">
                      <input
                        type="checkbox"
                        className="h-4 w-4 accent-accent"
                        checked={draft.enabled}
                        onChange={(e) => setDraft({ ...draft, enabled: e.target.checked })}
                      />
                      启用
                    </label>
                    <Button size="sm" onClick={saveAgentFields}>
                      保存基本信息
                    </Button>
                  </div>
                </div>
              </Card>

              <Card title="系统提示词">
                <div className="space-y-2">
                  <Textarea
                    rows={12}
                    className="font-mono"
                    value={draft.prompt}
                    onChange={(e) => setDraft({ ...draft, prompt: e.target.value })}
                  />
                  <p className="text-[11.5px] text-muted">
                    字段的键名与含义由运行时按输出契约自动追加，提示词里不必再写一遍。
                  </p>
                </div>
              </Card>
            </div>

            <div className={tab === 'context' ? 'space-y-4' : 'hidden'}>
              <Card title="运行配置">
                <div className="space-y-3">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div>
                      <span className="mb-1.5 block text-[11.5px] text-muted">服务商</span>
                      <Select
                        aria-label="服务商"
                        value={draft.providerId}
                        onChange={(e) => setDraft({ ...draft, providerId: e.target.value })}
                        options={[
                          { value: '', label: '（自动：第一个启用的服务商）' },
                          ...providers.map((p) => ({ value: p.id, label: p.name })),
                        ]}
                      />
                    </div>
                    <div>
                      <span className="mb-1.5 block text-[11.5px] text-muted">模型</span>
                      <Input
                        aria-label="模型"
                        placeholder="例如 qwen3.8-flash"
                        value={draft.model}
                        onChange={(e) => setDraft({ ...draft, model: e.target.value })}
                      />
                    </div>
                    <div>
                      <span className="mb-1.5 block text-[11.5px] text-muted">参数档</span>
                      <Select
                        aria-label="参数档"
                        value={draft.paramProfile}
                        onChange={(e) => setDraft({ ...draft, paramProfile: e.target.value })}
                        options={PARAM_PROFILES}
                      />
                    </div>
                    <div>
                      <span className="mb-1.5 block text-[11.5px] text-muted">触发方式</span>
                      <Select
                        aria-label="触发方式"
                        value={draft.triggerMode}
                        onChange={(e) => setDraft({ ...draft, triggerMode: e.target.value })}
                        options={TRIGGER_MODES}
                      />
                    </div>
                  </div>
                  <p className="text-[11.5px] text-muted">
                    模型名必须与服务商提供的一致，否则调用会失败。参数档决定发出去的采样参数：
                    严谨（temperature 0.2）、平衡（0.7）、发散（1.0）。没绑模型时会跟随「模型与费用」里的任务分路。
                  </p>
                </div>
              </Card>

              <Card title="上下文槽位">
                <div className="space-y-3">
                  <div className="flex flex-wrap gap-1.5">
                    {slots.map((slot) => {
                      const on = draft.slots.includes(slot.key)
                      return (
                        <button
                          key={slot.key}
                          type="button"
                          onClick={() => toggleSlot(slot.key)}
                          className={`h-7 rounded-tag border px-2.5 text-[12px] transition-colors duration-[120ms] ${
                            on
                              ? 'border-accent bg-accent-soft text-accent-ink'
                              : 'border-line bg-surface text-ink-2 hover:bg-sunken'
                          }`}
                        >
                          {slot.label}
                          <span className="ml-1 font-mono text-[10px] text-muted">{slot.key}</span>
                        </button>
                      )
                    })}
                  </div>
                  <ol className="space-y-1">
                    {draft.slots.map((key, index) => (
                      <li key={key} className="flex items-center gap-2">
                        <span className="text-[11.5px] tabular-nums text-faint">{index + 1}.</span>
                        <span className="font-mono text-[12px] text-ink-2">{key}</span>
                        <IconButton label="上移" onClick={() => moveSlot(key, -1)}>
                          <Icon name="chevron" className="-rotate-90" />
                        </IconButton>
                        <IconButton label="下移" onClick={() => moveSlot(key, 1)}>
                          <Icon name="chevron" className="rotate-90" />
                        </IconButton>
                      </li>
                    ))}
                    {draft.slots.length === 0 && (
                      <li className="text-[11.5px] text-muted">还没选槽位，这个智能体读不到任何上下文。</li>
                    )}
                  </ol>
                </div>
              </Card>

              <Card title="输出契约（JSON）">
                <div className="space-y-2">
                  <Textarea
                    rows={10}
                    className="font-mono"
                    value={draft.schemaText}
                    onChange={(e) => setDraft({ ...draft, schemaText: e.target.value })}
                    placeholder={'留空表示不做结构化校验，例如：\n{\n  "type": "object",\n  "properties": {"genre": {"type": "string", "title": "题材"}}\n}'}
                  />
                  {schemaError && <p className="text-[12px] text-warn">{schemaError}</p>}
                  <p className="text-[11.5px] text-muted">
                    属性上的 title 是字段的中文名，渲染时用来给模型生成字段说明 —— 改契约即改提示词。
                  </p>
                </div>
              </Card>
            </div>

            <div className={tab === 'versions' ? 'space-y-4' : 'hidden'}>
              <Card title="版本历史" actions={<Badge>{versions.length} 版</Badge>}>
                <ul className="divide-y divide-line">
                  {versions.map((v) => (
                    <li key={v.id} className="flex flex-wrap items-center gap-2.5 py-2.5">
                      <span className="text-[13px] text-ink-2">v{v.version_no}</span>
                      {v.version_no === currentVersionNo && <Badge tone="accent">当前</Badge>}
                      <span className="text-[12px] text-muted">{v.note || '—'}</span>
                      {v.version_no !== currentVersionNo && (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="ml-auto"
                          onClick={() => rollback(v.id)}
                        >
                          回滚到此版本
                        </Button>
                      )}
                    </li>
                  ))}
                </ul>
              </Card>
            </div>

            <div className={tab === 'debug' ? 'space-y-4' : 'hidden'}>
              {run ? (
                <section className="space-y-2">
                  <h3 className="text-[14px] font-semibold text-ink">调试台</h3>
                  <RunTrace run={run} />
                </section>
              ) : (
                <EmptyState title="还没有选中的运行" hint="点「单次运行」，或在最近运行里点「查看」。" />
              )}

              <Card title="最近运行">
                {recentRuns.length === 0 ? (
                  <p className="text-[12.5px] text-muted">这个智能体还没有运行记录。</p>
                ) : (
                  <ul className="divide-y divide-line">
                    {recentRuns.map((item) => (
                      <li key={item.id} className="flex flex-wrap items-center gap-3 py-2 text-[12px]">
                        <span className="text-muted">
                          {new Date(item.created_at ?? '').toLocaleString()}
                        </span>
                        <span className="text-ink-2">{item.model || '未指定模型'}</span>
                        <span className="tabular-nums text-ink-2">
                          {item.prompt_tokens + item.completion_tokens} tokens
                        </span>
                        <span className={item.status === 'ok' ? 'text-accent-ink' : 'text-warn'}>
                          {item.status}
                        </span>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="ml-auto"
                          onClick={() => setRun(item)}
                        >
                          查看
                        </Button>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </div>
          </div>
        ) : (
          <EmptyState title="左边挑一个智能体" hint="角色卡、上下文、版本与调试台都在这里。" />
        )}
      </div>
    </div>
  )
}
