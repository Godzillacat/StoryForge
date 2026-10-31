import { useState } from 'react'
import { api, type ChangeRow, type SnapshotView } from '../api/client'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { Input } from '../ui/Field'

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
    <Card title="版本与快照" className="space-y-3 text-[13.5px]">
      <p className="text-[11.5px] text-muted">
        快照记下结构与正文。灵感原话、运行记录与修订历史不在快照里，也不会被回滚。
      </p>

      <div className="flex flex-wrap items-center gap-2">
        <Input
          className="w-40"
          placeholder="快照名称"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <Input
          className="min-w-48 flex-1"
          placeholder="备注（可选）"
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
        <Button variant="primary" onClick={create} disabled={busy || !name.trim()}>
          新建快照
        </Button>
      </div>

      {notice && <p className="text-[11.5px] text-muted">{notice}</p>}

      {snapshots.length === 0 ? (
        <p className="text-[11.5px] text-muted">还没有快照。</p>
      ) : (
        <ul className="space-y-1">
          {snapshots.map((row) => (
            <li
              key={row.id}
              className="flex flex-wrap items-center gap-3 border-t border-line py-1"
            >
              <span className="text-ink-2">{row.name}</span>
              {row.auto && <Badge>自动备份</Badge>}
              <span className="text-[11.5px] text-muted">
                {row.volumes} 卷 / {row.chapters} 章 / {row.scenes} 场 / {row.words} 字
              </span>
              <span className="text-[11.5px] text-muted">
                {new Date(row.created_at).toLocaleString()}
              </span>
              {row.note && <span className="text-[11.5px] text-faint">{row.note}</span>}
              <span className="ml-auto flex items-center gap-2">
                <Button variant="ghost" size="sm" onClick={() => restore(row)} disabled={busy}>
                  回滚到此
                </Button>
                <Button variant="ghost" size="sm" onClick={() => remove(row)} disabled={busy}>
                  删除
                </Button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
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
    return <p className="text-[11.5px] text-muted">{emptyHint}</p>
  }
  return (
    <ul className="space-y-1 text-[13.5px]">
      {changes.map((row) => {
        const path = TARGET_PATHS[row.target_type]?.(row.target_id, projectId)
        return (
          <li
            key={row.id}
            className="flex flex-wrap items-center gap-2 border-t border-line py-1"
          >
            <span className="w-20 text-[11.5px] text-muted">{row.target_type_label}</span>
            {path ? (
              <a className="text-accent-ink underline-offset-2 hover:underline" href={path}>
                {row.target_label || '（已删除）'}
              </a>
            ) : (
              <span className="text-ink-2">{row.target_label || '（已删除）'}</span>
            )}
            <span className="text-[11.5px] text-muted">{row.action_label}</span>
            <span className="text-[11.5px] text-faint">{row.source_label}</span>
            {row.summary && <span className="text-[11.5px] text-muted">{row.summary}</span>}
            <span className="ml-auto text-[11.5px] text-faint">
              {new Date(row.created_at).toLocaleString()}
            </span>
          </li>
        )
      })}
    </ul>
  )
}
