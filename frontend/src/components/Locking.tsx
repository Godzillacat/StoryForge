import { useState } from 'react'
import {
  api,
  type ImpactReport,
  type ReviewMark,
  type RevisionApplyResult,
  type RevisionResult,
  type RevisionSuggestion,
} from '../api/client'
import { countSelected, isSelectable } from '../lib/revisionView'

/** 「现在」一栏的显示上限：面板是窄栏，长段落会把整列撑散。 */
const BEFORE_LIMIT = 60

/** 跳过原因里需要作者特别留意的两种：用琥珀色，其余用灰色。 */
const AMBER_REASONS = new Set(['现值已变化', '已锁定'])

function clip(text: string, limit: number): string {
  const collapsed = text.split(/\s+/).filter(Boolean).join(' ')
  if (collapsed.length <= limit) return collapsed
  return collapsed.slice(0, limit) + '…'
}

export function LockToggle({
  targetType,
  targetId,
  locked,
  inheritedLabel,
  onChanged,
}: {
  targetType: string
  targetId: string
  locked: boolean
  /** 非空表示锁定来自上级（卷 / 章），本对象自己没有锁。 */
  inheritedLabel?: string
  onChanged?: () => void
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function toggle() {
    if (busy) return
    // 解锁前确认：锁定是保护，误点解掉会让 AI 下次写入时动到这一处。
    if (locked && !inheritedLabel && !window.confirm('解锁后 AI 可以改动这里。确定解锁？')) {
      return
    }
    setBusy(true)
    setError('')
    try {
      await api.setLock(targetType, targetId, !locked)
      onChanged?.()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (inheritedLabel) {
    return (
      <span className="text-xs text-amber-400" title={`由「${inheritedLabel}」锁定`}>
        已锁定（继承）
      </span>
    )
  }

  return (
    <span className="inline-flex items-center gap-2">
      <button
        className={`rounded border px-2 py-0.5 text-xs ${
          locked
            ? 'border-amber-600 bg-amber-950/40 text-amber-300'
            : 'border-slate-700 text-slate-400'
        } ${busy ? 'opacity-50' : ''}`}
        onClick={toggle}
        disabled={busy}
        title={locked ? 'AI 不会改动这里' : '锁定后 AI 不会改动这里'}
      >
        {locked ? '🔒 已锁定' : '锁定'}
      </button>
      {error && <span className="text-xs text-red-400">{error}</span>}
    </span>
  )
}

export function ImpactPanel({
  projectId,
  targetType,
  targetId,
  onMarksChanged,
}: {
  projectId: string
  targetType: string
  targetId: string
  onMarksChanged?: () => void
}) {
  const [report, setReport] = useState<ImpactReport | null>(null)
  const [marks, setMarks] = useState<ReviewMark[]>([])
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const [open, setOpen] = useState(false)
  const [revisions, setRevisions] = useState<RevisionResult | null>(null)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [generating, setGenerating] = useState(false)
  const [applying, setApplying] = useState(false)
  const [applyResult, setApplyResult] = useState<RevisionApplyResult | null>(null)
  const [revisionError, setRevisionError] = useState('')

  function resetRevisions() {
    setRevisions(null)
    setSelected(new Set())
    setApplyResult(null)
    setRevisionError('')
  }

  async function load() {
    if (open) {
      setOpen(false)
      // 收起时一并清掉建议：下次展开的是新的目标状态，旧建议不该留在屏幕上。
      resetRevisions()
      return
    }
    setBusy(true)
    setNotice('')
    resetRevisions()
    try {
      const [impact, current] = await Promise.all([
        api.getImpact(projectId, targetType, targetId),
        api.listReviewMarks(projectId),
      ])
      setReport(impact)
      setMarks(current)
      setOpen(true)
    } catch (e) {
      setNotice((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function markDownstream() {
    if (!report) return
    // 只标**场景与章**这类会被内容改动牵动的对象；幕骨架与关系是结构描述，
    // 作者改上游时通常不需要重新通读它们。
    const items = report.groups
      .flatMap((group) => group.items)
      .filter((item) => ['scene', 'chapter', 'volume', 'entry'].includes(item.type))
      .map((item) => ({
        target_type: item.type,
        target_id: item.id,
        reason: `「${report.target.label}」已改动`,
      }))
    if (items.length === 0) {
      setNotice('没有需要标记的下游对象')
      return
    }
    setBusy(true)
    try {
      const result = await api.addReviewMarks(projectId, items)
      setMarks(result.marks)
      setNotice(`已标记 ${result.added} 条待复核`)
      onMarksChanged?.()
    } catch (e) {
      setNotice((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  // 影响面里已锁定的对象：服务端生成时已过滤掉它们，但面板可能比锁定状态旧，
  // 显示时再对一次，锁上的行立刻变成不可选并标「锁定」。
  const lockedKeys = new Set(
    (report?.groups ?? [])
      .flatMap((group) => group.items)
      .filter((item) => item.locked)
      .map((item) => `${item.type}-${item.id}`),
  )

  const skippedReasons = new Map<number, string>()
  for (const row of applyResult?.skipped ?? []) skippedReasons.set(row.index, row.reason)
  const appliedIndices = new Set((applyResult?.applied ?? []).map((row) => row.index))

  function rowState(item: RevisionSuggestion) {
    const skipped = skippedReasons.get(item.index) ?? ''
    const locked = skipped === '已锁定' || lockedKeys.has(`${item.target_type}-${item.target_id}`)
    const stale = skipped === '现值已变化'
    // 已写过的、以及因为别的原因跳过的（对象已删除、下标无效、字段不可改）都不再可选。
    const blocked = appliedIndices.has(item.index)
      ? '已应用'
      : skipped && !AMBER_REASONS.has(skipped)
        ? skipped
        : ''
    return { locked, stale, blocked }
  }

  function canSelect(item: RevisionSuggestion) {
    const state = rowState(item)
    return isSelectable(state) && !state.blocked
  }

  function toggle(index: number) {
    const item = revisions?.suggestions.find((row) => row.index === index)
    if (!item || !canSelect(item)) return
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(index)) next.delete(index)
      else next.add(index)
      return next
    })
  }

  async function generateRevisions() {
    if (generating || !report) return
    setGenerating(true)
    setRevisionError('')
    setApplyResult(null)
    setSelected(new Set())
    try {
      const result = await api.generateRevisions(projectId, {
        target_type: targetType,
        target_id: targetId,
      })
      setRevisions(result)
    } catch (e) {
      // 请求本身失败（目标不存在、网络）：只显示中文原因，不回显任何响应体。
      setRevisions(null)
      setRevisionError((e as Error).message)
    } finally {
      setGenerating(false)
    }
  }

  async function applySelected() {
    const runId = revisions?.run_id
    if (applying || !runId) return
    const accepted = (revisions?.suggestions ?? [])
      .filter((item) => selected.has(item.index) && canSelect(item))
      .map((item) => item.index)
    if (accepted.length === 0) {
      setRevisionError('先勾选要采纳的修订建议')
      return
    }
    setApplying(true)
    setRevisionError('')
    try {
      const result = await api.applyRevisions(projectId, { run_id: runId, accepted })
      setApplyResult(result)
      setSelected(new Set())
    } catch (e) {
      setRevisionError((e as Error).message)
    } finally {
      setApplying(false)
    }
  }

  // 可建议的对象只有「会改字段的场景与章」；影响面为空、全是锁定、
  // 或者只有设定条目/幕时，按钮都要禁用并说明原因。
  const sceneChapterItems = (report?.groups ?? [])
    .flatMap((group) => group.items)
    .filter((item) => item.type === 'scene' || item.type === 'chapter')
  const suggestibleCount = sceneChapterItems.filter((item) => !item.locked).length
  const suggestionHint = !report
    ? ''
    : report.totals.all === 0
      ? '没有可建议的下游对象'
      : sceneChapterItems.length === 0
        ? '影响面里没有可改的场景或章'
        : suggestibleCount === 0
          ? '场景与章都在锁定中，没有可建议的对象'
          : ''

  const suggestionStates = (revisions?.suggestions ?? []).map(rowState)
  const selectedCount = countSelected(
    suggestionStates.map((state) => ({
      locked: state.locked,
      stale: state.stale || Boolean(state.blocked),
    })),
    selected,
  )

  const markedIds = new Set(marks.map((mark) => mark.target_id))

  return (
    <div className="space-y-2">
      <button
        className="rounded border border-slate-700 px-3 py-1 text-xs text-slate-300 disabled:opacity-50"
        onClick={load}
        disabled={busy}
      >
        {open ? '收起影响面' : '看看会影响什么'}
      </button>
      {notice && <p className="text-xs text-slate-400">{notice}</p>}

      {open && report && (
        <div className="space-y-3 rounded border border-slate-800 bg-slate-900/60 p-3 text-xs">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-slate-400">
              共 {report.totals.all} 处下游，其中 {report.totals.locked} 处已锁定
            </span>
            <button
              className="rounded bg-indigo-600 px-3 py-1 disabled:opacity-50"
              onClick={markDownstream}
              disabled={busy}
            >
              只改上层，下游标为待复核
            </button>
            <button
              className="rounded border border-slate-700 px-3 py-1 text-slate-300 disabled:opacity-50"
              onClick={generateRevisions}
              disabled={generating || busy || suggestibleCount === 0}
              title={suggestionHint || '针对这次改动生成可逐条采纳的修订建议'}
            >
              {generating ? '生成中…' : '生成修订建议'}
            </button>
            {suggestionHint && <span className="text-slate-500">{suggestionHint}</span>}
          </div>

          {revisionError && <p className="text-red-400">{revisionError}</p>}

          {revisions && revisions.llm_status !== 'ok' && revisions.warning && (
            <p className="text-amber-300">{revisions.warning}</p>
          )}

          {revisions && revisions.llm_status === 'ok' && revisions.suggestions.length === 0 && (
            <p className="text-slate-400">{revisions.warning || '这次没有需要改的地方'}</p>
          )}

          {revisions && revisions.llm_status === 'ok' && revisions.suggestions.length > 0 && (
            <div className="space-y-2 rounded border border-slate-800 bg-slate-950/40 p-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-slate-300">
                  {revisions.suggestions.length} 条建议 · 采纳选中 {selectedCount} 条
                </span>
              </div>
              {revisions.warning && <p className="text-amber-300">{revisions.warning}</p>}
              <ul className="space-y-1">
                {revisions.suggestions.map((item) => {
                  const state = rowState(item)
                  const selectable = canSelect(item)
                  return (
                    <li
                      key={item.index}
                      className={`rounded border border-slate-800 p-2 ${
                        selectable ? '' : 'opacity-50'
                      }`}
                    >
                      <label className="flex items-start gap-2">
                        <input
                          type="checkbox"
                          className="mt-0.5"
                          checked={selected.has(item.index)}
                          disabled={!selectable}
                          onChange={() => toggle(item.index)}
                        />
                        <span className="space-y-0.5">
                          <span className="flex flex-wrap items-center gap-1 text-slate-200">
                            {item.target_label} · {item.field_label}
                            {state.locked && <span className="text-amber-400">锁定</span>}
                            {state.stale && <span className="text-amber-400">现值已变化</span>}
                            {state.blocked && (
                              <span className="text-slate-400">{state.blocked}</span>
                            )}
                          </span>
                          <span className="block text-slate-500">
                            现在：{clip(item.before, BEFORE_LIMIT) || '（空）'}
                          </span>
                          <span className="block text-slate-300">建议：{item.after}</span>
                          {item.reason && (
                            <span className="block text-slate-500">理由：{item.reason}</span>
                          )}
                        </span>
                      </label>
                    </li>
                  )
                })}
              </ul>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  className="rounded bg-indigo-600 px-3 py-1 disabled:opacity-50"
                  onClick={applySelected}
                  disabled={applying || selectedCount === 0}
                >
                  {applying ? '应用中…' : `采纳选中 ${selectedCount} 条`}
                </button>
                <button
                  className="rounded border border-slate-700 px-3 py-1 text-slate-400"
                  onClick={resetRevisions}
                  disabled={applying}
                >
                  全部不要
                </button>
              </div>
              {applyResult && (
                <p className="text-slate-300">
                  已采纳 {applyResult.applied.length} 条
                  {applyResult.skipped.length > 0 && (
                    <>
                      ，跳过 {applyResult.skipped.length} 条：
                      {applyResult.skipped.map((row) => (
                        <span
                          key={`${row.index}-${row.reason}`}
                          className={`ml-1 ${
                            AMBER_REASONS.has(row.reason) ? 'text-amber-400' : 'text-slate-400'
                          }`}
                        >
                          第 {row.index + 1} 条「{row.reason}」
                        </span>
                      ))}
                    </>
                  )}
                </p>
              )}
            </div>
          )}

          {report.groups.map((group) => (
            <div key={group.key} className="space-y-1">
              <div className="text-slate-300">
                {group.label}：{group.total}
                {group.locked > 0 && (
                  <span className="text-amber-400">（{group.locked} 处锁定）</span>
                )}
              </div>
              {group.note && <p className="text-slate-500">{group.note}</p>}
              {group.items.length > 0 && (
                <ul className="space-y-0.5 pl-3">
                  {group.items.slice(0, 20).map((item) => (
                    <li key={`${item.type}-${item.id}`} className="flex items-center gap-2">
                      <a className="text-indigo-400" href={item.path}>
                        {item.label}
                      </a>
                      {item.detail && (
                        <span className="truncate text-slate-500">{item.detail}</span>
                      )}
                      {item.locked && (
                        <span className="text-amber-400" title={item.locked_by}>
                          锁定
                        </span>
                      )}
                      {markedIds.has(item.id) && (
                        <span className="text-amber-400">已标待复核</span>
                      )}
                    </li>
                  ))}
                  {group.items.length > 20 && (
                    <li className="text-slate-500">… 另有 {group.items.length - 20} 项</li>
                  )}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function ReviewMarkBadge({
  marked,
  reason,
  onClick,
}: {
  marked: boolean
  reason: string
  onClick: () => void
}) {
  if (!marked) return null
  return (
    <button
      className="rounded bg-amber-950/50 px-1.5 py-0.5 text-[10px] text-amber-300"
      onClick={onClick}
      title={`${reason}（点击清除标记）`}
    >
      待复核
    </button>
  )
}

export function ReviewMarkList({
  projectId,
  marks,
  onReload,
}: {
  projectId: string
  marks: ReviewMark[]
  onReload: () => void
}) {
  const [error, setError] = useState('')
  if (marks.length === 0) return null

  async function clear(markId: string) {
    try {
      await api.clearReviewMark(markId)
      onReload()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <div className="space-y-1 rounded border border-amber-900/50 bg-amber-950/20 p-3 text-xs">
      <div className="flex items-center gap-2">
        <span className="text-amber-300">{marks.length} 条待复核</span>
        <button
          className="rounded border border-amber-800 px-2 py-0.5 text-amber-300"
          onClick={async () => {
            try {
              await api.clearReviewMarks(
                projectId,
                marks.map((mark) => ({
                  target_type: mark.target_type,
                  target_id: mark.target_id,
                })),
              )
              onReload()
            } catch (e) {
              setError((e as Error).message)
            }
          }}
        >
          全部清除
        </button>
      </div>
      {error && <p className="text-red-400">{error}</p>}
      <ul className="space-y-0.5">
        {marks.map((mark) => (
          <li key={mark.id} className="flex items-center gap-2">
            <span className="text-slate-500">{mark.type_label}</span>
            <a className="text-indigo-400" href={mark.path}>
              {mark.label}
            </a>
            {mark.reason && <span className="text-slate-500">{mark.reason}</span>}
            <button className="text-slate-500" onClick={() => clear(mark.id)}>
              清除
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
