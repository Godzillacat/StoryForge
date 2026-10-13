import { useEffect, useState } from 'react'
import { api, type Act, type ArchitectureOption, type Project, type RecommendResponse } from '../api/client'
import RunTrace from '../components/RunTrace'

export default function Architecture() {
  const [projects, setProjects] = useState<Project[]>([])
  const [projectId, setProjectId] = useState('')
  const [recommendation, setRecommendation] = useState<RecommendResponse | null>(null)
  const [chosen, setChosen] = useState<ArchitectureOption | null>(null)
  const [acts, setActs] = useState<Act[]>([])
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    api.listProjects().then((list) => {
      setProjects(list)
      if (list[0]) setProjectId(list[0].id)
    })
  }, [])

  useEffect(() => {
    if (!projectId) return
    api.getArchitecture(projectId).then((data) => setActs(data.acts))
  }, [projectId])

  async function recommend() {
    setBusy(true)
    setMessage('')
    try {
      setRecommendation(await api.recommendArchitecture(projectId))
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function adopt() {
    if (!recommendation || !chosen) return
    const bible = recommendation.story_bible_v0
    const actPayload =
      acts.length > 0
        ? acts.map((a) => ({
            seq: a.seq,
            name: a.name,
            purpose: a.purpose ?? undefined,
            target_word_ratio: a.target_word_ratio ?? undefined,
          }))
        : (bible.acts ?? []).map((a, index) => ({
            seq: index + 1,
            name: a.name,
            purpose: a.purpose,
            target_word_ratio: a.target_word_ratio,
          }))

    const saved = await api.adoptArchitecture(projectId, {
      tool_ref: chosen.tool,
      logline: bible.logline,
      theme: bible.theme,
      premise: bible.premise,
      ending_direction: bible.ending_direction,
      acts: actPayload,
    })
    setActs(saved.acts)
    setMessage('已写入项目结构')
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">架构推荐</h2>

      <div className="flex items-center gap-3">
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
        <button
          className="rounded bg-indigo-600 px-4 py-2 text-sm disabled:opacity-50"
          onClick={recommend}
          disabled={busy || !projectId}
        >
          {busy ? '生成中…' : '推荐结构'}
        </button>
        {message && <span className="text-sm text-slate-400">{message}</span>}
      </div>

      {recommendation && !recommendation.structured && (
        <div className="rounded bg-amber-950/40 p-3 text-sm text-amber-300">
          未结构化：{recommendation.parse_error}
          <pre className="mt-2 whitespace-pre-wrap text-xs">{recommendation.raw_text}</pre>
        </div>
      )}

      {recommendation?.structured && (
        <>
          <section className="grid gap-4 md:grid-cols-3">
            {recommendation.options.map((option) => (
              <button
                key={option.tool}
                onClick={() => setChosen(option)}
                className={`rounded border p-4 text-left text-sm ${
                  chosen?.tool === option.tool ? 'border-indigo-500 bg-slate-900' : 'border-slate-800'
                }`}
              >
                <div className="mb-2 font-medium text-slate-100">{option.tool}</div>
                <div className="mb-2 text-xs text-slate-400">适配度 {option.fit_score}</div>
                <p className="mb-2 text-slate-300">{option.reason}</p>
                {option.length_plan && (
                  <p className="mb-2 text-xs text-slate-500">篇幅：{option.length_plan}</p>
                )}
                {option.rhythm_shape && (
                  <p className="mb-2 text-xs text-slate-500">节奏：{option.rhythm_shape}</p>
                )}
                <ul className="list-disc space-y-1 pl-4 text-xs text-amber-300">
                  {option.risks.map((risk) => (
                    <li key={risk}>{risk}</li>
                  ))}
                </ul>
              </button>
            ))}
          </section>

          <section className="space-y-3 rounded border border-slate-800 p-4 text-sm">
            <h3 className="text-sm font-medium text-slate-300">故事圣经 v0</h3>
            <p>
              <span className="text-slate-500">logline：</span>
              {recommendation.story_bible_v0.logline ?? '—'}
            </p>
            <p>
              <span className="text-slate-500">主题句：</span>
              {recommendation.story_bible_v0.theme ?? '—'}
            </p>
            <p>
              <span className="text-slate-500">结局方向：</span>
              {recommendation.story_bible_v0.ending_direction ?? '—'}
            </p>
            <div>
              <div className="text-slate-500">幕骨架</div>
              <ul className="list-disc space-y-1 pl-5">
                {(recommendation.story_bible_v0.acts ?? []).map((act, index) => (
                  <li key={`${act.name}-${index}`}>
                    {act.name}
                    {act.purpose ? ` —— ${act.purpose}` : ''}
                  </li>
                ))}
              </ul>
            </div>
            <button
              className="rounded bg-emerald-700 px-4 py-2 text-sm disabled:opacity-50"
              onClick={adopt}
              disabled={!chosen}
            >
              采纳并写入项目
            </button>
          </section>
        </>
      )}

      {acts.length > 0 && (
        <section className="rounded border border-slate-800 p-4 text-sm">
          <h3 className="mb-2 text-sm font-medium text-slate-300">已写入的结构</h3>
          <ul className="list-disc space-y-1 pl-5">
            {acts.map((act) => (
              <li key={act.id}>
                第{act.seq}幕 {act.name}
                {act.purpose ? ` —— ${act.purpose}` : ''}
              </li>
            ))}
          </ul>
        </section>
      )}

      {recommendation && (
        <section className="space-y-2">
          <h3 className="text-sm font-medium text-slate-300">这次运行</h3>
          <RunTrace run={recommendation.run} />
        </section>
      )}
    </div>
  )
}
