import { useEffect, useState } from 'react'
import {
  api,
  type Act,
  type AdoptPayload,
  type ArchitectureOption,
  type Project,
  type RecommendResponse,
} from '../api/client'
import RunTrace from '../components/RunTrace'

interface DraftAct {
  seq: number
  name: string
  purpose: string
  target_word_ratio: string
}

const EMPTY_DRAFT = { logline: '', theme: '', premise: '', ending_direction: '' }

function actsFromBible(bible: { acts?: { name: string; purpose?: string; target_word_ratio?: number }[] }): DraftAct[] {
  return (bible.acts ?? []).map((act, index) => ({
    seq: index + 1,
    name: act.name,
    purpose: act.purpose ?? '',
    target_word_ratio: act.target_word_ratio == null ? '' : String(act.target_word_ratio),
  }))
}

export default function Architecture() {
  const [projects, setProjects] = useState<Project[]>([])
  const [projectId, setProjectId] = useState('')
  const [recommendation, setRecommendation] = useState<RecommendResponse | null>(null)
  const [chosen, setChosen] = useState<ArchitectureOption | null>(null)
  const [savedActs, setSavedActs] = useState<Act[]>([])
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  const [draft, setDraft] = useState(EMPTY_DRAFT)
  const [draftActs, setDraftActs] = useState<DraftAct[]>([])
  const [manual, setManual] = useState(false)

  useEffect(() => {
    api.listProjects().then((list) => {
      setProjects(list)
      if (list[0]) setProjectId(list[0].id)
    })
  }, [])

  useEffect(() => {
    if (!projectId) return
    api.getArchitecture(projectId).then((data) => setSavedActs(data.acts))
    setRecommendation(null)
    setChosen(null)
    setManual(false)
    setDraft(EMPTY_DRAFT)
    setDraftActs([])
  }, [projectId])

  async function recommend() {
    setBusy(true)
    setMessage('')
    try {
      const result = await api.recommendArchitecture(projectId)
      setRecommendation(result)
      if (result.structured) {
        const bible = result.story_bible_v0
        setDraft({
          logline: bible.logline ?? '',
          theme: bible.theme ?? '',
          premise: bible.premise ?? '',
          ending_direction: bible.ending_direction ?? '',
        })
        setDraftActs(actsFromBible(bible))
      }
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function startManual() {
    setManual(true)
    setRecommendation(null)
    setChosen(null)
    setMessage('')
    setDraft(EMPTY_DRAFT)
    setDraftActs([{ seq: 1, name: '', purpose: '', target_word_ratio: '' }])
  }

  function updateAct(index: number, patch: Partial<DraftAct>) {
    setDraftActs((prev) => prev.map((act, i) => (i === index ? { ...act, ...patch } : act)))
  }

  function addAct() {
    setDraftActs((prev) => [
      ...prev,
      { seq: prev.length + 1, name: '', purpose: '', target_word_ratio: '' },
    ])
  }

  function removeAct(index: number) {
    setDraftActs((prev) =>
      prev.filter((_, i) => i !== index).map((act, i) => ({ ...act, seq: i + 1 })),
    )
  }

  async function adopt() {
    const useManual = manual || !recommendation
    if (!useManual && !chosen) return

    const acts = draftActs
      .filter((act) => act.name.trim())
      .map((act, index) => ({
        seq: index + 1,
        name: act.name.trim(),
        purpose: act.purpose.trim() || undefined,
        target_word_ratio: act.target_word_ratio.trim()
          ? Number(act.target_word_ratio)
          : undefined,
      }))
    if (acts.length === 0) {
      setMessage('至少填一幕。')
      return
    }

    const payload: AdoptPayload = {
      tool_ref: chosen?.tool,
      logline: draft.logline.trim() || undefined,
      theme: draft.theme.trim() || undefined,
      premise: draft.premise.trim() || undefined,
      ending_direction: draft.ending_direction.trim() || undefined,
      acts,
    }

    try {
      const saved = await api.adoptArchitecture(projectId, payload)
      setSavedActs(saved.acts)
      setMessage('已写入项目结构')
    } catch (error) {
      setMessage((error as Error).message)
    }
  }

  const showEditor = manual || (recommendation?.structured ?? false)

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">架构推荐</h2>

      <div className="flex flex-wrap items-center gap-3">
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
        <button
          className="rounded border border-slate-700 px-4 py-2 text-sm disabled:opacity-50"
          onClick={startManual}
          disabled={!projectId}
        >
          手工建立故事圣经
        </button>
        {message && <span className="text-sm text-slate-400">{message}</span>}
      </div>

      {!showEditor && !savedActs.length && (
        <p className="rounded border border-slate-800 p-4 text-sm text-slate-500">
          还没有结构。点「推荐结构」让架构师给 2–3 套方案，或者点「手工建立故事圣经」自己写 ——
          手动档下 AI 不参与。
        </p>
      )}

      {recommendation && !recommendation.structured && (
        <div className="rounded bg-amber-950/40 p-3 text-sm text-amber-300">
          未结构化：{recommendation.parse_error}
          <pre className="mt-2 whitespace-pre-wrap text-xs">{recommendation.raw_text}</pre>
        </div>
      )}

      {recommendation?.structured && (
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
      )}

      {showEditor && (
        <section className="space-y-3 rounded border border-slate-800 p-4 text-sm">
          <h3 className="text-sm font-medium text-slate-300">
            故事圣经 v0{manual ? '（手工）' : '（可编辑，采纳的是你改过的版本）'}
          </h3>

          <label className="block">
            <span className="text-slate-500">logline</span>
            <textarea
              className="mt-1 h-20 w-full rounded border border-slate-700 bg-slate-900 p-3 text-sm"
              value={draft.logline}
              onChange={(e) => setDraft({ ...draft, logline: e.target.value })}
            />
          </label>
          <label className="block">
            <span className="text-slate-500">主题句</span>
            <textarea
              className="mt-1 h-20 w-full rounded border border-slate-700 bg-slate-900 p-3 text-sm"
              value={draft.theme}
              onChange={(e) => setDraft({ ...draft, theme: e.target.value })}
            />
          </label>
          <label className="block">
            <span className="text-slate-500">前提</span>
            <textarea
              className="mt-1 h-20 w-full rounded border border-slate-700 bg-slate-900 p-3 text-sm"
              value={draft.premise}
              onChange={(e) => setDraft({ ...draft, premise: e.target.value })}
            />
          </label>
          <label className="block">
            <span className="text-slate-500">结局方向</span>
            <textarea
              className="mt-1 h-20 w-full rounded border border-slate-700 bg-slate-900 p-3 text-sm"
              value={draft.ending_direction}
              onChange={(e) => setDraft({ ...draft, ending_direction: e.target.value })}
            />
          </label>

          <div>
            <div className="mb-2 flex items-center gap-3">
              <span className="text-slate-500">幕骨架</span>
              <button className="text-xs text-indigo-400" onClick={addAct}>
                加一幕
              </button>
            </div>
            <ul className="space-y-2">
              {draftActs.map((act, index) => (
                <li key={index} className="flex flex-wrap items-center gap-2">
                  <input
                    className="w-52 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                    placeholder="幕名"
                    value={act.name}
                    onChange={(e) => updateAct(index, { name: e.target.value })}
                  />
                  <input
                    className="min-w-[240px] flex-1 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                    placeholder="这一幕要做什么"
                    value={act.purpose}
                    onChange={(e) => updateAct(index, { purpose: e.target.value })}
                  />
                  <input
                    className="w-24 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                    placeholder="占比"
                    value={act.target_word_ratio}
                    onChange={(e) => updateAct(index, { target_word_ratio: e.target.value })}
                  />
                  <button className="text-xs text-amber-400" onClick={() => removeAct(index)}>
                    删除
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <button
            className="rounded bg-emerald-700 px-4 py-2 text-sm disabled:opacity-50"
            onClick={adopt}
            disabled={!manual && !chosen}
          >
            采纳并写入项目
          </button>
          {!manual && !chosen && (
            <p className="text-xs text-slate-500">先在上面选一套方案，再采纳。</p>
          )}
        </section>
      )}

      {savedActs.length > 0 && (
        <section className="rounded border border-slate-800 p-4 text-sm">
          <h3 className="mb-2 text-sm font-medium text-slate-300">已写入的结构</h3>
          <ul className="list-disc space-y-1 pl-5">
            {savedActs.map((act) => (
              <li key={act.id}>
                第{act.seq}幕 {act.name}
                {act.purpose ? ` —— ${act.purpose}` : ''}
                {act.target_word_ratio != null ? `（占比 ${act.target_word_ratio}）` : ''}
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
