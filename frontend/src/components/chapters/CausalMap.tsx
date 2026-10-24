import type { CausalIssue, CausalMapData } from '../../api/client'
import {
  NODE_GAP,
  NODE_WIDTH,
  ROW_HEIGHT,
  buildCausalRows,
  summarize,
} from '../../lib/causalMap'

// 节点盒子的高度：ROW_HEIGHT 里剩下的留给节点底下的断点小字。
const NODE_HEIGHT = 92

const BREAK_LABELS: Record<string, string> = {
  missing_goal: '缺目标',
  missing_turn: '缺转折',
}

function textOrEmpty(value: string): string {
  return value.trim() ? value : '（空）'
}

/** 问题标题可能是一整句（`explanation`）：全文进悬停提示，界面不截断。 */
function issueTooltip(issues: CausalIssue[]): string {
  return issues.map((issue) => issue.title).join('\n')
}

export default function CausalMap({
  data,
  loading,
  error,
  logicChecked,
  onSelectScene,
}: {
  data: CausalMapData | null
  loading: boolean
  error: string
  logicChecked: boolean
  onSelectScene: (id: string) => void
}) {
  if (error) {
    return (
      <p className="rounded border border-rose-900/60 bg-rose-950/20 p-4 text-sm text-rose-300">
        读取因果链失败：{error}
      </p>
    )
  }
  if (loading || !data) {
    return (
      <p className="rounded border border-slate-800 p-4 text-sm text-slate-500">
        正在读取因果链…
      </p>
    )
  }

  const { rows } = buildCausalRows(data)
  const summary = summarize(data)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline gap-3">
        <h3 className="text-sm font-medium text-slate-300">因果链</h3>
        <span className="text-xs text-slate-500">
          {summary.scenes} 场 · {summary.breaks} 个断点
        </span>
        <span className="text-xs text-slate-600">{summary.chapters} 章</span>
        <span className="text-xs text-slate-600">点节点回到结构设计并选中该场</span>
      </div>

      {logicChecked === false && (
        <p className="rounded border border-amber-900/60 bg-amber-950/30 p-3 text-sm text-amber-300">
          还没跑过逻辑自检，图里只标结构断点
        </p>
      )}

      {rows.length === 0 ? (
        <p className="rounded border border-slate-800 p-4 text-sm text-slate-500">
          还没有章节结构。去「结构设计」建卷，或先用 AI 排卷章。
        </p>
      ) : (
        rows.map((row) => (
          <section key={row.chapter.id} className="space-y-2">
            <div className="flex flex-wrap items-baseline gap-2">
              <span className="text-xs text-slate-500">{row.chapter.volume_label}</span>
              <span className="text-sm text-slate-200">{row.chapter.label}</span>
              <span className="text-xs text-slate-600">{row.nodes.length} 场</span>
            </div>

            {row.nodes.length === 0 ? (
              <p className="rounded border border-slate-800 p-3 text-sm text-slate-500">
                这一章还没有场景卡
              </p>
            ) : (
              <div className="overflow-x-auto rounded border border-slate-800 bg-slate-950/40 p-3">
                <div
                  className="relative"
                  style={{ width: row.width, height: ROW_HEIGHT }}
                >
                  {row.nodes.map((node, index) =>
                    index === 0 ? null : (
                      <span
                        key={`arrow-${node.id}`}
                        aria-hidden="true"
                        className="absolute top-8 text-center text-sm text-slate-600"
                        style={{ left: node.x - NODE_GAP, width: NODE_GAP }}
                      >
                        →
                      </span>
                    ),
                  )}
                  {row.nodes.map((node) => {
                    const structural = node.breaks.filter(
                      (item) => item === 'missing_goal' || item === 'missing_turn',
                    )
                    const hasIssue = node.breaks.includes('causality_issue')
                    return (
                      <div key={node.id}>
                        <button
                          type="button"
                          onClick={() => onSelectScene(node.id)}
                          title={`${node.label}
目标：${textOrEmpty(node.goal)}
转折：${textOrEmpty(node.turn)}`}
                          className={`absolute top-0 flex flex-col gap-0.5 rounded border border-slate-700 bg-slate-900 px-2.5 py-2 text-left text-xs text-slate-300 outline-none hover:border-slate-500 focus:ring-2 focus:ring-indigo-500 ${
                            structural.length > 0
                              ? 'border-l-4 border-l-amber-500'
                              : ''
                          }`}
                          style={{ left: node.x, width: NODE_WIDTH, height: NODE_HEIGHT }}
                        >
                          <span className="flex items-center justify-between gap-1">
                            <span className="truncate font-medium text-slate-200">
                              {node.label}
                            </span>
                            <span className="flex shrink-0 items-center gap-1">
                              {node.locked && (
                                <span title="已锁定" aria-label="已锁定">
                                  🔒
                                </span>
                              )}
                              {hasIssue && (
                                <span
                                  className="h-2 w-2 rounded-full bg-rose-500"
                                  title={issueTooltip(node.issues)}
                                />
                              )}
                            </span>
                          </span>
                          <span className="block truncate">
                            <span className="text-slate-500">目标：</span>
                            {textOrEmpty(node.goal)}
                          </span>
                          <span className="block truncate">
                            <span className="text-slate-500">转折：</span>
                            {textOrEmpty(node.turn)}
                          </span>
                        </button>
                        {(structural.length > 0 || hasIssue) && (
                          <span
                            className="absolute text-[11px] leading-4 text-amber-400"
                            style={{
                              left: node.x,
                              top: NODE_HEIGHT + 4,
                              width: NODE_WIDTH,
                            }}
                          >
                            {structural.length > 0 &&
                              structural
                                .map((item) => BREAK_LABELS[item] ?? item)
                                .join(' · ')}
                            {structural.length > 0 && hasIssue && ' · '}
                            {hasIssue && (
                              <span className="text-rose-400">因果问题</span>
                            )}
                          </span>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </section>
        ))
      )}
    </div>
  )
}
