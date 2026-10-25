import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { ProjectMetaView } from '../lib/projectMeta'

export interface ProjectMeta extends ProjectMetaView {
  entryCount: number | null
  loading: boolean
}

const EMPTY: ProjectMeta = {
  entryCount: null,
  volumes: null,
  chapters: null,
  words: null,
  loading: false,
}

// 同一项目重复进入侧栏不重复请求；切项目才重取。
const cache = new Map<string, Omit<ProjectMeta, 'loading'>>()

/**
 * 侧栏用的项目元数据：设定条目总数 + 卷 / 章 / 字数。
 * 任一项失败只让那一项变 `null`（界面显示「—」），不写 notice、不弹错 ——
 * 侧栏坏掉不该挡住正文。
 */
export function useProjectMeta(projectId: string): ProjectMeta {
  const [meta, setMeta] = useState<ProjectMeta>(() => {
    const cached = projectId ? cache.get(projectId) : undefined
    return cached ? { ...cached, loading: false } : EMPTY
  })

  useEffect(() => {
    if (!projectId) {
      setMeta(EMPTY)
      return
    }
    const cached = cache.get(projectId)
    if (cached) {
      setMeta({ ...cached, loading: false })
      return
    }
    let alive = true
    setMeta((prev) => ({ ...prev, loading: true }))
    Promise.all([
      api
        .listEntries(projectId)
        .then((rows) => rows.length)
        .catch(() => null),
      api
        .getExportReport(projectId)
        .then((report) => report)
        .catch(() => null),
    ]).then(([entryCount, report]) => {
      if (!alive) return
      const next = {
        entryCount,
        volumes: report?.volumes ?? null,
        chapters: report?.chapters ?? null,
        words: report?.total_words ?? null,
      }
      cache.set(projectId, next)
      setMeta({ ...next, loading: false })
    })
    return () => {
      alive = false
    }
  }, [projectId])

  return meta
}
