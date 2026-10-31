import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { cn } from './cn'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'accent' | 'warn'
type Size = 'sm' | 'md'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
}

const VARIANTS: Record<Variant, string> = {
  primary: 'border-transparent bg-accent text-white hover:bg-accent-ink',
  secondary: 'border-line-strong bg-surface text-ink-2 hover:bg-sunken',
  ghost: 'border-transparent text-muted hover:bg-sunken hover:text-ink-2',
  danger: 'border-transparent bg-danger text-white hover:opacity-90',
  // 语义色文字按钮：`accent` 给「新建 / 添加」这类正动作，`warn` 给「移除 /
  // 清除」这类提示动作。它们存在是因为 `cn` 只拼接、不消解冲突 —— 调用方
  // 自己传 `className="text-warn"` 能不能盖住 `ghost` 的 `text-muted`
  // 取决于 CSS 生成顺序（实测 `text-warn` 侥幸生效、`text-accent-ink` 不生效）。
  accent: 'border-transparent text-accent-ink hover:bg-accent-soft',
  warn: 'border-transparent text-warn hover:bg-warn-soft',
}

const SIZES: Record<Size, string> = {
  sm: 'h-[26px] px-2.5 text-[12.5px]',
  md: 'h-8 px-3 text-[13px]',
}

export function Button({ variant = 'secondary', size = 'md', className, type = 'button', ...rest }: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        'inline-flex items-center justify-center gap-1.5 rounded-control border font-ui transition-colors duration-[120ms] disabled:cursor-not-allowed disabled:opacity-45',
        SIZES[size],
        VARIANTS[variant],
        className,
      )}
      {...rest}
    />
  )
}

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  label: string
  children: ReactNode
}

export function IconButton({ label, className, type = 'button', children, ...rest }: IconButtonProps) {
  return (
    <button
      type={type}
      aria-label={label}
      title={label}
      className={cn(
        'inline-flex h-7 w-7 items-center justify-center rounded-control text-muted transition-colors duration-[120ms] hover:bg-sunken hover:text-ink-2',
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  )
}
