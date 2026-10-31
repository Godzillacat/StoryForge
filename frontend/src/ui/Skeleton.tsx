import { cn } from './cn'

/** 首次加载的占位；轮询与局部刷新不用它（会闪）。 */
export function Skeleton({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <div className={cn('space-y-2.5', className)} aria-hidden="true">
      {Array.from({ length: lines }).map((_, index) => (
        <div key={index} className={cn('h-3 animate-pulse rounded bg-sunken', index === lines - 1 && 'w-2/3')} />
      ))}
    </div>
  )
}
