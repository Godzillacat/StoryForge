import { useState } from 'react'
import { api } from '../api/client'
import { runProjectGuard } from '../lib/projectGuard'
import { useCurrentProject } from '../state/ProjectContext'
import { Button, IconButton } from '../ui/Button'
import { Dialog } from '../ui/Dialog'
import { Field, Input, Select } from '../ui/Field'
import { Icon } from '../ui/icons'

/**
 * 侧栏顶部的项目选择器：全站唯一的「当前项目」入口。
 * 折叠态只留一个首字母按钮 —— 点它先展开侧栏，再切换。
 */
export function ProjectSwitcher({ collapsed, onExpand }: { collapsed: boolean; onExpand: () => void }) {
  const { projects, projectId, project, loading, error: listError, select, refresh } = useCurrentProject()
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function create() {
    const value = name.trim()
    if (!value || busy) return
    // 新建之后会自动切到新项目 —— 和切项目一样要先过「未保存」这一关。
    if (!runProjectGuard()) return
    setBusy(true)
    setError('')
    try {
      const created = await api.createProject({ name: value })
      await refresh()
      select(created.id)
      setCreating(false)
      setName('')
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (collapsed) {
    return (
      <div className="mb-3 flex justify-center">
        <IconButton
          label="展开侧栏以切换项目"
          onClick={onExpand}
          className="h-8 w-8 border border-line bg-paper text-[12px] font-semibold text-accent-ink"
        >
          {(project?.name ?? '项').slice(0, 1)}
        </IconButton>
      </div>
    )
  }

  return (
    <div className="mb-3 px-1">
      <div className="mb-1 flex items-center justify-between">
        <span className="text-[11px] tracking-[.12em] text-muted">项目</span>
        <button
          type="button"
          onClick={() => setCreating(true)}
          className="inline-flex items-center gap-1 rounded-control px-1.5 py-0.5 text-[11.5px] text-muted transition-colors duration-[120ms] hover:bg-sunken hover:text-ink-2"
        >
          <Icon name="plus" size={13} />
          新建
        </button>
      </div>
      {projects.length > 0 ? (
        <Select
          aria-label="当前项目"
          value={projectId}
          onChange={(event) => {
            if (runProjectGuard()) select(event.target.value)
          }}
          options={projects.map((row) => ({ value: row.id, label: row.name }))}
        />
      ) : listError ? (
        <p className="text-[11.5px] leading-relaxed text-warn">读取项目列表失败：{listError}</p>
      ) : (
        <p className="text-[12px] text-muted">{loading ? '读取中…' : '还没有项目'}</p>
      )}
      {listError ? (
        <button
          type="button"
          onClick={() => void refresh()}
          className="mt-1 rounded-control px-1.5 py-0.5 text-[11.5px] text-warn transition-colors duration-[120ms] hover:bg-warn-soft"
        >
          重试
        </button>
      ) : null}

      <Dialog
        open={creating}
        title="新建项目"
        onClose={() => setCreating(false)}
        footer={
          <>
            <Button onClick={() => setCreating(false)}>取消</Button>
            <Button variant="primary" onClick={() => void create()} disabled={busy || !name.trim()}>
              创建
            </Button>
          </>
        }
      >
        <Field label="项目名称">
          <Input
            autoFocus
            value={name}
            placeholder="例如：南滨旧城"
            onChange={(event) => setName(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') void create()
            }}
          />
        </Field>
        {error ? <p className="mt-2 text-[12px] text-danger">{error}</p> : null}
      </Dialog>
    </div>
  )
}
