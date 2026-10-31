import type { ReactNode } from 'react'
import { cn } from './cn'

export type IconName =
  | 'dashboard'
  | 'idea'
  | 'architecture'
  | 'world'
  | 'relations'
  | 'timeline'
  | 'terms'
  | 'chapters'
  | 'write'
  | 'read'
  | 'pipeline'
  | 'studio'
  | 'models'
  | 'chevron'
  | 'close'
  | 'lock'
  | 'plus'
  | 'search'
  | 'more'

/** 手写图标：统一 20×20、1.5 描边、currentColor。不引图标库。 */
const PATHS: Record<IconName, ReactNode> = {
  dashboard: (
    <>
      <rect x="3" y="3" width="6" height="6" rx="1" />
      <rect x="11" y="3" width="6" height="6" rx="1" />
      <rect x="3" y="11" width="6" height="6" rx="1" />
      <rect x="11" y="11" width="6" height="6" rx="1" />
    </>
  ),
  idea: (
    <>
      <path d="M10 3a5 5 0 0 0-3 9v2h6v-2a5 5 0 0 0-3-9Z" />
      <path d="M8 17h4" />
    </>
  ),
  architecture: (
    <>
      <path d="M10 3l7 14H3L10 3Z" />
      <path d="M10 10v7" />
    </>
  ),
  world: (
    <>
      <circle cx="10" cy="10" r="7" />
      <ellipse cx="10" cy="10" rx="3" ry="7" />
      <path d="M3 10h14" />
    </>
  ),
  relations: (
    <>
      <circle cx="6" cy="7" r="2.5" />
      <circle cx="14" cy="13" r="2.5" />
      <path d="M8 8.5l4 3" />
    </>
  ),
  timeline: (
    <>
      <path d="M3 10h14" />
      <circle cx="7" cy="10" r="1.6" />
      <circle cx="13" cy="10" r="1.6" />
    </>
  ),
  terms: (
    <>
      <path d="M10 3h6v6l-7 7-6-6 7-7Z" />
      <circle cx="13.5" cy="6.5" r="1" />
    </>
  ),
  chapters: <path d="M4 5h12M4 10h12M4 15h8" />,
  write: <path d="M4 16l1-4 9-9 3 3-9 9-4 1Z" />,
  read: (
    <>
      <path d="M3 4h6v12H3z" />
      <path d="M11 4h6v12h-6z" />
    </>
  ),
  pipeline: (
    <>
      <circle cx="4.5" cy="10" r="2" />
      <circle cx="10" cy="10" r="2" />
      <circle cx="15.5" cy="10" r="2" />
      <path d="M6.5 10h1.5M12 10h1.5" />
    </>
  ),
  studio: (
    <>
      <path d="M3 6h14M3 14h14" />
      <circle cx="8" cy="6" r="2" />
      <circle cx="13" cy="14" r="2" />
    </>
  ),
  models: (
    <>
      <path d="M10 3l6 3.5v7L10 17l-6-3.5v-7L10 3Z" />
      <path d="M10 10l6-3.5M10 10v7M10 10L4 6.5" />
    </>
  ),
  chevron: <path d="M8 5l5 5-5 5" />,
  close: <path d="M6 6l8 8M14 6l-8 8" />,
  lock: (
    <>
      <rect x="5" y="9" width="10" height="8" rx="2" />
      <path d="M7.5 9V7a2.5 2.5 0 0 1 5 0v2" />
    </>
  ),
  plus: <path d="M10 4v12M4 10h12" />,
  search: (
    <>
      <circle cx="9" cy="9" r="5.5" />
      <path d="M13 13l4 4" />
    </>
  ),
  more: (
    <>
      <circle cx="5" cy="10" r="1.2" fill="currentColor" stroke="none" />
      <circle cx="10" cy="10" r="1.2" fill="currentColor" stroke="none" />
      <circle cx="15" cy="10" r="1.2" fill="currentColor" stroke="none" />
    </>
  ),
}

export function Icon({ name, size = 20, className }: { name: IconName; size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={cn('shrink-0', className)}
    >
      {PATHS[name]}
    </svg>
  )
}
