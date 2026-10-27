import type { VolumeNode } from '../../api/client'
import { buildRhythmSeries } from '../../lib/chapterViews'
import { CHART } from '../../ui/chartTokens'

const COL_WIDTH = 44
const LABEL_WIDTH = 88
const RIGHT_PAD = 16
const TOP = 32
const ROW_HEIGHT = 88
const ROW_GAP = 12
const DIALOGUE_HEIGHT = 64

// 用色一律从 `ui/chartTokens` 取，这里不再写裸十六进制。
// 四行是各自独立的小图、左侧各有文字标签，**颜色不承担区分职责** —— 所以
// 冲突与对话同用主序列色；「钩子」沿用虚线这一层级编码（原先靠 emerald 与
// amber 两种颜色区分，而那两个色的 CVD 差正落在警告带里）。

export default function RhythmCurve({
  volumes,
  onSelectChapter,
}: {
  volumes: VolumeNode[]
  onSelectChapter: (id: string) => void
}) {
  const series = buildRhythmSeries(volumes)
  if (series.chapters.length === 0) {
    return (
      <p className="rounded-card border border-line bg-surface p-4 text-[13.5px] text-muted">
        还没有卷章。去「结构设计」建卷，或先用 AI 排卷章。
      </p>
    )
  }

  const width = LABEL_WIDTH + series.chapters.length * COL_WIDTH + RIGHT_PAD
  const targetTop = TOP
  const targetBottom = targetTop + ROW_HEIGHT
  const conflictTop = targetBottom + ROW_GAP
  const conflictBottom = conflictTop + ROW_HEIGHT
  const hookTop = conflictBottom + ROW_GAP
  const hookBottom = hookTop + ROW_HEIGHT
  const dialogueTop = hookBottom + ROW_GAP
  const dialogueBottom = dialogueTop + DIALOGUE_HEIGHT
  const height = dialogueBottom + 28
  const x = (index: number) => LABEL_WIDTH + index * COL_WIDTH + COL_WIDTH / 2
  const levelY = (value: number, top: number, bottom: number) =>
    bottom - 8 - ((value - 1) / 4) * (bottom - top - 16)
  const ratioY = (value: number) =>
    dialogueBottom - 8 - value * (DIALOGUE_HEIGHT - 16)
  const path = (
    values: (number | null)[],
    yFor: (value: number) => number,
  ) => {
    let result = ''
    let open = false
    values.forEach((value, index) => {
      if (value == null) {
        open = false
        return
      }
      result += `${open ? 'L' : 'M'}${x(index)} ${yFor(value)} `
      open = true
    })
    return result.trim()
  }
  const hasAny = series.chapters.some(
    (chapter) =>
      chapter.targetWords != null ||
      chapter.conflict != null ||
      chapter.dialogue != null ||
      chapter.hook != null,
  )
  const barWidth = COL_WIDTH * 0.5
  const barPath = (index: number, value: number) => {
    const left = x(index) - barWidth / 2
    const right = left + barWidth
    const bottom = targetBottom - 8
    const barHeight = (value / series.maxTargetWords) * (ROW_HEIGHT - 16)
    const top = bottom - barHeight
    const radius = Math.min(4, barHeight, barWidth / 2)
    return [
      `M${left} ${bottom}`,
      `V${top + radius}`,
      `Q${left} ${top} ${left + radius} ${top}`,
      `H${right - radius}`,
      `Q${right} ${top} ${right} ${top + radius}`,
      `V${bottom}`,
      'Z',
    ].join(' ')
  }
  const conflictValues = series.chapters.map((chapter) => chapter.conflict)
  const hookValues = series.chapters.map((chapter) => chapter.hook)
  const dialogueValues = series.chapters.map((chapter) => chapter.dialogue)
  const volumeOpacity = (index: number) => (index % 2 === 0 ? 0.55 : 0.2)

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-[14px] font-semibold text-ink">节奏曲线</h3>
        <p className="text-[11.5px] text-muted">
          目标字数（P1 尚无正文，不是实际字数）· 点任意一章可回到结构设计
        </p>
      </div>
      {!hasAny && (
        <p className="rounded-control bg-warn-soft p-3 text-[13.5px] text-warn">
          章还没填节奏指标，去结构设计里补。
        </p>
      )}
      <p className="text-[11.5px] text-muted">
        冲突未评 {series.missing.conflict} 章 · 钩子未评 {series.missing.hook} 章 ·
        对话未评 {series.missing.dialogue} 章 · 目标字数未填{' '}
        {series.missing.targetWords} 章
      </p>
      <div className="overflow-x-auto rounded-card border border-line bg-surface p-3">
        <svg width={width} height={height} role="img" aria-label="节奏曲线">
          {series.bands.map((band, index) =>
            band.end > band.start ? (
              <g key={band.id}>
                <rect
                  x={LABEL_WIDTH + band.start * COL_WIDTH}
                  y={TOP - 8}
                  width={(band.end - band.start) * COL_WIDTH}
                  height={dialogueBottom - TOP + 8}
                  fill={CHART.band}
                  opacity={volumeOpacity(index)}
                />
                <text
                  x={LABEL_WIDTH + ((band.start + band.end) / 2) * COL_WIDTH}
                  y={TOP - 14}
                  textAnchor="middle"
                  fill={CHART.axisLabel}
                  fontSize={11}
                >
                  {band.name}
                </text>
              </g>
            ) : null,
          )}
          {[targetTop, conflictTop, hookTop, dialogueTop].map((top) => (
            <line
              key={top}
              x1={LABEL_WIDTH}
              x2={width - RIGHT_PAD}
              y1={top}
              y2={top}
              stroke={CHART.grid}
            />
          ))}
          <text x={0} y={targetTop + 16} fill={CHART.axisLabel} fontSize={11}>
            目标字数
          </text>
          <text x={0} y={conflictTop + 16} fill={CHART.axisLabel} fontSize={11}>
            冲突强度
          </text>
          <text x={0} y={hookTop + 16} fill={CHART.axisLabel} fontSize={11}>
            钩子强度
          </text>
          <text x={0} y={dialogueTop + 16} fill={CHART.axisLabel} fontSize={11}>
            对话占比
          </text>
          {[1, 3, 5].map((level) => (
            <g key={`grid-${level}`}>
              <line
                x1={LABEL_WIDTH}
                x2={width - RIGHT_PAD}
                y1={levelY(level, conflictTop, conflictBottom)}
                y2={levelY(level, conflictTop, conflictBottom)}
                stroke={CHART.grid}
                opacity={0.6}
              />
              <line
                x1={LABEL_WIDTH}
                x2={width - RIGHT_PAD}
                y1={levelY(level, hookTop, hookBottom)}
                y2={levelY(level, hookTop, hookBottom)}
                stroke={CHART.grid}
                opacity={0.6}
              />
            </g>
          ))}
          {series.chapters.map((chapter, index) =>
            chapter.targetWords == null ? null : (
              <path
                key={`bar-${chapter.id}`}
                d={barPath(index, chapter.targetWords)}
                fill={CHART.series}
                opacity={0.8}
              />
            ),
          )}
          <path
            d={path(conflictValues, (value) =>
              levelY(value, conflictTop, conflictBottom),
            )}
            fill="none"
            stroke={CHART.series}
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d={path(hookValues, (value) =>
              levelY(value, hookTop, hookBottom),
            )}
            fill="none"
            stroke={CHART.dashed}
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeDasharray="5 4"
          />
          <path
            d={path(dialogueValues, ratioY)}
            fill="none"
            stroke={CHART.series}
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          {series.chapters.map((chapter, index) => (
            <g key={`dots-${chapter.id}`}>
              {chapter.conflict != null && (
                <circle
                  cx={x(index)}
                  cy={levelY(chapter.conflict, conflictTop, conflictBottom)}
                  r={4}
                  fill={CHART.series}
                  stroke={CHART.pointStroke}
                  strokeWidth={2}
                />
              )}
              {chapter.hook != null && (
                <circle
                  cx={x(index)}
                  cy={levelY(chapter.hook, hookTop, hookBottom)}
                  r={4}
                  fill={CHART.dashed}
                  stroke={CHART.pointStroke}
                  strokeWidth={2}
                />
              )}
              {chapter.dialogue != null && (
                <circle
                  cx={x(index)}
                  cy={ratioY(chapter.dialogue)}
                  r={4}
                  fill={CHART.series}
                  stroke={CHART.pointStroke}
                  strokeWidth={2}
                />
              )}
            </g>
          ))}
          {series.chapters.map((chapter, index) => (
            <text
              key={`x-${chapter.id}`}
              x={x(index)}
              y={height - 8}
              textAnchor="middle"
              fill={CHART.axisTick}
              fontSize={10}
            >
              {chapter.chapterSeq + 1}
            </text>
          ))}
          {series.chapters.map((chapter, index) => (
            <rect
              key={`hit-${chapter.id}`}
              x={LABEL_WIDTH + index * COL_WIDTH}
              y={TOP - 8}
              width={COL_WIDTH}
              height={dialogueBottom - TOP + 8}
              fill="transparent"
              role="button"
              tabIndex={0}
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
                {`${chapter.label}（${chapter.volumeName}）
目标字数：${chapter.targetWords ?? '未填'}
冲突：${chapter.conflict ?? '未评'} · 钩子：${chapter.hook ?? '未评'} · 对话占比：${
                  chapter.dialogue == null
                    ? '未评'
                    : `${Math.round(chapter.dialogue * 100)}%`
                }
推进线：${chapter.lines.join('、') || '未填'}`}
              </title>
            </rect>
          ))}
        </svg>
      </div>
    </div>
  )
}
