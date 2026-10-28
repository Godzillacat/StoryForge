import type { ContextPreview as ContextPreviewData } from '../../api/client'

interface Props {
  data: ContextPreviewData | null
  loading: boolean
  error: string
}

export default function ContextPreview({ data, loading, error }: Props) {
  if (loading) {
    return <p className="text-[13.5px] text-muted">正在准备上下文…</p>
  }
  if (error) {
    return <p className="rounded-control border border-warn bg-warn-soft p-2 text-[13.5px] text-warn">{error}</p>
  }
  if (!data) {
    return <p className="text-[13.5px] text-muted">选中场景后显示本次将注入的上下文。</p>
  }

  return (
    <section className="space-y-3 text-[13.5px]">
      <h3 className="font-medium text-ink-2">上下文预览</h3>
      <p className={`text-[11.5px] ${data.over_budget ? 'text-warn' : 'text-muted'}`}>
        {data.agent.name} v{data.agent.version_no} · 估算 {data.estimated_tokens} /{' '}
        {data.token_budget} tokens
      </p>
      {data.slots.map((slot) => (
        <details key={slot.key} className="rounded-control border border-line p-2">
          <summary className="cursor-pointer text-ink-2">
            {slot.label}{' '}
            <span className="text-[11.5px] text-muted">{slot.estimated_tokens} tokens</span>
            {data.trimmed[slot.key] && (
              <span className="ml-2 text-[11.5px] text-warn">{data.trimmed[slot.key]}</span>
            )}
          </summary>
          <pre className="mt-2 whitespace-pre-wrap break-words text-[11.5px] text-muted">
            {slot.text ?? (data.trimmed[slot.key] ? '（已丢弃）' : '（本槽位暂无内容）')}
          </pre>
        </details>
      ))}
    </section>
  )
}
