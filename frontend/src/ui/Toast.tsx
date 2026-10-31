import type { ReactNode } from 'react'
import { IconButton } from './Button'
import { cn } from './cn'

type Tone = 'ok' | 'warn' | 'danger'

const TONES: Record<Tone, string> = {
  ok: 'border-line bg-surface text-ink-2',
  warn: 'border-warn bg-warn-soft text-warn',
  danger: 'border-danger bg-surface text-danger',
}

/**
 * 轻提示：只负责外观与关闭，不持有队列、不自动消失。
 * 本轮不做全局 ToastHost —— 全站 211 处 `setNotice` 的成败判定不改。
 */
export function Toast({
  tone = 'ok',
  message,
  onDismiss,
  className,
}: {
  tone?: Tone
  message: ReactNode
  onDismiss?: () => void
  className?: string
}) {
  return (
    <div
      role="status"
      className={cn(
        'pointer-events-auto flex items-start gap-3 rounded-card border px-3.5 py-2.5 text-[12.5px] shadow-overlay',
        TONES[tone],
        className,
      )}
    >
      <span className="flex-1 leading-relaxed">{message}</span>
      {onDismiss ? (
        <IconButton label="关闭提示" onClick={onDismiss} className="-mr-1 -mt-0.5 h-6 w-6">
          ×
        </IconButton>
      ) : null}
    </div>
  )
}
