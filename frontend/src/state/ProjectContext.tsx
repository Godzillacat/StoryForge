import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { api, type Project } from '../api/client'
import { KEY_CURRENT_PROJECT, readString, writeString } from '../lib/persisted'
import { pickProjectId } from '../lib/projectSelection'

export interface ProjectContextValue {
  projects: Project[]
  projectId: string
  project: Project | null
  loading: boolean
  error: string
  select: (id: string) => void
  refresh: () => Promise<void>
}

const ProjectContext = createContext<ProjectContextValue | null>(null)

/**
 * 当前项目由外壳持有：13 个页面不再各自拉项目列表、各自放一个下拉。
 * 列表读失败只写 `error`，不抛 —— 页面自己决定显示什么，但不会白屏。
 */
export function ProjectProvider({ children }: { children: ReactNode }) {
  const [projects, setProjects] = useState<Project[]>([])
  const [projectId, setProjectId] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const token = useRef(0)

  const refresh = useCallback(async () => {
    const current = ++token.current
    try {
      const list = await api.listProjects()
      if (token.current !== current) return
      setProjects(list)
      setError('')
      setProjectId(pickProjectId(readString(KEY_CURRENT_PROJECT), list))
    } catch (err) {
      if (token.current !== current) return
      setError((err as Error).message)
    } finally {
      if (token.current === current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  // 回落出来的项目也要记住，否则每次启动都会重新回落到第一个。
  useEffect(() => {
    if (projectId) writeString(KEY_CURRENT_PROJECT, projectId)
  }, [projectId])

  const select = useCallback((id: string) => {
    setProjectId(id)
    writeString(KEY_CURRENT_PROJECT, id)
  }, [])

  const value = useMemo<ProjectContextValue>(
    () => ({
      projects,
      projectId,
      project: projects.find((row) => row.id === projectId) ?? null,
      loading,
      error,
      select,
      refresh,
    }),
    [projects, projectId, loading, error, select, refresh],
  )

  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>
}

export function useCurrentProject(): ProjectContextValue {
  const value = useContext(ProjectContext)
  if (!value) throw new Error('useCurrentProject 必须在 ProjectProvider 内使用')
  return value
}
