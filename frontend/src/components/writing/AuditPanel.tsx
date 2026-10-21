import type { AuditIssue, AuditResolution } from '../../api/client'

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
  critical: 'border-red-900 text-red-300',
  major: 'border-amber-900 text-amber-300',
  minor: 'border-slate-700 text-slate-300',
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
    <section className="space-y-3 text-sm">
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-medium text-slate-300">一致性审计</h3>
        <button
          type="button"
          disabled={running || !canRun}
          onClick={onRun}
          className="rounded border border-slate-700 px-2 py-1 text-xs text-slate-300 hover:text-white disabled:opacity-50"
          title={hasBody ? undefined : '采纳正文后才能审校'}
        >
          {running ? '审校中…' : lastAuditedAt ? '重新审校' : '审校'}
        </button>
      </div>
      <p className="text-xs text-slate-500">
        {lastAuditedAt ? `上次审校：${new Date(lastAuditedAt).toLocaleString()}` : '还没有审校'}
      </p>

      {warning && (
        <p className="rounded border border-amber-900 bg-amber-950/40 p-2 text-xs text-amber-300">
          {warning}
        </p>
      )}

      {!hasBody && <p className="text-sm text-slate-500">采纳正文后可审校。</p>}

      {hasBody && issues.length === 0 && !warning && lastAuditedAt && (
        <p className="text-sm text-slate-500">当前没有待处理问题。</p>
      )}

      <ul className="space-y-2">
        {issues.map((issue) => (
          <li key={issue.id} className="space-y-2 rounded border border-slate-800 p-2">
            <div className="flex flex-wrap items-center gap-1 text-xs">
              <span className="rounded border border-slate-700 px-1 text-slate-400">
                {issue.source_label}
              </span>
              <span
                className={`rounded border px-1 ${
                  SEVERITY_STYLES[issue.severity] ?? SEVERITY_STYLES.minor
                }`}
              >
                {issue.severity_label}
              </span>
              <span className="text-slate-400">
                {issue.layer_label ?? issue.kind_label}
              </span>
            </div>

            {issue.quote && (
              <blockquote className="whitespace-pre-wrap break-words border-l-2 border-slate-700 pl-2 text-slate-300">
                {issue.quote}
              </blockquote>
            )}
            {issue.rule_ref && (
              <p className="text-xs text-slate-400">冲突对象：{issue.rule_ref}</p>
            )}
            <p className="text-slate-300">{issue.explanation}</p>
            {issue.reader_impact && (
              <p className="text-xs text-slate-500">读者观感：{issue.reader_impact}</p>
            )}
            {issue.options.length > 0 && (
              <ul className="list-inside list-disc text-xs text-slate-400">
                {issue.options.map((option, index) => (
                  <li key={index}>{option}</li>
                ))}
              </ul>
            )}

            <div className="flex flex-wrap gap-1">
              <button
                type="button"
                disabled={running}
                onClick={() => onResolve(issue, 'story')}
                className="rounded border border-slate-700 px-2 py-0.5 text-xs text-slate-400 hover:text-white disabled:opacity-50"
              >
                改故事
              </button>
              <button
                type="button"
                disabled={running}
                onClick={() => onResolve(issue, 'setting')}
                className="rounded border border-slate-700 px-2 py-0.5 text-xs text-slate-400 hover:text-white disabled:opacity-50"
              >
                改设定
              </button>
              <button
                type="button"
                disabled={running}
                onClick={() => onResolve(issue, 'character')}
                className="rounded border border-slate-700 px-2 py-0.5 text-xs text-slate-400 hover:text-white disabled:opacity-50"
              >
                改人物
              </button>
              <button
                type="button"
                disabled={running}
                onClick={() => onResolve(issue, 'exception')}
                className="rounded border border-slate-700 px-2 py-0.5 text-xs text-slate-400 hover:text-white disabled:opacity-50"
              >
                接受为特例
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
