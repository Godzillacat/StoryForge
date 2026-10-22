import { useState } from 'react'
import { api, type ChangeRow, type SnapshotView } from '../api/client'

export function SnapshotPanel({
  projectId,
  snapshots,
  onReload,
  onRestored,
}: {
  projectId: string
  snapshots: SnapshotView[]
  onReload: () => void
  onRestored?: () => void
}) {
  const [name, setName] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')

  async function create() {
    setBusy(true)
    setNotice('')
    try {
      await api.createSnapshot(projectId, { name, note })
      setName('')
      setNote('')
      setNotice('已创建快照')
      onReload()
    } catch (error) {
      setNotice((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function restore(row: SnapshotView) {
    const message =
      `回滚会把整个项目结构恢复到「${row.name}」（${row.volumes} 卷 / ${row.chapters} 章 / ` +
      `${row.scenes} 场 / ${row.words} 字）。\n\n` +
      '此后新增的卷、章、场景、设定条目、时间线与伏笔都会被移除；' +
      '灵感原话、运行记录、修订历史与审计问题不受影响。\n\n' +
      '回滚前会自动存一份备份，回滚本身可以撤销。继续？'
    if (!window.confirm(message)) return
    setBusy(true)
    setNotice('')
    try {
      const result = await api.restoreSnapshot(row.id)
      setNotice(
        result.backup
          ? `已回滚；回滚前自动备份为「${result.backup.name}」`
          : '已回滚（回滚的是一份自动备份，不再另存备份）',
      )
      onReload()
      onRestored?.()
    } catch (error) {
      setNotice((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function remove(row: SnapshotView) {
    if (!window.confirm(`删除快照「${row.name}」？项目本身不受影响。`)) return
    setBusy(true)
    try {
      await api.deleteSnapshot(row.id)
      onReload()
    } catch (error) {
      setNotice((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="space-y-3 rounded border border-slate-800 p-4 text-sm">
      <h3 className="text-sm font-medium text-slate-300">版本与快照</h3>
      <p className="text-xs text-slate-500">
        快照记下结构与正文。灵感原话、运行记录与修订历史不在快照里，也不会被回滚。
      </p>

      <div className="flex flex-wrap items-center gap-2">
        <input
          className="rounded border border-slate-700 bg-slate-900 px-3 py-1.5 text-sm"
          placeholder="快照名称"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <input
          className="min-w-48 flex-1 rounded border border-slate-700 bg-slate-900 px-3 py-1.5 text-sm"
          placeholder="备注（可选）"
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
        <button
          className="rounded bg-indigo-600 px-3 py-1.5 disabled:opacity-50"
          onClick={create}
          disabled={busy || !name.trim()}
        >
          新建快照
        </button>
      </div>

      {notice && <p className="text-xs text-slate-400">{notice}</p>}

      {snapshots.length === 0 ? (
        <p className="text-xs text-slate-500">还没有快照。</p>
      ) : (
        <ul className="space-y-1">
          {snapshots.map((row) => (
            <li
              key={row.id}
              className="flex flex-wrap items-center gap-3 border-t border-slate-800 py-1"
            >
              <span className="text-slate-300">{row.name}</span>
              {row.auto && (
                <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-400">
                  自动备份
                </span>
              )}
              <span className="text-xs text-slate-500">
                {row.volumes} 卷 / {row.chapters} 章 / {row.scenes} 场 / {row.words} 字
              </span>
              <span className="text-xs text-slate-500">
                {new Date(row.created_at).toLocaleString()}
              </span>
              {row.note && <span className="text-xs text-slate-600">{row.note}</span>}
              <span className="ml-auto space-x-2 text-xs">
                <button
                  className="text-amber-400 disabled:opacity-50"
                  onClick={() => restore(row)}
                  disabled={busy}
                >
                  回滚到此
                </button>
                <button
                  className="text-slate-500 disabled:opacity-50"
                  onClick={() => remove(row)}
                  disabled={busy}
                >
                  删除
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

const TARGET_PATHS: Record<string, (id: string, projectId: string) => string> = {
  scene: (id, project) => `/write?project=${project}&scene=${id}`,
  chapter: (_id, project) => `/chapters?project=${project}`,
  volume: (_id, project) => `/chapters?project=${project}`,
  entry: (id, project) => `/world?project=${project}&entry=${id}`,
  architecture: (_id, project) => `/architecture?project=${project}`,
  snapshot: (_id, project) => `/dashboard?project=${project}`,
}

export function ChangeList({
  projectId,
  changes,
  emptyHint = '还没有改动记录。',
}: {
  projectId: string
  changes: ChangeRow[]
  emptyHint?: string
}) {
  if (changes.length === 0) {
    return <p className="text-xs text-slate-500">{emptyHint}</p>
  }
  return (
    <ul className="space-y-1 text-sm">
      {changes.map((row) => {
        const path = TARGET_PATHS[row.target_type]?.(row.target_id, projectId)
        return (
          <li
            key={row.id}
            className="flex flex-wrap items-center gap-2 border-t border-slate-800 py-1"
          >
            <span className="w-20 text-xs text-slate-500">{row.target_type_label}</span>
            {path ? (
              <a className="text-indigo-400" href={path}>
                {row.target_label || '（已删除）'}
              </a>
            ) : (
              <span className="text-slate-300">{row.target_label || '（已删除）'}</span>
            )}
            <span className="text-xs text-slate-400">{row.action_label}</span>
            <span className="text-xs text-slate-600">{row.source_label}</span>
            {row.summary && <span className="text-xs text-slate-500">{row.summary}</span>}
            <span className="ml-auto text-xs text-slate-600">
              {new Date(row.created_at).toLocaleString()}
            </span>
          </li>
        )
      })}
    </ul>
  )
}
