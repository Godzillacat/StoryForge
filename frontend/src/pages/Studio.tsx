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

export default function Studio() {
  const [agents, setAgents] = useState<Agent[]>([])
  const [providers, setProviders] = useState<ProviderView[]>([])
  const [slots, setSlots] = useState<SlotSpec[]>([])
  const [projectId, setProjectId] = useState('')
  const [selected, setSelected] = useState<Agent | null>(null)
  const [versions, setVersions] = useState<AgentVersion[]>([])
  const [run, setRun] = useState<RunView | null>(null)
  const [notice, setNotice] = useState('')

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
    api.listProjects().then((list) => {
      if (list[0]) setProjectId(list[0].id)
    })
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

  async function runOnce() {
    if (!selected || !projectId) return
    try {
      const response = await api.runAgent(projectId, selected.id)
      setRun(response.run)
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
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">智能体工作室</h2>

      <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
        <nav className="space-y-1">
          {agents.map((agent) => (
            <button
              key={agent.id}
              onClick={() => setSelected(agent)}
              className={`block w-full rounded px-3 py-2 text-left text-sm ${
                selected?.id === agent.id ? 'bg-slate-800' : 'hover:bg-slate-900'
              } ${agent.enabled ? '' : 'opacity-50'}`}
            >
              <span className="mr-2 text-slate-400">{agent.role_label}</span>
              {agent.name}
              {!agent.enabled && <span className="ml-2 text-xs">（已停用）</span>}
            </button>
          ))}
        </nav>

        {selected ? (
          <div className="space-y-6">
            <div className="text-sm text-slate-400">
              任务类型：{selected.task_type} · 当前版本 v{currentVersionNo}
            </div>

            <section className="space-y-3 rounded border border-slate-800 p-4">
              <h3 className="text-sm font-medium text-slate-300">角色卡</h3>
              <div className="flex flex-wrap items-center gap-3 text-sm">
                <label className="text-slate-400">名称</label>
                <input
                  className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                  value={draft.name}
                  onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                />
                <label className="text-slate-400">定位</label>
                <input
                  className="w-32 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                  value={draft.roleLabel}
                  onChange={(e) => setDraft({ ...draft, roleLabel: e.target.value })}
                />
                <label className="text-slate-400">颜色</label>
                <input
                  type="color"
                  className="h-9 w-14 rounded border border-slate-700 bg-slate-900"
                  value={draft.color}
                  onChange={(e) => setDraft({ ...draft, color: e.target.value })}
                />
                <label className="flex items-center gap-2 text-slate-400">
                  <input
                    type="checkbox"
                    checked={draft.enabled}
                    onChange={(e) => setDraft({ ...draft, enabled: e.target.checked })}
                  />
                  启用
                </label>
                <button
                  className="rounded border border-slate-700 px-4 py-2 text-sm"
                  onClick={saveAgentFields}
                >
                  保存基本信息
                </button>
              </div>
            </section>

            <section className="space-y-3 rounded border border-slate-800 p-4">
              <h3 className="text-sm font-medium text-slate-300">系统提示词</h3>
              <textarea
                className="h-56 w-full rounded border border-slate-700 bg-slate-900 p-3 font-mono text-xs"
                value={draft.prompt}
                onChange={(e) => setDraft({ ...draft, prompt: e.target.value })}
              />
              <p className="text-xs text-slate-500">
                字段的键名与含义由运行时按输出契约自动追加，提示词里不必再写一遍。
              </p>
            </section>

            <section className="space-y-3 rounded border border-slate-800 p-4 text-sm">
              <h3 className="text-sm font-medium text-slate-300">运行配置</h3>
              <div className="flex flex-wrap items-center gap-3">
                <label className="text-slate-400">服务商</label>
                <select
                  className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                  value={draft.providerId}
                  onChange={(e) => setDraft({ ...draft, providerId: e.target.value })}
                >
                  <option value="">（自动：第一个启用的服务商）</option>
                  {providers.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
                <label className="text-slate-400">模型</label>
                <input
                  className="w-64 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                  placeholder="例如 qwen3.8-flash"
                  value={draft.model}
                  onChange={(e) => setDraft({ ...draft, model: e.target.value })}
                />
                <label className="text-slate-400">参数档</label>
                <select
                  className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                  value={draft.paramProfile}
                  onChange={(e) => setDraft({ ...draft, paramProfile: e.target.value })}
                >
                  {PARAM_PROFILES.map((p) => (
                    <option key={p.value} value={p.value}>
                      {p.label}
                    </option>
                  ))}
                </select>
                <label className="text-slate-400">触发方式</label>
                <select
                  className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                  value={draft.triggerMode}
                  onChange={(e) => setDraft({ ...draft, triggerMode: e.target.value })}
                >
                  {TRIGGER_MODES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </div>
              <p className="text-xs text-slate-500">
                模型名必须与服务商提供的一致，否则调用会失败。参数档目前只存不生效（属 P3）。
              </p>
            </section>

            <section className="space-y-3 rounded border border-slate-800 p-4 text-sm">
              <h3 className="text-sm font-medium text-slate-300">上下文槽位</h3>
              <div className="flex flex-wrap gap-2">
                {slots.map((slot) => {
                  const on = draft.slots.includes(slot.key)
                  return (
                    <button
                      key={slot.key}
                      onClick={() => toggleSlot(slot.key)}
                      className={`rounded border px-3 py-1 text-xs ${
                        on ? 'border-indigo-500 bg-slate-800' : 'border-slate-700'
                      }`}
                    >
                      {slot.label}
                      <span className="ml-1 font-mono text-[10px] text-slate-500">{slot.key}</span>
                    </button>
                  )
                })}
              </div>
              <ol className="space-y-1">
                {draft.slots.map((key, index) => (
                  <li key={key} className="flex items-center gap-3">
                    <span className="text-slate-500">{index + 1}.</span>
                    <span className="font-mono text-xs">{key}</span>
                    <button className="text-xs text-indigo-400" onClick={() => moveSlot(key, -1)}>
                      上移
                    </button>
                    <button className="text-xs text-indigo-400" onClick={() => moveSlot(key, 1)}>
                      下移
                    </button>
                  </li>
                ))}
                {draft.slots.length === 0 && (
                  <li className="text-xs text-slate-500">还没选槽位，这个智能体读不到任何上下文。</li>
                )}
              </ol>
            </section>

            <section className="space-y-3 rounded border border-slate-800 p-4">
              <h3 className="text-sm font-medium text-slate-300">输出契约（JSON）</h3>
              <textarea
                className="h-52 w-full rounded border border-slate-700 bg-slate-900 p-3 font-mono text-xs"
                value={draft.schemaText}
                onChange={(e) => setDraft({ ...draft, schemaText: e.target.value })}
                placeholder={'留空表示不做结构化校验，例如：\n{\n  "type": "object",\n  "properties": {"genre": {"type": "string", "title": "题材"}}\n}'}
              />
              {schemaError && <p className="text-xs text-amber-400">{schemaError}</p>}
              <p className="text-xs text-slate-500">
                属性上的 title 是字段的中文名，渲染时用来给模型生成字段说明 —— 改契约即改提示词。
              </p>
            </section>

            <div className="flex items-center gap-2">
              <button className="rounded bg-indigo-600 px-4 py-2 text-sm" onClick={saveVersion}>
                保存为新版本
              </button>
              <button
                className="rounded border border-slate-700 px-4 py-2 text-sm"
                onClick={runOnce}
                disabled={!projectId}
              >
                单次运行
              </button>
            </div>
            {notice && <p className="text-sm text-slate-400">{notice}</p>}

            <section className="text-sm">
              <h3 className="mb-2 font-medium text-slate-300">版本历史</h3>
              <ul className="space-y-1">
                {versions.map((v) => (
                  <li key={v.id} className="flex items-center gap-3">
                    <span className="text-slate-400">v{v.version_no}</span>
                    {v.version_no === currentVersionNo && (
                      <span className="text-xs text-emerald-400">当前</span>
                    )}
                    <span className="text-slate-500">{v.note || '—'}</span>
                    {v.version_no !== currentVersionNo && (
                      <button className="text-xs text-indigo-400" onClick={() => rollback(v.id)}>
                        回滚到此版本
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            </section>

            {run && (
              <section className="space-y-2">
                <h3 className="text-sm font-medium text-slate-300">调试台</h3>
                <RunTrace run={run} />
              </section>
            )}
          </div>
        ) : (
          <p className="text-sm text-slate-500">左边挑一个智能体。</p>
        )}
      </div>
    </div>
  )
}
