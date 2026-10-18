import type { ContextPreview as ContextPreviewData } from '../../api/client'

interface Props {
  data: ContextPreviewData | null
  loading: boolean
  error: string
}

export default function ContextPreview({ data, loading, error }: Props) {
  if (loading) {
    return <p className="text-sm text-slate-500">正在准备上下文…</p>
  }
  if (error) {
    return <p className="rounded border border-amber-900 bg-amber-950/40 p-2 text-sm text-amber-300">{error}</p>
  }
  if (!data) {
    return <p className="text-sm text-slate-500">选中场景后显示本次将注入的上下文。</p>
  }

  return (
    <section className="space-y-3 text-sm">
      <h3 className="font-medium text-slate-300">上下文预览</h3>
      <p className={`text-xs ${data.over_budget ? 'text-amber-300' : 'text-slate-500'}`}>
        {data.agent.name} v{data.agent.version_no} · 估算 {data.estimated_tokens} /{' '}
        {data.token_budget} tokens
      </p>
      {data.slots.map((slot) => (
        <details key={slot.key} className="rounded border border-slate-800 p-2">
          <summary className="cursor-pointer text-slate-300">
            {slot.label}{' '}
            <span className="text-xs text-slate-500">{slot.estimated_tokens} tokens</span>
            {data.trimmed[slot.key] && (
              <span className="ml-2 text-xs text-amber-300">{data.trimmed[slot.key]}</span>
            )}
          </summary>
          <pre className="mt-2 whitespace-pre-wrap break-words text-xs text-slate-400">
            {slot.text ?? (data.trimmed[slot.key] ? '（已丢弃）' : '（本槽位暂无内容）')}
          </pre>
        </details>
      ))}
    </section>
  )
}
