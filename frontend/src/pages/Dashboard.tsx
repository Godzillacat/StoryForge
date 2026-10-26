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
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { EmptyState } from '../ui/EmptyState'

export default function Dashboard() {
  // 项目列表与「当前项目」由外壳持有；这里只读，不再自己拉、不再自己选。
  const {
    projects,
    project: selected,
    projectId,
    refresh: reloadProjects,
    error: listError,
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

  const kpis = [
    { label: '总字数', value: report ? report.total_words : '—' },
    {
      label: '已写场景',
      value: report ? `${report.scenes - report.scenes_without_body.length} / ${report.scenes}` : '—',
    },
    { label: '未回收伏笔', value: report ? report.unrecovered_foreshadows.length : '—' },
    {
      label: '待处理问题',
      value: report ? report.open_audit_issues + report.open_logic_issues : '—',
    },
  ]

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="font-serif text-[19px] font-semibold text-ink">故事仪表盘</h2>
        {selected && <span className="text-[13px] text-muted">{selected.name}</span>}
        <div className="ml-auto flex items-center gap-2">
          {selected && (
            <>
              <a
                className="inline-flex h-8 items-center rounded-control border border-line-strong bg-surface px-3 text-[13px] text-ink-2 transition-colors duration-[120ms] hover:bg-sunken"
                href={api.exportUrl(selected.id, 'md')}
              >
                导出 Markdown
              </a>
              <a
                className="inline-flex h-8 items-center rounded-control bg-accent px-3 text-[13px] text-white transition-colors duration-[120ms] hover:bg-accent-ink"
                href={api.exportUrl(selected.id, 'epub', epubTemplate)}
              >
                导出 EPUB
              </a>
            </>
          )}
        </div>
      </div>

      {notice && (
        <p className="rounded-control border-l-2 border-warn bg-warn-soft p-2.5 text-[13px] text-warn">
          {notice}
        </p>
      )}

      {projects.length === 0 && listError && (
        <p className="rounded-control border-l-2 border-warn bg-warn-soft p-2.5 text-[13px] text-warn">
          读取项目列表失败：{listError}。这不是「没有项目」，请确认后端在运行后重试。
        </p>
      )}
      {projects.length === 0 && !listError && (
        <EmptyState title="还没有项目" hint="用左侧项目选择器新建一个 —— 建项目的入口只有那一处。" />
      )}

      <div className="grid grid-cols-4 gap-3">
        {kpis.map((kpi) => (
          <Card key={kpi.label}>
            <div className="text-[11px] tracking-[.08em] text-muted">{kpi.label}</div>
            <div className="mt-1 font-serif text-[26px] leading-tight text-ink tabular-nums">
              {kpi.value}
            </div>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-[1fr_360px] items-start gap-4">
        <div className="space-y-4">
          <Card title="体检单">
            {selected ? (
              <dl className="space-y-2 text-[13.5px]">
                <div className="flex justify-between">
                  <dt className="text-muted">未写场景</dt>
                  <dd className="text-ink-2 tabular-nums">
                    {report?.scenes_without_body.length ?? 0}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted">未回收伏笔</dt>
                  <dd className="text-ink-2 tabular-nums">
                    {report?.unrecovered_foreshadows.length ?? 0}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted">锁定对象</dt>
                  <dd className="text-ink-2 tabular-nums">
                    {report?.locked_counts
                      ? Object.values(report.locked_counts).reduce((a, b) => a + b, 0)
                      : '—'}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted">待复核</dt>
                  <dd className="text-ink-2 tabular-nums">{report?.review_marks ?? 0}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted">累计调用</dt>
                  <dd className="text-ink-2 tabular-nums">{cost?.runs ?? 0} 次</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted">累计费用</dt>
                  <dd className="text-ink-2 tabular-nums">
                    ${(cost?.cost_estimate ?? 0).toFixed(4)}
                    {!!cost?.unpriced_runs && (
                      <span className="ml-1 text-[11.5px] text-warn">
                        （{cost.unpriced_runs} 次未定价）
                      </span>
                    )}
                  </dd>
                </div>
                {!!settings?.budget_alert && (cost?.cost_estimate ?? 0) > settings.budget_alert && (
                  <p className="rounded-control bg-warn-soft p-2 text-[11.5px] text-warn">
                    已超过预算提醒线 ${settings.budget_alert}。只是提醒，不会拦下调用。
                  </p>
                )}
              </dl>
            ) : (
              <p className="text-[13px] text-muted">用左侧项目选择器选一个项目，这里显示它的体检单。</p>
            )}
          </Card>

          <Card title="最近改动">
            {selected ? (
              <ChangeList
                projectId={selected.id}
                changes={changes}
                emptyHint="这个项目还没有改动记录。"
              />
            ) : (
              <p className="text-[13px] text-muted">选一个项目查看改动历史。</p>
            )}
          </Card>
        </div>

        <div className="space-y-4">
          <Card title="导出与成品报告" className="space-y-3">
            {selected && report ? (
              <>
                <p className="text-[11.5px] text-muted">
                  共 {report.total_words} 字 · {report.volumes} 卷 {report.chapters} 章 ·{' '}
                  {report.scenes} 场
                </p>
                {(report.scenes_without_body.length > 0 ||
                  report.unrecovered_foreshadows.length > 0 ||
                  report.open_audit_issues > 0 ||
                  report.open_logic_issues > 0) && (
                  <p className="rounded-control bg-warn-soft p-2 text-[11.5px] text-warn">
                    还有未闭环项：未写场景 {report.scenes_without_body.length}、未回收伏笔{' '}
                    {report.unrecovered_foreshadows.length}、未处理告警{' '}
                    {report.open_audit_issues + report.open_logic_issues}、待复核{' '}
                    {report.review_marks ?? 0}。仍可导出。
                  </p>
                )}
                <div className="flex flex-wrap items-center gap-2">
                  <a
                    className="inline-flex h-8 items-center rounded-control border border-line-strong bg-surface px-3 text-[13px] text-ink-2 transition-colors duration-[120ms] hover:bg-sunken"
                    href={api.exportUrl(selected.id, 'md')}
                  >
                    Markdown
                  </a>
                  <a
                    className="inline-flex h-8 items-center rounded-control border border-line-strong bg-surface px-3 text-[13px] text-ink-2 transition-colors duration-[120ms] hover:bg-sunken"
                    href={api.exportUrl(selected.id, 'txt')}
                  >
                    TXT
                  </a>
                  <select
                    className="h-8 rounded-control border border-line-strong bg-surface px-2.5 pr-6 text-[13px] text-ink-2 outline-none transition-colors duration-[120ms] focus:border-accent focus:shadow-[0_0_0_3px_var(--accent-soft)]"
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
                    className="inline-flex h-8 items-center rounded-control bg-accent px-3 text-[13px] text-white transition-colors duration-[120ms] hover:bg-accent-ink"
                    href={api.exportUrl(selected.id, 'epub', epubTemplate)}
                  >
                    EPUB
                  </a>
                </div>

                <div className="space-y-1 border-t border-line pt-3">
                  <p className="text-[11.5px] text-muted">封面</p>
                  {coverSet ? (
                    <div className="flex items-center gap-2 text-[11.5px]">
                      <img
                        src={`/api/projects/${selected.id}/cover`}
                        alt="封面"
                        className="h-16 w-12 rounded-tag border border-line object-cover"
                      />
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={coverBusy}
                        onClick={() => coverInput.current?.click()}
                      >
                        换一张
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-warn"
                        disabled={coverBusy}
                        onClick={() => void removeCover()}
                      >
                        移除
                      </Button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 text-[11.5px]">
                      <span className="text-muted">未设置封面，EPUB 不会带封面页。</span>
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={coverBusy}
                        onClick={() => coverInput.current?.click()}
                      >
                        上传
                      </Button>
                    </div>
                  )}
                  <input
                    ref={coverInput}
                    type="file"
                    accept="image/png,image/jpeg"
                    className="hidden"
                    onChange={(event) => void uploadCover(event.target.files?.[0])}
                  />
                  <p className="text-[11.5px] text-faint">PNG 或 JPEG，最大 4 MB。</p>
                </div>
              </>
            ) : (
              <p className="text-[13px] text-muted">选一个项目查看成品报告。</p>
            )}
          </Card>

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
        </div>
      </div>
    </div>
  )
}
