import { useEffect, useMemo, useState } from 'react'
import { api, type EntryTypesResponse, type TermRow } from '../api/client'
import { useCurrentProject } from '../state/ProjectContext'
import { Badge } from '../ui/Badge'
import { EmptyState } from '../ui/EmptyState'
import { Input } from '../ui/Field'
import { Table, Td, Th } from '../ui/Table'
import { ambiguousForms } from '../lib/termConflicts'

const CHIP_BASE =
  'h-7 rounded-tag border px-2.5 text-[12px] transition-colors duration-[120ms]'
const CHIP_ACTIVE = 'border-accent bg-accent-soft text-accent-ink'
const CHIP_IDLE = 'border-line bg-surface text-ink-2 hover:bg-sunken'

export default function Terms() {
  // 当前项目由外壳持有；切换入口在侧栏。
  const { projectId } = useCurrentProject()
  const [terms, setTerms] = useState<TermRow[]>([])
  const [types, setTypes] = useState<EntryTypesResponse | null>(null)
  const [keyword, setKeyword] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [notice, setNotice] = useState('')

  useEffect(() => {
    api.listEntryTypes().then(setTypes)
  }, [])

  useEffect(() => {
    if (!projectId) return
    setTerms([])
    api
      .listTerms(projectId)
      .then(setTerms)
      .catch((error) => setNotice((error as Error).message))
  }, [projectId])

  const typeLabel = useMemo(() => {
    const map = new Map((types?.types ?? []).map((t) => [t.key, t.label]))
    return (key: string) => map.get(key) ?? key
  }, [types])

  const visible = useMemo(() => {
    const needle = keyword.trim()
    return terms.filter(
      (t) => (!typeFilter || t.type === typeFilter) && (!needle || t.form.includes(needle)),
    )
  }, [terms, keyword, typeFilter])

  const ambiguous = useMemo(() => ambiguousForms(terms), [terms])

  // 空态先看所选类型本身有没有词：有词、只是被关键词筛空，才说「没有匹配」。
  const typeHasTerms = !typeFilter || terms.some((t) => t.type === typeFilter)

  const emptyMessage = !typeHasTerms
    ? `「${typeLabel(typeFilter)}」这一类还没有术语。`
    : keyword.trim()
      ? typeFilter
        ? `在「${typeLabel(typeFilter)}」里没有匹配「${keyword.trim()}」的写法。`
        : `没有匹配「${keyword.trim()}」的写法。`
      : '还没有术语。到「世界观」页建几条设定，它们的名字与别名会自动出现在这里。'

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="font-serif text-[22px] font-semibold text-ink">术语表</h2>
        <div className="w-64">
          <Input
            aria-label="搜索术语"
            placeholder="查标准写法"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
          />
        </div>
        <span className="text-[12px] text-muted">共 {visible.length} 条</span>
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        <button
          type="button"
          onClick={() => setTypeFilter('')}
          className={`${CHIP_BASE} ${typeFilter === '' ? CHIP_ACTIVE : CHIP_IDLE}`}
        >
          全部
        </button>
        {(types?.types ?? []).map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTypeFilter(t.key)}
            className={`${CHIP_BASE} ${typeFilter === t.key ? CHIP_ACTIVE : CHIP_IDLE}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <p className="text-[12px] text-muted">
        这一页是投影：每个条目的名字与别名都算术语，只有名字的裸术语也在列。
      </p>

      {notice && (
        <p className="rounded-control border-l-2 border-danger bg-surface p-3 text-[13px] text-danger">
          {notice}
        </p>
      )}

      {visible.length > 0 ? (
        <Table>
          <thead>
            <tr>
              <Th>写法</Th>
              <Th>类型</Th>
              <Th>来源条目</Th>
            </tr>
          </thead>
          <tbody>
            {visible.map((term, index) => {
              const shared = ambiguous.get(term.form)
              return (
                // key 里带行号：同一条目里写重复别名（录入层不去重）会让
                // `entry_id + form` 撞键 —— 本页无逐行状态，加行号即可。
                <tr key={`${term.entry_id}-${term.form}-${index}`} className="h-11 hover:bg-sunken">
                  <Td>
                    <span className="flex flex-wrap items-center gap-2">
                      {term.form}
                      {!term.is_primary && <Badge tone="plain">别名</Badge>}
                      {shared && <Badge tone="warn">{shared.length} 个条目共用</Badge>}
                    </span>
                    {shared && (
                      <span className="mt-0.5 block text-[11px] text-warn">
                        条目{shared.map((name) => `「${name}」`).join('')}共用这一称呼
                      </span>
                    )}
                  </Td>
                  <Td>{typeLabel(term.type)}</Td>
                  <Td>{term.entry_name}</Td>
                </tr>
              )
            })}
          </tbody>
        </Table>
      ) : (
        <EmptyState title={emptyMessage} />
      )}
    </div>
  )
}
