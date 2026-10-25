import type { ReactNode } from 'react'

export function EmptyState({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2.5 px-6 py-12 text-center">
      <p className="text-[14px] font-semibold text-ink-2">{title}</p>
      {hint ? <p className="max-w-[38ch] text-[12.5px] leading-relaxed text-muted">{hint}</p> : null}
      {action ? <div className="mt-1">{action}</div> : null}
    </div>
  )
}
