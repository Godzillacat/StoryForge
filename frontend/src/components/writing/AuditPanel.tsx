import type { AuditIssue, AuditResolution } from '../../api/client'
import { Button } from '../../ui/Button'

interface Props {
  issues: AuditIssue[]
  lastAuditedAt: string | null
  running: boolean
  warning: string
  canRun: boolean
  hasBody: boolean
  onRun: () => void
  onResolve: (issue: AuditIssue, resolution: AuditResolution) => void
}

const SEVERITY_STYLES: Record<string, string> = {
  critical: 'border-danger text-danger',
  major: 'border-warn text-warn',
  minor: 'border-line-strong text-ink-2',
}

export default function AuditPanel({
  issues,
  lastAuditedAt,
  running,
  warning,
  canRun,
  hasBody,
  onRun,
  onResolve,
}: Props) {
  return (
    <section className="space-y-3 text-[13.5px]">
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-medium text-ink-2">一致性审计</h3>
        <Button
          size="sm"
          disabled={running || !canRun}
          onClick={onRun}
          title={hasBody ? undefined : '采纳正文后才能审校'}
        >
          {running ? '审校中…' : lastAuditedAt ? '重新审校' : '审校'}
        </Button>
      </div>
      <p className="text-[11.5px] text-muted">
        {lastAuditedAt ? `上次审校：${new Date(lastAuditedAt).toLocaleString()}` : '还没有审校'}
      </p>

      {warning && (
        <p className="rounded-control border border-warn bg-warn-soft p-2 text-[11.5px] text-warn">
          {warning}
        </p>
      )}

      {!hasBody && <p className="text-[13.5px] text-muted">采纳正文后可审校。</p>}

      {hasBody && issues.length === 0 && !warning && lastAuditedAt && (
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
