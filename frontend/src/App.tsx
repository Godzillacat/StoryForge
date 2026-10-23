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

const NAV = [
  { to: '/dashboard', label: '故事仪表盘' },
  { to: '/idea', label: '灵感与解析' },
  { to: '/architecture', label: '架构推荐' },
  { to: '/world', label: '世界观' },
  { to: '/relations', label: '关系网' },
  { to: '/timeline', label: '时间线' },
  { to: '/terms', label: '术语表' },
  { to: '/chapters', label: '章节设计' },
  { to: '/write', label: '写作台' },
  { to: '/read', label: '阅读器' },
  { to: '/pipeline', label: '管线编排' },
  { to: '/studio', label: '智能体工作室' },
  { to: '/models', label: '模型与费用' },
]

export default function App() {
  const paddingless = useLocation().pathname
  return (
    <div className="flex h-screen">
      <aside className="w-56 shrink-0 border-r border-slate-800 p-4">
        <h1 className="mb-6 text-lg font-semibold tracking-wide">StoryForge</h1>
        <nav className="space-y-1">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `block rounded px-3 py-2 text-sm ${
                  isActive ? 'bg-slate-800 text-white' : 'text-slate-400 hover:bg-slate-900'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main
        className={`flex min-h-0 flex-1 flex-col overflow-auto ${
          // 阅读器要通铺自己的配色与滚动区；其余页面统一内边距。
          paddingless === '/read' ? '' : 'p-6'
        }`}
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
