import { useEffect, useRef, useState } from 'react'
import { api, type CostSummary, type ExportReport, type Project, type Settings } from '../api/client'

export default function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([])
  const [selected, setSelected] = useState<Project | null>(null)
  const [cost, setCost] = useState<CostSummary | null>(null)
  const [report, setReport] = useState<ExportReport | null>(null)
  const [settings, setSettings] = useState<Settings | null>(null)
  const [name, setName] = useState('')
  const [notice, setNotice] = useState('')
  const reportToken = useRef(0)

  useEffect(() => {
    api
      .listProjects()
      .then(setProjects)
      .catch((error) => setNotice((error as Error).message))
    api.getSettings().then(setSettings).catch(() => setSettings(null))
  }, [])

  useEffect(() => {
    const token = ++reportToken.current
    if (!selected) {
      setCost(null)
      setReport(null)
      return
    }
    setReport(null)
    api
      .projectCost(selected.id)
      .then((value) => {
        if (reportToken.current === token) setCost(value)
      })
      .catch(() => {
        if (reportToken.current === token) setCost(null)
      })
    api
      .getExportReport(selected.id)
      .then((value) => {
        if (reportToken.current === token) setReport(value)
      })
      .catch((error) => {
        if (reportToken.current === token) setNotice((error as Error).message)
      })
  }, [selected])

  async function create() {
    if (!name.trim()) return
    try {
      const project = await api.createProject({ name: name.trim() })
      setProjects((prev) => [project, ...prev])
      setSelected(project)
      setName('')
      setNotice('')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">故事仪表盘</h2>

      {notice && <p className="rounded bg-amber-950/40 p-3 text-sm text-amber-300">{notice}</p>}

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
          {projects.length === 0 && !notice && (
            <p className="text-sm text-slate-500">还没有项目，先建一个。</p>
          )}
        </section>

        <div className="space-y-4">
          <section className="rounded border border-slate-800 p-4">
            <h3 className="mb-3 text-sm font-medium text-slate-300">体检单</h3>
            {selected ? (
              <dl className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <dt className="text-slate-500">字数</dt>
                  <dd>{report?.total_words ?? 0}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-slate-500">已写场景</dt>
                  <dd>
                    {report
                      ? `${report.scenes - report.scenes_without_body.length} / ${report.scenes}`
                      : '—'}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-slate-500">未回收伏笔</dt>
                  <dd>{report?.unrecovered_foreshadows.length ?? 0}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-slate-500">未处理告警</dt>
                  <dd>
                    {report
                      ? `审计 ${report.open_audit_issues} · 逻辑 ${report.open_logic_issues}`
                      : '—'}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-slate-500">锁定对象</dt>
                  <dd>
                    {report?.locked_counts
                      ? Object.values(report.locked_counts).reduce((a, b) => a + b, 0)
                      : '—'}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-slate-500">待复核</dt>
                  <dd>{report?.review_marks ?? 0}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-slate-500">累计调用</dt>
                  <dd>{cost?.runs ?? 0} 次</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-slate-500">累计费用</dt>
                  <dd>
                    ${(cost?.cost_estimate ?? 0).toFixed(4)}
                    {!!cost?.unpriced_runs && (
                      <span className="ml-1 text-xs text-amber-400">
                        （{cost.unpriced_runs} 次未定价）
                      </span>
                    )}
                  </dd>
                </div>
                {!!settings?.budget_alert && (cost?.cost_estimate ?? 0) > settings.budget_alert && (
                  <p className="rounded border border-amber-900 bg-amber-950/40 p-2 text-xs text-amber-300">
                    已超过预算提醒线 ${settings.budget_alert}。只是提醒，不会拦下调用。
                  </p>
                )}
              </dl>
            ) : (
              <p className="text-sm text-slate-500">选一个项目看体检单。</p>
            )}
          </section>

          <section className="space-y-3 rounded border border-slate-800 p-4">
            <h3 className="text-sm font-medium text-slate-300">导出与成品报告</h3>
            {selected && report ? (
              <>
                <p className="text-xs text-slate-500">
                  共 {report.total_words} 字 · {report.volumes} 卷 {report.chapters} 章 ·{' '}
                  {report.scenes} 场
                </p>
                {(report.scenes_without_body.length > 0 ||
                  report.unrecovered_foreshadows.length > 0 ||
                  report.open_audit_issues > 0 ||
                  report.open_logic_issues > 0) && (
                  <p className="rounded border border-amber-900 bg-amber-950/40 p-2 text-xs text-amber-300">
                    还有未闭环项：未写场景 {report.scenes_without_body.length}、未回收伏笔{' '}
                    {report.unrecovered_foreshadows.length}、未处理告警{' '}
                    {report.open_audit_issues + report.open_logic_issues}、待复核{' '}
                    {report.review_marks ?? 0}。仍可导出。
                  </p>
                )}
                <div className="flex flex-wrap gap-2 text-sm">
                  <a
                    href={api.exportUrl(selected.id, 'md')}
                    className="rounded border border-slate-700 px-3 py-1 text-slate-300 hover:text-white"
                  >
                    Markdown
                  </a>
                  <a
                    href={api.exportUrl(selected.id, 'txt')}
                    className="rounded border border-slate-700 px-3 py-1 text-slate-300 hover:text-white"
                  >
                    TXT
                  </a>
                  <a
                    href={api.exportUrl(selected.id, 'epub')}
                    className="rounded border border-slate-700 px-3 py-1 text-slate-300 hover:text-white"
                  >
                    EPUB
                  </a>
                </div>
              </>
            ) : (
              <p className="text-sm text-slate-500">选一个项目查看成品报告。</p>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}
