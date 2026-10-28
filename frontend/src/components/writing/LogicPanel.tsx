import type { AuditIssue, AuditResolution, LogicStage } from '../../api/client'
import { Button } from '../../ui/Button'

interface Props {
  stage: LogicStage
  issues: AuditIssue[]
  lastCheckedAt: string | null
  running: boolean
  warning: string
  canRun: boolean
  hasBody: boolean
  onStageChange: (stage: LogicStage) => void
  onRun: () => void
  onResolve: (issue: AuditIssue, resolution: AuditResolution) => void
}

const SEVERITY_STYLES: Record<string, string> = {
  critical: 'border-danger text-danger',
  major: 'border-warn text-warn',
  minor: 'border-line-strong text-ink-2',
}

const STAGE_LABELS: Record<LogicStage, string> = {
  plan: '场景卡',
  text: '正文',
}

export default function LogicPanel({
  stage,
  issues,
  lastCheckedAt,
  running,
  warning,
  canRun,
  hasBody,
  onStageChange,
  onRun,
  onResolve,
}: Props) {
  const runnable = canRun && (stage === 'plan' || hasBody)

  return (
    <section className="space-y-3 text-[13.5px]">
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-medium text-ink-2">逻辑自检</h3>
        <Button
          size="sm"
          disabled={running || !runnable}
          onClick={onRun}
          title={stage === 'text' && !hasBody ? '采纳正文后才能检查正文' : undefined}
        >
          {running ? '检查中…' : lastCheckedAt ? '重新检查' : '开始检查'}
        </Button>
      </div>

      <div className="flex gap-1">
        {(Object.keys(STAGE_LABELS) as LogicStage[]).map((value) => (
          <button
            key={value}
            type="button"
            disabled={running}
            onClick={() => onStageChange(value)}
            className={`rounded-control px-2 py-0.5 text-[11.5px] disabled:opacity-50 ${
              stage === value ? 'bg-accent-soft text-accent-ink' : 'text-muted hover:text-ink'
            }`}
          >
            {STAGE_LABELS[value]}
          </button>
        ))}
      </div>

      <p className="text-[11.5px] text-muted">
        {lastCheckedAt
          ? `上次检查（${STAGE_LABELS[stage]}）：${new Date(lastCheckedAt).toLocaleString()}`
          : `还没有对${STAGE_LABELS[stage]}做逻辑自检`}
      </p>

      {warning && (
        <p className="rounded-control border border-warn bg-warn-soft p-2 text-[11.5px] text-warn">
          {warning}
        </p>
      )}

      {stage === 'text' && !hasBody && (
        <p className="text-[13.5px] text-muted">采纳正文后才能对正文做逻辑自检。</p>
      )}

      {runnable && issues.length === 0 && !warning && lastCheckedAt && (
        <p className="text-[13.5px] text-muted">当前没有待处理问题。</p>
      )}

      <ul className="space-y-2">
        {issues.map((issue) => (
          <li key={issue.id} className="space-y-2 rounded-control border border-line p-2">
            <div className="flex flex-wrap items-center gap-1 text-[11.5px]">
              <span className="rounded-tag border border-line-strong px-1 text-muted">
                {issue.source_label}
              </span>
              <span
                className={`rounded-tag border px-1 ${
                  SEVERITY_STYLES[issue.severity] ?? SEVERITY_STYLES.minor
                }`}
              >
                {issue.severity_label}
              </span>
              <span className="text-muted">
                {issue.layer_label ?? issue.kind_label}
              </span>
            </div>

            {issue.quote && (
              <blockquote className="whitespace-pre-wrap break-words border-l-2 border-line-strong pl-2 text-ink-2">
                {issue.quote}
              </blockquote>
            )}
            {issue.rule_ref && (
              <p className="text-[11.5px] text-muted">冲突对象：{issue.rule_ref}</p>
            )}
            <p className="text-ink-2">{issue.explanation}</p>
            {issue.reader_impact && (
              <p className="text-[11.5px] text-muted">读者观感：{issue.reader_impact}</p>
            )}
            {issue.options.length > 0 && (
              <ul className="list-inside list-disc text-[11.5px] text-muted">
                {issue.options.map((option, index) => (
                  <li key={index}>{option}</li>
                ))}
              </ul>
            )}

            <div className="flex flex-wrap gap-1">
              <Button
                size="sm"
                disabled={running}
                onClick={() => onResolve(issue, 'story')}
              >
                改故事
              </Button>
              <Button
                size="sm"
                disabled={running}
                onClick={() => onResolve(issue, 'setting')}
              >
                改设定
              </Button>
              <Button
                size="sm"
                disabled={running}
                onClick={() => onResolve(issue, 'character')}
              >
                改人物
              </Button>
              <Button
                size="sm"
                disabled={running}
                onClick={() => onResolve(issue, 'exception')}
              >
                接受为特例
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
