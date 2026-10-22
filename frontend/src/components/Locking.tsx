import { useState } from 'react'
import { api, type ImpactReport, type ReviewMark } from '../api/client'

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

  async function load() {
    if (open) {
      setOpen(false)
      return
    }
    setBusy(true)
    setNotice('')
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
              className="rounded border border-slate-700 px-3 py-1 text-slate-500"
              disabled
              title="逐条生成修订建议需要单独的模型调用，后续提供"
            >
              生成修订建议（后续提供）
            </button>
          </div>

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
