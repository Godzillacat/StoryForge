interface Props {
  text: string
  generating: boolean
}

export default function GenerationStream({ text, generating }: Props) {
  if (!generating && !text) return null
  return (
    <section className="space-y-2 rounded-card border border-accent bg-accent-soft p-3">
      <h3 className="text-[13.5px] font-medium text-accent-ink">
        {generating ? '正在生成…' : '本次生成结果'}
      </h3>
      <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words font-mono text-[13.5px] leading-7 text-ink">
        {text || '等待第一段…'}
      </pre>
    </section>
  )
}
