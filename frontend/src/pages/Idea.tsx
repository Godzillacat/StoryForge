import { useEffect, useState } from 'react'
import { api, type Idea as IdeaRow, type RunView } from '../api/client'
import RunTrace from '../components/RunTrace'
import { useCurrentProject } from '../state/ProjectContext'

const FIELD_LABELS: Record<string, string> = {
  genre: '题材',
  sub_genre: '子类型',
  premise: '一句话前提',
  protagonist_desire: '主角欲望',
  conflict_source: '核心冲突源',
  emotional_core: '情感内核',
  tone: '调性',
  length_expectation: '篇幅预期',
  comparable_works: '可能参考坐标',
}

export default function Idea() {
  // 当前项目由外壳持有；切换入口在侧栏。
  const { projectId } = useCurrentProject()
  const [ideas, setIdeas] = useState<IdeaRow[]>([])
  const [draft, setDraft] = useState('')
  const [run, setRun] = useState<RunView | null>(null)
  const [parseError, setParseError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (projectId) api.listIdeas(projectId).then(setIdeas)
  }, [projectId])

  const current = ideas[ideas.length - 1]

  async function addIdea() {
    if (!draft.trim() || !projectId) return
    setSaveError(null)
    try {
      const idea = await api.createIdea(projectId, draft.trim())
      setIdeas((prev) => [...prev, idea])
      setDraft('')
    } catch (error) {
      // 保存失败不能默默无事发生：草稿留在输入框里，作者才不丢刚写的原话
      setSaveError((error as Error).message)
    }
  }

  async function parse() {
    if (!current || !projectId) return
    setBusy(true)
    try {
      const response = await api.parseIdea(projectId, current.id)
      setRun(response.run)
      setParseError(response.parse_error)
      setIdeas((prev) => prev.map((i) => (i.id === response.idea.id ? response.idea : i)))
    } catch (error) {
      setParseError((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">灵感与解析</h2>

      <section className="space-y-2">
        <div className="text-xs text-amber-400">这段文字 AI 不会改，解析结果只会另起一份。</div>
        <textarea
          className="h-28 w-full rounded border border-slate-700 bg-slate-900 p-3 text-sm"
          placeholder="丢一段话、几个标签、一句「我想写个什么」"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
        />
        <div className="flex gap-2">
          <button className="rounded border border-slate-700 px-4 py-2 text-sm" onClick={addIdea}>
            存为灵感
          </button>
          <button
            className="rounded bg-indigo-600 px-4 py-2 text-sm disabled:opacity-50"
            onClick={parse}
            disabled={busy || !current}
          >
            {busy ? '解析中…' : '解析'}
          </button>
        </div>
        {saveError && (
          <div className="rounded bg-rose-950/40 p-3 text-sm text-rose-300">
            灵感没存上：{saveError}
          </div>
        )}
      </section>

      {current && (
        <section className="rounded border border-slate-800 p-4 text-sm">
          <div className="mb-2 text-xs text-slate-500">作者原话（不会被覆盖）</div>
          <p className="whitespace-pre-wrap text-slate-200">{current.raw_text}</p>
        </section>
      )}

      {parseError && (
        <div className="rounded bg-amber-950/40 p-3 text-sm text-amber-300">
          未结构化：{parseError}
        </div>
      )}

      {current?.parsed_json && (
        <section className="space-y-3 rounded border border-slate-800 p-4">
          {/* 只读：解析结果没有更新接口，想改就重新解析 —— 不留假入口。 */}
          <h3 className="text-sm font-medium text-slate-300">解析卡 · 只读</h3>
          {Object.entries(FIELD_LABELS).map(([key, label]) => (
            <div key={key}>
              <div className="text-xs text-slate-500">{label}</div>
              <div className="text-slate-200">
                {Array.isArray(current.parsed_json![key])
                  ? (current.parsed_json![key] as string[]).join('、')
                  : String(current.parsed_json![key] ?? '—')}
              </div>
            </div>
          ))}
          {Array.isArray(current.parsed_json.open_questions) &&
            (current.parsed_json.open_questions as string[]).length > 0 && (
              <div className="rounded bg-slate-900 p-3">
                <div className="mb-1 text-xs text-slate-500">它没把握的问题，等你补</div>
                <ul className="list-disc space-y-1 pl-5">
                  {(current.parsed_json.open_questions as string[]).map((q) => (
                    <li key={q}>{q}</li>
                  ))}
                </ul>
              </div>
            )}
        </section>
      )}

      {run && (
        <section className="space-y-2">
          <h3 className="text-sm font-medium text-slate-300">这次运行</h3>
          <RunTrace run={run} />
        </section>
      )}
    </div>
  )
}
