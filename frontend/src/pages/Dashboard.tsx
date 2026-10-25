import { useEffect, useRef, useState } from 'react'
import {
  api,
  type ChangeRow,
  type CostSummary,
  type ExportReport,
  type Settings,
  type SnapshotView,
} from '../api/client'
import { ChangeList, SnapshotPanel } from '../components/Snapshots'
import { useCurrentProject } from '../state/ProjectContext'
import { EmptyState } from '../ui/EmptyState'

export default function Dashboard() {
  // 项目列表与「当前项目」由外壳持有；这里只读，不再自己拉、不再自己选。
  const {
    projects,
    project: selected,
    projectId,
    select,
    refresh: reloadProjects,
  } = useCurrentProject()
  // 封面是否已设置。**与项目对象分开存**：它一变就替换项目的话，
  // 下面的 report effect 会重跑、整张导出卡片塌成占位。
  const [coverSet, setCoverSet] = useState(false)
  const [cost, setCost] = useState<CostSummary | null>(null)
  const [report, setReport] = useState<ExportReport | null>(null)
  const [settings, setSettings] = useState<Settings | null>(null)
  const [notice, setNotice] = useState('')
  const [snapshots, setSnapshots] = useState<SnapshotView[]>([])
  const [changes, setChanges] = useState<ChangeRow[]>([])
  const reportToken = useRef(0)
  // 导出模板是**每次导出选一次**的参数，不是项目设置 —— 所以不落库、不记忆。
  const [epubTemplate, setEpubTemplate] = useState<'plain' | 'classic'>('plain')
  const [coverBusy, setCoverBusy] = useState(false)
  const coverInput = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    api.getSettings().then(setSettings).catch(() => setSettings(null))
  }, [])

  // 封面标记跟着项目走；单独一个 effect，免得刷新项目列表时把报告一起重拉。
  useEffect(() => {
    setCoverSet(Boolean(selected?.has_cover))
  }, [projectId, selected?.has_cover])

  useEffect(() => {
    const token = ++reportToken.current
    if (!projectId) {
      setCost(null)
      setReport(null)
      return
    }
    setReport(null)
    setSnapshots([])
    setChanges([])
    loadSnapshots(projectId, token)
    api
      .projectCost(projectId)
      .then((value) => {
        if (reportToken.current === token) setCost(value)
      })
      .catch(() => {
        if (reportToken.current === token) setCost(null)
      })
    api
      .getExportReport(projectId)
      .then((value) => {
        if (reportToken.current === token) setReport(value)
      })
      .catch((error) => {
        if (reportToken.current === token) setNotice((error as Error).message)
      })
  }, [projectId])

  function loadSnapshots(projectId: string, token: number) {
    api
      .listSnapshots(projectId)
      .then((rows) => {
        if (reportToken.current === token) setSnapshots(rows)
      })
      .catch(() => {
        if (reportToken.current === token) setSnapshots([])
      })
    api
      .listChanges(projectId, { limit: 20 })
      .then((body) => {
        if (reportToken.current === token) setChanges(body.changes)
      })
      .catch(() => {
        if (reportToken.current === token) setChanges([])
      })
  }

  function reloadSnapshots() {
    if (!projectId) return
    loadSnapshots(projectId, reportToken.current)
  }

  async function uploadCover(file: File | undefined) {
    if (!file || !selected) return
    setCoverBusy(true)
    setNotice('')
    try {
      await api.uploadCover(selected.id, file)
      setCoverSet(true)
      await reloadProjects()
    } catch (error) {
      setNotice((error as Error).message)
    } finally {
      setCoverBusy(false)
      // 同一个文件再选一次也要能触发 change。
      if (coverInput.current) coverInput.current.value = ''
    }
  }

  async function removeCover() {
    if (!selected) return
    setCoverBusy(true)
    setNotice('')
    try {
      await api.removeCover(selected.id)
      setCoverSet(false)
      await reloadProjects()
    } catch (error) {
      setNotice((error as Error).message)
    } finally {
      setCoverBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">故事仪表盘</h2>

      {notice && <p className="rounded bg-amber-950/40 p-3 text-sm text-amber-300">{notice}</p>}

      {projects.length === 0 && !notice && (
        <EmptyState title="还没有项目" hint="用左侧项目选择器新建一个 —— 建项目的入口只有那一处。" />
      )}

      <div className="grid grid-cols-3 gap-4">
        <section className="col-span-2 space-y-2">
          {projects.map((p) => (
            <button
              key={p.id}
              onClick={() => select(p.id)}
              className={`block w-full rounded border px-4 py-3 text-left ${
                projectId === p.id ? 'border-indigo-500 bg-slate-900' : 'border-slate-800'
              }`}
            >
              <div className="font-medium">{p.name}</div>
              <div className="text-xs text-slate-500">
                {p.genre ?? '未定题材'} · {p.tone ?? '未定调性'}
              </div>
            </button>
          ))}
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
                <div className="flex flex-wrap items-center gap-2 text-sm">
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
                  <select
                    className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-slate-300"
                    value={epubTemplate}
                    onChange={(event) =>
                      setEpubTemplate(event.target.value as 'plain' | 'classic')
                    }
                    title="EPUB 的排版样式；每次导出选一次"
                  >
                    <option value="plain">素雅</option>
                    <option value="classic">传统</option>
                  </select>
                  <a
                    href={api.exportUrl(selected.id, 'epub', epubTemplate)}
                    className="rounded border border-slate-700 px-3 py-1 text-slate-300 hover:text-white"
                  >
                    EPUB
                  </a>
                </div>

                <div className="mt-3 space-y-1 border-t border-slate-800 pt-3 text-sm">
                  <p className="text-xs text-slate-500">封面</p>
                  {coverSet ? (
                    <div className="flex items-center gap-2 text-xs">
                      <img
                        src={`/api/projects/${selected.id}/cover`}
                        alt="封面"
                        className="h-16 w-12 rounded border border-slate-700 object-cover"
                      />
                      <button
                        className="text-slate-400 hover:text-white disabled:opacity-50"
                        disabled={coverBusy}
                        onClick={() => coverInput.current?.click()}
                      >
                        换一张
                      </button>
                      <button
                        className="text-slate-400 hover:text-red-300 disabled:opacity-50"
                        disabled={coverBusy}
                        onClick={() => void removeCover()}
                      >
                        移除
                      </button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-slate-500">未设置封面，EPUB 不会带封面页。</span>
                      <button
                        className="text-slate-400 hover:text-white disabled:opacity-50"
                        disabled={coverBusy}
                        onClick={() => coverInput.current?.click()}
                      >
                        上传
                      </button>
                    </div>
                  )}
                  <input
                    ref={coverInput}
                    type="file"
                    accept="image/png,image/jpeg"
                    className="hidden"
                    onChange={(event) => void uploadCover(event.target.files?.[0])}
                  />
                  <p className="text-xs text-slate-600">PNG 或 JPEG，最大 4 MB。</p>
                </div>
              </>
            ) : (
              <p className="text-sm text-slate-500">选一个项目查看成品报告。</p>
            )}
          </section>
          {selected && (
            <SnapshotPanel
              projectId={selected.id}
              snapshots={snapshots}
              onReload={reloadSnapshots}
              onRestored={() => {
                // 回滚改了整份结构：报告与费用都过期了，重新拉一遍。
                // 持令牌守卫 —— 回滚途中切了项目时，这批响应属于旧项目。
                const token = reportToken.current
                const projectId = selected.id
                setReport(null)
                api
                  .getExportReport(projectId)
                  .then((value) => {
                    if (reportToken.current === token) setReport(value)
                  })
                  .catch(() => {
                    if (reportToken.current === token) setReport(null)
                  })
                api
                  .projectCost(projectId)
                  .then((value) => {
                    if (reportToken.current === token) setCost(value)
                  })
                  .catch(() => {
                    if (reportToken.current === token) setCost(null)
                  })
              }}
            />
          )}

          <section className="space-y-3 rounded border border-slate-800 p-4">
            <h3 className="text-sm font-medium text-slate-300">最近改动</h3>
            {selected ? (
              <ChangeList
                projectId={selected.id}
                changes={changes}
                emptyHint="这个项目还没有改动记录。"
              />
            ) : (
              <p className="text-sm text-slate-500">选一个项目查看改动历史。</p>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}
