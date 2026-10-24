import type { LogicChainItem } from '../../api/client'
import type { GraphNode } from '../../lib/logicChainGraph'
import {
  buildLogicChainGraph,
  shortenSentence,
  COLUMN_WIDTH,
  NODE_WIDTH,
  PAD_BOTTOM,
  PAD_LEFT,
} from '../../lib/logicChainGraph'

// 深色底 #020617 上实测（WCAG 相对亮度）：sky-500 7.28:1、amber-500 9.39:1、emerald-500 7.95:1
const COLORS: Record<string, string> = { cause: '#0ea5e9', turn: '#f59e0b', reveal: '#10b981' }

/** 未知类型回落到中性灰，而不是抛错：后端将来多一类时图仍然画得出来。 */
function colorOf(kind: string): string {
  return COLORS[kind] ?? '#94a3b8'
}

/**
 * 边从源节点右缘连到目标节点左缘，控制点水平外推。
 * 相邻两次命中常落在同一列（同一段里的两处逻辑），此时两点反向，控制点会把线撑成一个绕回的弧。
 */
function edgePath(from: GraphNode, to: GraphNode): string {
  const sx = from.x + from.width
  const sy = from.y + from.height / 2
  const tx = to.x
  const ty = to.y + to.height / 2
  const bend = Math.max(32, Math.abs(tx - sx) / 2)
  return `M ${sx} ${sy} C ${sx + bend} ${sy}, ${tx - bend} ${ty}, ${tx} ${ty}`
}

/** 节点内可用宽度（左右各留 10）能放下几个字：11px 中文字宽约等于字号。 */
const SENTENCE_CHARS = 13

export default function LogicChainGraph({
  chain,
  paragraphs,
}: {
  chain: LogicChainItem[]
  paragraphs: number
}) {
  // 零命中不画 0×0 的空 svg：空态文案由父组件负责。
  if (chain.length === 0) {
    return null
  }

  const graph = buildLogicChainGraph(chain, paragraphs)
  const nodeByIndex = new Map<number, GraphNode>(graph.nodes.map((node) => [node.index, node]))
  const tickY = graph.height - PAD_BOTTOM + 18

  return (
    <div className="overflow-x-auto rounded border border-slate-800 bg-slate-950">
      <svg
        role="img"
        aria-label="逻辑链"
        width={graph.width}
        height={graph.height}
        viewBox={`0 0 ${graph.width} ${graph.height}`}
        className="block"
      >
        {/* 先画边，再画节点：线压在节点下面，不会穿过文字。 */}
        {graph.edges.map((edge) => {
          const from = nodeByIndex.get(edge.fromIndex)
          const to = nodeByIndex.get(edge.toIndex)
          if (!from || !to) {
            return null
          }
          return (
            <path
              key={`${edge.fromIndex}-${edge.toIndex}`}
              d={edgePath(from, to)}
              stroke={colorOf(edge.kind)}
              strokeWidth={1.5}
              fill="none"
              opacity={0.45}
            />
          )
        })}

        {graph.nodes.map((node) => {
          const color = colorOf(node.kind)
          const sentence = shortenSentence(node.sentence, SENTENCE_CHARS)
          return (
            <g key={node.index}>
              <title>{`¶${node.paragraph} · ${node.sentence} · ${node.marker || '无连接词'}`}</title>
              <rect
                x={node.x}
                y={node.y}
                width={node.width}
                height={node.height}
                rx={6}
                fill="#0f172a"
                stroke={color}
                strokeOpacity={0.6}
              />
              <rect x={node.x} y={node.y} width={3} height={node.height} rx={1.5} fill={color} />
              <text x={node.x + 12} y={node.y + 18} fill={color} fontSize={11}>
                {node.kindLabel}
              </text>
              <text x={node.x + 12} y={node.y + 38} fill="#cbd5e1" fontSize={11}>
                {sentence}
              </text>
            </g>
          )
        })}

        {/* 段落刻度：空列也画，作者据此看出「这一段没有逻辑链」。 */}
        {graph.columns.map((column) => (
          <text
            key={column.paragraph}
            x={PAD_LEFT + (column.paragraph - 1) * COLUMN_WIDTH + NODE_WIDTH / 2}
            y={tickY}
            textAnchor="middle"
            fontSize={10}
            fill={column.nodes.length > 0 ? '#64748b' : '#334155'}
          >
            {`¶${column.paragraph}`}
          </text>
        ))}
      </svg>
    </div>
  )
}
