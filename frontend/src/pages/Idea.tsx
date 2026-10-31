import { useEffect, useState } from 'react'
import { api, type Idea as IdeaRow, type RunView } from '../api/client'
import RunTrace from '../components/RunTrace'
import { useCurrentProject } from '../state/ProjectContext'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { EmptyState } from '../ui/EmptyState'
import { Textarea } from '../ui/Field'

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
    <div className="space-y-5">
      <h2 className="font-serif text-[22px] font-semibold text-ink">灵感与解析</h2>

      <div className="grid items-start gap-5 xl:grid-cols-[300px_minmax(0,1fr)]">
        <Card
          title="灵感条目"
          actions={<Badge>{ideas.length} 条</Badge>}
          className="xl:sticky xl:top-4"
        >
          {ideas.length === 0 ? (
            <EmptyState title="还没有灵感" hint="在右侧写一段话，点「存为灵感」。" />
          ) : (
            <ol className="space-y-1.5">
              {ideas.map((idea, index) => (
                <li
                  key={idea.id}
                  className={`rounded-control border p-2.5 ${
                    idea.id === current?.id
                      ? 'border-accent bg-accent-soft'
                      : 'border-line bg-surface'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] tabular-nums text-faint">#{index + 1}</span>
                    <Badge tone={idea.parsed_json ? 'accent' : 'plain'}>
                      {idea.parsed_json ? '已解析' : '未解析'}
                    </Badge>
                    {idea.id === current?.id && <Badge tone="warn">当前</Badge>}
                  </div>
                  <p className="mt-1 line-clamp-2 text-[12.5px] leading-[1.6] text-ink-2">
                    {idea.raw_text}
                  </p>
                </li>
              ))}
            </ol>
          )}
        </Card>

        <div className="max-w-[760px] space-y-4">
          <Card title="丢一段灵感">
            <div className="space-y-3">
              <p className="text-[12px] text-warn">这段文字 AI 不会改，解析结果只会另起一份。</p>
              <Textarea
                rows={5}
                placeholder="丢一段话、几个标签、一句「我想写个什么」"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
              />
              <div className="flex items-center gap-2">
                <Button onClick={addIdea}>存为灵感</Button>
                <Button variant="primary" onClick={parse} disabled={busy || !current}>
                  {busy ? '解析中…' : '解析'}
                </Button>
                <span className="text-[11.5px] text-muted">
                  解析作用于最新一条灵感；想改解析结果，重新解析即可。
                </span>
              </div>
              {saveError && (
                <div className="rounded-control border-l-2 border-danger bg-surface p-3 text-[13px] text-danger">
                  灵感没存上：{saveError}
                </div>
              )}
            </div>
          </Card>

          {current && (
            <Card title="作者原话（不会被覆盖）">
              <p className="whitespace-pre-wrap rounded-control bg-sunken p-3 font-serif text-[16px] leading-[1.9] text-ink">
                {current.raw_text}
              </p>
            </Card>
          )}

          {parseError && (
            <div className="rounded-control border-l-2 border-warn bg-warn-soft p-3 text-[13px] text-warn">
              未结构化：{parseError}
            </div>
          )}

          {current?.parsed_json && (
            <Card title="解析卡 · 只读">
              <div className="grid gap-3 sm:grid-cols-2">
                {Object.entries(FIELD_LABELS).map(([key, label]) => (
                  <div key={key} className="space-y-0.5">
                    <div className="text-[11px] tracking-[.08em] text-muted">{label}</div>
                    <div className="text-[13.5px] leading-[1.6] text-ink-2">
                      {Array.isArray(current.parsed_json![key])
                        ? (current.parsed_json![key] as string[]).join('、')
                        : String(current.parsed_json![key] ?? '—')}
                    </div>
                  </div>
                ))}
              </div>
              <p className="mt-3 text-[11.5px] text-muted">
                解析卡没有更新接口，想改就重新解析 —— 这里不留假入口。
              </p>
              {Array.isArray(current.parsed_json.open_questions) &&
                (current.parsed_json.open_questions as string[]).length > 0 && (
                  <div className="mt-3 rounded-control bg-sunken p-3">
                    <div className="mb-1 text-[11.5px] text-muted">它没把握的问题，等你补</div>
                    <ul className="list-disc space-y-1 pl-5 text-[13px] text-ink-2">
                      {(current.parsed_json.open_questions as string[]).map((q) => (
                        <li key={q}>{q}</li>
                      ))}
                    </ul>
                  </div>
                )}
            </Card>
          )}

          {run && (
            <section className="space-y-2">
              <h3 className="text-[14px] font-semibold text-ink">这次运行</h3>
              <RunTrace run={run} />
            </section>
          )}
        </div>
      </div>
    </div>
  )
}
