import { useEffect, useState } from 'react'
import {
  api,
  type CostBreakdown,
  type CostSummary,
  type ModelPrice,
  type ProviderView,
  type Settings,
  type Tool,
} from '../api/client'
import { costLabel } from '../lib/format'
import { useCurrentProject } from '../state/ProjectContext'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { EmptyState } from '../ui/EmptyState'
import { Input, Select } from '../ui/Field'
import { Tabs } from '../ui/Tabs'
import { Table, Td, Th } from '../ui/Table'

type Tab = 'providers' | 'params' | 'prices' | 'cost' | 'tools'

const TABS: { key: Tab; label: string }[] = [
  { key: 'providers', label: '服务商' },
  { key: 'params', label: '分路与参数' },
  { key: 'prices', label: '单价' },
  { key: 'cost', label: '费用' },
  { key: 'tools', label: '工具库' },
]

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
  // 当前项目由外壳持有：费用页只看这本书的花费。
  const { projectId } = useCurrentProject()
  const [cost, setCost] = useState<CostSummary | null>(null)
  const [form, setForm] = useState({ name: '', base_url: '', api_key: '' })
  const [notice, setNotice] = useState('')
  const [tab, setTab] = useState<Tab>('providers')

  useEffect(() => {
    api.listProviders().then(setProviders)
    api.listModelPrices().then(setPrices).catch(() => setPrices([]))
    api.getSettings().then(setSettings)
    api.listTools().then(setTools)
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
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="font-serif text-[22px] font-semibold text-ink">模型与费用</h2>
        <Badge>{providers.length} 服务商</Badge>
        <Badge>{prices.length} 条单价</Badge>
      </div>

      {notice && <p className="text-[13px] text-muted">{notice}</p>}

      <Tabs items={TABS} active={tab} onChange={(key) => setTab(key as Tab)} />

      <div className={tab === 'providers' ? 'space-y-4' : 'hidden'}>
        <Card title="服务商">
          <div className="space-y-3">
            <div className="grid gap-2 md:grid-cols-[160px_minmax(0,1fr)_220px_auto]">
              <Input
                aria-label="服务商名称"
                placeholder="名称"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
              <Input
                aria-label="接口地址"
                placeholder="接口地址 /v1"
                value={form.base_url}
                onChange={(e) => setForm({ ...form, base_url: e.target.value })}
              />
              <Input
                aria-label="API Key"
                type="password"
                placeholder="API Key（加密存本机）"
                value={form.api_key}
                onChange={(e) => setForm({ ...form, api_key: e.target.value })}
              />
              <Button variant="primary" className="justify-self-start" onClick={addProvider}>
                添加
              </Button>
            </div>

            {providers.length === 0 ? (
              <EmptyState title="还没配置服务商" hint="填名称与接口地址，API Key 会经 DPAPI 加密存在本机。" />
            ) : (
              <ul className="divide-y divide-line">
                {providers.map((p) => (
                  <li key={p.id} className="space-y-2 py-3 first:pt-0 last:pb-0">
                    <div className="flex flex-wrap items-center gap-3">
                      <span className="w-32 text-[13.5px] font-medium text-ink-2">{p.name}</span>
                      <span className="w-64 truncate text-[12.5px] text-muted">{p.base_url}</span>
                      <span className="font-mono text-[11.5px] text-muted">
                        {p.api_key_masked || '未设密钥'}
                      </span>
                      {!p.enabled && <Badge tone="warn">已停用</Badge>}
                      <div className="ml-auto flex items-center gap-1">
                        <Button size="sm" variant="ghost" onClick={() => test(p.id)}>
                          测试连通性
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
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
                        </Button>
                        <Button size="sm" variant="warn" onClick={() => removeProvider(p.id)}>
                          删除
                        </Button>
                      </div>
                    </div>

                    {editing?.id === p.id && (
                      <div className="grid gap-2 rounded-control border border-line bg-sunken p-2.5 md:grid-cols-[140px_minmax(0,1fr)_200px_auto_auto]">
                        <Input
                          aria-label="名称"
                          value={editing.name}
                          onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                        />
                        <Input
                          aria-label="接口地址"
                          value={editing.base_url}
                          onChange={(e) => setEditing({ ...editing, base_url: e.target.value })}
                        />
                        <Input
                          aria-label="密钥"
                          type="password"
                          placeholder="密钥（留空不修改）"
                          value={editing.api_key}
                          onChange={(e) => setEditing({ ...editing, api_key: e.target.value })}
                        />
                        <label className="flex items-center gap-2 text-[12.5px] text-ink-2">
                          <input
                            type="checkbox"
                            className="h-4 w-4 accent-accent"
                            checked={editing.enabled}
                            onChange={(e) => setEditing({ ...editing, enabled: e.target.checked })}
                          />
                          启用
                        </label>
                        <div className="flex gap-1.5">
                          <Button size="sm" variant="primary" onClick={saveProvider}>
                            保存
                          </Button>
                          <Button size="sm" onClick={() => setEditing(null)}>
                            取消
                          </Button>
                        </div>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}

            <div className="flex flex-wrap items-center gap-3 border-t border-line pt-3">
              <span className="text-[12.5px] text-muted">测试用模型</span>
              <div className="w-64">
                <Input
                  aria-label="测试用模型"
                  placeholder="留空则用已绑定的模型"
                  value={testModel}
                  onChange={(e) => setTestModel(e.target.value)}
                />
              </div>
              <span className="text-[11.5px] text-muted">
                连通性测试必须带模型名 —— 空模型名的「通过」只证明地址可达。
              </span>
            </div>
          </div>
        </Card>
      </div>

      <div className={tab === 'params' ? 'space-y-4' : 'hidden'}>
        <Card title="模型分路">
          <p className="text-[13px] leading-[1.7] text-ink-2">
            分路按任务类型配置在设置里（`model_routing`），当前没有图形界面；每个智能体也可以在工作室里显式绑定模型。
            这里管理两条全局参数。
          </p>
        </Card>
        <div className="grid gap-4 md:grid-cols-2">
          <Card title="上下文预算">
            <div className="space-y-2">
              <div className="w-32">
                <Input
                  type="number"
                  aria-label="上下文预算"
                  // key 让服务端值变化时重挂载：作者输入过程中不会被回写打断，
                  // 保存挪到 onBlur 后也不会每敲一个数字就发一次 PUT。
                  key={settings?.context_token_budget ?? 8000}
                  defaultValue={settings?.context_token_budget ?? 8000}
                  onBlur={(e) => saveBudget(Number(e.target.value))}
                />
              </div>
              <p className="text-[11.5px] text-muted">
                tokens。超预算时按优先级裁剪，并明示砍掉了什么。
              </p>
            </div>
          </Card>
          <Card title="请求超时">
            <div className="space-y-2">
              <div className="w-32">
                <Input
                  type="number"
                  aria-label="请求超时"
                  // key 让服务端值变化时重挂载：作者输入过程中不会被回写打断，
                  // 保存挪到 onBlur 后也不会每敲一个数字就发一次 PUT。
                  key={settings?.request_timeout_seconds ?? 300}
                  defaultValue={settings?.request_timeout_seconds ?? 300}
                  onBlur={(e) => saveTimeout(Number(e.target.value))}
                />
              </div>
              <p className="text-[11.5px] text-muted">
                秒。重推理模型在长任务上可能跑两分钟以上，调大可避免半途被掐断。
              </p>
            </div>
          </Card>
        </div>
      </div>

      <div className={tab === 'prices' ? 'space-y-4' : 'hidden'}>
        <Card title="模型单价（每百万 token）">
          <div className="space-y-3">
            <p className="text-[11.5px] text-muted">
              单价按「服务商 + 模型」保存，同一个模型绑在多个智能体上只填一次。没配单价的模型，费用会显示为未定价，
              而不是 0。
            </p>
            <div className="grid gap-2 md:grid-cols-[180px_200px_130px_130px_auto]">
              <Select
                aria-label="单价服务商"
                value={priceForm.provider_id}
                onChange={(e) => setPriceForm({ ...priceForm, provider_id: e.target.value })}
                options={[
                  { value: '', label: '（选服务商）' },
                  ...providers.map((p) => ({ value: p.id, label: p.name })),
                ]}
              />
              <Input
                aria-label="模型名"
                placeholder="模型名，例如 qwen3.8-flash"
                value={priceForm.model}
                onChange={(e) => setPriceForm({ ...priceForm, model: e.target.value })}
              />
              <Input
                aria-label="输入单价"
                placeholder="输入单价"
                value={priceForm.input_price}
                onChange={(e) => setPriceForm({ ...priceForm, input_price: e.target.value })}
              />
              <Input
                aria-label="输出单价"
                placeholder="输出单价"
                value={priceForm.output_price}
                onChange={(e) => setPriceForm({ ...priceForm, output_price: e.target.value })}
              />
              <Button variant="primary" className="justify-self-start" onClick={savePrice}>
                保存单价
              </Button>
            </div>

            <Table>
              <thead>
                <tr>
                  <Th>服务商</Th>
                  <Th>模型</Th>
                  <Th align="right">输入</Th>
                  <Th align="right">输出</Th>
                  <Th>币种</Th>
                  <Th align="right">操作</Th>
                </tr>
              </thead>
              <tbody>
                {prices.map((row) => (
                  <tr key={row.id} className="h-11">
                    <Td>{providers.find((p) => p.id === row.provider_id)?.name ?? '已删除的服务商'}</Td>
                    <Td className="font-mono text-[12px]">{row.model}</Td>
                    <Td align="right">{row.input_price}</Td>
                    <Td align="right">{row.output_price}</Td>
                    <Td>{row.currency}</Td>
                    <Td align="right">
                      <Button size="sm" variant="warn" onClick={() => removePrice(row.id)}>
                        删除
                      </Button>
                    </Td>
                  </tr>
                ))}
                {prices.length === 0 && (
                  <tr>
                    <Td colSpan={6} className="text-muted">
                      还没有配置单价，费用会显示为未定价。
                    </Td>
                  </tr>
                )}
              </tbody>
            </Table>
          </div>
        </Card>
      </div>

      <div className={tab === 'cost' ? 'space-y-4' : 'hidden'}>
        <Card title="费用">
          {cost ? (
            <div className="space-y-4">
              <div className="flex flex-wrap items-baseline gap-x-5 gap-y-1">
                <span className="font-serif text-[28px] font-semibold leading-[1.2] text-ink">
                  {costLabel(cost.cost_estimate)}
                </span>
                <span className="text-[13px] text-muted">
                  {cost.runs} 次调用 · {cost.prompt_tokens + cost.completion_tokens} tokens
                </span>
                {cost.unpriced_runs > 0 && (
                  <Badge tone="warn">其中 {cost.unpriced_runs} 次未定价</Badge>
                )}
              </div>
              {settings?.budget_alert && cost.cost_estimate > settings.budget_alert && (
                <p className="rounded-control bg-warn-soft p-2.5 text-[12.5px] text-warn">
                  本项目累计费用已超过预算提醒线 {costLabel(settings.budget_alert)}。这只是提醒，不会拦下调用。
                </p>
              )}
              <div className="grid gap-5 md:grid-cols-2">
                <Breakdown title="按智能体" rows={cost.by_agent} nameOf={(row) => row.name ?? ''} />
                <Breakdown title="按任务" rows={cost.by_task} nameOf={(row) => row.label ?? ''} />
              </div>
            </div>
          ) : (
            <EmptyState title="还没有费用记录" hint="选一个项目后，这里显示它的调用与花费。" />
          )}
        </Card>
      </div>

      <div className={tab === 'tools' ? 'space-y-4' : 'hidden'}>
        <Card title="创作工具库" actions={<Badge>{tools.length} 份</Badge>}>
          <ul className="divide-y divide-line">
            {tools.map((t) => (
              <li key={t.id} className="flex flex-wrap items-baseline gap-2 py-2 text-[13px]">
                <Badge>{t.category}</Badge>
                <span className="font-medium text-ink-2">{t.name}</span>
                <span className="text-[11.5px] text-muted">{t.description}</span>
              </li>
            ))}
          </ul>
        </Card>
      </div>
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
      <h4 className="mb-1.5 text-[11px] tracking-[.08em] text-muted">{title}</h4>
      <Table>
        <thead>
          <tr>
            <Th>名称</Th>
            <Th align="right">次数</Th>
            <Th align="right">tokens</Th>
            <Th align="right">费用</Th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={`${nameOf(row)}-${index}`} className="h-11">
              <Td>{nameOf(row)}</Td>
              <Td align="right">
                {row.runs}
                {row.unpriced_runs > 0 && (
                  <span className="ml-1 text-warn">（{row.unpriced_runs} 未定价）</span>
                )}
              </Td>
              <Td align="right">{row.prompt_tokens + row.completion_tokens}</Td>
              <Td align="right">{costLabel(row.cost_estimate)}</Td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <Td colSpan={4} className="text-muted">
                还没有调用记录。
              </Td>
            </tr>
          )}
        </tbody>
      </Table>
    </div>
  )
}
