import { useEffect, useState } from 'react'
import { api, type LogicChainResponse } from '../../api/client'
import LogicChainGraph from './LogicChainGraph'

const COLORS: Record<string, string> = {
  cause: 'text-sky-300',
  turn: 'text-amber-300',
  reveal: 'text-emerald-300',
}

/** 逻辑链：把正文里**已有的**因果 / 转折 / 揭示摆出来。
 *
 * 与逻辑自检的问题清单并列但**不混在一起** —— 链是「正文里写了什么」，
 * 问题是「哪里讲不通」。混在一起会让作者以为链里每一句都有问题。
 *
 * `body` 只用来决定何时重取：它是服务端的已采纳正文，保存 / 采纳 / 恢复
 * 之后才会变。`undefined` 表示正文还没加载完，此时不取（否则会先取到一次
 * 「没有正文」）。
 */
export default function LogicChain({
  sceneId,
  body,
}: {
  sceneId: string
  body: string | null | undefined
}) {
  const [data, setData] = useState<LogicChainResponse | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  // 默认图形：图是本项交付物，文本列表退成备选。切换只改这一处本地状态，
  // 不碰 `data`、也不进 `useEffect` 的依赖 —— 切模式不该重跑接口。
  const [mode, setMode] = useState<'graph' | 'text'>('graph')

  // 换场回到默认图形：作者换一场时看到的应是这一场的图，而不是上一场留下的选择。
  // 只重置模式，取数仍由下面那个 effect 管，两者互不影响。
  useEffect(() => {
    setMode('graph')
  }, [sceneId])

  useEffect(() => {
    setData(null)
    setError('')
    if (body === undefined) return
    setLoading(true)
    let cancelled = false
    api
      .logicChain(sceneId)
      .then((value) => {
        if (!cancelled) setData(value)
      })
      .catch((e) => {
        if (!cancelled) setError((e as Error).message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [sceneId, body])

  return (
    <section className="space-y-2 rounded border border-slate-800 p-3 text-sm">
      <div className="flex items-center gap-2">
        <h3 className="font-medium text-slate-300">逻辑链</h3>
        {data && data.summary.total > 0 && (
          <span className="text-xs text-slate-500">
            因果 {data.summary.cause} · 转折 {data.summary.turn} · 揭示{' '}
            {data.summary.reveal}
          </span>
        )}
        <div
          role="group"
          aria-label="逻辑链视图切换"
          className="ml-auto flex shrink-0 gap-1"
        >
          {(
            [
              ['graph', '图形'],
              ['text', '文本'],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              aria-pressed={mode === value}
              disabled={!data || data.chain.length === 0}
              onClick={() => setMode(value)}
              className={`rounded px-2 py-0.5 text-xs outline-none focus-visible:ring-1 focus-visible:ring-slate-500 disabled:cursor-not-allowed disabled:opacity-40 ${
                mode === value ? 'bg-slate-800 text-slate-200' : 'text-slate-400'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <p className="text-xs text-slate-500">
        从正文里按连接词抽出，不做判断。问题清单在下面。
      </p>

      {loading && <p className="text-xs text-slate-500">正在读取正文…</p>}
      {error && <p className="text-xs text-red-400">{error}</p>}

      {data && data.chain.length === 0 && (
        <p className="text-xs text-slate-500">{data.reason || '没有可展示的句子。'}</p>
      )}

      {data && data.chain.length > 0 && mode === 'graph' && (
        <div className="space-y-1">
          <p className="text-xs text-slate-500">
            按出现顺序相连，不代表句子真的指向哪一句。
          </p>
          <LogicChainGraph chain={data.chain} paragraphs={data.paragraphs} />
        </div>
      )}

      {data && data.chain.length > 0 && mode === 'text' && (
        <ul className="space-y-1">
          {data.chain.map((item, index) => (
            <li key={`${item.paragraph}-${index}`} className="flex gap-2 text-xs">
              <span className="w-8 shrink-0 text-slate-600">¶{item.paragraph}</span>
              <span className={`w-8 shrink-0 ${COLORS[item.kind] ?? 'text-slate-400'}`}>
                {item.kind_label}
              </span>
              <span className="flex-1 text-slate-300">{item.sentence}</span>
              <span className="shrink-0 text-slate-600">{item.marker}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
