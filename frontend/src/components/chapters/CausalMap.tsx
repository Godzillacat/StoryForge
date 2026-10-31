import type { CausalIssue, CausalMapData } from '../../api/client'
import {
  NODE_GAP,
  NODE_WIDTH,
  ROW_HEIGHT,
  buildCausalRows,
  summarize,
} from '../../lib/causalMap'
import { Icon } from '../../ui/icons'

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
      <p className="rounded-card border-l-2 border-danger bg-surface p-4 text-[13.5px] text-danger">
        读取因果链失败：{error}
      </p>
    )
  }
  if (loading || !data) {
    return (
      <p className="rounded-card border border-line bg-surface p-4 text-[13.5px] text-muted">
        正在读取因果链…
      </p>
    )
  }

  const { rows } = buildCausalRows(data)
  const summary = summarize(data)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline gap-3">
        <h3 className="text-[14px] font-semibold text-ink">因果链</h3>
        <span className="text-[11.5px] text-muted">
          {summary.scenes} 场 · {summary.breaks} 个断点
        </span>
        <span className="text-[11.5px] text-faint">{summary.chapters} 章</span>
        <span className="text-[11.5px] text-faint">点节点回到结构设计并选中该场</span>
      </div>

      {logicChecked === false && (
        <p className="rounded-control bg-warn-soft p-3 text-[13.5px] text-warn">
          还没跑过逻辑自检，图里只标结构断点
        </p>
      )}

      {rows.length === 0 ? (
        <p className="rounded-card border border-line bg-surface p-4 text-[13.5px] text-muted">
          还没有章节结构。去「结构设计」建卷，或先用 AI 排卷章。
        </p>
      ) : (
        rows.map((row) => (
          <section key={row.chapter.id} className="space-y-2">
            <div className="flex flex-wrap items-baseline gap-2">
              <span className="text-[11.5px] text-muted">{row.chapter.volume_label}</span>
              <span className="text-[13.5px] text-ink-2">{row.chapter.label}</span>
              <span className="text-[11.5px] text-faint">{row.nodes.length} 场</span>
            </div>

            {row.nodes.length === 0 ? (
              <p className="rounded-card border border-line bg-surface p-3 text-[13.5px] text-muted">
                这一章还没有场景卡
              </p>
            ) : (
              <div className="overflow-x-auto rounded-card border border-line bg-surface p-3">
                <div
                  className="relative"
                  style={{ width: row.width, height: ROW_HEIGHT }}
                >
                  {row.nodes.map((node, index) =>
                    index === 0 ? null : (
                      <span
                        key={`arrow-${node.id}`}
                        aria-hidden="true"
                        className="absolute top-8 text-center text-[13.5px] text-faint"
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
                          className={`absolute top-0 flex flex-col gap-0.5 rounded-control border border-line-strong bg-surface px-2.5 py-2 text-left text-[11.5px] text-ink-2 outline-none transition-colors duration-[120ms] hover:border-accent focus:ring-2 focus:ring-accent-soft ${
                            structural.length > 0
                              ? 'border-l-4 border-l-warn'
                              : ''
                          }`}
                          style={{ left: node.x, width: NODE_WIDTH, height: NODE_HEIGHT }}
                        >
                          <span className="flex items-center justify-between gap-1">
                            <span className="truncate font-medium text-ink">
                              {node.label}
                            </span>
                            <span className="flex shrink-0 items-center gap-1">
                              {node.locked && (
                                <span className="text-warn" title="已锁定" aria-label="已锁定">
                                  <Icon name="lock" size={12} />
                                </span>
                              )}
                              {hasIssue && (
                                <span
                                  className="h-2 w-2 rounded-full bg-danger"
                                  title={issueTooltip(node.issues)}
                                />
                              )}
                            </span>
                          </span>
                          <span className="block truncate">
                            <span className="text-muted">目标：</span>
                            {textOrEmpty(node.goal)}
                          </span>
                          <span className="block truncate">
                            <span className="text-muted">转折：</span>
                            {textOrEmpty(node.turn)}
                          </span>
                        </button>
                        {(structural.length > 0 || hasIssue) && (
                          <span
                            className="absolute text-[11px] leading-4 text-warn"
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
                              <span className="text-danger">因果问题</span>
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
