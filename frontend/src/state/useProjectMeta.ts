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

/** 缓存 30 秒：够挡住来回切项目的重复请求，又不会让「刚写完一章」永远显示旧数字。 */
const TTL_MS = 30_000

const cache = new Map<string, { meta: Omit<ProjectMeta, 'loading'>; at: number }>()

/**
 * 侧栏用的项目元数据：设定条目总数 + 卷 / 章 / 字数。
 * 任一项失败只让那一项变 `null`（界面显示「—」），不写 notice、不弹错 ——
 * 侧栏坏掉不该挡住正文。失败的结果不进缓存，免得一次瞬时故障粘住整个会话。
 */
export function useProjectMeta(projectId: string): ProjectMeta {
  const [meta, setMeta] = useState<ProjectMeta>(EMPTY)

  useEffect(() => {
    if (!projectId) {
      setMeta(EMPTY)
      return
    }
    const hit = cache.get(projectId)
    if (hit && Date.now() - hit.at < TTL_MS) {
      setMeta({ ...hit.meta, loading: false })
      return
    }
    let alive = true
    // 换到没有缓存的项目时先清空：宁可显示「—」，也不显示上一本的卷章字数。
    setMeta({ ...EMPTY, loading: true })
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
      if (report) cache.set(projectId, { meta: next, at: Date.now() })
      setMeta({ ...next, loading: false })
    })
    return () => {
      alive = false
    }
  }, [projectId])

  return meta
}
