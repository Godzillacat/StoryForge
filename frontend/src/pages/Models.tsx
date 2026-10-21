import { useEffect, useState } from 'react'
import {
  api,
  type CostBreakdown,
  type CostSummary,
  type ModelPrice,
  type Project,
  type ProviderView,
  type Settings,
  type Tool,
} from '../api/client'
import { costLabel } from '../lib/format'

export default function Models() {
  const [providers, setProviders] = useState<ProviderView[]>([])
  const [prices, setPrices] = useState<ModelPrice[]>([])
  const [priceForm, setPriceForm] = useState({
    provider_id: '',
    model: '',
    input_price: '',
    output_price: '',
  })
  const [settings, setSettings] = useState<Settings | null>(null)
  const [tools, setTools] = useState<Tool[]>([])
  const [projects, setProjects] = useState<Project[]>([])
  const [projectId, setProjectId] = useState('')
  const [cost, setCost] = useState<CostSummary | null>(null)
  const [form, setForm] = useState({ name: '', base_url: '', api_key: '' })
  const [notice, setNotice] = useState('')

  useEffect(() => {
    api.listProviders().then(setProviders)
    api.listModelPrices().then(setPrices).catch(() => setPrices([]))
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

  const [editing, setEditing] = useState<{ id: string; name: string; base_url: string; api_key: string; enabled: boolean } | null>(null)
  const [testModel, setTestModel] = useState('')

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
      const result = await api.testProvider(id, testModel.trim() || undefined)
      setNotice(`${result.ok ? '正常' : '失败'}：${result.message}`)
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function saveProvider() {
    if (!editing) return
    try {
      const updated = await api.updateProvider(editing.id, {
        name: editing.name.trim(),
        base_url: editing.base_url.trim(),
        ...(editing.api_key.trim() ? { api_key: editing.api_key.trim() } : {}),
        enabled: editing.enabled,
      })
      setProviders((prev) => prev.map((p) => (p.id === updated.id ? updated : p)))
      setEditing(null)
      setNotice('已保存。密钥留空表示不修改。')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function removeProvider(id: string) {
    if (!window.confirm('删除这家服务商？本机保存的密钥会一并删除，且无法恢复。')) return
    try {
      await api.deleteProvider(id)
      setProviders((prev) => prev.filter((p) => p.id !== id))
      if (editing?.id === id) setEditing(null)
      setNotice('已删除')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function savePrice() {
    if (!priceForm.provider_id) {
      setNotice('先选一家服务商')
      return
    }
    if (!priceForm.model.trim()) {
      setNotice('模型名要填')
      return
    }
    const input = Number(priceForm.input_price || 0)
    const output = Number(priceForm.output_price || 0)
    if (!Number.isFinite(input) || !Number.isFinite(output) || input < 0 || output < 0) {
      setNotice('单价必须是大于等于 0 的数字')
      return
    }
    try {
      const saved = await api.upsertModelPrice({
        provider_id: priceForm.provider_id,
        model: priceForm.model.trim(),
        input_price: input,
        output_price: output,
      })
      setPrices((prev) => {
        const rest = prev.filter((row) => row.id !== saved.id)
        return [...rest, saved].sort((a, b) => a.model.localeCompare(b.model))
      })
      setPriceForm({ ...priceForm, model: '', input_price: '', output_price: '' })
      setNotice('单价已保存。')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function removePrice(id: string) {
    try {
      await api.deleteModelPrice(id)
      setPrices((prev) => prev.filter((row) => row.id !== id))
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function saveTimeout(value: number) {
    if (!settings) return
    // 清空输入框会让 Number('') 变成 0，而 0 会把之后每一次模型调用都立刻掐断。
    if (!Number.isFinite(value) || value <= 0) {
      setNotice('请求超时必须填大于 0 的秒数')
      return
    }
    try {
      setSettings(await api.updateSettings({ request_timeout_seconds: value }))
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function saveBudget(value: number) {
    if (!settings) return
    // 清空输入框会让 Number('') 变成 0，而 0 会把下一次运行的上下文裁光。
    if (!Number.isFinite(value) || value <= 0) {
      setNotice('上下文预算必须填大于 0 的 token 数')
      return
    }
    try {
      setSettings(await api.updateSettings({ context_token_budget: value }))
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
            <li key={p.id} className="space-y-2 border-b border-slate-800 pb-2 last:border-0">
              <div className="flex flex-wrap items-center gap-4">
                <span className="w-32">{p.name}</span>
                <span className="w-64 truncate text-slate-500">{p.base_url}</span>
                <span className="font-mono text-xs text-slate-500">{p.api_key_masked || '未设密钥'}</span>
                {!p.enabled && <span className="text-xs text-amber-400">已停用</span>}
                <button className="text-xs text-indigo-400" onClick={() => test(p.id)}>
                  测试连通性
                </button>
                <button
                  className="text-xs text-indigo-400"
                  onClick={() =>
                    setEditing({
                      id: p.id,
                      name: p.name,
                      base_url: p.base_url,
                      api_key: '',
                      enabled: p.enabled,
                    })
                  }
                >
                  编辑
                </button>
                <button className="text-xs text-amber-400" onClick={() => removeProvider(p.id)}>
                  删除
                </button>
              </div>

              {editing?.id === p.id && (
                <div className="flex flex-wrap items-center gap-2">
                  <input
                    className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                    value={editing.name}
                    onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                  />
                  <input
                    className="w-80 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                    value={editing.base_url}
                    onChange={(e) => setEditing({ ...editing, base_url: e.target.value })}
                  />
                  <input
                    className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                    type="password"
                    placeholder="密钥（留空不修改）"
                    value={editing.api_key}
                    onChange={(e) => setEditing({ ...editing, api_key: e.target.value })}
                  />
                  <label className="flex items-center gap-2 text-slate-400">
                    <input
                      type="checkbox"
                      checked={editing.enabled}
                      onChange={(e) => setEditing({ ...editing, enabled: e.target.checked })}
                    />
                    启用
                  </label>
                  <button className="rounded bg-indigo-600 px-4 py-2 text-sm" onClick={saveProvider}>
                    保存
                  </button>
                  <button
                    className="rounded border border-slate-700 px-4 py-2 text-sm"
                    onClick={() => setEditing(null)}
                  >
                    取消
                  </button>
                </div>
              )}
            </li>
          ))}
          {providers.length === 0 && <li className="text-slate-500">还没配置服务商。</li>}
        </ul>
        <div className="flex items-center gap-3 text-sm">
          <label className="text-slate-400">测试用模型</label>
          <input
            className="w-64 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
            placeholder="留空则用已绑定的模型"
            value={testModel}
            onChange={(e) => setTestModel(e.target.value)}
          />
          <span className="text-slate-500">
            连通性测试必须带模型名 —— 空模型名的「通过」只证明地址可达。
          </span>
        </div>
      </section>

      <section className="space-y-2 rounded border border-slate-800 p-4 text-sm">
        <h3 className="text-sm font-medium text-slate-300">上下文预算</h3>
        <div className="flex items-center gap-3">
          <input
            type="number"
            // key 让服务端值变化时重挂载：作者输入过程中不会被回写打断，
            // 保存挪到 onBlur 后也不会每敲一个数字就发一次 PUT。
            key={settings?.context_token_budget ?? 8000}
            defaultValue={settings?.context_token_budget ?? 8000}
            className="w-32 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
            onBlur={(e) => saveBudget(Number(e.target.value))}
          />
          <span className="text-slate-500">tokens。超预算时按优先级裁剪，并明示砍掉了什么。</span>
        </div>
      </section>

      <section className="space-y-2 rounded border border-slate-800 p-4 text-sm">
        <h3 className="text-sm font-medium text-slate-300">请求超时</h3>
        <div className="flex items-center gap-3">
          <input
            type="number"
            // key 让服务端值变化时重挂载：作者输入过程中不会被回写打断，
            // 保存挪到 onBlur 后也不会每敲一个数字就发一次 PUT。
            key={settings?.request_timeout_seconds ?? 300}
            defaultValue={settings?.request_timeout_seconds ?? 300}
            className="w-32 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
            onBlur={(e) => saveTimeout(Number(e.target.value))}
          />
          <span className="text-slate-500">
            秒。重推理模型在长任务上可能跑两分钟以上，调大可避免半途被掐断。
          </span>
        </div>
      </section>

      <section className="space-y-3 rounded border border-slate-800 p-4 text-sm">
        <h3 className="text-sm font-medium text-slate-300">模型单价（每百万 token）</h3>
        <p className="text-xs text-slate-500">
          单价按「服务商 + 模型」保存，同一个模型绑在多个智能体上只填一次。没配单价的模型，费用会显示为未定价，
          而不是 0。
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <select
            className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
            value={priceForm.provider_id}
            onChange={(e) => setPriceForm({ ...priceForm, provider_id: e.target.value })}
          >
            <option value="">（选服务商）</option>
            {providers.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          <input
            className="w-56 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
            placeholder="模型名，例如 qwen3.8-flash"
            value={priceForm.model}
            onChange={(e) => setPriceForm({ ...priceForm, model: e.target.value })}
          />
          <input
            className="w-28 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
            placeholder="输入单价"
            value={priceForm.input_price}
            onChange={(e) => setPriceForm({ ...priceForm, input_price: e.target.value })}
          />
          <input
            className="w-28 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
            placeholder="输出单价"
            value={priceForm.output_price}
            onChange={(e) => setPriceForm({ ...priceForm, output_price: e.target.value })}
          />
          <button className="rounded bg-indigo-600 px-4 py-2 text-sm" onClick={savePrice}>
            保存单价
          </button>
        </div>

        <table className="w-full text-left text-xs">
          <thead className="text-slate-500">
            <tr>
              <th className="py-1">服务商</th>
              <th className="py-1">模型</th>
              <th className="py-1">输入</th>
              <th className="py-1">输出</th>
              <th className="py-1">币种</th>
              <th className="py-1" />
            </tr>
          </thead>
          <tbody>
            {prices.map((row) => (
              <tr key={row.id} className="border-t border-slate-800">
                <td className="py-1">
                  {providers.find((p) => p.id === row.provider_id)?.name ?? '已删除的服务商'}
                </td>
                <td className="py-1 font-mono">{row.model}</td>
                <td className="py-1">{row.input_price}</td>
                <td className="py-1">{row.output_price}</td>
                <td className="py-1">{row.currency}</td>
                <td className="py-1 text-right">
                  <button className="text-amber-400" onClick={() => removePrice(row.id)}>
                    删除
                  </button>
                </td>
              </tr>
            ))}
            {prices.length === 0 && (
              <tr>
                <td className="py-2 text-slate-500" colSpan={6}>
                  还没有配置单价，费用会显示为未定价。
                </td>
              </tr>
            )}
          </tbody>
        </table>
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
          <>
            <p className="text-slate-400">
              {cost.runs} 次调用 · {cost.prompt_tokens + cost.completion_tokens} tokens ·{' '}
              {costLabel(cost.cost_estimate)}
              {cost.unpriced_runs > 0 && (
                <span className="ml-2 text-amber-400">其中 {cost.unpriced_runs} 次未定价</span>
              )}
            </p>
            {settings?.budget_alert && cost.cost_estimate > settings.budget_alert && (
              <p className="rounded border border-amber-900 bg-amber-950/40 p-2 text-xs text-amber-300">
                本项目累计费用已超过预算提醒线 {costLabel(settings.budget_alert)}。这只是提醒，不会拦下调用。
              </p>
            )}
            <div className="grid gap-4 md:grid-cols-2">
              <Breakdown title="按智能体" rows={cost.by_agent} nameOf={(row) => row.name ?? ''} />
              <Breakdown title="按任务" rows={cost.by_task} nameOf={(row) => row.label ?? ''} />
            </div>
          </>
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

function Breakdown({
  title,
  rows,
  nameOf,
}: {
  title: string
  rows: CostBreakdown[]
  nameOf: (row: CostBreakdown) => string
}) {
  return (
    <div>
      <h4 className="mb-1 text-xs text-slate-500">{title}</h4>
      <table className="w-full text-left text-xs">
        <thead className="text-slate-500">
          <tr>
            <th className="py-1">名称</th>
            <th className="py-1">次数</th>
            <th className="py-1">tokens</th>
            <th className="py-1">费用</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={`${nameOf(row)}-${index}`} className="border-t border-slate-800">
              <td className="py-1">{nameOf(row)}</td>
              <td className="py-1">
                {row.runs}
                {row.unpriced_runs > 0 && (
                  <span className="ml-1 text-amber-400">（{row.unpriced_runs} 未定价）</span>
                )}
              </td>
              <td className="py-1">{row.prompt_tokens + row.completion_tokens}</td>
              <td className="py-1">{costLabel(row.cost_estimate)}</td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td className="py-2 text-slate-500" colSpan={4}>
                还没有调用记录。
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
