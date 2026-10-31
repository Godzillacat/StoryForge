import { useEffect, useRef, useState } from 'react'
import {
  api,
  type Agent,
  type Pipeline,
  type PipelineNodeSpec,
  type PipelineRun,
} from '../api/client'
import { useCurrentProject } from '../state/ProjectContext'
import { Badge } from '../ui/Badge'
import { Button, IconButton } from '../ui/Button'
import { Card } from '../ui/Card'
import { EmptyState } from '../ui/EmptyState'
import { Select } from '../ui/Field'
import { Icon } from '../ui/icons'

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
  ok: 'text-accent-ink',
  running: 'text-accent-ink',
  awaiting: 'text-warn',
  blocked: 'text-warn',
  failed: 'text-danger',
  skipped: 'text-muted',
  cancelled: 'text-muted',
  pending: 'text-muted',
}

function statusTone(status: string): 'plain' | 'accent' | 'warn' {
  if (status === 'ok' || status === 'running') return 'accent'
  if (status === 'awaiting' || status === 'blocked' || status === 'failed') return 'warn'
  return 'plain'
}

export default function Pipeline() {
  // 当前项目由外壳持有；切换入口在侧栏。
  const { projectId } = useCurrentProject()
  const [pipeline, setPipeline] = useState<Pipeline | null>(null)
  const [agents, setAgents] = useState<Agent[]>([])
  const [run, setRun] = useState<PipelineRun | null>(null)
  const [notice, setNotice] = useState('')
  const [newType, setNewType] = useState('')
  const token = useRef(0)

  useEffect(() => {
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

  const runNodeBySeq = new Map((run?.nodes ?? []).map((node) => [node.seq, node]))

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="font-serif text-[22px] font-semibold text-ink">管线编排</h2>
        {pipeline && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[12.5px] text-muted">检查点策略</span>
            <div className="w-44">
              <Select
                aria-label="检查点策略"
                value={pipeline.policy}
                onChange={(e) => changePolicy(e.target.value)}
                options={pipeline.policies.map((item) => ({
                  value: item.value,
                  label: item.label,
                }))}
              />
            </div>
            <Button
              variant="primary"
              onClick={start}
              disabled={run !== null && ['running', 'awaiting', 'paused'].includes(run.status)}
            >
              开始运行
            </Button>
            <Button onClick={reset}>恢复默认管线</Button>
          </div>
        )}
      </div>

      {notice && <p className="text-[13px] text-muted">{notice}</p>}

      <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-3">
          {pipeline && (
            <ol className="relative space-y-3">
              <span className="absolute bottom-4 left-[11px] top-4 w-px bg-line" aria-hidden="true" />
              {pipeline.nodes.map((node, index) => {
                const runNode = runNodeBySeq.get(node.seq)
                return (
                  <li key={`${node.id}-${index}`} className="relative pl-7">
                    <span className="absolute left-0 top-3 flex h-6 w-6 items-center justify-center rounded-full border border-line-strong bg-surface text-[11px] tabular-nums text-muted">
                      {index + 1}
                    </span>
                    <article className="rounded-card border border-line bg-surface p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-[14px] font-semibold text-ink">{node.name}</span>
                        <Badge>{node.task_type}</Badge>
                        {runNode && (
                          <Badge tone={statusTone(runNode.status)}>
                            {STATUS_LABELS[runNode.status] ?? runNode.status}
                          </Badge>
                        )}
                        <div className="ml-auto flex items-center gap-1">
                          <IconButton
                            label="上移"
                            disabled={index === 0}
                            onClick={() => move(index, -1)}
                            className="disabled:opacity-30"
                          >
                            <Icon name="chevron" className="-rotate-90" />
                          </IconButton>
                          <IconButton
                            label="下移"
                            disabled={index === pipeline.nodes.length - 1}
                            onClick={() => move(index, 1)}
                            className="disabled:opacity-30"
                          >
                            <Icon name="chevron" className="rotate-90" />
                          </IconButton>
                          <Button size="sm" variant="warn" onClick={() => remove(index)}>
                            删除
                          </Button>
                        </div>
                      </div>
                      <div className="mt-2.5 flex flex-wrap items-center gap-3">
                        <div className="w-52">
                          <Select
                            aria-label={`${node.name} 的智能体`}
                            value={node.agent_id ?? ''}
                            onChange={(e) => bindAgent(index, e.target.value)}
                            options={[
                              { value: '', label: '按任务类型自动' },
                              ...agents
                                .filter((a) => a.task_type === node.task_type)
                                .map((a) => ({ value: a.id, label: a.name })),
                            ]}
                          />
                        </div>
                        <label className="flex items-center gap-1.5 text-[12.5px] text-ink-2">
                          <input
                            type="checkbox"
                            className="h-4 w-4 accent-accent"
                            checked={node.checkpoint}
                            onChange={() => toggle(index, 'checkpoint')}
                          />
                          检查点
                        </label>
                        <label className="flex items-center gap-1.5 text-[12.5px] text-ink-2">
                          <input
                            type="checkbox"
                            className="h-4 w-4 accent-accent"
                            checked={node.enabled}
                            onChange={() => toggle(index, 'enabled')}
                          />
                          启用
                        </label>
                      </div>
                    </article>
                  </li>
                )
              })}
            </ol>
          )}

          {pipeline && (
            <div className="flex flex-wrap items-center gap-2 pl-7">
              <div className="w-52">
                <Select
                  aria-label="要追加的任务类型"
                  value={newType}
                  onChange={(e) => setNewType(e.target.value)}
                  options={[
                    { value: '', label: '（选任务类型）' },
                    ...pipeline.node_types.map((item) => ({
                      value: item.task_type,
                      label: item.label,
                    })),
                  ]}
                />
              </div>
              <Button onClick={append} disabled={!newType}>
                追加节点
              </Button>
            </div>
          )}

          <p className="pl-7 text-[11.5px] text-muted">
            管线只产出结构材料：每个节点跑完后，去对应页面审阅并采纳。正文写作在写作台与批量生成里。
          </p>
        </div>

        <Card
          title="最近一次运行"
          actions={
            run ? (
              <Badge tone={statusTone(run.status)}>{RUN_LABELS[run.status] ?? run.status}</Badge>
            ) : undefined
          }
          className="xl:sticky xl:top-4"
        >
          {!run ? (
            <EmptyState title="还没有运行" hint="配置好节点后点「开始运行」。" />
          ) : (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[11.5px] text-muted">
                  {new Date(run.created_at).toLocaleString()}
                </span>
                <div className="ml-auto flex items-center gap-1.5">
                  {run.status === 'running' && (
                    <Button size="sm" onClick={() => control('pause')}>
                      暂停
                    </Button>
                  )}
                  {(run.status === 'paused' || run.status === 'awaiting') && (
                    <Button size="sm" variant="primary" onClick={() => control('resume')}>
                      继续
                    </Button>
                  )}
                  {!['completed', 'cancelled'].includes(run.status) && (
                    <Button size="sm" variant="warn" onClick={() => control('cancel')}>
                      取消
                    </Button>
                  )}
                </div>
              </div>

              {run.message && (
                <p className="rounded-control bg-warn-soft p-2 text-[12px] text-warn">
                  {run.message}
                </p>
              )}

              <ul className="space-y-2">
                {run.nodes.map((node) => (
                  <li key={node.id} className="border-t border-line pt-2">
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] tabular-nums text-faint">{node.seq + 1}</span>
                      <span className="text-[13px] font-medium text-ink-2">{node.name}</span>
                      <span
                        className={`ml-auto text-[11.5px] ${RUN_COLORS[node.status] ?? 'text-muted'}`}
                      >
                        {STATUS_LABELS[node.status] ?? node.status}
                      </span>
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      {node.message && (
                        <span className="text-[11.5px] text-muted">{node.message}</span>
                      )}
                      {typeof node.summary?.review_path === 'string' && (
                        <a
                          className="text-[11.5px] text-accent-ink underline-offset-2 hover:underline"
                          href={node.summary.review_path as string}
                        >
                          去审阅
                        </a>
                      )}
                      {node.generation_run_id && (
                        <a
                          className="text-[11.5px] text-muted underline-offset-2 hover:text-ink-2 hover:underline"
                          href={`/studio`}
                          title={node.generation_run_id}
                        >
                          运行记录
                        </a>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
