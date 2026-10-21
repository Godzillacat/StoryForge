import type { AuditIssue, AuditResolution, LogicStage } from '../../api/client'

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
  critical: 'border-red-900 text-red-300',
  major: 'border-amber-900 text-amber-300',
  minor: 'border-slate-700 text-slate-300',
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
    <section className="space-y-3 text-sm">
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-medium text-slate-300">逻辑自检</h3>
        <button
          type="button"
          disabled={running || !runnable}
          onClick={onRun}
          title={stage === 'text' && !hasBody ? '采纳正文后才能检查正文' : undefined}
          className="rounded border border-slate-700 px-2 py-1 text-xs text-slate-300 hover:text-white disabled:opacity-50"
        >
          {running ? '检查中…' : lastCheckedAt ? '重新检查' : '开始检查'}
        </button>
      </div>

      <div className="flex gap-1">
        {(Object.keys(STAGE_LABELS) as LogicStage[]).map((value) => (
          <button
            key={value}
            type="button"
            disabled={running}
            onClick={() => onStageChange(value)}
            className={`rounded px-2 py-0.5 text-xs disabled:opacity-50 ${
              stage === value ? 'bg-slate-800 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            {STAGE_LABELS[value]}
          </button>
        ))}
      </div>

      <p className="text-xs text-slate-500">
        {lastCheckedAt
          ? `上次检查（${STAGE_LABELS[stage]}）：${new Date(lastCheckedAt).toLocaleString()}`
          : `还没有对${STAGE_LABELS[stage]}做逻辑自检`}
      </p>

      {warning && (
        <p className="rounded border border-amber-900 bg-amber-950/40 p-2 text-xs text-amber-300">
          {warning}
        </p>
      )}

      {stage === 'text' && !hasBody && (
        <p className="text-sm text-slate-500">采纳正文后才能对正文做逻辑自检。</p>
      )}

      {runnable && issues.length === 0 && !warning && lastCheckedAt && (
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
