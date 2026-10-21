import { useState } from 'react'
import type {
  ChapterStatusOption,
  Foreshadow,
  VolumeNode,
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
]

function hints(row: LedgerRow): string {
  const out: string[] = []
  if (row.missingPlant) out.push('缺埋设')
  if (row.missingPay) out.push('缺计划回收')
  if (row.actualPay) out.push('已回收')
  else if (!row.missingPay) out.push('已计划、未回收')
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
  onSelectScene,
}: {
  volumes: VolumeNode[]
  foreshadows: Foreshadow[]
  statuses: ChapterStatusOption[]
  onSelectScene: (id: string) => void
}) {
  const [filter, setFilter] = useState<LedgerFilter>('all')
  const rows = buildForeshadowLedger(volumes, foreshadows)
  if (foreshadows.length === 0) {
    return (
      <p className="rounded border border-slate-800 p-4 text-sm text-slate-500">
        还没有伏笔。在结构设计的场景编辑器里挂上伏笔后，这里会按故事顺序列出。
      </p>
    )
  }
  const visible = filterLedger(rows, filter)
  const labelByKey = new Map(
    statuses.map((status): [string, string] => [status.key, status.label]),
  )
  const missingPlant = rows.filter((row) => row.missingPlant).length
  const missingPay = rows.filter((row) => row.missingPay).length
  const unpaid = rows.filter((row) => row.unpaid).length

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-sm font-medium text-slate-300">伏笔账本</h3>
        <p className="text-xs text-slate-500">
          共 {rows.length} 条 · 缺埋设 {missingPlant} · 缺计划回收 {missingPay} · 未回收{' '}
          {unpaid}
        </p>
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
              <th className="px-3 py-2">规划状态</th>
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
                  <LocationCell location={row.actualPay} onSelect={onSelectScene} />
                </td>
                <td className="px-3 py-2 text-slate-400">
                  {labelByKey.get(row.status) ?? row.status}
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
        规划状态只有「规划中 / 已确认」。实际回收由写作台「回写建议」经作者确认后写入，
        不改规划状态；生命周期状态属 P4。本页只读，埋设与计划回收在结构设计的场景编辑器里改。
      </p>
    </div>
  )
}
