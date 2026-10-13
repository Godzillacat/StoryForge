import { useEffect, useState } from 'react'
import { api, type CostSummary, type Project, type ProviderView, type Settings, type Tool } from '../api/client'
import { costLabel } from '../lib/format'

export default function Models() {
  const [providers, setProviders] = useState<ProviderView[]>([])
  const [settings, setSettings] = useState<Settings | null>(null)
  const [tools, setTools] = useState<Tool[]>([])
  const [projects, setProjects] = useState<Project[]>([])
  const [projectId, setProjectId] = useState('')
  const [cost, setCost] = useState<CostSummary | null>(null)
  const [form, setForm] = useState({ name: '', base_url: '', api_key: '' })
  const [notice, setNotice] = useState('')

  useEffect(() => {
    api.listProviders().then(setProviders)
    api.getSettings().then(setSettings)
    api.listTools().then(setTools)
    api.listProjects().then((list) => {
      setProjects(list)
      if (list[0]) setProjectId(list[0].id)
    })
  }, [])

  useEffect(() => {
    if (projectId) api.projectCost(projectId).then(setCost)
  }, [projectId])

  async function addProvider() {
    if (!form.name.trim() || !form.base_url.trim()) {
      setNotice('名称与接口地址都要填')
      return
    }
    try {
      const created = await api.createProvider({
        name: form.name.trim(),
        kind: 'custom',
        base_url: form.base_url.trim(),
        api_key: form.api_key || undefined,
      })
      setProviders((prev) => [...prev, created])
      setForm({ name: '', base_url: '', api_key: '' })
      setNotice('已添加。接口地址填到 /v1 为止，例如 https://api.deepseek.com/v1')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function test(id: string) {
    try {
      const result = await api.testProvider(id)
      setNotice(`${result.ok ? '正常' : '失败'}：${result.message}`)
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function saveBudget(value: number) {
    if (!settings) return
    try {
      const updated = await api.updateSettings({ context_token_budget: value })
      setSettings(updated)
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">模型与费用</h2>
      {notice && <p className="rounded bg-slate-900 p-3 text-sm text-slate-300">{notice}</p>}

      <section className="space-y-3 rounded border border-slate-800 p-4">
        <h3 className="text-sm font-medium text-slate-300">服务商</h3>
        <div className="flex flex-wrap gap-2">
          <input
            className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
            placeholder="名称"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
          <input
            className="w-80 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
            placeholder="接口地址 /v1"
            value={form.base_url}
            onChange={(e) => setForm({ ...form, base_url: e.target.value })}
          />
          <input
            className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
            type="password"
            placeholder="API Key（加密存本机）"
            value={form.api_key}
            onChange={(e) => setForm({ ...form, api_key: e.target.value })}
          />
          <button className="rounded bg-indigo-600 px-4 py-2 text-sm" onClick={addProvider}>
            添加
          </button>
        </div>

        <ul className="space-y-2 text-sm">
          {providers.map((p) => (
            <li key={p.id} className="flex items-center gap-4">
              <span className="w-32">{p.name}</span>
              <span className="w-64 truncate text-slate-500">{p.base_url}</span>
              <span className="font-mono text-xs text-slate-500">{p.api_key_masked || '未设密钥'}</span>
              <button className="text-xs text-indigo-400" onClick={() => test(p.id)}>
                测试连通性
              </button>
            </li>
          ))}
          {providers.length === 0 && <li className="text-slate-500">还没配置服务商。</li>}
        </ul>
      </section>

      <section className="space-y-2 rounded border border-slate-800 p-4 text-sm">
        <h3 className="text-sm font-medium text-slate-300">上下文预算</h3>
        <div className="flex items-center gap-3">
          <input
            type="number"
            className="w-32 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
            value={settings?.context_token_budget ?? 8000}
            onChange={(e) => saveBudget(Number(e.target.value))}
          />
          <span className="text-slate-500">tokens。超预算时按优先级裁剪，并明示砍掉了什么。</span>
        </div>
      </section>

      <section className="space-y-2 rounded border border-slate-800 p-4 text-sm">
        <h3 className="text-sm font-medium text-slate-300">费用</h3>
        <select
          className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
        >
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        {cost && (
          <p className="text-slate-400">
            {cost.runs} 次调用 · {cost.prompt_tokens + cost.completion_tokens} tokens ·{' '}
            {costLabel(cost.cost_estimate)}
          </p>
        )}
      </section>

      <section className="space-y-2 rounded border border-slate-800 p-4 text-sm">
        <h3 className="text-sm font-medium text-slate-300">创作工具库</h3>
        <ul className="space-y-1">
          {tools.map((t) => (
            <li key={t.id}>
              <span className="text-slate-500">[{t.category}]</span> {t.name}
              <span className="ml-2 text-xs text-slate-600">{t.description}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
