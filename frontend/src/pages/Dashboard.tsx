import { useEffect, useState } from 'react'
import { api, type CostSummary, type Project } from '../api/client'

export default function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([])
  const [selected, setSelected] = useState<Project | null>(null)
  const [cost, setCost] = useState<CostSummary | null>(null)
  const [name, setName] = useState('')

  useEffect(() => {
    api.listProjects().then(setProjects)
  }, [])

  useEffect(() => {
    if (selected) api.projectCost(selected.id).then(setCost)
  }, [selected])

  async function create() {
    if (!name.trim()) return
    const project = await api.createProject({ name: name.trim() })
    setProjects((prev) => [project, ...prev])
    setSelected(project)
    setName('')
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">故事仪表盘</h2>

      <div className="flex gap-2">
        <input
          className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
          placeholder="新项目名称"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <button className="rounded bg-indigo-600 px-4 py-2 text-sm" onClick={create}>
          新建项目
        </button>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <section className="col-span-2 space-y-2">
          {projects.map((p) => (
            <button
              key={p.id}
              onClick={() => setSelected(p)}
              className={`block w-full rounded border px-4 py-3 text-left ${
                selected?.id === p.id ? 'border-indigo-500 bg-slate-900' : 'border-slate-800'
              }`}
            >
              <div className="font-medium">{p.name}</div>
              <div className="text-xs text-slate-500">
                {p.genre ?? '未定题材'} · {p.tone ?? '未定调性'}
              </div>
            </button>
          ))}
          {projects.length === 0 && <p className="text-sm text-slate-500">还没有项目，先建一个。</p>}
        </section>

        <section className="rounded border border-slate-800 p-4">
          <h3 className="mb-3 text-sm font-medium text-slate-300">体检单</h3>
          {selected ? (
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-slate-500">字数</dt>
                <dd>0</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">结构完整度</dt>
                <dd>待 P1c</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">未处理告警</dt>
                <dd>待 P2</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">累计调用</dt>
                <dd>{cost?.runs ?? 0} 次</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">累计费用</dt>
                <dd>${(cost?.cost_estimate ?? 0).toFixed(4)}</dd>
              </div>
            </dl>
          ) : (
            <p className="text-sm text-slate-500">选一个项目看体检单。</p>
          )}
        </section>
      </div>
    </div>
  )
}
