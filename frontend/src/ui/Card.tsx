import type { ReactNode } from 'react'
import { cn } from './cn'

interface ContainerProps {
  title?: ReactNode
  actions?: ReactNode
  className?: string
  children: ReactNode
}

/** 卡片：1px 线 + 8px 圆角，不加阴影（阴影只留给浮层）。 */
export function Card({ title, actions, className, children }: ContainerProps) {
  const hasHeader = Boolean(title || actions)
  return (
    <section className={cn('rounded-card border border-line bg-surface p-4', className)}>
      {hasHeader ? (
        <header className="mb-3 flex items-center gap-2">
          {title ? <h3 className="text-[14px] font-semibold text-ink">{title}</h3> : null}
          {actions ? <div className="ml-auto flex items-center gap-2">{actions}</div> : null}
        </header>
      ) : null}
      {children}
    </section>
  )
}

/** 面板：占满一列、自己滚动，常用于左右侧栏。 */
export function Panel({ title, actions, className, children }: ContainerProps) {
  const hasHeader = Boolean(title || actions)
  return (
    <section className={cn('flex min-h-0 flex-col overflow-hidden rounded-card border border-line bg-surface', className)}>
      {hasHeader ? (
        <header className="flex h-11 shrink-0 items-center gap-2 border-b border-line px-3.5">
          {title ? <h2 className="text-[13.5px] font-semibold text-ink">{title}</h2> : null}
          {actions ? <div className="ml-auto flex items-center gap-2">{actions}</div> : null}
        </header>
      ) : null}
      <div className="min-h-0 flex-1 overflow-auto">{children}</div>
    </section>
  )
}
