import { useEffect, useMemo, useState } from 'react'
import { api, type EntryRelation, type SettingEntry } from '../api/client'
import { useCurrentProject } from '../state/ProjectContext'

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

  useEffect(() => {
    if (!projectId) return
    setNotice('')
    setDraft({ from_id: '', to_id: '', kind: '', strength: '', note: '', reverse: true })
    api.listEntries(projectId).then(setEntries).catch((e) => setNotice((e as Error).message))
    api.listRelations(projectId).then(setRelations).catch((e) => setNotice((e as Error).message))
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
      <div className="space-y-2">
        <div className="text-xs text-slate-500">
          {from.name} → {to.name}
        </div>
        {rows.map((relation) => (
          <div key={relation.id} className="flex flex-wrap items-center gap-2 text-sm">
            <input
              className="w-32 rounded border border-slate-700 bg-slate-900 px-2 py-1 text-sm"
              defaultValue={relation.kind}
              onBlur={(e) => {
                if (e.target.value !== relation.kind) patch(relation, { kind: e.target.value })
              }}
            />
            <select
              className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-sm"
              value={relation.strength ?? ''}
              onChange={(e) =>
                patch(relation, { strength: e.target.value ? Number(e.target.value) : null })
              }
            >
              <option value="">未评</option>
              {STRENGTHS.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
            <input
              className="min-w-48 flex-1 rounded border border-slate-700 bg-slate-900 px-2 py-1 text-sm"
              defaultValue={relation.note}
              placeholder="备注"
              onBlur={(e) => {
                if (e.target.value !== relation.note) patch(relation, { note: e.target.value })
              }}
            />
            <button className="text-xs text-amber-400" onClick={() => remove(relation)}>
              删除
            </button>
          </div>
        ))}
        {rows.length === 0 && total > 0 && (
          <div className="text-xs text-slate-500">另有 {total} 条关系未匹配当前筛选</div>
        )}
        {total === 0 && (
          <div className="flex items-center gap-3 text-xs text-slate-500">
            <span>未记录</span>
            {other[0] && (
              <button className="text-indigo-400" onClick={() => fillReverse(other[0])}>
                补录反向
              </button>
            )}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-xl font-semibold">关系网</h2>
        <label className="flex items-center gap-2 text-sm text-slate-400">
          <input
            type="checkbox"
            checked={onlyCharacters}
            onChange={(e) => setOnlyCharacters(e.target.checked)}
          />
          仅人物之间
        </label>
        <input
          className="w-40 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
          placeholder="按关系类型筛"
          value={kindFilter}
          onChange={(e) => setKindFilter(e.target.value)}
        />
      </div>

      <section className="space-y-3 rounded border border-slate-800 p-4">
        <h3 className="text-sm font-medium text-slate-300">建立关系</h3>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <select
            className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-sm"
            value={draft.from_id}
            onChange={(e) => setDraft({ ...draft, from_id: e.target.value })}
          >
            <option value="">起点条目</option>
            {selectable.map((entry) => (
              <option key={entry.id} value={entry.id}>
                {entry.name}
              </option>
            ))}
          </select>
          <select
            className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-sm"
            value={draft.to_id}
            onChange={(e) => setDraft({ ...draft, to_id: e.target.value })}
          >
            <option value="">终点条目</option>
            {selectable
              .filter((entry) => entry.id !== draft.from_id)
              .map((entry) => (
                <option key={entry.id} value={entry.id}>
                  {entry.name}
                </option>
              ))}
          </select>
          <input
            className="w-32 rounded border border-slate-700 bg-slate-900 px-2 py-1 text-sm"
            placeholder="关系类型"
            value={draft.kind}
            onChange={(e) => setDraft({ ...draft, kind: e.target.value })}
          />
          <select
            className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-sm"
            value={draft.strength}
            onChange={(e) => setDraft({ ...draft, strength: e.target.value })}
          >
            <option value="">未评</option>
            {STRENGTHS.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
          <input
            className="min-w-48 flex-1 rounded border border-slate-700 bg-slate-900 px-2 py-1 text-sm"
            placeholder="备注"
            value={draft.note}
            onChange={(e) => setDraft({ ...draft, note: e.target.value })}
          />
          <label className="flex items-center gap-2 text-slate-400">
            <input
              type="checkbox"
              checked={draft.reverse}
              onChange={(e) => setDraft({ ...draft, reverse: e.target.checked })}
            />
            同时建立反向关系
          </label>
          <button className="rounded bg-indigo-600 px-3 py-1.5 text-sm" onClick={add}>
            建立
          </button>
        </div>
        <p className="text-xs text-slate-500">
          反向那条初始与正向相同；按语义改成对应称谓（如「师父」的反向可能是「徒弟」），两侧可是不同强弱。
        </p>
      </section>

      {notice && <p className="text-sm text-slate-400">{notice}</p>}

      <div className="space-y-3">
        {visiblePairs.map(({ pair, forward, backward }) => (
          <section key={pair.key} className="space-y-3 rounded border border-slate-800 p-4">
            <h3 className="text-sm font-medium text-slate-300">
              {pair.a.name} ⇄ {pair.b.name}
            </h3>
            {directionRows(pair.a, pair.b, forward, pair.forward.length, backward)}
            {directionRows(pair.b, pair.a, backward, pair.backward.length, forward)}
          </section>
        ))}
        {visiblePairs.length === 0 && (
          <p className="text-sm text-slate-500">
            {kindFilter.trim()
              ? `没有关系类型包含「${kindFilter.trim()}」的关系。`
              : '还没有关系。先在世界观里建两个人物，再回这里建立关系。'}
          </p>
        )}
      </div>
    </div>
  )
}
