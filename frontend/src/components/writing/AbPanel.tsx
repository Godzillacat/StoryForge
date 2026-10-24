import { useEffect, useRef, useState } from 'react'
import {
  api,
  streamSceneGeneration,
  type AbBranch,
  type AbSession,
} from '../../api/client'
import { diffParagraphs } from '../../lib/abDiff'

type Side = 'A' | 'B'

interface SideView {
  /** 这一版的正文：生成中逐段追加；刷新后从草稿读回。 */
  text: string
  /** 这一版自己的失败原因；另一版不受影响。 */
  error: string
}

function emptySides(): Record<Side, SideView> {
  return { A: { text: '', error: '' }, B: { text: '', error: '' } }
}

/** `side` 由库名解析而来；正常只有 A/B，兜底把认不出的按 A 处理。 */
function sideOf(branch: AbBranch): Side {
  return branch.side === 'B' ? 'B' : 'A'
}

export default function AbPanel({
  sceneId,
  locked,
  disabled = false,
  onAdopted,
}: {
  sceneId: string
  locked: boolean
  disabled?: boolean
  onAdopted: () => void
}) {
  const [session, setSession] = useState<AbSession | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [runningSide, setRunningSide] = useState<Side | null>(null)
  const [sides, setSides] = useState<Record<Side, SideView>>(emptySides)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  // 切场景时旧响应不许覆盖新面板 —— 与 BranchPanel 用同一种令牌。
  const token = useRef(0)
  const streamRef = useRef<Record<Side, string>>({ A: '', B: '' })
  const abortRef = useRef<AbortController | null>(null)

  async function reload(): Promise<AbSession | null> {
    const current = token.current
    try {
      const data = await api.getAb(sceneId)
      if (token.current !== current) return null
      setSession(data)
      // 组已经结束（采纳或两条都丢掉）：两栏的正文随之清掉，别留到下一次。
      if (!data.group) setSides(emptySides())
      return data
    } catch (e) {
      if (token.current === current) setError((e as Error).message)
      return null
    }
  }

  async function loadPreviews(branches: AbBranch[], current: number) {
    // GET 只给字数、不给正文；继续态要能先读一遍再选，所以逐版回读草稿。
    await Promise.all(
      branches
        .filter((branch) => branch.has_draft)
        .map(async (branch) => {
          try {
            const detail = await api.getBranch(branch.id)
            const content = detail.draft?.content ?? ''
            if (!content || token.current !== current) return
            const side = sideOf(branch)
            setSides((prev) => ({ ...prev, [side]: { ...prev[side], text: content } }))
          } catch {
            // 预览是辅助信息：取不到不影响采纳与丢弃。
          }
        }),
    )
  }

  useEffect(() => {
    token.current += 1
    const current = token.current
    abortRef.current?.abort()
    abortRef.current = null
    setSession(null)
    setSides(emptySides())
    setError('')
    setNotice('')
    setBusy(false)
    setRunningSide(null)
    setLoading(true)
    void (async () => {
      const data = await reload()
      if (data) await loadPreviews(data.branches, current)
      if (token.current === current) setLoading(false)
    })()
    return () => {
      // 切场景或卸载时中止在途生成：流读取器不能留在已作废的场景上。
      token.current += 1
      abortRef.current?.abort()
    }
    // sceneId 变了就整块重来；reload / loadPreviews 是闭包，不必进依赖。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sceneId])

  async function discardBranches(branches: AbBranch[], current: number) {
    for (const branch of branches) {
      if (token.current !== current) return
      await api.discardAb(sceneId, branch.id)
    }
  }

  /** 生成一版：流式正文进自己那一栏，结束后回读字数与 has_draft。 */
  async function runSide(branch: AbBranch, current: number) {
    const side = sideOf(branch)
    streamRef.current[side] = ''
    setRunningSide(side)
    setSides((prev) => ({ ...prev, [side]: { text: '', error: '' } }))
    const controller = new AbortController()
    abortRef.current = controller
    let failure = ''
    try {
      await streamSceneGeneration(
        sceneId,
        {
          onDelta: (text) => {
            if (token.current !== current) return
            streamRef.current[side] += text
            const next = streamRef.current[side]
            setSides((prev) => ({ ...prev, [side]: { ...prev[side], text: next } }))
          },
          onError: (data) => {
            if (token.current !== current) return
            failure =
              data.chars > 0
                ? `${data.message}（已保留 ${data.chars} 字）`
                : data.message
          },
        },
        controller.signal,
        branch.id,
      )
    } catch (e) {
      if (token.current === current && (e as Error).name !== 'AbortError') {
        failure = (e as Error).message
      }
    } finally {
      if (abortRef.current === controller) abortRef.current = null
    }
    if (token.current !== current) return
    if (failure) {
      setSides((prev) => ({ ...prev, [side]: { ...prev[side], error: failure } }))
    }
    // 不论成败都以服务端为准：失败时也可能已保留了部分草稿。
    await reload()
    if (failure && token.current === current) {
      // 失败时服务端保留的不一定是刚流出来的这段（也可能一条都没留）：
      // 预览必须与「用这一版」实际采纳的内容一致，所以回读服务端草稿。
      try {
        const detail = await api.getBranch(branch.id)
        if (token.current === current) {
          const content = detail.draft?.content ?? ''
          setSides((prev) => ({ ...prev, [side]: { ...prev[side], text: content } }))
        }
      } catch {
        // 回读失败就保留本地流式内容 —— 报错原因已经说清了哪一版没写完。
      }
    }
    if (token.current === current) setRunningSide(null)
  }

  async function generate() {
    if (!sceneId || disabled || locked || busy || runningSide) return
    const current = token.current
    setBusy(true)
    setError('')
    setNotice('')
    setSides(emptySides())
    try {
      // 建组前现查一次：旧组不清理、普通分支列表又过滤 A/B，它那两条分支
      // 在刷新后就再也找不回来（GET 只给最近一组）。
      const existing = await api.getAb(sceneId)
      if (token.current !== current) return
      if (existing.group) {
        const message =
          '这一场还有一组没处理的 A/B。\n\n' +
          '开始新的会先把旧的两版都丢掉；正文不受影响。继续？'
        if (!window.confirm(message)) return
        await discardBranches(existing.branches, current)
        if (token.current !== current) return
      }
      const created = await api.createAb(sceneId)
      if (token.current !== current) return
      setSession(created)
      // 建组是两条从主版继承正文的分支：先回读一次拿准字数与 has_draft。
      const canonical = await reload()
      // 先 A 后 B：SQLite 单写者，两条流同时写会互相等；顺序跑也才说得清
      // 哪一版没出来。A 失败不影响 B，之后可按栏重试。
      for (const branch of (canonical ?? created).branches) {
        if (token.current !== current) return
        await runSide(branch, current)
      }
    } catch (e) {
      if (token.current === current) {
        setError((e as Error).message)
        // 半途失败（例如旧组只丢了一条）时界面必须回到真实状态。
        await reload()
      }
    } finally {
      if (token.current === current) setBusy(false)
    }
  }

  async function retry(side: Side) {
    if (disabled || locked || busy || runningSide) return
    const branch = session?.branches.find((item) => sideOf(item) === side)
    if (!branch) return
    const current = token.current
    setBusy(true)
    setError('')
    setNotice('')
    try {
      await runSide(branch, current)
    } finally {
      if (token.current === current) setBusy(false)
    }
  }

  async function adopt(side: Side) {
    if (disabled || locked || busy || runningSide) return
    const branch = session?.branches.find((item) => sideOf(item) === side)
    if (!branch || !branch.has_draft) return
    const message =
      `用 ${side} 版替换这一场的正文？\n\n` +
      '当前正文（若有）会进修订历史（来源「分支」），另一版会一起丢弃。'
    if (!window.confirm(message)) return
    const current = token.current
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const result = await api.adoptAb(sceneId, branch.id)
      if (token.current !== current) return
      setSession({ group: null, branches: [] })
      setSides(emptySides())
      setNotice(
        `已采纳 ${side} 版（${result.chars} 字）` +
          (result.revision_created ? '，修订历史里能看到这一版' : ''),
      )
      // 正文与章节树的刷新交给 Writing —— 面板不另造状态源。
      onAdopted()
    } catch (e) {
      if (token.current === current) setError((e as Error).message)
    } finally {
      if (token.current === current) setBusy(false)
    }
  }

  async function discardOne(side: Side) {
    if (disabled || busy || runningSide) return
    const branch = session?.branches.find((item) => sideOf(item) === side)
    if (!branch) return
    if (!window.confirm(`丢弃 ${side} 版？正文和另一版都不受影响。`)) return
    const current = token.current
    setBusy(true)
    setError('')
    setNotice('')
    try {
      await api.discardAb(sceneId, branch.id)
      if (token.current !== current) return
      setSides((prev) => ({ ...prev, [side]: { text: '', error: '' } }))
      setNotice(`已丢弃 ${side} 版`)
      // 只删这一条：另一条仍在时 GET 继续返回它；两条都没了就回到「没有组」。
      await reload()
    } catch (e) {
      if (token.current === current) setError((e as Error).message)
    } finally {
      if (token.current === current) setBusy(false)
    }
  }

  async function discardAll() {
    if (disabled || busy || runningSide) return
    const branches = session?.branches ?? []
    if (!session?.group || branches.length === 0) return
    if (!window.confirm('两版都不要？两版草稿会被删除，正文不动。')) return
    const current = token.current
    setBusy(true)
    setError('')
    setNotice('')
    try {
      await discardBranches(branches, current)
      if (token.current !== current) return
      setSession({ group: null, branches: [] })
      setSides(emptySides())
      setNotice('两版都已丢弃，正文没有变')
    } catch (e) {
      if (token.current === current) {
        setError((e as Error).message)
        // 可能只丢掉了一条：回到服务端的真实状态，别在界面上假装两条都没了。
        await reload()
      }
    } finally {
      if (token.current === current) setBusy(false)
    }
  }

  const branches = session?.branches ?? []
  const buttonsDisabled = busy || runningSide !== null || disabled
  // 两栏都有正文时才比差异；生成中 B 还没出来时先不显示。
  const diff =
    sides.A.text.trim() !== '' && sides.B.text.trim() !== ''
      ? diffParagraphs(sides.A.text, sides.B.text)
      : null

  return (
    <section className="space-y-2 rounded border border-slate-800 p-3 text-sm">
      <div className="flex items-center gap-2">
        <h3 className="font-medium text-slate-300">A/B 并排</h3>
        <span className="text-xs text-slate-500">
          {runningSide
            ? `正在生成 ${runningSide} 版…`
            : session?.group
              ? '有一组未处理'
              : '同一份上下文，两版选一'}
        </span>
      </div>
      <p className="text-xs text-slate-500">
        两版用同一场景卡、同一智能体生成；采纳一版会替换正文（旧正文进修订历史），另一版一起丢弃。
      </p>

      {locked && (
        <p className="text-xs text-amber-400">这一场已锁定：不能并排生成，也不能采纳。</p>
      )}
      {error && <p className="text-xs text-red-400">{error}</p>}
      {notice && <p className="text-xs text-slate-400">{notice}</p>}

      {loading && <p className="text-xs text-slate-500">正在读取这一场的 A/B…</p>}

      {!loading && !session?.group && (
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="rounded bg-indigo-600 px-3 py-1 text-xs text-white hover:bg-indigo-500 disabled:opacity-50"
            onClick={() => void generate()}
            disabled={locked || busy || runningSide !== null || disabled}
            title={locked ? '这一场已锁定' : undefined}
          >
            A/B 并排生成
          </button>
          {locked && <span className="text-xs text-amber-400">这一场已锁定</span>}
        </div>
      )}

      {!loading && session?.group && (
        <div className="space-y-2">
          <div
            className={`grid gap-2 ${branches.length > 1 ? 'grid-cols-2' : 'grid-cols-1'}`}
          >
            {branches.map((branch) => {
              const side = sideOf(branch)
              const view = sides[side]
              return (
                <div
                  key={branch.id}
                  className="flex min-w-0 flex-col gap-1 rounded border border-slate-800 bg-slate-950/50 p-2"
                >
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
                    <span className="font-medium text-slate-200" title={branch.label}>
                      {side} 版
                    </span>
                    {runningSide === side ? (
                      <span className="text-slate-500">生成中…</span>
                    ) : (
                      <>
                        <span className="text-slate-500">{branch.chars} 字</span>
                        {branch.has_draft ? (
                          <span className="text-emerald-400">有草稿</span>
                        ) : (
                          <span className="text-slate-500">还没有草稿</span>
                        )}
                      </>
                    )}
                    {diff && <span className="text-slate-500">差异 {diff.changed} 段</span>}
                  </div>
                  <pre className="max-h-56 overflow-auto whitespace-pre-wrap break-words text-xs leading-6 text-slate-300">
                    {view.text ||
                      (branch.has_draft
                        ? '草稿已生成。'
                        : '生成后这里显示这一版的正文。')}
                  </pre>
                  {view.error && <p className="text-xs text-red-400">{view.error}</p>}
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      className="rounded bg-emerald-700 px-2 py-1 text-xs text-white hover:bg-emerald-600 disabled:opacity-50"
                      onClick={() => void adopt(side)}
                      disabled={buttonsDisabled || locked || !branch.has_draft}
                      title={
                        locked
                          ? '这一场已锁定'
                          : branch.has_draft
                            ? undefined
                            : '这一版还没有草稿'
                      }
                    >
                      用这一版
                    </button>
                    {(!branch.has_draft || view.error !== '') && (
                      <button
                        type="button"
                        className="rounded border border-indigo-800 px-2 py-1 text-xs text-indigo-300 hover:text-white disabled:opacity-50"
                        onClick={() => void retry(side)}
                        disabled={buttonsDisabled || locked}
                      >
                        重试这一版
                      </button>
                    )}
                    <button
                      type="button"
                      className="rounded border border-slate-700 px-2 py-1 text-xs text-slate-400 hover:text-white disabled:opacity-50"
                      onClick={() => void discardOne(side)}
                      disabled={buttonsDisabled}
                    >
                      丢弃这一版
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
          <button
            type="button"
            className="rounded border border-amber-800 px-2 py-1 text-xs text-amber-300 hover:text-amber-200 disabled:opacity-50"
            onClick={() => void discardAll()}
            disabled={buttonsDisabled}
          >
            两版都不要
          </button>
        </div>
      )}
    </section>
  )
}
