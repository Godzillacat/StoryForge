import type { ReactNode } from 'react'

/**
 * 空态：颜色一律继承父级（`text-current` 语义），这样在浅色新页面与过渡期的深色旧页面里都读得清。
 * 一句话说明 + 一个动作，不写「暂无数据」这种空话。
 */
export function EmptyState({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2.5 px-6 py-12 text-center">
      <p className="text-[14px] font-semibold">{title}</p>
      {hint ? <p className="max-w-[38ch] text-[12.5px] leading-relaxed opacity-70">{hint}</p> : null}
      {action ? <div className="mt-1">{action}</div> : null}
    </div>
  )
}
