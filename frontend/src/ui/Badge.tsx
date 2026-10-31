import type { ReactNode } from 'react'
import { cn } from './cn'

type Tone = 'plain' | 'accent' | 'warn'

const TONES: Record<Tone, string> = {
  plain: 'bg-sunken text-ink-2',
  accent: 'bg-accent-soft text-accent-ink',
  warn: 'bg-warn-soft text-warn',
}

export function Badge({ tone = 'plain', className, children }: { tone?: Tone; className?: string; children: ReactNode }) {
  return (
    <span
      className={cn('inline-flex h-5 items-center rounded-tag px-[7px] text-[11px] leading-none', TONES[tone], className)}
    >
      {children}
    </span>
  )
}
