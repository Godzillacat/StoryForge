import { useState } from 'react'
import {
  api,
  type ChapterStatusOption,
  type Foreshadow,
  type ForeshadowSummary,
  type VolumeNode,
} from '../../api/client'
import {
  buildForeshadowLedger,
  filterLedger,
  type LedgerFilter,
  type LedgerLocation,
  type LedgerRow,
} from '../../lib/chapterViews'

const FILTERS: { key: LedgerFilter; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'missing_plant', label: '缺埋设' },
  { key: 'missing_pay', label: '缺计划回收' },
  { key: 'unpaid', label: '未回收' },
  { key: 'dropped', label: '已弃' },
]

function hints(row: LedgerRow): string {
  const out: string[] = []
  if (row.missingPlant) out.push('缺埋设')
  if (row.missingPay) out.push('缺计划回收')
  if (row.effectiveStatus === 'dropped') out.push('作者已放弃')
  // 「已收」但没记位置：作者手设的，正文里还没落到具体场景。说清楚，
  // 否则同一行的「实际回收位置」列写着「未安排」，两列看着互相打架。
  else if (row.effectiveStatus === 'paid') {
    out.push(row.actualPay ? '已回收' : '已收（未记录位置）')
  } else if (!row.missingPay) out.push('已计划、未回收')
  if (row.sameScene) out.push('埋设与回收同一场')
  return out.join(' ')
}

function LocationCell({
  location,
  onSelect,
}: {
  location: LedgerLocation | null
  onSelect: (id: string) => void
}) {
  if (!location) return <span className="text-amber-300">未安排</span>
  return (
    <button
      className="text-left text-indigo-300 hover:underline"
      title={location.fullLabel}
      onClick={() => onSelect(location.sceneId)}
    >
      {location.shortLabel}
    </button>
  )
}

export default function ForeshadowLedger({
  volumes,
  foreshadows,
  statuses,
  summary,
  onSelectScene,
  onChanged,
  onNotice,
  busy,
}: {
  volumes: VolumeNode[]
  foreshadows: Foreshadow[]
  /** 生命周期词表。由页面从 `/api/foreshadow-types` 拉取，界面不硬编第二份。 */
  statuses: ChapterStatusOption[]
  /** 四类计数与回收率由后端算（`/foreshadows/summary`），前端不重算一遍规则。 */
  summary: ForeshadowSummary | null
  onSelectScene: (id: string) => void
  /** 改完状态后由页面刷新列表与汇总。 */
  onChanged: () => Promise<void>
  onNotice: (message: string) => void
  busy: boolean
}) {
  const [filter, setFilter] = useState<LedgerFilter>('all')
  // 正在保存的那一行：防止双击连发两次 PATCH，也让作者看得出是哪一行在动。
  const [savingId, setSavingId] = useState('')
  const rows = buildForeshadowLedger(volumes, foreshadows)

  async function changeStatus(row: LedgerRow, next: string) {
    // 旧值是唯一不能早返回的情形：库里存的是 `confirmed`，界面上显示的却是
    // 「规划中」。不跳过才能把库里的值改写成 `planned`。
    if (next === row.effectiveStatus && !row.statusIsLegacy) return
    setSavingId(row.id)
    onNotice('')
    try {
      await api.updateForeshadow(row.id, { status: next })
      await onChanged()
      // 位置字段是事实，会在下一次显示时压过作者刚选的状态。不说明的话，
      // 作者会以为自己的选择没保存 —— 这两种情形各说一句。
      if (next !== 'paid' && next !== 'dropped' && row.actualPay) {
        onNotice(
          `「${row.name}」的实际回收位置已记录，状态仍显示为「已收」。` +
            `要改回其他状态，先点这一行的「清掉实际回收」。`,
        )
      } else if (next === 'planned' && row.plant) {
        onNotice(
          `「${row.name}」的埋设位置已记录，状态仍显示为「已埋」。` +
            `埋设位置在结构设计的场景编辑器里改。`,
        )
      }
    } catch (error) {
      onNotice((error as Error).message)
    } finally {
      setSavingId('')
    }
  }

  /** 回写助手可能把伏笔匹配到错误的场景；作者得能撤销那条事实。 */
  async function clearActualPay(row: LedgerRow) {
    setSavingId(row.id)
    onNotice('')
    try {
      await api.updateForeshadow(row.id, { actual_pay_scene_id: null })
      await onChanged()
      onNotice(`已清掉「${row.name}」的实际回收位置。`)
    } catch (error) {
      onNotice((error as Error).message)
    } finally {
      setSavingId('')
    }
  }

  if (foreshadows.length === 0) {
    return (
      <p className="rounded border border-slate-800 p-4 text-sm text-slate-500">
        还没有伏笔。在结构设计的场景编辑器里挂上伏笔后，这里会按故事顺序列出。
      </p>
    )
  }

  const visible = filterLedger(rows, filter)
  // 分母 = 未放弃的三类；`dropped` 不进分母（与后端同一口径）。
  const denominator = summary
    ? summary.paid + summary.planted + summary.planned
    : 0

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-sm font-medium text-slate-300">伏笔账本</h3>
        {summary ? (
          <p className="text-xs text-slate-500">
            共 {summary.total} 条 · 已收 {summary.paid} · 已埋未收 {summary.planted} ·
            规划中 {summary.planned} · 已弃 {summary.dropped} · 回收率{' '}
            {(summary.rate * 100).toFixed(0)}%
            {denominator > 0 && `（${summary.paid}/${denominator}）`}
          </p>
        ) : (
          // 列表拉到了、统计没拉到：显示一排 0 会被读成「一条都没收」。
          <p className="text-xs text-amber-400">
            统计不可用（表格里的数据是好的）。共 {rows.length} 条。
          </p>
        )}
        <p className="text-xs text-slate-600">回收率不算已弃的伏笔。</p>
      </div>
      <div className="flex flex-wrap gap-2">
        {FILTERS.map((item) => (
          <button
            key={item.key}
            className={`rounded border px-3 py-1 text-sm ${
              filter === item.key
                ? 'border-indigo-500 bg-slate-800 text-white'
                : 'border-slate-700 text-slate-400 hover:bg-slate-900'
            }`}
            onClick={() => setFilter(item.key)}
          >
            {item.label}
          </button>
        ))}
      </div>
      <div className="overflow-x-auto rounded border border-slate-800">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-900 text-xs text-slate-400">
            <tr>
              <th className="px-3 py-2">名称</th>
              <th className="px-3 py-2">备注</th>
              <th className="px-3 py-2">埋设位置</th>
              <th className="px-3 py-2">计划回收位置</th>
              <th className="px-3 py-2">实际回收位置</th>
              <th className="px-3 py-2">状态</th>
              <th className="px-3 py-2">提示</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((row) => (
              <tr key={row.id} className="border-t border-slate-800 align-top">
                <td className="px-3 py-2 font-medium">{row.name}</td>
                <td className="px-3 py-2 text-slate-400">
                  <span
                    className="block max-w-[16rem] truncate"
                    title={row.note}
                  >
                    {row.note || '—'}
                  </span>
                </td>
                <td className="px-3 py-2">
                  <LocationCell location={row.plant} onSelect={onSelectScene} />
                </td>
                <td className="px-3 py-2">
                  <LocationCell location={row.pay} onSelect={onSelectScene} />
                </td>
                <td className="px-3 py-2">
                  <div className="space-y-1">
                    <LocationCell location={row.actualPay} onSelect={onSelectScene} />
                    {row.actualPay && (
                      <button
                        className="block text-xs text-slate-500 hover:text-red-300 hover:underline disabled:opacity-50"
                        disabled={busy || savingId !== ''}
                        onClick={() => void clearActualPay(row)}
                        title="回写助手可能匹配错了场景；清掉后状态会退回按埋设位置派生"
                      >
                        清掉实际回收
                      </button>
                    )}
                  </div>
                </td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-1">
                    <select
                      className="rounded border border-slate-700 bg-slate-900 px-1 py-0.5 text-xs text-slate-200 disabled:opacity-50"
                      value={row.effectiveStatus}
                      disabled={busy || savingId !== ''}
                      onChange={(event) => void changeStatus(row, event.target.value)}
                      title="作者显式设置的状态；位置字段与它不一致时会显示派生值"
                    >
                      {statuses.map((status) => (
                        <option key={status.key} value={status.key}>
                          {status.label}
                        </option>
                      ))}
                      {/* 词表没拉到时下拉会是一片空白；用服务端给的中文名兜底，
                          至少让作者看得出现在是什么状态（只是选不了）。 */}
                      {statuses.length === 0 && (
                        <option value={row.effectiveStatus}>{row.statusLabel}</option>
                      )}
                    </select>
                    {savingId === row.id && (
                      <span className="text-xs text-slate-500">保存中…</span>
                    )}
                    {/* 旧值那一行也「不等」，但那是词表归一、不是位置派生，
                        两个标记同时出现会让作者以为位置字段改过。 */}
                    {row.statusIsDerived && !row.statusIsLegacy && savingId !== row.id && (
                      <span
                        className="text-xs text-slate-500"
                        title={`作者设的状态是「${row.status}」，位置字段显示它已经走到这一步`}
                      >
                        派生
                      </span>
                    )}
                    {row.statusIsLegacy && (
                      <button
                        className="text-xs text-amber-400 hover:underline disabled:opacity-50"
                        disabled={busy || savingId !== ''}
                        onClick={() => void changeStatus(row, row.effectiveStatus)}
                        title="旧版本用的是「已确认」，它已归入「规划中」。点一下把库里的值改成「规划中」。"
                      >
                        旧值 · 点此更新
                      </button>
                    )}
                  </div>
                </td>
                <td className="px-3 py-2 text-xs text-amber-300">
                  {hints(row)}
                </td>
              </tr>
            ))}
            {visible.length === 0 && (
              <tr>
                <td
                  colSpan={7}
                  className="px-3 py-4 text-center text-sm text-slate-500"
                >
                  这个筛选下没有伏笔。
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-slate-500">
        状态可以从位置字段派生（埋了就是「已埋」、正文里收了就是「已收」），只有「已弃」是作者判断、
        不会被派生覆盖。实际回收由写作台「回写建议」经作者确认后写入。埋设与计划回收在结构设计的
        场景编辑器里改。
      </p>
    </div>
  )
}
