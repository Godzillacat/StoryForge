import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  api,
  type EntryRelation,
  type EntryTypesResponse,
  type RunView,
  type SettingEntry,
} from '../api/client'
import CandidateList, { type CandidateRow } from '../components/CandidateList'
import RunTrace from '../components/RunTrace'
import { ImpactPanel, LockToggle } from '../components/Locking'
import EntryEditor, {
  EMPTY_DRAFT,
  characterFieldsOf,
  joinList,
  splitList,
  type EntryDraft,
} from '../components/EntryEditor'
import { useCurrentProject } from '../state/ProjectContext'

function draftOf(entry: SettingEntry, characterFields: { key: string }[]): EntryDraft {
  return {
    type: entry.type,
    name: entry.name,
    aliases: joinList(entry.aliases),
    tags: joinList(entry.tags),
    summary: entry.summary,
    description: entry.description,
    hardness: entry.hardness ?? '',
    fields: characterFieldsOf(entry, characterFields),
  }
}

export default function World() {
  // 当前项目由外壳持有；`projects` 只用来核对审校深链带来的 ?project= 是否有效。
  const { projects, projectId, select } = useCurrentProject()
  const [types, setTypes] = useState<EntryTypesResponse | null>(null)
  const [entries, setEntries] = useState<SettingEntry[]>([])
  const [relations, setRelations] = useState<EntryRelation[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [draft, setDraft] = useState<EntryDraft>(EMPTY_DRAFT)
  const [creating, setCreating] = useState(false)
  const [notice, setNotice] = useState('')
  // 深链失效单独一条：页面里的 notice 会随项目切换被清空，这条不能。
  const [linkWarning, setLinkWarning] = useState('')
  const [relationDraft, setRelationDraft] = useState({ to_id: '', kind: '', strength: '' })
  const [candidates, setCandidates] = useState<CandidateRow[]>([])
  const [openQuestions, setOpenQuestions] = useState<string[]>([])
  const [suggesting, setSuggesting] = useState(false)
  const [lastRun, setLastRun] = useState<RunView | null>(null)
  // 作废在途候选请求用的令牌。真模型下单次要 100 秒以上，作者在等待期间
  // 切项目是常态；没有它，响应回来会把上一个项目的候选写进当前项目。
  const runToken = useRef(0)
  // 条目 / 关联的加载令牌：切项目是常驻入口，迟到响应不许覆盖新项目的清单。
  const dataToken = useRef(0)
  // 审校面板的「改设定 / 改人物」会带 ?entry=<id> 跳过来；等条目加载完再选中。
  const [searchParams] = useSearchParams()
  const deepEntryId = searchParams.get('entry')
  const requestedProjectId = searchParams.get('project')
  const [loadedProjectId, setLoadedProjectId] = useState('')
  const deepLinkApplied = useRef('')

  useEffect(() => {
    api.listEntryTypes().then(setTypes)
  }, [])

  // 审校深链会带 `?project=<id>`：认它，但不绕过外壳。
  // 只认一次 —— 认完就把 URL 忘掉，否则作者在页内切项目会被它一直拽回去。
  // 链接里的项目不在列表里就明说一句，而不是静默落到别的项目上。
  useEffect(() => {
    if (!requestedProjectId || projects.length === 0) return
    if (deepLinkApplied.current === requestedProjectId) return
    deepLinkApplied.current = requestedProjectId
    if (projects.some((project) => project.id === requestedProjectId)) {
      if (requestedProjectId !== projectId) select(requestedProjectId)
      return
    }
    setLinkWarning('链接里的项目不存在，已显示当前项目')
  }, [requestedProjectId, projects, projectId, select])

  // 类型与硬度是**两份**词表，都从接口来 —— 合到一张 map 里，
  // 否则硬度的键（hard / soft / atmosphere）会在界面上原样露出来。
  const typeLabel = useMemo(() => {
    const map = new Map(
      [...(types?.types ?? []), ...(types?.hardness ?? [])].map((t) => [t.key, t.label]),
    )
    return (key: string) => map.get(key) ?? key
  }, [types])

  useEffect(() => {
    if (!projectId) return
    const token = ++dataToken.current
    // 作废在途的候选请求：它属于上一个项目，回来时不能再写当前项目的状态。
    runToken.current++
    // 换项目即整体重置：选中项、草稿、提示都跟着换，避免上一条目的内容
    // 留在编辑器里被误当成新项目的。
    setSelectedId(null)
    setCreating(false)
    setDraft(EMPTY_DRAFT)
    setNotice('')
    // 候选区也是项目作用域的状态：上一批候选的 key 与 source_run_id 都指向
    // 旧项目，留在新项目上会被误采纳，RunTrace 也会展示旧项目的运行。
    setCandidates([])
    setOpenQuestions([])
    setLastRun(null)
    setSuggesting(false)
    setLoadedProjectId('')
    api
      .listEntries(projectId)
      .then((list) => {
        if (dataToken.current !== token) return
        setEntries(list)
        setLoadedProjectId(projectId)
      })
      .catch((e) => {
        if (dataToken.current !== token) return
        setNotice((e as Error).message)
        setLoadedProjectId(projectId)
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

  function selectEntry(entry: SettingEntry) {
    setSelectedId(entry.id)
    setCreating(false)
    setDraft(draftOf(entry, types?.character_fields ?? []))
    setNotice('')
    setRelationDraft({ to_id: '', kind: '', strength: '' })
  }

  function startCreating() {
    setSelectedId(null)
    setCreating(true)
    setDraft(EMPTY_DRAFT)
    setNotice('')
  }

  // 深链只应用一次：之后的保存 / 刷新不能把作者手动选中的条目抢回去。
  useEffect(() => {
    if (!deepEntryId || loadedProjectId !== projectId || !types) return
    if (deepLinkApplied.current === deepEntryId) return
    deepLinkApplied.current = deepEntryId
    const target = entries.find(
      (entry) => entry.id === deepEntryId && entry.project_id === projectId,
    )
    if (target) selectEntry(target)
    else setNotice('没有找到这条设定，可能已被删除')
  }, [deepEntryId, loadedProjectId, projectId, entries, types])

  function payloadOf(next: EntryDraft) {
    return {
      type: next.type,
      name: next.name.trim(),
      aliases: splitList(next.aliases),
      tags: splitList(next.tags),
      summary: next.summary,
      description: next.description,
      hardness: next.hardness || null,
      // 人物八项只对人物类条目有意义；非人物条目若原样带上这些键，
      // 会把脏值写成空串（或把隐藏草稿里的旧值带过去）。
      ...(next.type === 'character' ? next.fields : {}),
    }
  }

  async function refresh() {
    setEntries(await api.listEntries(projectId))
    setRelations(await api.listRelations(projectId))
  }

  async function suggest() {
    setSuggesting(true)
    setNotice('')
    const token = runToken.current
    try {
      const result = await api.suggestEntries(projectId)
      // 期间换过项目 —— 这批候选属于上一个项目，丢掉。
      if (token !== runToken.current) return
      setLastRun(result.run)
      // key 带上 run id：每批候选的 key 都不同，展开态不会跨批串味。
      setCandidates(
        result.entries.map((entry, index) => ({ key: `${result.run.id}:${index}`, entry })),
      )
      setOpenQuestions(result.open_questions)
      if (!result.structured) {
        // 后端保证未结构化时一定给出一句可读原因（含「上游还没做」与调用失败两种），
        // 所以这里直接显示它，不再套「未结构化：」这个前缀 —— 模板缺失并不是格式问题。
        setNotice(result.parse_error ?? '模型没有按契约返回')
      }
    } catch (error) {
      if (token === runToken.current) setNotice((error as Error).message)
    } finally {
      // 令牌已作废时 busy 由换项目的 effect 自己收尾，这里不要越俎代庖。
      if (token === runToken.current) setSuggesting(false)
    }
  }

  async function adoptCandidate(next: EntryDraft, key: string): Promise<boolean> {
    try {
      await api.createEntry(projectId, {
        type: next.type,
        name: next.name.trim(),
        aliases: splitList(next.aliases),
        tags: splitList(next.tags),
        summary: next.summary,
        description: next.description,
        hardness: next.hardness || null,
        ...(next.type === 'character' ? next.fields : {}),
        source_run_id: lastRun?.id ?? null,
      })
      await refresh()
      // 采纳成功即把这行移出候选：改名采纳之后，候选行里的原名字不会
      // 落进「已存在」的判定里，按钮会一直亮着，再点一次就多一条重复条目。
      setCandidates((prev) => prev.filter((row) => row.key !== key))
      setNotice('已采纳')
      return true
    } catch (error) {
      setNotice((error as Error).message)
      return false
    }
  }

  function discardCandidate(key: string) {
    setCandidates((prev) => prev.filter((row) => row.key !== key))
  }

  async function save() {
    if (!draft.name.trim()) {
      setNotice('先给这条设定起个名字')
      return
    }
    try {
      if (creating) {
        const created = await api.createEntry(projectId, payloadOf(draft))
        await refresh()
        setCreating(false)
        setSelectedId(created.id)
      } else if (selectedId) {
        await api.updateEntry(selectedId, payloadOf(draft))
        await refresh()
      }
      setNotice('已保存')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function remove() {
    if (!selectedId) return
    if (!window.confirm('删除这条设定？指向它的关联也会一并删掉。')) return
    try {
      await api.deleteEntry(selectedId)
      setSelectedId(null)
      setDraft(EMPTY_DRAFT)
      await refresh()
      setNotice('已删除')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function addRelation() {
    if (!selectedId || !relationDraft.to_id || !relationDraft.kind.trim()) {
      setNotice('关联要选目标条目并写明是什么关系')
      return
    }
    try {
      await api.createRelation(projectId, {
        from_id: selectedId,
        to_id: relationDraft.to_id,
        kind: relationDraft.kind.trim(),
        strength: relationDraft.strength ? Number(relationDraft.strength) : null,
      })
      setRelationDraft({ to_id: '', kind: '', strength: '' })
      await refresh()
      setNotice('已建立关联')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function removeRelation(relationId: string) {
    try {
      await api.deleteRelation(relationId)
      await refresh()
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  const grouped = useMemo(() => {
    const map = new Map<string, SettingEntry[]>()
    for (const entry of entries) {
      const list = map.get(entry.type) ?? []
      list.push(entry)
      map.set(entry.type, list)
    }
    return [...map.entries()].sort((a, b) => typeLabel(a[0]).localeCompare(typeLabel(b[0])))
  }, [entries, typeLabel])

  const outgoing = relations.filter((r) => r.from_id === selectedId)
  const nameOf = (id: string) => entries.find((e) => e.id === id)?.name ?? '（已删除）'

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-xl font-semibold">世界观</h2>
        <button
          className="rounded border border-slate-700 px-4 py-2 text-sm disabled:opacity-50"
          onClick={startCreating}
          disabled={!projectId}
        >
          新建条目
        </button>
        <button
          className="rounded bg-indigo-600 px-4 py-2 text-sm disabled:opacity-50"
          onClick={suggest}
          disabled={!projectId || suggesting}
        >
          {suggesting ? '生成中…' : '让 AI 提候选'}
        </button>
      </div>

      {linkWarning && (
        <p className="rounded border border-amber-900 bg-amber-950/40 p-3 text-sm text-amber-300">
          {linkWarning}
        </p>
      )}

      {notice && <p className="rounded bg-slate-900 p-3 text-sm text-slate-300">{notice}</p>}

      {candidates.length > 0 && (
        <CandidateList
          candidates={candidates}
          types={types}
          existing={entries}
          busy={suggesting}
          onAdopt={adoptCandidate}
          onDiscard={discardCandidate}
        />
      )}

      {openQuestions.length > 0 && (
        <section className="rounded border border-slate-800 p-4 text-sm">
          <h3 className="mb-2 text-sm font-medium text-slate-300">它没把握的问题，等你补</h3>
          <ul className="list-disc space-y-1 pl-5 text-slate-300">
            {openQuestions.map((question) => (
              <li key={question}>{question}</li>
            ))}
          </ul>
        </section>
      )}

      {lastRun && (
        <section className="space-y-2">
          <h3 className="text-sm font-medium text-slate-300">最近一次生成</h3>
          <RunTrace run={lastRun} />
        </section>
      )}

      <div className="grid gap-6 lg:grid-cols-[260px_1fr]">
        <nav className="space-y-3">
          {grouped.map(([type, list]) => (
            <div key={type}>
              <div className="mb-1 text-xs text-slate-500">{typeLabel(type)}</div>
              <ul className="space-y-1">
                {list.map((entry) => (
                  <li key={entry.id}>
                    <button
                      onClick={() => selectEntry(entry)}
                      className={`block w-full rounded px-3 py-1.5 text-left text-sm ${
                        selectedId === entry.id ? 'bg-slate-800' : 'hover:bg-slate-900'
                      }`}
                    >
                      {entry.name}
                      {entry.hardness && (
                        <span className="ml-2 text-xs text-slate-500">
                          {typeLabel(entry.hardness)}
                        </span>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
          {entries.length === 0 && (
            <p className="text-sm text-slate-500">
              {projectId
                ? '还没有设定。点「新建条目」自己写，或者到上面的候选区让 AI 先提一批。'
                : '先去「故事仪表盘」新建一个项目。'}
            </p>
          )}
        </nav>

        <div className="space-y-4">
          {(creating || selectedId) && (
            <section className="space-y-4 rounded border border-slate-800 p-4">
              {selectedId && projectId && (
                <div className="space-y-2 border-b border-slate-800 pb-3">
                  <div className="flex items-center gap-3 text-sm">
                    <span className="text-slate-400">锁定</span>
                    <LockToggle
                      targetType="entry"
                      targetId={selectedId}
                      locked={entries.find((e) => e.id === selectedId)?.locked === true}
                      onChanged={refresh}
                    />
                  </div>
                  <ImpactPanel
                    projectId={projectId}
                    targetType="entry"
                    targetId={selectedId}
                    onMarksChanged={refresh}
                  />
                </div>
              )}
              <EntryEditor draft={draft} types={types} onChange={setDraft} />
              <div className="flex items-center gap-2">
                <button className="rounded bg-indigo-600 px-4 py-2 text-sm" onClick={save}>
                  {creating ? '创建' : '保存'}
                </button>
                {!creating && (
                  <button
                    className="rounded border border-slate-700 px-4 py-2 text-sm text-amber-400"
                    onClick={remove}
                  >
                    删除
                  </button>
                )}
              </div>
            </section>
          )}

          {selectedId && (
            <section className="space-y-3 rounded border border-slate-800 p-4 text-sm">
              <h3 className="text-sm font-medium text-slate-300">指向别处的关联</h3>
              <ul className="space-y-1">
                {outgoing.map((relation) => (
                  <li key={relation.id} className="flex items-center gap-3">
                    <span className="text-slate-400">{relation.kind}</span>
                    <span className="text-xs text-slate-500">
                      强度 {relation.strength ?? '未评'}
                    </span>
                    <span>{nameOf(relation.to_id)}</span>
                    <button
                      className="text-xs text-amber-400"
                      onClick={() => removeRelation(relation.id)}
                    >
                      删除
                    </button>
                  </li>
                ))}
                {outgoing.length === 0 && (
                  <li className="text-xs text-slate-500">还没有指向别处的关联。</li>
                )}
              </ul>
              <div className="flex flex-wrap items-center gap-2">
                <input
                  className="w-36 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                  placeholder="关系，如「位于」"
                  value={relationDraft.kind}
                  onChange={(e) => setRelationDraft({ ...relationDraft, kind: e.target.value })}
                />
                <select
                  className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                  value={relationDraft.strength}
                  onChange={(e) => setRelationDraft({ ...relationDraft, strength: e.target.value })}
                >
                  <option value="">未评</option>
                  {[1, 2, 3, 4, 5].map((value) => (
                    <option key={value} value={value}>
                      强度 {value}
                    </option>
                  ))}
                </select>
                <select
                  className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                  value={relationDraft.to_id}
                  onChange={(e) => setRelationDraft({ ...relationDraft, to_id: e.target.value })}
                >
                  <option value="">选目标条目</option>
                  {entries
                    .filter((e) => e.id !== selectedId)
                    .map((e) => (
                      <option key={e.id} value={e.id}>
                        {e.name}
                      </option>
                    ))}
                </select>
                <button className="text-xs text-indigo-400" onClick={addRelation}>
                  建立关联
                </button>
              </div>
              <p className="text-xs text-slate-500">
                关联是有向的：「甲 位于 乙」与「乙 位于 甲」是两条不同的关系。
              </p>
            </section>
          )}
        </div>
      </div>
    </div>
  )
}
