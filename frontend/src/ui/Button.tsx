import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { cn } from './cn'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
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
