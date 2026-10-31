import type { HTMLAttributes, ReactNode, TdHTMLAttributes, ThHTMLAttributes } from 'react'
import { cn } from './cn'

type Align = 'left' | 'right'

export function Table({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={cn('overflow-x-auto', className)}>
      <table className="w-full border-collapse">{children}</table>
    </div>
  )
}

export function Th({
  align = 'left',
  className,
  children,
  ...rest
}: ThHTMLAttributes<HTMLTableCellElement> & { align?: Align }) {
  return (
    <th
      className={cn(
        'border-b border-line px-2.5 pb-2.5 text-[11px] font-medium tracking-[.08em] text-muted',
        align === 'right' ? 'text-right' : 'text-left',
        className,
      )}
      {...rest}
    >
      {children}
    </th>
  )
}

export function Td({
  align = 'left',
  className,
  children,
  ...rest
}: TdHTMLAttributes<HTMLTableCellElement> & { align?: Align; children?: ReactNode }) {
  return (
    <td
      className={cn(
        'border-b border-line px-2.5 py-[11px] text-[13.5px] text-ink-2',
        align === 'right' ? 'text-right tabular-nums' : 'text-left',
        className,
      )}
      {...rest}
    >
      {children}
    </td>
  )
}

export type { Align as TableAlign }
export type TableRowProps = HTMLAttributes<HTMLTableRowElement>
