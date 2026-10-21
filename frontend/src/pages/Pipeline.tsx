import { useEffect, useRef, useState } from 'react'
import {
  api,
  type Agent,
  type Pipeline,
  type PipelineNodeSpec,
  type PipelineRun,
  type Project,
} from '../api/client'

const STATUS_LABELS: Record<string, string> = {
  pending: '待执行',
  running: '执行中',
  ok: '完成',
  awaiting: '待确认',
  blocked: '缺前置',
  skipped: '已跳过',
  failed: '失败',
  cancelled: '已取消',
}

const RUN_LABELS: Record<string, string> = {
  running: '运行中',
  paused: '已暂停',
  awaiting: '等待确认',
  completed: '已完成',
  cancelled: '已取消',
  failed: '失败',
}

const RUN_COLORS: Record<string, string> = {
  ok: 'text-emerald-400',
  running: 'text-indigo-400',
  awaiting: 'text-amber-400',
  blocked: 'text-amber-400',
  failed: 'text-red-400',
  skipped: 'text-slate-500',
  cancelled: 'text-slate-500',
  pending: 'text-slate-500',
}

export default function Pipeline() {
  const [projects, setProjects] = useState<Project[]>([])
  const [projectId, setProjectId] = useState('')
  const [pipeline, setPipeline] = useState<Pipeline | null>(null)
  const [agents, setAgents] = useState<Agent[]>([])
  const [run, setRun] = useState<PipelineRun | null>(null)
  const [notice, setNotice] = useState('')
  const [newType, setNewType] = useState('')
  const token = useRef(0)

  useEffect(() => {
    api.listProjects().then((list) => {
      setProjects(list)
      if (list[0]) setProjectId(list[0].id)
    })
    api.listAgents().then(setAgents).catch(() => setAgents([]))
  }, [])

  useEffect(() => {
    const current = ++token.current
    if (!projectId) {
      setPipeline(null)
      setRun(null)
      return
    }
    api
      .getPipeline(projectId)
      .then((value) => {
        if (token.current === current) setPipeline(value)
      })
      .catch((error) => {
        if (token.current === current) setNotice((error as Error).message)
      })
    api
      .latestPipelineRun(projectId)
      .then((value) => {
        if (token.current === current) setRun(value)
      })
      .catch(() => {
        if (token.current === current) setRun(null)
      })
  }, [projectId])

  // 运行中才轮询：已完成/已取消的运行不需要再查。
  const active = run !== null && ['running', 'awaiting', 'paused'].includes(run.status)
  useEffect(() => {
    if (!run || !active) return
    const current = token.current
    const timer = window.setInterval(() => {
      api
        .getPipelineRun(run.id)
        .then((value) => {
          if (token.current === current) setRun(value)
        })
        .catch(() => undefined)
    }, 2000)
    return () => window.clearInterval(timer)
  }, [run, active])

  function draftNodes(nodes: PipelineNodeSpec[]) {
    return nodes.map((node) => ({
      name: node.name,
      task_type: node.task_type,
      agent_id: node.agent_id,
      checkpoint: node.checkpoint,
      enabled: node.enabled,
    }))
  }

  async function save(nodes: PipelineNodeSpec[], policy?: string) {
    if (!pipeline) return
    try {
      const updated = await api.updatePipeline(pipeline.project_id, {
        policy: policy ?? pipeline.policy,
        nodes: draftNodes(nodes),
      })
      setPipeline(updated)
      setNotice('已保存')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function changePolicy(value: string) {
    if (!pipeline) return
    await save(pipeline.nodes, value)
  }

  async function move(index: number, delta: number) {
    if (!pipeline) return
    const next = index + delta
    if (next < 0 || next >= pipeline.nodes.length) return
    const nodes = [...pipeline.nodes]
    ;[nodes[index], nodes[next]] = [nodes[next], nodes[index]]
    await save(nodes)
  }

  async function toggle(index: number, key: 'enabled' | 'checkpoint') {
    if (!pipeline) return
    const nodes = pipeline.nodes.map((node, i) =>
      i === index ? { ...node, [key]: !node[key] } : node,
    )
    await save(nodes)
  }

  async function remove(index: number) {
    if (!pipeline) return
    if (pipeline.nodes.length <= 1) {
      setNotice('管线至少要保留一个节点')
      return
    }
    await save(pipeline.nodes.filter((_, i) => i !== index))
  }

  async function append() {
    if (!pipeline || !newType) return
    const type = pipeline.node_types.find((t) => t.task_type === newType)
    const nodes = [
      ...pipeline.nodes,
      {
        id: '',
        seq: pipeline.nodes.length,
        name: type?.label ?? newType,
        task_type: newType,
        agent_id: null,
        checkpoint: false,
        enabled: true,
      },
    ]
    await save(nodes)
    setNewType('')
  }

  async function bindAgent(index: number, agentId: string) {
    if (!pipeline) return
    const nodes = pipeline.nodes.map((node, i) =>
      i === index ? { ...node, agent_id: agentId || null } : node,
    )
    await save(nodes)
  }

  async function reset() {
    if (!pipeline) return
    if (!window.confirm('恢复默认管线会覆盖当前的节点顺序与绑定。继续？')) return
    try {
      setPipeline(await api.resetPipeline(pipeline.project_id))
      setNotice('已恢复默认管线')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function start() {
    if (!pipeline) return
    try {
      setRun(await api.startPipelineRun(pipeline.project_id))
      setNotice('')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function control(action: 'pause' | 'resume' | 'cancel') {
    if (!run) return
    try {
      const call = {
        pause: api.pausePipelineRun,
        resume: api.resumePipelineRun,
        cancel: api.cancelPipelineRun,
      }[action]
      setRun(await call(run.id))
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">管线编排</h2>

      {notice && <p className="rounded bg-slate-900 p-3 text-sm text-slate-300">{notice}</p>}

      <div className="flex flex-wrap items-center gap-3 text-sm">
        <select
          className="rounded border border-slate-700 bg-slate-900 px-3 py-2"
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
        >
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        {pipeline && (
          <>
            <label className="text-slate-400">检查点策略</label>
            <select
              className="rounded border border-slate-700 bg-slate-900 px-3 py-2"
              value={pipeline.policy}
              onChange={(e) => changePolicy(e.target.value)}
            >
              {pipeline.policies.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
            <button
              className="rounded bg-indigo-600 px-4 py-2 disabled:opacity-50"
              onClick={start}
              disabled={run !== null && ['running', 'awaiting', 'paused'].includes(run.status)}
            >
              开始运行
            </button>
            <button className="rounded border border-slate-700 px-4 py-2" onClick={reset}>
              恢复默认管线
            </button>
          </>
        )}
      </div>

      {pipeline && (
        <section className="space-y-2 rounded border border-slate-800 p-4">
          <h3 className="text-sm font-medium text-slate-300">节点</h3>
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-slate-500">
              <tr>
                <th className="py-1">#</th>
                <th className="py-1">名称</th>
                <th className="py-1">任务</th>
                <th className="py-1">智能体</th>
                <th className="py-1">检查点</th>
                <th className="py-1">启用</th>
                <th className="py-1" />
              </tr>
            </thead>
            <tbody>
              {pipeline.nodes.map((node, index) => (
                <tr key={`${node.id}-${index}`} className="border-t border-slate-800">
                  <td className="py-1 text-slate-500">{index + 1}</td>
                  <td className="py-1">{node.name}</td>
                  <td className="py-1 font-mono text-xs text-slate-500">{node.task_type}</td>
                  <td className="py-1">
                    <select
                      className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs"
                      value={node.agent_id ?? ''}
                      onChange={(e) => bindAgent(index, e.target.value)}
                    >
                      <option value="">按任务类型自动</option>
                      {agents
                        .filter((a) => a.task_type === node.task_type)
                        .map((a) => (
                          <option key={a.id} value={a.id}>
                            {a.name}
                          </option>
                        ))}
                    </select>
                  </td>
                  <td className="py-1">
                    <input
                      type="checkbox"
                      checked={node.checkpoint}
                      onChange={() => toggle(index, 'checkpoint')}
                    />
                  </td>
                  <td className="py-1">
                    <input
                      type="checkbox"
                      checked={node.enabled}
                      onChange={() => toggle(index, 'enabled')}
                    />
                  </td>
                  <td className="space-x-2 py-1 text-right text-xs">
                    <button className="text-indigo-400" onClick={() => move(index, -1)}>
                      上移
                    </button>
                    <button className="text-indigo-400" onClick={() => move(index, 1)}>
                      下移
                    </button>
                    <button className="text-amber-400" onClick={() => remove(index)}>
                      删除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex items-center gap-2 pt-2 text-sm">
            <select
              className="rounded border border-slate-700 bg-slate-900 px-3 py-2"
              value={newType}
              onChange={(e) => setNewType(e.target.value)}
            >
              <option value="">（选任务类型）</option>
              {pipeline.node_types.map((item) => (
                <option key={item.task_type} value={item.task_type}>
                  {item.label}
                </option>
              ))}
            </select>
            <button
              className="rounded border border-slate-700 px-4 py-2 disabled:opacity-50"
              onClick={append}
              disabled={!newType}
            >
              追加节点
            </button>
          </div>
        </section>
      )}

      {run && (
        <section className="space-y-3 rounded border border-slate-800 p-4 text-sm">
          <div className="flex flex-wrap items-center gap-3">
            <h3 className="font-medium text-slate-300">最近一次运行</h3>
            <span className={RUN_COLORS[run.status] ?? 'text-slate-400'}>
              {RUN_LABELS[run.status] ?? run.status}
            </span>
            <span className="text-xs text-slate-500">
              {new Date(run.created_at).toLocaleString()}
            </span>
            <div className="ml-auto space-x-2">
              {run.status === 'running' && (
                <button className="rounded border border-slate-700 px-3 py-1" onClick={() => control('pause')}>
                  暂停
                </button>
              )}
              {(run.status === 'paused' || run.status === 'awaiting') && (
                <button className="rounded bg-indigo-600 px-3 py-1" onClick={() => control('resume')}>
                  继续
                </button>
              )}
              {!['completed', 'cancelled'].includes(run.status) && (
                <button className="rounded border border-amber-700 px-3 py-1 text-amber-300" onClick={() => control('cancel')}>
                  取消
                </button>
              )}
            </div>
          </div>

          {run.message && (
            <p className="rounded bg-amber-950/40 p-2 text-xs text-amber-300">{run.message}</p>
          )}

          <ul className="space-y-1">
            {run.nodes.map((node) => (
              <li key={node.id} className="flex flex-wrap items-center gap-3 border-t border-slate-800 py-1">
                <span className="w-6 text-slate-500">{node.seq + 1}</span>
                <span className="w-32">{node.name}</span>
                <span className={`w-20 text-xs ${RUN_COLORS[node.status] ?? ''}`}>
                  {STATUS_LABELS[node.status] ?? node.status}
                </span>
                <span className="flex-1 text-xs text-slate-500">{node.message}</span>
                {typeof node.summary?.review_path === 'string' && (
                  <a className="text-xs text-indigo-400" href={node.summary.review_path as string}>
                    去审阅
                  </a>
                )}
                {node.generation_run_id && (
                  <a
                    className="text-xs text-slate-500"
                    href={`/studio`}
                    title={node.generation_run_id}
                  >
                    运行记录
                  </a>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      <p className="text-xs text-slate-500">
        管线只产出结构材料：每个节点跑完后，去对应页面审阅并采纳。正文写作在写作台与批量生成里。
      </p>
    </div>
  )
}
