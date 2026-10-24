import { useEffect, useRef, useState } from 'react'
import {
  api,
  streamSceneGeneration,
  type BranchDetail,
  type BranchRevisionRow,
  type BranchSummary,
} from '../../api/client'
import { buildBranchRows, defaultChildName } from '../../lib/branchTree'

export default function BranchPanel({
  sceneId,
  selectedBranchId,
  onSelect,
  onMerged,
  disabled,
}: {
  sceneId: string
  selectedBranchId: string | null
  onSelect: (branchId: string | null) => void
  onMerged: () => void
  disabled: boolean
}) {
  const [rows, setRows] = useState<BranchSummary[]>([])
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  // 切场景时旧响应不许覆盖新列表 —— 列表会串成上一个场景的分支。
  const token = useRef(0)
  // 树形排序：根在前、子紧随父；缩进与父名由 buildBranchRows 算。
  const treeRows = buildBranchRows(rows)

  async function reload() {
    const current = token.current
    try {
      const list = await api.listBranches(sceneId)
      if (token.current === current) setRows(list)
    } catch (error) {
      if (token.current === current) setNotice((error as Error).message)
    }
  }

  useEffect(() => {
    token.current += 1
    setRows([])
    setNotice('')
    void reload()
    // sceneId 变了就重新拉；reload 是闭包，不必进依赖。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sceneId])

  async function create() {
    if (!name.trim()) return
    setBusy(true)
    setNotice('')
    try {
      const row = await api.createBranch(sceneId, { name: name.trim() })
      setName('')
      await reload()
      onSelect(row.id)
    } catch (error) {
      setNotice((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  /**
   * 从这一条派生：新分支复制父分支正文，挂在这条下面（最多三层）。
   * 默认名先避让当前列表（「父名 · 派生」「… 2」「… 3」），**在打开
   * prompt 前算好**；作者改完名提交时若仍重名，后端照旧 400、错误原样
   * 显示 —— 前端不静默加序号、也不替后端做唯一性判断。
   */
  async function derive(parent: BranchSummary) {
    const suggested = defaultChildName(
      parent.name,
      rows.map((row) => row.name),
    )
    const input = window.prompt('新分支名称（正文从这一版复制）', suggested)
    if (input === null) return
    const clean = input.trim()
    if (!clean) return
    setBusy(true)
    setNotice('')
    try {
      const row = await api.createBranch(sceneId, {
        name: clean,
        parent_id: parent.id,
      })
      await reload()
      onSelect(row.id)
    } catch (error) {
      setNotice((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function merge(row: BranchSummary) {
    const message =
      `把分支「${row.name}」合入主版？\n\n` +
      '主版当前正文会被替换；替换前那一版会进修订历史（来源「分支」），可以恢复。\n' +
      '分支本身会保留，不会删除。'
    if (!window.confirm(message)) return
    setBusy(true)
    setNotice('')
    try {
      const result = await api.mergeBranch(row.id)
      setNotice(`已合入主版（${result.chars} 字）；分支「${row.name}」仍在`)
      await reload()
      onMerged()
    } catch (error) {
      setNotice((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function discard(row: BranchSummary) {
    if (!window.confirm(`丢弃分支「${row.name}」？主版不受影响。`)) return
    setBusy(true)
    try {
      await api.discardBranch(row.id)
      if (selectedBranchId === row.id) onSelect(null)
      await reload()
    } catch (error) {
      setNotice((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="space-y-2 rounded border border-slate-800 p-3 text-sm">
      <div className="flex items-center gap-2">
        <h3 className="font-medium text-slate-300">分支</h3>
        <span className="text-xs text-slate-500">
          {rows.length > 0 ? `${rows.length} 条` : '没有分支'}
        </span>
      </div>
      <p className="text-xs text-slate-500">
        分支是同一场戏的另一种写法；场景卡（目标 / 冲突 / 转折）是共享的。
        可以从任意一版「派生」出新分支，最多三层。
      </p>

      {notice && <p className="text-xs text-slate-400">{notice}</p>}

      <div className="flex items-center gap-2">
        <input
          className="min-w-0 flex-1 rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs"
          placeholder="分支名称，例如「A 案」"
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={disabled || busy}
        />
        <button
          className="rounded border border-slate-700 px-2 py-1 text-xs disabled:opacity-50"
          onClick={create}
          disabled={disabled || busy || !name.trim()}
        >
          开分支
        </button>
      </div>

      <ul className="space-y-1">
        <li>
          <button
            className={`w-full rounded px-2 py-1 text-left text-xs ${
              selectedBranchId === null
                ? 'bg-slate-800 text-white'
                : 'text-slate-400 hover:bg-slate-900'
            }`}
            onClick={() => onSelect(null)}
          >
            主版
          </button>
        </li>
        {treeRows.map((row) => (
          <li key={row.id} className="space-y-1">
            <div
              className="flex items-center gap-2"
              style={{ paddingLeft: row.indent }}
            >
              <button
                className={`min-w-0 flex-1 truncate rounded px-2 py-1 text-left text-xs ${
                  selectedBranchId === row.id
                    ? 'bg-slate-800 text-white'
                    : 'text-slate-400 hover:bg-slate-900'
                }`}
                onClick={() => onSelect(row.id)}
              >
                <span className="block truncate">
                  {row.name}
                  <span className="ml-2 text-slate-600">{row.chars} 字</span>
                  {row.has_draft && (
                    <span className="ml-1 text-emerald-400">有草稿</span>
                  )}
                </span>
                {row.parentName && (
                  <span className="block truncate text-[10px] text-slate-600">
                    派生自 {row.parentName}
                  </span>
                )}
              </button>
              <button
                className="text-xs text-sky-400 disabled:opacity-50"
                onClick={() => derive(row)}
                disabled={disabled || busy || row.depth >= 3}
                title={
                  row.depth >= 3 ? '最多三层分支' : '从这一版派生（正文复制过来）'
                }
              >
                派生
              </button>
              <button
                className="text-xs text-amber-400 disabled:opacity-50"
                onClick={() => merge(row)}
                disabled={disabled || busy}
                title="合入主版（分支保留）"
              >
                合入
              </button>
              <button
                className="text-xs text-slate-500 disabled:opacity-50"
                onClick={() => discard(row)}
                disabled={disabled || busy}
              >
                丢弃
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

export function BranchBodyEditor({
  branch,
  sceneId,
  busy,
  onChange,
  onSaved,
}: {
  branch: BranchDetail
  sceneId: string
  busy: boolean
  onChange: (content: string) => void
  onSaved: () => void
}) {
  const [saving, setSaving] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [stream, setStream] = useState('')
  const [error, setError] = useState('')
  const [revisions, setRevisions] = useState<BranchRevisionRow[]>([])
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    setRevisions([])
    setStream('')
    setError('')
    api
      .listBranchRevisions(branch.id)
      .then(setRevisions)
      .catch(() => undefined)
  }, [branch.id])

  // 分支的 AI 与主版的 AI 是同一条链路：锁定、段落锁、记账全部照旧。
  async function generate() {
    setGenerating(true)
    setError('')
    setStream('')
    const controller = new AbortController()
    abortRef.current = controller
    try {
      await streamSceneGeneration(
        sceneId,
        {
          onDelta: (text) => setStream((current) => current + text),
          onError: (data) => setError(data.message),
        },
        controller.signal,
        branch.id,
      )
      onSaved()
    } catch (e) {
      if ((e as Error).name !== 'AbortError') setError((e as Error).message)
    } finally {
      setGenerating(false)
      abortRef.current = null
    }
  }

  function stop() {
    abortRef.current?.abort()
  }

  async function save() {
    setSaving(true)
    setError('')
    try {
      await api.saveBranchBody(branch.id, branch.content)
      onSaved()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  async function saveDraft() {
    if (!branch.draft) return
    setSaving(true)
    setError('')
    try {
      await api.saveBranchDraft(branch.id, branch.draft.content)
      onSaved()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  async function adopt() {
    setSaving(true)
    setError('')
    try {
      await api.adoptBranchDraft(branch.id)
      onSaved()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const disabled = busy || saving || generating

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-300">
          正在看：分支「{branch.name}」
        </span>
        {generating ? (
          <button
            className="rounded bg-amber-600 px-3 py-1 text-xs text-white"
            onClick={stop}
          >
            停止
          </button>
        ) : (
          <button
            className="rounded bg-indigo-600 px-3 py-1 text-xs text-white disabled:opacity-50"
            onClick={generate}
            disabled={disabled}
          >
            生成到这条分支
          </button>
        )}
        <button
          className="rounded border border-slate-700 px-3 py-1 text-xs disabled:opacity-50"
          onClick={save}
          disabled={disabled}
        >
          保存分支正文
        </button>
        {error && <span className="text-xs text-red-400">{error}</span>}
      </div>

      <textarea
        className="h-96 w-full rounded border border-slate-700 bg-slate-950 p-3 font-mono text-sm leading-7"
        value={branch.content}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        placeholder="这条分支的正文。"
      />

      {branch.draft && (
        <div className="space-y-2 rounded border border-emerald-900 bg-emerald-950/20 p-2">
          <div className="flex items-center gap-2 text-xs text-emerald-300">
            <span>分支草稿</span>
            <button
              className="rounded border border-emerald-800 px-2 py-0.5 disabled:opacity-50"
              onClick={saveDraft}
              disabled={disabled}
            >
              保存草稿
            </button>
            <button
              className="rounded bg-emerald-700 px-2 py-0.5 text-white disabled:opacity-50"
              onClick={adopt}
              disabled={disabled}
            >
              采纳为分支正文
            </button>
          </div>
          <pre className="max-h-48 overflow-auto whitespace-pre-wrap text-xs text-slate-300">
            {branch.draft.content}
          </pre>
        </div>
      )}

      {(stream || generating) && (
        <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded border border-slate-800 bg-slate-950 p-2 text-xs text-slate-400">
          {stream || '正在生成…'}
        </pre>
      )}

      {revisions.length > 0 && (
        <div className="space-y-1 text-xs text-slate-500">
          <p>这条分支的修订（{revisions.length}）</p>
          <ul className="space-y-0.5">
            {revisions.slice(0, 10).map((item) => (
              <li key={item.id}>
                {item.source === 'ai' ? 'AI 采纳' : '作者保存'} · {item.chars} 字 ·{' '}
                {new Date(item.created_at).toLocaleString()}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
