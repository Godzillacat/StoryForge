import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import Architecture from './pages/Architecture'
import Dashboard from './pages/Dashboard'
import Idea from './pages/Idea'
import Models from './pages/Models'
import Relations from './pages/Relations'
import Studio from './pages/Studio'
import Terms from './pages/Terms'
import World from './pages/World'

const NAV = [
  { to: '/dashboard', label: '故事仪表盘' },
  { to: '/idea', label: '灵感与解析' },
  { to: '/architecture', label: '架构推荐' },
  { to: '/world', label: '世界观' },
  { to: '/relations', label: '关系网' },
  { to: '/terms', label: '术语表' },
  { to: '/studio', label: '智能体工作室' },
  { to: '/models', label: '模型与费用' },
]

export default function App() {
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
      <main className="flex-1 overflow-auto p-6">
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/idea" element={<Idea />} />
          <Route path="/architecture" element={<Architecture />} />
          <Route path="/world" element={<World />} />
          <Route path="/relations" element={<Relations />} />
          <Route path="/terms" element={<Terms />} />
          <Route path="/studio" element={<Studio />} />
          <Route path="/models" element={<Models />} />
        </Routes>
      </main>
    </div>
  )
}
