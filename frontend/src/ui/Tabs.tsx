import { cn } from './cn'

export interface TabItem {
  key: string
  label: string
  count?: number
}

export interface TabsProps {
  items: TabItem[]
  active: string
  onChange: (key: string) => void
  className?: string
}

export function Tabs({ items, active, onChange, className }: TabsProps) {
  return (
    <div role="tablist" className={cn('flex items-center gap-0.5', className)}>
      {items.map((item) => {
        const selected = item.key === active
        return (
          <button
            key={item.key}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(item.key)}
            className={cn(
              'inline-flex h-7 items-center gap-1.5 rounded-control px-2.5 text-[12.5px] transition-colors duration-[120ms]',
              selected ? 'bg-sunken font-semibold text-ink' : 'text-muted hover:text-ink-2',
            )}
          >
            {item.label}
            {typeof item.count === 'number' ? <span className="text-[11px] text-faint">{item.count}</span> : null}
          </button>
        )
      })}
    </div>
  )
}
