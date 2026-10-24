import type {
  CausalBreak,
  CausalChapter,
  CausalIssue,
  CausalMapData,
} from '../api/client'

// 图上的一格：宽固定，章内横向排开；行高留给节点底下的断点小字。
export const NODE_WIDTH = 180
export const NODE_GAP = 28
export const ROW_HEIGHT = 120

/** 章内一个场景节点。x 由序号决定，组件不另算一份公式。 */
export interface CausalNode {
  id: string
  label: string
  goal: string
  turn: string
  x: number
  breaks: CausalBreak[]
  issues: CausalIssue[]
  locked: boolean
}

/** 一章一行：章信息 + 按故事顺序摆好的节点。 */
export interface CausalRow {
  chapter: CausalChapter
  nodes: CausalNode[]
  /** 行内容宽度：最后一个节点的右缘，横向滚动容器按它撑开。 */
  width: number
}

export interface CausalRows {
  rows: CausalRow[]
  totals: CausalMapData['totals']
}

export interface CausalSummary {
  scenes: number
  breaks: number
  chapters: number
}

/**
 * 布局纯函数：把接口返回摊成「一章一行」。
 *
 * 断点、问题、锁定原样透传 —— 这里只排位置，不解释数据，
 * 判定是后端 `causal_service` 的职责，前端不抄第二份规则。
 * 空章保留成一行（nodes 为空），由组件显示空态，不画空链。
 */
export function buildCausalRows(data: CausalMapData | null | undefined): CausalRows {
  const rows = (data?.chapters ?? []).map((chapter) => {
    const nodes = chapter.scenes.map((scene, index) => ({
      id: scene.id,
      label: scene.label,
      goal: scene.goal,
      turn: scene.turn,
      x: index * (NODE_WIDTH + NODE_GAP),
      breaks: scene.breaks ?? [],
      issues: scene.issues ?? [],
      locked: scene.locked === true,
    }))
    return {
      chapter,
      nodes,
      width: nodes.length === 0 ? 0 : nodes[nodes.length - 1].x + NODE_WIDTH,
    }
  })
  return { rows, totals: summarize(data) }
}

/**
 * 顶部计数。从章/场景/断点自己数，而不是直接抄 `totals`：
 * 两者不一致时（接口漏算或多算）界面上的数字就露馅，测试也拿它对照后端。
 */
export function summarize(data: CausalMapData | null | undefined): CausalSummary {
  const chapters = data?.chapters ?? []
  let scenes = 0
  let breaks = 0
  for (const chapter of chapters) {
    scenes += chapter.scenes.length
    for (const scene of chapter.scenes) {
      breaks += scene.breaks?.length ?? 0
    }
  }
  return { scenes, breaks, chapters: chapters.length }
}
