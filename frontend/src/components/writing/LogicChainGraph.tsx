import type { LogicChainItem } from '../../api/client'
import type { GraphNode } from '../../lib/logicChainGraph'
import {
  buildLogicChainGraph,
  shortenSentence,
  columnCenterX,
  edgePathFor,
  tickBaselineY,
  NODE_TEXT_MAX,
} from '../../lib/logicChainGraph'

// 深色底 #020617 上实测（WCAG 相对亮度）：sky-500 7.28:1、amber-500 9.39:1、emerald-500 7.95:1
const COLORS: Record<string, string> = { cause: '#0ea5e9', turn: '#f59e0b', reveal: '#10b981' }

/** 未知类型回落到中性灰，而不是抛错：后端将来多一类时图仍然画得出来。 */
function colorOf(kind: string): string {
  return COLORS[kind] ?? '#94a3b8'
}

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
              d={edgePathFor(from, to)}
              stroke={colorOf(edge.kind)}
              strokeWidth={1.5}
              fill="none"
              opacity={0.45}
            />
          )
        })}

        {graph.nodes.map((node) => {
          const color = colorOf(node.kind)
          const sentence = shortenSentence(node.sentence, NODE_TEXT_MAX)
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
            x={columnCenterX(column.paragraph)}
            y={tickBaselineY(graph.height)}
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
