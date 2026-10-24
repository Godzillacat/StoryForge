import type { LogicChainItem } from '../api/client'

// 图形几何常量：一处定义，布局与渲染共用。
export const NODE_WIDTH = 168
export const NODE_HEIGHT = 52
export const COLUMN_WIDTH = 192
export const ROW_GAP = 12
export const PAD_LEFT = 16
export const PAD_TOP = 24
export const PAD_BOTTOM = 28

/** 列的水平中心：节点左缘与底部刻度都从这里派生，组件不另算一份公式。 */
export function columnCenterX(paragraph: number): number {
  return PAD_LEFT + (paragraph - 1) * COLUMN_WIDTH + NODE_WIDTH / 2
}

/** 底部段落刻度的基线：落在 PAD_BOTTOM 留白区里，组件不自己编偏移量。 */
export function tickBaselineY(height: number): number {
  return height - PAD_BOTTOM + 18
}

export interface GraphNode {
  index: number
  paragraph: number
  sentence: string
  kind: string
  kindLabel: string
  marker: string
  x: number
  y: number
  width: number
  height: number
}

export interface GraphEdge {
  fromIndex: number
  toIndex: number
  kind: string
}

export interface GraphColumn {
  paragraph: number
  nodes: GraphNode[]
}

export interface LogicChainGraph {
  columns: GraphColumn[]
  nodes: GraphNode[]
  edges: GraphEdge[]
  width: number
  height: number
  maxRows: number
}

/**
 * 把逻辑链命中铺成「段落列 × 列内行」的轨道图。
 *
 * 列数取 max(段落总数, 最大命中段)，这样服务端把 paragraphs 给少时也不会丢节点；
 * 空段落保留成空列，作者能看出「这一段没有任何逻辑链命中」。
 */
export function buildLogicChainGraph(chain: LogicChainItem[], paragraphs: number): LogicChainGraph {
  // 零命中时不画空图，交给调用方显示原有 reason。
  if (chain.length === 0) {
    return { columns: [], nodes: [], edges: [], width: 0, height: 0, maxRows: 0 }
  }

  // 以命中段兜底：paragraphs 偏小（甚至为 0）时，命中靠后的节点仍要出现。
  // 先归一成有限整数：接口漏字段时会是 undefined，不拦的话 NaN 会一路算进宽高。
  const safeParagraphs = Number.isFinite(paragraphs) ? Math.trunc(paragraphs) : 0
  const maxHitParagraph = chain.reduce((max, item) => Math.max(max, item.paragraph), 0)
  const columnCount = Math.max(safeParagraphs, maxHitParagraph)

  // 先按段落分桶，桶内保持命中在原链里的先后顺序。
  const positionsByParagraph = new Map<number, number[]>()
  chain.forEach((item, position) => {
    const bucket = positionsByParagraph.get(item.paragraph)
    if (bucket) {
      bucket.push(position)
    } else {
      positionsByParagraph.set(item.paragraph, [position])
    }
  })

  const columns: GraphColumn[] = []
  const nodes: GraphNode[] = []
  const indexByPosition: number[] = new Array<number>(chain.length).fill(0)
  let maxRows = 0

  for (let paragraph = 1; paragraph <= columnCount; paragraph += 1) {
    const positions = positionsByParagraph.get(paragraph) ?? []
    const columnNodes: GraphNode[] = []
    positions.forEach((position, row) => {
      const item = chain[position]
      const node: GraphNode = {
        index: nodes.length,
        paragraph: item.paragraph,
        sentence: item.sentence,
        kind: item.kind,
        kindLabel: item.kind_label,
        marker: item.marker,
        x: columnCenterX(paragraph) - NODE_WIDTH / 2,
        y: PAD_TOP + row * (NODE_HEIGHT + ROW_GAP),
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
      }
      indexByPosition[position] = node.index
      columnNodes.push(node)
      nodes.push(node)
    })
    maxRows = Math.max(maxRows, columnNodes.length)
    columns.push({ paragraph, nodes: columnNodes })
  }

  // 边只表达出现顺序：相邻两次命中连一条线，颜色由目标端类型决定。
  // 端点用的是「扁平节点下标」（列优先铺开的 nodes 下标），不是段落下标。
  const edges: GraphEdge[] = []
  for (let position = 1; position < chain.length; position += 1) {
    edges.push({
      fromIndex: indexByPosition[position - 1],
      toIndex: indexByPosition[position],
      kind: chain[position].kind,
    })
  }

  return {
    columns,
    nodes,
    edges,
    width: PAD_LEFT * 2 + (columnCount - 1) * COLUMN_WIDTH + NODE_WIDTH,
    height: PAD_TOP + maxRows * (NODE_HEIGHT + ROW_GAP) - ROW_GAP + PAD_BOTTOM,
    maxRows,
  }
}

/** 节点内只放截断后的句子，全文由调用方放进 <title>。 */
export function shortenSentence(text: string, max = 22): string {
  if (text.length <= max) {
    return text
  }
  return text.slice(0, max) + '…'
}
