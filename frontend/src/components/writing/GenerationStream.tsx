interface Props {
  text: string
  generating: boolean
}

export default function GenerationStream({ text, generating }: Props) {
  if (!generating && !text) return null
  return (
    <section className="space-y-2 rounded border border-indigo-900 bg-indigo-950/20 p-3">
      <h3 className="text-sm font-medium text-indigo-200">
        {generating ? '正在生成…' : '本次生成结果'}
      </h3>
      <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words font-mono text-sm leading-7 text-slate-100">
        {text || '等待第一段…'}
      </pre>
    </section>
  )
}
