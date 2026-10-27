import { Fragment, useState } from 'react'
import { api, type CharacterDriftData } from '../../api/client'
import {
  buildDriftGrid,
  type DriftCell,
  type DriftChapter,
  type DriftRow,
} from '../../lib/characterDrift'
import { Button } from '../../ui/Button'

/** 表头只放得下几个字：章标题截断，全文进悬停提示。 */
function shortLabel(label: string): string {
  return label.length > 8 ? `${label.slice(0, 7)}…` : label
}

/** 悬停 / 提示里的完整章名。两卷都可能有「第1章 雨夜」，带上卷名才分得开。 */
function chapterTitle(chapter: DriftChapter): string {
  return chapter.volumeLabel
    ? `${chapter.volumeLabel} · ${chapter.label}`
    : chapter.label
}

/** 正在编辑的格子。`exists` = 这一格已经有记录（决定是否给「删除」）。 */
interface EditTarget {
  chapterId: string
  entryId: string
  chapterLabel: string
  name: string
  note: string
  exists: boolean
}

export default function CharacterDrift({
  data,
  loading,
  error,
  onReload,
  onNotice,
}: {
  data: CharacterDriftData | null
  loading: boolean
  error: string
  /** 保存 / 删除后**重取整本**：`changed` 由后端按「上一条记录」重算，前端不猜。 */
  onReload: () => Promise<void>
  onNotice: (message: string) => void
}) {
  const [editing, setEditing] = useState<EditTarget | null>(null)
  const [text, setText] = useState('')
  // 正在写库：防止双击连发两次 PUT（第二次会覆盖第一次，作者却以为没生效）。
  const [saving, setSaving] = useState(false)
  // 保存失败的文案就地显示：页头提示离格子太远，作者找不到是哪一格出错。
  const [editError, setEditError] = useState('')

  if (error) {
    return (
      <p className="rounded-card border-l-2 border-danger bg-surface p-4 text-[13.5px] text-danger">
        读取性格漂移失败：{error}
      </p>
    )
  }
  if (loading || !data) {
    return (
      <p className="rounded-card border border-line bg-surface p-4 text-[13.5px] text-muted">
        正在读取性格漂移…
      </p>
    )
  }

  const grid = buildDriftGrid(data)
  const { chapters, rows, totals } = grid
  const sparseNames = rows
    .filter((row) => row.recorded === 1)
    .map((row) => row.name)
    .join('、')

  function openEditor(row: DriftRow, chapter: DriftChapter, cell: DriftCell | null) {
    // 预填现值：空格子预填空串 = 新增；有记录的格子预填那句状态 = 改它。
    setEditing({
      chapterId: chapter.id,
      entryId: row.entryId,
      chapterLabel: chapterTitle(chapter),
      name: row.name,
      note: cell?.note ?? '',
      exists: cell !== null,
    })
    setText(cell?.note ?? '')
    setEditError('')
  }

  function closeEditor() {
    setEditing(null)
    setText('')
    setEditError('')
  }

  async function save() {
    if (!editing || saving) return
    const note = text.trim()
    if (!note) {
      setEditError('状态不能为空')
      return
    }
    setSaving(true)
    setEditError('')
    const { chapterId, entryId, name, chapterLabel } = editing
    try {
      await api.putCharacterState(chapterId, entryId, note)
      // 先关编辑器再重取：重取后这一格的内容以服务端为准，不在这里拼乐观结果。
      closeEditor()
      await onReload()
      onNotice(`已记录「${name}」在${chapterLabel}的状态。`)
    } catch (error) {
      setEditError((error as Error).message)
    } finally {
      setSaving(false)
    }
  }

  async function remove() {
    if (!editing || saving || !editing.exists) return
    setSaving(true)
    setEditError('')
    const { chapterId, entryId, name, chapterLabel } = editing
    try {
      await api.deleteCharacterState(chapterId, entryId)
      closeEditor()
      // 删掉中间一条会让后面格子的 `changed` 重算，所以必须整本重取。
      await onReload()
      onNotice(`已删掉「${name}」在${chapterLabel}的状态。`)
    } catch (error) {
      setEditError((error as Error).message)
    } finally {
      setSaving(false)
    }
  }

  if (rows.length === 0) {
    return (
      <div className="space-y-2">
        <p className="rounded-card border border-line bg-surface p-4 text-[13.5px] text-muted">
          {data.reason || '还没有状态记录'}
        </p>
        <p className="text-[11.5px] text-faint">
          先在「结构设计」排好卷章、在「世界观」建好人物；之后在这里点任意格子，
          给人物记一行当时的状态。
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-baseline gap-3">
        <h3 className="text-[13.5px] font-medium text-ink-2">性格漂移</h3>
        <span className="text-[11.5px] text-muted">
          {totals.characters} 人 · {totals.changes} 处变化 ·{' '}
          <span
            title={
              sparseNames
                ? `只有一条记录、看不出漂移：${sparseNames}`
                : undefined
            }
          >
            {totals.sparse} 人只有一条记录
          </span>
        </span>
        <span className="text-[11.5px] text-faint">点格子记状态或改已记的状态</span>
      </div>

      <div className="flex flex-wrap items-center gap-4 text-[11.5px] text-muted">
        <span className="flex items-center gap-1.5">
          <span aria-hidden="true" className="inline-block h-2.5 w-2.5 rounded-sm bg-warn" />
          与上一条不同
        </span>
        <span className="flex items-center gap-1.5">
          <span aria-hidden="true" className="inline-block h-2.5 w-2.5 rounded-sm bg-line-strong" />
          与上一条相同
        </span>
        <span className="flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className="inline-block h-2.5 w-2.5 rounded-sm border border-dashed border-line-strong"
          />
          没有记录
        </span>
      </div>

      <div className="overflow-x-auto rounded-card border border-line">
        <table className="min-w-full text-left text-[13.5px]">
          <thead>
            <tr>
              <th scope="col" className="whitespace-nowrap px-3 py-2 text-[11.5px] font-normal text-muted">
                人物
              </th>
              {chapters.map((chapter) => (
                <th
                  key={chapter.id}
                  scope="col"
                  className="whitespace-nowrap px-2 py-2 text-[11.5px] font-normal text-muted"
                  title={chapterTitle(chapter)}
                >
                  {shortLabel(chapter.label)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <Fragment key={row.entryId}>
                <tr className="border-t border-line align-middle">
                  <th
                    scope="row"
                    className="whitespace-nowrap px-3 py-2 text-left font-medium text-ink"
                  >
                    {row.name}
                    <span className="ml-2 text-[11.5px] font-normal text-muted">
                      {row.changes > 0 && `${row.changes} 变`}
                      {row.changes > 0 && row.recorded === 1 && ' · '}
                      {row.recorded === 1 && '仅一条'}
                    </span>
                  </th>
                  {chapters.map((chapter, index) => {
                    const cell = row.cells[index] ?? null
                    const active =
                      editing !== null &&
                      editing.entryId === row.entryId &&
                      editing.chapterId === chapter.id
                    return (
                      <td key={chapter.id} className="p-1">
                        <button
                          type="button"
                          onClick={() => openEditor(row, chapter, cell)}
                          title={
                            cell
                              ? `${row.name} · ${chapterTitle(chapter)}\n${cell.note}`
                              : `${row.name} · ${chapterTitle(chapter)}\n没有记录（点一下记一条）`
                          }
                          aria-label={`${row.name} · ${chapterTitle(chapter)}：${
                            cell ? cell.note : '没有记录'
                          }`}
                          className={`block w-full truncate rounded-control border px-2 py-1 text-left text-[11.5px] outline-none focus:ring-2 focus:ring-accent-soft ${
                            active ? 'ring-2 ring-accent-soft' : ''
                          } ${
                            cell === null
                              ? // 空留白：不写「没变」，也不写 0。加号只在悬停/聚焦时露出来，
                                // 否则整张表的空白会被一串符号填满。
                                'border-transparent text-transparent hover:border-line-strong hover:text-muted focus:text-muted'
                              : cell.changed
                                ? 'border-warn bg-warn-soft text-warn hover:border-warn'
                                : 'border-line-strong bg-sunken text-ink-2 hover:border-accent'
                          }`}
                        >
                          {cell ? cell.note : '＋'}
                        </button>
                      </td>
                    )
                  })}
                </tr>
                {editing !== null && editing.entryId === row.entryId && (
                  <tr className="border-t border-line bg-sunken">
                    <td colSpan={chapters.length + 1} className="px-3 py-2">
                      <div className="space-y-2">
                        <div className="flex flex-wrap items-baseline gap-2 text-[11.5px]">
                          <span className="text-ink">{editing.name}</span>
                          <span className="text-muted" title={editing.chapterLabel}>
                            {editing.chapterLabel}
                          </span>
                          <span className="text-muted">
                            {editing.exists ? '改这一条' : '新增一条'}
                          </span>
                          <span className="text-faint">一行状态，≤500 字</span>
                        </div>
                        <textarea
                          autoFocus
                          rows={2}
                          value={text}
                          disabled={saving}
                          onChange={(event) => setText(event.target.value)}
                          onKeyDown={(event) => {
                            // Esc 放弃、Ctrl/Cmd+Enter 保存：手不用离开输入框。
                            if (event.key === 'Escape') {
                              event.preventDefault()
                              closeEditor()
                            } else if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
                              event.preventDefault()
                              void save()
                            }
                          }}
                          placeholder={
                            editing.note
                              ? ''
                              : '如「怕水，遇事先退半步」——当时的状态，不是评价'
                          }
                          className="w-full rounded-control border border-line-strong bg-surface px-3 py-2 text-[13.5px] text-ink disabled:opacity-50"
                        />
                        <div className="flex flex-wrap items-center gap-2">
                          <Button
                            variant="primary"
                            size="sm"
                            disabled={saving || !text.trim()}
                            onClick={() => void save()}
                            title={text.trim() ? '保存后重取整本，变化标记由服务端重算' : '状态不能为空'}
                          >
                            {saving ? '保存中…' : '保存'}
                          </Button>
                          {editing.exists && (
                            <Button
                              variant="danger"
                              size="sm"
                              disabled={saving}
                              onClick={() => void remove()}
                            >
                              删除
                            </Button>
                          )}
                          <Button
                            size="sm"
                            disabled={saving}
                            onClick={closeEditor}
                          >
                            取消
                          </Button>
                          {editError && (
                            <span className="text-[11.5px] text-danger">{editError}</span>
                          )}
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-[11.5px] text-muted">
        只列有记录的人物。琥珀格 = 与这个人上一条记录不同（不是与上一章比）；
        灰格 = 记了但没变；空白 = 没有记录。变化是否合理属逻辑自检，这里不做判断。
      </p>
    </div>
  )
}
