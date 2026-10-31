import { useEffect, useMemo, useRef, useState } from 'react'
import { api, type EntryRelation, type SettingEntry } from '../api/client'
import { useCurrentProject } from '../state/ProjectContext'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { EmptyState } from '../ui/EmptyState'
import { Field, Input, Select } from '../ui/Field'
import { Table, Td, Th } from '../ui/Table'

const STRENGTHS = [1, 2, 3, 4, 5]

interface Pair {
  key: string
  a: SettingEntry
  b: SettingEntry
  forward: EntryRelation[]
  backward: EntryRelation[]
}

export default function Relations() {
  // 当前项目由外壳持有；切换入口在侧栏。
  const { projectId } = useCurrentProject()
  const [entries, setEntries] = useState<SettingEntry[]>([])
  const [relations, setRelations] = useState<EntryRelation[]>([])
  const [onlyCharacters, setOnlyCharacters] = useState(true)
  const [kindFilter, setKindFilter] = useState('')
  const [notice, setNotice] = useState('')
  const [draft, setDraft] = useState({
    from_id: '',
    to_id: '',
    kind: '',
    strength: '',
    note: '',
    reverse: true,
  })
  // 迟到响应不许覆盖新项目的清单：切项目现在是常驻入口。
  const dataToken = useRef(0)

  useEffect(() => {
    if (!projectId) return
    const token = ++dataToken.current
    setNotice('')
    setDraft({ from_id: '', to_id: '', kind: '', strength: '', note: '', reverse: true })
    api
      .listEntries(projectId)
      .then((rows) => {
        if (dataToken.current !== token) return
        setEntries(rows)
      })
      .catch((e) => {
        if (dataToken.current !== token) return
        setNotice((e as Error).message)
      })
    api
      .listRelations(projectId)
      .then((rows) => {
        if (dataToken.current !== token) return
        setRelations(rows)
      })
      .catch((e) => {
        if (dataToken.current !== token) return
        setNotice((e as Error).message)
      })
  }, [projectId])

  const byId = useMemo(() => new Map(entries.map((e) => [e.id, e])), [entries])
  const selectable = onlyCharacters
    ? entries.filter((e) => e.type === 'character')
    : entries

  // 分对只看「仅人物之间」，**不看**关系类型筛选：后者只决定每一行显不显示。
  // 若拿筛过的集合分对，某一方向的关系会被误判成「未记录」，作者点「补录反向」
  // 就会往已占用的方向再写一条。
  const pairs = useMemo(() => {
    const relevant = relations.filter((relation) => {
      const from = byId.get(relation.from_id)
      const to = byId.get(relation.to_id)
      if (!from || !to) return false
      if (onlyCharacters && (from.type !== 'character' || to.type !== 'character')) return false
      return true
    })
    const map = new Map<string, Pair>()
    for (const relation of relevant) {
      const from = byId.get(relation.from_id)!
      const to = byId.get(relation.to_id)!
      const [a, b] = [from, to].sort((x, y) => x.id.localeCompare(y.id))
      const key = `${a.id}:${b.id}`
      let pair = map.get(key)
      if (!pair) {
        pair = { key, a, b, forward: [], backward: [] }
        map.set(key, pair)
      }
      if (relation.from_id === a.id) pair.forward.push(relation)
      else pair.backward.push(relation)
    }
    return [...map.values()]
  }, [relations, byId, onlyCharacters])

  function filterByKind(rows: EntryRelation[]) {
    const needle = kindFilter.trim()
    return needle ? rows.filter((relation) => relation.kind.includes(needle)) : rows
  }

  // 每一对的方向存在性用**未筛**的 rows 判断；只有要渲染的行才受类型筛选影响。
  const visiblePairs = pairs
    .map((pair) => ({
      pair,
      forward: filterByKind(pair.forward),
      backward: filterByKind(pair.backward),
    }))
    .filter(
      (view) =>
        !kindFilter.trim() || view.forward.length > 0 || view.backward.length > 0,
    )

  function nameOf(id: string) {
    return byId.get(id)?.name ?? '（已删除）'
  }

  async function refresh() {
    setEntries(await api.listEntries(projectId))
    setRelations(await api.listRelations(projectId))
  }

  async function add() {
    if (!draft.from_id || !draft.to_id || !draft.kind.trim()) {
      setNotice('起点、终点与关系类型都要填')
      return
    }
    try {
      await api.createRelation(projectId, {
        from_id: draft.from_id,
        to_id: draft.to_id,
        kind: draft.kind.trim(),
        strength: draft.strength ? Number(draft.strength) : null,
        note: draft.note,
        create_reverse: draft.reverse,
      })
      setDraft({ from_id: '', to_id: '', kind: '', strength: '', note: '', reverse: true })
      await refresh()
      setNotice('已建立关系')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function patch(relation: EntryRelation, body: Record<string, unknown>) {
    try {
      await api.updateRelation(relation.id, body)
      await refresh()
      setNotice('已更新')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function remove(relation: EntryRelation) {
    if (!window.confirm(`删除「${nameOf(relation.from_id)} → ${nameOf(relation.to_id)}」这条关系？`)) {
      return
    }
    try {
      await api.deleteRelation(relation.id)
      await refresh()
      setNotice('已删除')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function fillReverse(source: EntryRelation) {
    try {
      await api.createRelation(projectId, {
        from_id: source.to_id,
        to_id: source.from_id,
        kind: source.kind,
        strength: source.strength,
        note: source.note,
        create_reverse: false,
      })
      await refresh()
      setNotice('已补录反向关系；建议按语义改成对应的称谓')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  function directionRows(
    from: SettingEntry,
    to: SettingEntry,
    rows: EntryRelation[],
    total: number,
    other: EntryRelation[],
  ) {
    return (
      <>
        {rows.map((relation) => (
          <tr key={relation.id} className="h-11">
            <Td className="whitespace-nowrap">{from.name}</Td>
            <Td className="text-faint">→</Td>
            <Td className="whitespace-nowrap">{to.name}</Td>
            <Td>
              <div className="w-32">
                <Input
                  defaultValue={relation.kind}
                  aria-label="关系类型"
                  onBlur={(e) => {
                    if (e.target.value !== relation.kind) patch(relation, { kind: e.target.value })
                  }}
                />
              </div>
            </Td>
            <Td>
              <div className="w-20">
                <Select
                  aria-label="关系强度"
                  value={relation.strength ?? ''}
                  onChange={(e) =>
                    patch(relation, { strength: e.target.value ? Number(e.target.value) : null })
                  }
                  options={[
                    { value: '', label: '未评' },
                    ...STRENGTHS.map((value) => ({ value: String(value), label: String(value) })),
                  ]}
                />
              </div>
            </Td>
            <Td className="min-w-[140px]">
              <Input
                defaultValue={relation.note}
                aria-label="关系备注"
                placeholder="备注"
                onBlur={(e) => {
                  if (e.target.value !== relation.note) patch(relation, { note: e.target.value })
                }}
              />
            </Td>
            <Td align="right">
              <Button size="sm" variant="warn" onClick={() => remove(relation)}>
                删除
              </Button>
            </Td>
          </tr>
        ))}
        {rows.length === 0 && total > 0 && (
          <tr>
            <Td colSpan={7} className="text-muted">
              另有 {total} 条关系未匹配当前筛选
            </Td>
          </tr>
        )}
        {total === 0 && (
          <tr>
            <Td colSpan={7}>
              <div className="flex items-center gap-3 text-muted">
                <span>未记录</span>
                {other[0] && (
                  <Button size="sm" variant="accent" onClick={() => fillReverse(other[0])}>
                    补录反向
                  </Button>
                )}
              </div>
            </Td>
          </tr>
        )}
      </>
    )
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="font-serif text-[22px] font-semibold text-ink">关系网</h2>
        <span className="text-[12px] text-muted">
          {pairs.length} 对 · {relations.length} 条
        </span>
      </div>

      {notice && <p className="text-[13px] text-muted">{notice}</p>}

      <div className="grid items-start gap-5 xl:grid-cols-[300px_minmax(0,1fr)]">
        <div className="space-y-4 xl:sticky xl:top-4">
          <Card title="筛选">
            <div className="space-y-3">
              <label className="flex items-center gap-2 text-[13px] text-ink-2">
                <input
                  type="checkbox"
                  className="h-4 w-4 accent-accent"
                  checked={onlyCharacters}
                  onChange={(e) => setOnlyCharacters(e.target.checked)}
                />
                只看人物之间
              </label>
              <Field label="按关系类型筛">
                <Input
                  placeholder="如「师父」"
                  value={kindFilter}
                  onChange={(e) => setKindFilter(e.target.value)}
                />
              </Field>
              <p className="text-[11.5px] text-muted">
                类型筛选只决定行显不显示，不参与分对 —— 否则某一方向会被误判成「未记录」。
              </p>
            </div>
          </Card>

          <Card title="建立关系">
            <div className="space-y-3">
              <Field label="起点条目">
                <Select
                  aria-label="起点条目"
                  value={draft.from_id}
                  onChange={(e) => setDraft({ ...draft, from_id: e.target.value })}
                  options={[
                    { value: '', label: '起点条目' },
                    ...selectable.map((entry) => ({ value: entry.id, label: entry.name })),
                  ]}
                />
              </Field>
              <Field label="终点条目">
                <Select
                  aria-label="终点条目"
                  value={draft.to_id}
                  onChange={(e) => setDraft({ ...draft, to_id: e.target.value })}
                  options={[
                    { value: '', label: '终点条目' },
                    ...selectable
                      .filter((entry) => entry.id !== draft.from_id)
                      .map((entry) => ({ value: entry.id, label: entry.name })),
                  ]}
                />
              </Field>
              <div className="grid grid-cols-[minmax(0,1fr)_88px] gap-2">
                <Field label="关系类型">
                  <Input
                    placeholder="如「师父」"
                    value={draft.kind}
                    onChange={(e) => setDraft({ ...draft, kind: e.target.value })}
                  />
                </Field>
                <Field label="强度">
                  <Select
                    aria-label="强度"
                    value={draft.strength}
                    onChange={(e) => setDraft({ ...draft, strength: e.target.value })}
                    options={[
                      { value: '', label: '未评' },
                      ...STRENGTHS.map((value) => ({ value: String(value), label: String(value) })),
                    ]}
                  />
                </Field>
              </div>
              <Field label="备注">
                <Input
                  placeholder="备注"
                  value={draft.note}
                  onChange={(e) => setDraft({ ...draft, note: e.target.value })}
                />
              </Field>
              <label className="flex items-center gap-2 text-[13px] text-ink-2">
                <input
                  type="checkbox"
                  className="h-4 w-4 accent-accent"
                  checked={draft.reverse}
                  onChange={(e) => setDraft({ ...draft, reverse: e.target.checked })}
                />
                同时建立反向关系
              </label>
              <Button variant="primary" onClick={add}>
                建立
              </Button>
              <p className="text-[11.5px] text-muted">
                反向那条初始与正向相同；按语义改成对应称谓（如「师父」的反向可能是「徒弟」），两侧可是不同强弱。
              </p>
              <div className="flex flex-wrap gap-1.5 border-t border-line pt-3">
                <Badge>{selectable.length} 个可选条目</Badge>
                {onlyCharacters && <Badge tone="accent">仅人物</Badge>}
              </div>
            </div>
          </Card>
        </div>

        <div className="space-y-3">
          {visiblePairs.map(({ pair, forward, backward }) => (
            <Card key={pair.key} title={<span>{pair.a.name} ⇄ {pair.b.name}</span>}>
              <Table>
                <thead>
                  <tr>
                    <Th>A</Th>
                    <Th>方向</Th>
                    <Th>B</Th>
                    <Th>类型</Th>
                    <Th>强度</Th>
                    <Th>备注</Th>
                    <Th align="right">操作</Th>
                  </tr>
                </thead>
                <tbody>
                  {directionRows(pair.a, pair.b, forward, pair.forward.length, backward)}
                  {directionRows(pair.b, pair.a, backward, pair.backward.length, forward)}
                </tbody>
              </Table>
            </Card>
          ))}
          {visiblePairs.length === 0 && (
            <EmptyState
              title={
                kindFilter.trim()
                  ? `没有关系类型包含「${kindFilter.trim()}」的关系。`
                  : '还没有关系'
              }
              hint={
                kindFilter.trim()
                  ? undefined
                  : '先在世界观里建两个人物，再回这里建立关系。'
              }
            />
          )}
        </div>
      </div>
    </div>
  )
}
