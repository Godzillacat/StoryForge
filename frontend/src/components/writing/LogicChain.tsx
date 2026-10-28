import { useEffect, useRef, useState } from 'react'
import { api, type LogicChainResponse } from '../../api/client'
import LogicChainGraph from './LogicChainGraph'

// 三条类别色必须两两可分辨（原文用的是 sky / amber / emerald），且与图形视图
// 的 `chartTokens` 三条序列色对应：cause = accent、turn = warn、reveal = ink-2。
const COLORS: Record<string, string> = {
  cause: 'text-accent-ink',
  turn: 'text-warn',
  reveal: 'text-ink-2',
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
  // 全屏只看这一份 `data`：不复制、不重取。右栏在 xl 下仅 320px，图放不下时才用。
  const [expanded, setExpanded] = useState(false)
  // 覆盖层真正可见的条件：既点了展开，手头也真有可画的链（重取期间 data 会短暂为 null）。
  const dialogOpen = expanded && Boolean(data && data.chain.length > 0)
  // 关掉覆盖层后把焦点还给触发它的按钮。不做焦点圈闭，循环 Tab 留待后续。
  const expandButtonRef = useRef<HTMLButtonElement | null>(null)
  const wasDialogOpen = useRef(false)

  // 换场回到默认图形，并关掉上一场的全屏图：取数仍由下面那个 effect 管。
  useEffect(() => {
    setMode('graph')
    setExpanded(false)
  }, [sceneId])

  // 打开时锁住真正的滚动容器：外壳是 <div class="flex h-screen"> + <main class="overflow-auto">，
  // body 本身不滚，锁 body 是空操作。关闭 / 换场 / 卸载都恢复打开前的值；找不到 main 就跳过。
  // ESC 与「关闭」按钮走同一个出口：setExpanded(false)。
  useEffect(() => {
    if (!dialogOpen) return
    const scroller = document.querySelector('main')
    const previousOverflow = scroller?.style.overflow
    if (scroller) scroller.style.overflow = 'hidden'
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setExpanded(false)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      if (scroller) scroller.style.overflow = previousOverflow ?? ''
    }
  }, [dialogOpen])

  // 覆盖层从开到关的那一次渲染后，把焦点还给「展开」按钮。
  useEffect(() => {
    if (wasDialogOpen.current && !dialogOpen) {
      expandButtonRef.current?.focus()
    }
    wasDialogOpen.current = dialogOpen
  }, [dialogOpen])

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
    <section className="space-y-2 rounded-card border border-line bg-surface p-3 text-[13.5px]">
      <div className="flex items-center gap-2">
        <h3 className="font-medium text-ink-2">逻辑链</h3>
        {data && data.summary.total > 0 && (
          <span className="text-[11.5px] text-muted">
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
              onClick={() => {
                setMode(value)
                // 全屏图只在图形模式有意义，切走时一并收起。
                setExpanded(false)
              }}
              className={`rounded-control px-2 py-0.5 text-[11.5px] outline-none focus-visible:ring-1 focus-visible:ring-accent-soft disabled:cursor-not-allowed disabled:opacity-40 ${
                mode === value ? 'bg-accent-soft text-accent-ink' : 'text-muted'
              }`}
            >
              {label}
            </button>
          ))}
          {mode === 'graph' && (
            <button
              type="button"
              ref={expandButtonRef}
              aria-haspopup="dialog"
              aria-expanded={expanded}
              disabled={!data || data.chain.length === 0}
              onClick={() => setExpanded(true)}
              className="rounded-control px-2 py-0.5 text-[11.5px] text-muted outline-none focus-visible:ring-1 focus-visible:ring-accent-soft disabled:cursor-not-allowed disabled:opacity-40"
            >
              展开
            </button>
          )}
        </div>
      </div>
      <p className="text-[11.5px] text-muted">
        从正文里按连接词抽出，不做判断。问题清单在下面。
      </p>

      {loading && <p className="text-[11.5px] text-muted">正在读取正文…</p>}
      {error && <p className="text-[11.5px] text-danger">{error}</p>}

      {data && data.chain.length === 0 && (
        <p className="text-[11.5px] text-muted">{data.reason || '没有可展示的句子。'}</p>
      )}

      {data && data.chain.length > 0 && mode === 'graph' && (
        <div className="space-y-1">
          <p className="text-[11.5px] text-muted">
            按出现顺序相连，不代表句子真的指向哪一句。
          </p>
          <LogicChainGraph chain={data.chain} paragraphs={data.paragraphs} />
        </div>
      )}

      {data && data.chain.length > 0 && mode === 'text' && (
        <ul className="space-y-1">
          {data.chain.map((item, index) => (
            <li key={`${item.paragraph}-${index}`} className="flex gap-2 text-[11.5px]">
              <span className="w-8 shrink-0 text-faint">¶{item.paragraph}</span>
              <span className={`w-8 shrink-0 ${COLORS[item.kind] ?? 'text-muted'}`}>
                {item.kind_label}
              </span>
              <span className="flex-1 text-ink-2">{item.sentence}</span>
              <span className="shrink-0 text-faint">{item.marker}</span>
            </li>
          ))}
        </ul>
      )}

      {/* 全屏覆盖层：右栏太窄时把同一张图放大看，不另取数据。
          `overscroll-contain` 让滚到边界时不再把滚动传给下面的 main。 */}
      {dialogOpen && data && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="逻辑链图形视图"
          className="fixed inset-0 z-50 overflow-auto overscroll-contain bg-ink/30 p-4 md:p-8"
        >
          <div className="mx-auto max-w-6xl rounded-card border border-line bg-surface p-4">
            <div className="mb-3 flex items-center gap-2">
              <h3 className="font-medium text-ink">逻辑链 · 图形视图</h3>
              <button
                type="button"
                autoFocus
                onClick={() => setExpanded(false)}
                className="ml-auto rounded-control px-2 py-0.5 text-[11.5px] text-muted outline-none hover:text-ink focus-visible:ring-1 focus-visible:ring-accent-soft"
              >
                关闭
              </button>
            </div>
            <LogicChainGraph chain={data.chain} paragraphs={data.paragraphs} />
          </div>
        </div>
      )}
    </section>
  )
}
