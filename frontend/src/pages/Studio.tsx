import { useEffect, useState } from 'react'
import { api, type Agent, type AgentVersion, type RunView } from '../api/client'
import RunTrace from '../components/RunTrace'

export default function Studio() {
  const [agents, setAgents] = useState<Agent[]>([])
  const [projectId, setProjectId] = useState('')
  const [selected, setSelected] = useState<Agent | null>(null)
  const [versions, setVersions] = useState<AgentVersion[]>([])
  const [draftPrompt, setDraftPrompt] = useState('')
  const [run, setRun] = useState<RunView | null>(null)
  const [notice, setNotice] = useState('')

  useEffect(() => {
    api.listAgents().then(setAgents)
    // 调试台只需要一个项目来跑，不列项目列表 —— 项目切换在别的页做
    api.listProjects().then((list) => {
      if (list[0]) setProjectId(list[0].id)
    })
  }, [])

  useEffect(() => {
    if (!selected) return
    setDraftPrompt(selected.current_version?.system_prompt ?? '')
    api.listVersions(selected.id).then(setVersions)
  }, [selected])

  async function saveVersion() {
    if (!selected) return
    await api.createVersion(selected.id, { system_prompt: draftPrompt, note: '手动编辑' })
    const refreshed = await api.listAgents()
    setAgents(refreshed)
    setSelected(refreshed.find((a) => a.id === selected.id) ?? null)
    setNotice('已保存为新版本')
  }

  async function rollback(versionId: string) {
    if (!selected) return
    await api.rollback(selected.id, versionId)
    const refreshed = await api.listAgents()
    setAgents(refreshed)
    setSelected(refreshed.find((a) => a.id === selected.id) ?? null)
    setNotice('已回滚')
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
              }`}
            >
              <span className="mr-2">{agent.role_label}</span>
              {agent.name}
            </button>
          ))}
        </nav>

        {selected ? (
          <div className="space-y-4">
            <div className="text-sm text-slate-400">
              任务类型：{selected.task_type} · 当前版本 v{selected.current_version?.version_no}
            </div>

            <section className="space-y-2">
              <label className="text-sm text-slate-300">系统提示词</label>
              <textarea
                className="h-64 w-full rounded border border-slate-700 bg-slate-900 p-3 font-mono text-xs"
                value={draftPrompt}
                onChange={(e) => setDraftPrompt(e.target.value)}
              />
              <div className="flex gap-2">
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
            </section>

            <section className="text-sm">
              <h3 className="mb-2 font-medium text-slate-300">版本历史</h3>
              <ul className="space-y-1">
                {versions.map((v) => (
                  <li key={v.id} className="flex items-center gap-3">
                    <span className="text-slate-400">v{v.version_no}</span>
                    <span className="text-slate-500">{v.note || '—'}</span>
                    <button className="text-xs text-indigo-400" onClick={() => rollback(v.id)}>
                      回滚到此版本
                    </button>
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
