import type { SettingLoadData } from '../../api/client'
import { COL_W, buildLoadSeries } from '../../lib/settingLoad'
import { CHART } from '../../ui/chartTokens'

// 版式：顶部留给图例，中间是绘图区，底部一行章标签。
const PAD_X = 16
const TOP = 24
const PLOT_H = 120
const AXIS_H = 30

// 用色一律从 `ui/chartTokens` 取。这一张的两条序列**并置在同一绘图区**里
// （柱与折线重叠），所以必须用两种不同的色相：柱走主序列，密度线走次序列。

/** x 轴标签只放得下几个字：长标题截断，全文进悬停提示。 */
function shortLabel(label: string): string {
  return label.length > 6 ? `${label.slice(0, 5)}…` : label
}

export default function SettingLoadCurve({
  data,
  loading,
  error,
  onSelectChapter,
}: {
  data: SettingLoadData | null
  loading: boolean
  error: string
  onSelectChapter: (id: string) => void
}) {
  if (error) {
    return (
      <p className="rounded-card border-l-2 border-danger bg-surface p-4 text-[13.5px] text-danger">
        读取设定投放失败：{error}
      </p>
    )
  }
  if (loading || !data) {
    return (
      <p className="rounded-card border border-line bg-surface p-4 text-[13.5px] text-muted">
        正在统计设定投放…
      </p>
    )
  }

  const series = buildLoadSeries(data)
  const { totals } = data

  if (series.chapters.length === 0) {
    return (
      <p className="rounded-card border border-line bg-surface p-4 text-[13.5px] text-muted">
        {data.reason || '还没有卷章。去「结构设计」建卷，或先用 AI 排卷章。'}
      </p>
    )
  }

  const width = PAD_X * 2 + series.chapters.length * COL_W
  const baseline = TOP + PLOT_H
  const height = baseline + AXIS_H
  // 每列的横向中心：柱、折线点与点击区共用。
  const centerX = (index: number) => PAD_X + index * COL_W + COL_W / 2
  const barWidth = COL_W * 0.5
  const plotInner = PLOT_H - 12
  // 有值就必须看得见：占比极小的柱给 3px 下限，免得被当成「这一章没有新设定」。
  const barHeight = (value: number) =>
    value > 0 ? Math.max(3, (value / series.maxNew) * plotInner) : 0
  const barPath = (center: number, value: number) => {
    const h = barHeight(value)
    if (h <= 0) return ''
    const left = center - barWidth / 2
    const right = center + barWidth / 2
    const top = baseline - h
    const radius = Math.min(4, h, barWidth / 2)
    return [
      `M${left} ${baseline}`,
      `V${top + radius}`,
      `Q${left} ${top} ${left + radius} ${top}`,
      `H${right - radius}`,
      `Q${right} ${top} ${right} ${top + radius}`,
      `V${baseline}`,
      'Z',
    ].join(' ')
  }
  const densityY = (value: number) =>
    baseline - (Math.max(0, value) / series.maxDensity) * plotInner
  // 没写正文的章把折线断开：那时密度是 0 而不是「投放为零」，连过去会撒谎。
  let densityPath = ''
  series.chapters.forEach((chapter, index) => {
    if (!chapter.hasBody) return
    densityPath += `${densityPath ? 'L' : 'M'}${centerX(index)} ${densityY(
      chapter.density,
    )} `
  })

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-baseline gap-3">
        <h3 className="text-[14px] font-semibold text-ink">设定投放</h3>
        <span className="text-[11.5px] text-muted">
          {totals.entries} 个条目 · 已投放 {totals.delivered} · 从未出现{' '}
          {totals.never_seen} · {totals.ambiguities} 处重名
        </span>
        <span className="text-[11.5px] text-faint">点章回到结构设计并选中该章</span>
      </div>

      {data.reason && (
        <p className="rounded-control bg-warn-soft p-3 text-[13.5px] text-warn">
          {data.reason}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-4 text-[11.5px] text-muted">
        <span className="flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className="inline-block h-2.5 w-2.5 rounded-sm"
            style={{ background: CHART.series }}
          />
          每章新设定数
        </span>
        <span className="flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className="inline-block h-0.5 w-3.5"
            style={{ background: CHART.seriesAlt }}
          />
          每千字提及密度
        </span>
        <span className="flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className="inline-block h-2.5 w-2.5 rounded-sm border border-dashed border-line-strong"
          />
          未写正文
        </span>
      </div>

      <div className="overflow-x-auto rounded-card border border-line bg-surface p-3">
        <svg width={width} height={height} role="img" aria-label="设定投放曲线">
          <line
            x1={PAD_X}
            x2={width - PAD_X}
            y1={baseline}
            y2={baseline}
            stroke={CHART.grid}
          />
          {series.chapters.map((chapter, index) =>
            chapter.hasBody ? null : (
              <g key={`empty-${chapter.id}`}>
                <rect
                  x={PAD_X + index * COL_W + 6}
                  y={TOP}
                  width={COL_W - 12}
                  height={PLOT_H}
                  fill={CHART.placeholder}
                  stroke={CHART.placeholderStroke}
                  strokeDasharray="4 4"
                  opacity={0.7}
                />
                <text
                  x={centerX(index)}
                  y={TOP + PLOT_H / 2}
                  transform={`rotate(-90 ${centerX(index)} ${TOP + PLOT_H / 2})`}
                  textAnchor="middle"
                  fill={CHART.axisTick}
                  fontSize={10}
                >
                  未写
                </text>
              </g>
            ),
          )}
          {series.chapters.map((chapter, index) =>
            chapter.hasBody && chapter.newCount > 0 ? (
              <path
                key={`bar-${chapter.id}`}
                d={barPath(centerX(index), chapter.newCount)}
                fill={CHART.series}
                opacity={0.85}
              />
            ) : null,
          )}
          {densityPath.trim() && (
            <path
              d={densityPath.trim()}
              fill="none"
              stroke={CHART.seriesAlt}
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}
          {series.chapters.map((chapter, index) =>
            chapter.hasBody ? (
              <circle
                key={`dot-${chapter.id}`}
                cx={centerX(index)}
                cy={densityY(chapter.density)}
                r={3.5}
                fill={CHART.seriesAlt}
                stroke={CHART.pointStroke}
                strokeWidth={2}
              />
            ) : null,
          )}
          {series.chapters.map((chapter, index) => (
            <text
              key={`label-${chapter.id}`}
              x={centerX(index)}
              y={height - 8}
              textAnchor="middle"
              fill={CHART.axisTick}
              fontSize={9}
            >
              {shortLabel(chapter.label)}
            </text>
          ))}
          {series.chapters.map((chapter, index) => (
            <rect
              key={`hit-${chapter.id}`}
              x={PAD_X + index * COL_W}
              y={TOP - 8}
              width={COL_W}
              height={PLOT_H + 8}
              fill="transparent"
              role="button"
              tabIndex={0}
              aria-label={chapter.label}
              className="cursor-pointer outline-none focus:fill-accent-soft"
              onClick={() => onSelectChapter(chapter.id)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault()
                  onSelectChapter(chapter.id)
                }
              }}
            >
              <title>
                {chapter.hasBody
                  ? `${chapter.label}（${chapter.volumeLabel}）\n新 ${
                      chapter.newCount
                    } / 提及 ${chapter.mentions} / ${chapter.chars} 字`
                  : `${chapter.label}（${chapter.volumeLabel}）\n未写正文`}
              </title>
            </rect>
          ))}
        </svg>
      </div>
    </div>
  )
}
