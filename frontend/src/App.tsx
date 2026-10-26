import { useState } from 'react'
import { NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import Architecture from './pages/Architecture'
import Chapters from './pages/Chapters'
import Dashboard from './pages/Dashboard'
import Idea from './pages/Idea'
import Models from './pages/Models'
import Pipeline from './pages/Pipeline'
import Reader from './pages/Reader'
import Relations from './pages/Relations'
import Studio from './pages/Studio'
import Terms from './pages/Terms'
import Timeline from './pages/Timeline'
import World from './pages/World'
import Writing from './pages/Writing'
import { KEY_SIDEBAR_COLLAPSED, readFlag, writeFlag } from './lib/persisted'
import { NAV_GROUPS } from './lib/nav'
import { summaryLine } from './lib/projectMeta'
import { ProjectSwitcher } from './components/ProjectSwitcher'
import { useCurrentProject } from './state/ProjectContext'
import { useProjectMeta } from './state/useProjectMeta'
import { cn } from './ui/cn'
import { Icon } from './ui/icons'

/**
 * 过渡脚手架：还没换到新语言的页面，继续用旧的深色底，避免"新外壳 + 白底旧页"读不清。
 * 每迁移完一页就从这里删掉一条；批次 3 结束后整个常量连同使用处一起删除。
 */
const LEGACY_DARK = new Set([
  '/idea',
  '/architecture',
  '/relations',
  '/timeline',
  '/terms',
  '/chapters',
  '/write',
  '/pipeline',
  '/studio',
  '/models',
])

export default function App() {
  const pathname = useLocation().pathname
  // 尾斜杠不算另一条路由：`/world/` 与 `/world` 必须是同一页、同一套底色。
  const routePath = pathname.replace(/\/+$/, '') || '/'
  const [collapsed, setCollapsed] = useState(() => readFlag(KEY_SIDEBAR_COLLAPSED, false))
  const { projectId } = useCurrentProject()
  const meta = useProjectMeta(projectId)

  function applyCollapsed(next: boolean) {
    setCollapsed(next)
    writeFlag(KEY_SIDEBAR_COLLAPSED, next)
  }

  return (
    <div className="flex h-screen bg-paper text-ink">
      <aside
        className={cn(
          'flex shrink-0 flex-col border-r border-line bg-surface py-4 transition-[width] duration-150',
          collapsed ? 'w-14 px-2' : 'w-[236px] px-3',
        )}
      >
        <div className={cn('mb-4 flex items-center', collapsed ? 'justify-center' : 'px-2')}>
          {collapsed ? (
            <span className="font-serif text-[17px] font-semibold text-accent-ink" title="StoryForge">
              S
            </span>
          ) : (
            <h1 className="font-serif text-[19px] font-semibold tracking-[.02em]">StoryForge</h1>
          )}
        </div>

        <ProjectSwitcher collapsed={collapsed} onExpand={() => applyCollapsed(false)} />

        <nav className="min-h-0 flex-1 overflow-y-auto">
          {NAV_GROUPS.map((group) => (
            <div key={group.title} className="mt-3 first:mt-0">
              {collapsed ? null : (
                <div className="mb-1 px-2 text-[11px] tracking-[.12em] text-muted">{group.title}</div>
              )}
              <div className="space-y-0.5">
                {group.items.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    title={collapsed ? item.label : undefined}
                    className={({ isActive }) =>
                      cn(
                        'flex h-8 items-center gap-2 rounded-control text-[13.5px] transition-colors duration-[120ms]',
                        collapsed ? 'justify-center' : 'px-2',
                        isActive
                          ? 'bg-accent-soft font-semibold text-accent-ink'
                          : 'text-ink-2 hover:bg-sunken hover:text-ink',
                      )
                    }
                  >
                    <Icon name={item.icon} size={18} />
                    {collapsed ? null : <span className="truncate">{item.label}</span>}
                    {collapsed || !item.badge ? null : (
                      <span className="ml-auto text-[11px] text-muted">
                        {item.badge === 'entries' ? (meta.entryCount ?? '—') : null}
                      </span>
                    )}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        {collapsed ? null : (
          <div className="mt-2 truncate px-1 text-[11px] text-muted" title={summaryLine(meta)}>
            {summaryLine(meta)}
          </div>
        )}

        <div className={cn('mt-2 border-t border-line pt-2', collapsed ? 'flex justify-center' : 'flex justify-end')}>
          <button
            type="button"
            onClick={() => applyCollapsed(!collapsed)}
            aria-label={collapsed ? '展开侧栏' : '收起侧栏'}
            aria-expanded={!collapsed}
            className="inline-flex h-7 w-7 items-center justify-center rounded-control text-muted transition-colors duration-[120ms] hover:bg-sunken hover:text-ink-2"
          >
            <Icon name="chevron" className={collapsed ? '' : 'rotate-180'} />
          </button>
        </div>
      </aside>

      <main
        className={cn(
          'flex min-h-0 flex-1 flex-col overflow-auto',
          // 阅读器要通铺自己的配色与滚动区；其余页面统一内边距（页面级重排在各页批次里做）。
          routePath === '/read' ? '' : 'p-6',
          LEGACY_DARK.has(routePath) && 'bg-slate-950 text-slate-100',
        )}
      >
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/idea" element={<Idea />} />
          <Route path="/architecture" element={<Architecture />} />
          <Route path="/world" element={<World />} />
          <Route path="/relations" element={<Relations />} />
          <Route path="/timeline" element={<Timeline />} />
          <Route path="/terms" element={<Terms />} />
          <Route path="/chapters" element={<Chapters />} />
          <Route path="/write" element={<Writing />} />
          <Route path="/read" element={<Reader />} />
          <Route path="/pipeline" element={<Pipeline />} />
          <Route path="/studio" element={<Studio />} />
          <Route path="/models" element={<Models />} />
        </Routes>
      </main>
    </div>
  )
}
