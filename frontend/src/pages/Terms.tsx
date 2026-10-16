import { useEffect, useMemo, useState } from 'react'
import { api, type EntryTypesResponse, type Project, type TermRow } from '../api/client'

export default function Terms() {
  const [projects, setProjects] = useState<Project[]>([])
  const [projectId, setProjectId] = useState('')
  const [terms, setTerms] = useState<TermRow[]>([])
  const [types, setTypes] = useState<EntryTypesResponse | null>(null)
  const [keyword, setKeyword] = useState('')
  const [notice, setNotice] = useState('')

  useEffect(() => {
    api.listEntryTypes().then(setTypes)
    api.listProjects().then((list) => {
      setProjects(list)
      if (list[0]) setProjectId(list[0].id)
    })
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
    if (!needle) return terms
    return terms.filter((t) => t.form.includes(needle))
  }, [terms, keyword])

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-xl font-semibold">术语表</h2>
        <select
          className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
        >
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <input
          className="w-64 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
          placeholder="查标准写法"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
        />
        <span className="text-xs text-slate-500">
          这一页是投影：每个条目的名字与别名都算术语，只有名字的裸术语也在列。
        </span>
      </div>

      {notice && <p className="rounded bg-slate-900 p-3 text-sm text-slate-300">{notice}</p>}

      <table className="w-full text-left text-sm">
        <thead className="text-xs text-slate-500">
          <tr>
            <th className="py-2">写法</th>
            <th className="py-2">类型</th>
            <th className="py-2">来源条目</th>
          </tr>
        </thead>
        <tbody>
          {visible.map((term, index) => (
            // key 里带行号：同一条目里写重复别名（录入层不去重）会让
            // `entry_id + form` 撞键 —— 本页无逐行状态，加行号即可。
            <tr key={`${term.entry_id}-${term.form}-${index}`} className="border-t border-slate-800">
              <td className="py-2">
                {term.form}
                {!term.is_primary && <span className="ml-2 text-xs text-slate-500">别名</span>}
              </td>
              <td className="py-2 text-slate-400">{typeLabel(term.type)}</td>
              <td className="py-2 text-slate-400">{term.entry_name}</td>
            </tr>
          ))}
          {visible.length === 0 && (
            <tr>
              <td colSpan={3} className="py-4 text-slate-500">
                {keyword.trim()
                  ? `没有匹配「${keyword.trim()}」的写法。`
                  : '还没有术语。到「世界观」页建几条设定，它们的名字与别名会自动出现在这里。'}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
