import { useEffect, useRef, type ReactNode } from 'react'
import { IconButton } from './Button'
import { cn } from './cn'

/**
 * 确认框。本轮只服务新增的确认入口；全站 25 处 `window.confirm` 不替换。
 * ESC 关闭、打开时把焦点移到对话框上（键盘用户不会掉到背后的页面里）。
 */
export function Dialog({
  open,
  title,
  onClose,
  children,
  footer,
  className,
}: {
  open: boolean
  title: string
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
  className?: string
}) {
  const boxRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    boxRef.current?.focus()
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30 p-6" onClick={onClose}>
      <div
        ref={boxRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className={cn(
          'w-full max-w-md overflow-hidden rounded-overlay border border-line bg-surface shadow-overlay outline-none',
          className,
        )}
        onClick={(event) => event.stopPropagation()}
      >
        <header className="flex items-center gap-2 border-b border-line px-4 py-3">
          <h2 className="text-[14px] font-semibold text-ink">{title}</h2>
          <div className="ml-auto">
            <IconButton label="关闭" onClick={onClose}>
              ×
            </IconButton>
          </div>
        </header>
        <div className="px-4 py-3.5 text-[13px] text-ink-2">{children}</div>
        {footer ? <footer className="flex justify-end gap-2 border-t border-line px-4 py-3">{footer}</footer> : null}
      </div>
    </div>
  )
}
