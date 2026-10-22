import { useEffect, useState } from 'react'
import { api, type BranchDetail, type BranchSummary } from '../../api/client'

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

  async function reload() {
    try {
      setRows(await api.listBranches(sceneId))
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  useEffect(() => {
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
        {rows.map((row) => (
          <li key={row.id} className="space-y-1">
            <div className="flex items-center gap-2">
              <button
                className={`min-w-0 flex-1 truncate rounded px-2 py-1 text-left text-xs ${
                  selectedBranchId === row.id
                    ? 'bg-slate-800 text-white'
                    : 'text-slate-400 hover:bg-slate-900'
                }`}
                onClick={() => onSelect(row.id)}
              >
                {row.name}
                <span className="ml-2 text-slate-600">{row.chars} 字</span>
                {row.has_draft && <span className="ml-1 text-emerald-400">有草稿</span>}
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
  busy,
  onChange,
  onSaved,
}: {
  branch: BranchDetail
  busy: boolean
  onChange: (content: string) => void
  onSaved: () => void
}) {
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

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

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <span className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-300">
          正在看：分支「{branch.name}」
        </span>
        <button
          className="rounded border border-slate-700 px-3 py-1 text-xs disabled:opacity-50"
          onClick={save}
          disabled={busy || saving}
        >
          保存分支正文
        </button>
        {error && <span className="text-xs text-red-400">{error}</span>}
      </div>
      <textarea
        className="h-96 w-full rounded border border-slate-700 bg-slate-950 p-3 font-mono text-sm leading-7"
        value={branch.content}
        onChange={(e) => onChange(e.target.value)}
        disabled={busy || saving}
        placeholder="这条分支的正文。"
      />
    </div>
  )
}
