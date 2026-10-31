import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import {
  api,
  type Act,
  type AdoptPayload,
  type ArchitectureOption,
  type RecommendResponse,
} from '../api/client'
import RunTrace from '../components/RunTrace'
import { ImpactPanel, LockToggle } from '../components/Locking'
import { useCurrentProject } from '../state/ProjectContext'
import { comparisonSummary } from '../lib/architectureSummary'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { EmptyState } from '../ui/EmptyState'
import { Field, Input, Textarea } from '../ui/Field'

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

function OptionRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="space-y-0.5">
      <div className="text-[11px] tracking-[.08em] text-muted">{label}</div>
      <div className="text-[13px] leading-[1.6] text-ink-2">{children}</div>
    </div>
  )
}

export default function Architecture() {
  // 当前项目由外壳持有；切换入口在侧栏。
  const { projectId } = useCurrentProject()
  const [recommendation, setRecommendation] = useState<RecommendResponse | null>(null)
  const [chosen, setChosen] = useState<ArchitectureOption | null>(null)
  const [savedActs, setSavedActs] = useState<Act[]>([])
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  const [draft, setDraft] = useState(EMPTY_DRAFT)
  const [draftActs, setDraftActs] = useState<DraftAct[]>([])
  const [manual, setManual] = useState(false)
  // 项目里已经写入过故事圣经 —— 这时编辑器要能回填并继续改
  const [hasSaved, setHasSaved] = useState(false)
  const [archId, setArchId] = useState('')
  const [archLocked, setArchLocked] = useState(false)
  // 作废在途推荐响应用的令牌：递增即代表「这次推荐的结果已经不要了」
  const runToken = useRef(0)

  useEffect(() => {
    if (!projectId) return
    runToken.current++ // 换项目即作废在途推荐，别让它回来填错项目
    setBusy(false) // 作废的同时必须自己收尾：recommend 的 finally 被 token 守卫拦下，不会替我们清
    setRecommendation(null)
    setChosen(null)
    setManual(false)
    setMessage('')
    setDraft(EMPTY_DRAFT)
    setDraftActs([])
    setSavedActs([]) // 先清空，避免旧项目的幕挂在新项目标题下
    setHasSaved(false)
    setArchId('')
    setArchLocked(false)

    api
      .getArchitecture(projectId)
      .then((data) => {
        setSavedActs(data.acts)
        const arch = data.architecture
        if (!arch) return
        setHasSaved(true)
        setArchId(arch.id)
        setArchLocked(arch.locked)
        setDraft({
          logline: arch.logline ?? '',
          theme: arch.theme ?? '',
          premise: arch.premise ?? '',
          ending_direction: arch.ending_direction ?? '',
        })
        setDraftActs(
          data.acts.map((act, index) => ({
            seq: index + 1,
            name: act.name,
            purpose: act.purpose ?? '',
            target_word_ratio:
              act.target_word_ratio == null ? '' : String(act.target_word_ratio),
          })),
        )
      })
      .catch((error) => setMessage((error as Error).message))
  }, [projectId])

  async function recommend() {
    setBusy(true)
    setMessage('')
    const token = runToken.current

    try {
      const result = await api.recommendArchitecture(projectId)
      // 期间作者换了项目、或转去手工写了 —— 这次的结果已经作废，丢掉。
      if (token !== runToken.current) return
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
      if (token === runToken.current) setMessage((error as Error).message)
    } finally {
      if (token === runToken.current) setBusy(false)
    }
  }

  function startManual() {
    runToken.current++ // 作废在途推荐：作者已经在手写了，别让模型产出回来覆盖
    setBusy(false)
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
    // 三种可采纳的来源：手工录入、选中了某套推荐、或项目里已有结构（继续编辑）。
    if (!manual && !chosen && !hasSaved) return

    const acts = draftActs
      .filter((act) => act.name.trim())
      .map((act, index) => ({
        seq: index + 1,
        name: act.name.trim(),
        purpose: act.purpose.trim(),
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
      // 空串是「清空这一项」。不能传 undefined —— 键会从请求里消失，
      // 而后端把「键缺失」当成「保持原值」，作者删掉的文字会静默回来。
      logline: draft.logline.trim(),
      theme: draft.theme.trim(),
      premise: draft.premise.trim(),
      ending_direction: draft.ending_direction.trim(),
      acts,
    }

    try {
      const saved = await api.adoptArchitecture(projectId, payload)
      setSavedActs(saved.acts)
      setHasSaved(true)
      setArchId(saved.architecture.id)
      setArchLocked(saved.architecture.locked)
      setMessage('已写入项目结构')
    } catch (error) {
      setMessage((error as Error).message)
    }
  }

  const showEditor = manual || (recommendation?.structured ?? false) || hasSaved
  const summary = recommendation?.structured ? comparisonSummary(recommendation.options) : ''

  return (
    <div className="space-y-5">
      <h2 className="font-serif text-[22px] font-semibold text-ink">架构推荐</h2>

      <div className="flex flex-wrap items-center gap-3">
        <Button variant="primary" onClick={recommend} disabled={busy || !projectId}>
          {busy ? '生成中…' : '推荐结构'}
        </Button>
        <Button onClick={startManual} disabled={!projectId}>
          手工建立故事圣经
        </Button>
        {message && <span className="text-[13px] text-muted">{message}</span>}
      </div>

      {!showEditor && !savedActs.length && (
        <EmptyState
          title="还没有结构"
          hint="点「推荐结构」让架构师给 2–3 套方案，或者点「手工建立故事圣经」自己写 —— 手动档下 AI 不参与。"
        />
      )}

      {recommendation && !recommendation.structured && (
        <div className="rounded-control border-l-2 border-warn bg-warn-soft p-3 text-[13px] text-warn">
          未结构化：{recommendation.parse_error}
          <pre className="mt-2 whitespace-pre-wrap text-[11.5px]">{recommendation.raw_text}</pre>
        </div>
      )}

      {recommendation?.structured && (
        <section className="space-y-3">
          {summary && <p className="text-[12.5px] text-muted">{summary}</p>}
          <div className="grid items-stretch gap-4 md:grid-cols-3">
            {recommendation.options.map((option) => (
              <button
                key={option.tool}
                type="button"
                onClick={() => setChosen(option)}
                className={`flex h-full flex-col gap-3 rounded-card border p-4 text-left transition-colors duration-[120ms] ${
                  chosen?.tool === option.tool
                    ? 'border-accent bg-accent-soft'
                    : 'border-line bg-surface hover:bg-sunken'
                }`}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[14px] font-semibold text-ink">{option.tool}</span>
                  <Badge tone="accent">适配度 {option.fit_score}</Badge>
                  {chosen?.tool === option.tool && <Badge tone="warn">已选</Badge>}
                </div>
                <OptionRow label="理由">{option.reason}</OptionRow>
                <OptionRow label="篇幅分配">{option.length_plan || '—'}</OptionRow>
                <OptionRow label="节奏形态">{option.rhythm_shape || '—'}</OptionRow>
                <OptionRow label="风险">
                  <ul className="list-disc space-y-1 pl-4 text-[12.5px] text-warn">
                    {option.risks.map((risk) => (
                      <li key={risk}>{risk}</li>
                    ))}
                  </ul>
                </OptionRow>
              </button>
            ))}
          </div>
        </section>
      )}

      {showEditor && (
        <Card
          title={
            <span>
              故事圣经 v0
              {manual
                ? '（手工）'
                : recommendation?.structured
                  ? '（可编辑，采纳的是你改过的版本）'
                  : '（已写入项目，可继续修改）'}
            </span>
          }
        >
          <div className="space-y-3">
            <div className="grid gap-3 md:grid-cols-2">
              <Field label="logline">
                <Textarea
                  value={draft.logline}
                  onChange={(e) => setDraft({ ...draft, logline: e.target.value })}
                />
              </Field>
              <Field label="主题句">
                <Textarea
                  value={draft.theme}
                  onChange={(e) => setDraft({ ...draft, theme: e.target.value })}
                />
              </Field>
              <Field label="前提">
                <Textarea
                  value={draft.premise}
                  onChange={(e) => setDraft({ ...draft, premise: e.target.value })}
                />
              </Field>
              <Field label="结局方向">
                <Textarea
                  value={draft.ending_direction}
                  onChange={(e) => setDraft({ ...draft, ending_direction: e.target.value })}
                />
              </Field>
            </div>

            <div className="space-y-2 border-t border-line pt-3">
              <div className="flex items-center gap-3">
                <span className="text-[12.5px] font-medium text-ink-2">幕骨架</span>
                <Button size="sm" variant="accent" onClick={addAct}>
                  加一幕
                </Button>
              </div>
              <ul className="space-y-2">
                {draftActs.map((act, index) => (
                  <li key={index} className="flex flex-wrap items-center gap-2">
                    <div className="w-52">
                      <Input
                        aria-label={`第 ${index + 1} 幕名称`}
                        placeholder="幕名"
                        value={act.name}
                        onChange={(e) => updateAct(index, { name: e.target.value })}
                      />
                    </div>
                    <div className="min-w-[200px] flex-1">
                      <Input
                        aria-label={`第 ${index + 1} 幕要做什么`}
                        placeholder="这一幕要做什么"
                        value={act.purpose}
                        onChange={(e) => updateAct(index, { purpose: e.target.value })}
                      />
                    </div>
                    <div className="w-24">
                      <Input
                        aria-label={`第 ${index + 1} 幕占比`}
                        placeholder="占比"
                        value={act.target_word_ratio}
                        onChange={(e) => updateAct(index, { target_word_ratio: e.target.value })}
                      />
                    </div>
                    <Button size="sm" variant="warn" onClick={() => removeAct(index)}>
                      删除
                    </Button>
                  </li>
                ))}
              </ul>
            </div>

            <div className="flex flex-wrap items-center gap-3 border-t border-line pt-3">
              <Button
                variant="primary"
                onClick={adopt}
                disabled={(!manual && !chosen && !hasSaved) || archLocked}
                title={archLocked ? '故事圣经已锁定，AI 不会改动它' : undefined}
              >
                采纳并写入项目
              </Button>
              {archId && (
                <LockToggle
                  targetType="architecture"
                  targetId={archId}
                  locked={archLocked}
                  onChanged={async () => {
                    try {
                      const data = await api.getArchitecture(projectId)
                      setArchLocked(data.architecture?.locked === true)
                    } catch (error) {
                      setMessage((error as Error).message)
                    }
                  }}
                />
              )}
            </div>
            {archLocked && (
              <p className="rounded-control bg-warn-soft p-2.5 text-[12px] text-warn">
                故事圣经已锁定：可以继续编辑草稿，但写入项目会被拒绝，直到解锁。
              </p>
            )}
            {archId && (
              <ImpactPanel
                projectId={projectId}
                targetType="architecture"
                targetId={archId}
              />
            )}
            {recommendation?.structured && !chosen && !manual && !hasSaved && (
              <p className="text-[12px] text-muted">先在上面选一套方案，再采纳。</p>
            )}
          </div>
        </Card>
      )}

      {savedActs.length > 0 && (
        <Card title="已写入的结构">
          <ul className="list-disc space-y-1 pl-5 text-[13.5px] text-ink-2">
            {savedActs.map((act) => (
              <li key={act.id}>
                第{act.seq}幕 {act.name}
                {act.purpose ? ` —— ${act.purpose}` : ''}
                {act.target_word_ratio != null ? `（占比 ${act.target_word_ratio}）` : ''}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {recommendation && (
        <section className="space-y-2">
          <h3 className="text-[14px] font-semibold text-ink">这次运行</h3>
          <RunTrace run={recommendation.run} />
        </section>
      )}
    </div>
  )
}
