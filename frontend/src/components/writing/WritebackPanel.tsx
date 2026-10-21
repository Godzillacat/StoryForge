import { useEffect, useState } from 'react'
import type {
  WritebackApplyPayload,
  WritebackSuggestion,
} from '../../api/client'

interface Props {
  suggestion: WritebackSuggestion | null
  loading: boolean
  applying: boolean
  canRun: boolean
  hasBody: boolean
  onRun: () => void
  onApply: (payload: WritebackApplyPayload) => void
}

export default function WritebackPanel({
  suggestion,
  loading,
  applying,
  canRun,
  hasBody,
  onRun,
  onApply,
}: Props) {
  const [useSummary, setUseSummary] = useState(false)
  const [summary, setSummary] = useState('')
  const [stateById, setStateById] = useState<Record<string, string>>({})
  const [selectedCharacters, setSelectedCharacters] = useState<Set<string>>(new Set())
  const [selectedForeshadows, setSelectedForeshadows] = useState<Set<string>>(new Set())

  useEffect(() => {
    const current = suggestion
    setUseSummary(false)
    setSummary(current?.chapter_summary ?? '')
    setStateById(
      Object.fromEntries(
        (current?.character_updates ?? []).map((item) => [
          item.entry_id,
          item.current_state,
        ]),
      ),
    )
    setSelectedCharacters(new Set())
    setSelectedForeshadows(new Set())
  }, [suggestion])

  const toggleCharacter = (id: string) => {
    setSelectedCharacters((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleForeshadow = (id: string) => {
    setSelectedForeshadows((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const canApply =
    !applying &&
    (useSummary ||
      selectedCharacters.size > 0 ||
      selectedForeshadows.size > 0)

  const apply = () => {
    const payload: WritebackApplyPayload = {
      character_updates: [...selectedCharacters].map((id) => ({
        entry_id: id,
        current_state: stateById[id] ?? '',
      })),
      foreshadow_pays: [...selectedForeshadows].map((id) => ({
        foreshadow_id: id,
      })),
    }
    if (useSummary) payload.chapter_summary = summary
    onApply(payload)
  }

  return (
    <section className="space-y-3 text-sm">
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-medium text-slate-300">回写建议</h3>
        <button
          type="button"
          disabled={loading || applying || !canRun || !hasBody}
          onClick={onRun}
          title={hasBody ? undefined : '采纳正文后才能生成回写建议'}
          className="rounded border border-slate-700 px-2 py-1 text-xs text-slate-300 hover:text-white disabled:opacity-50"
        >
          {loading ? '生成中…' : suggestion ? '重新生成' : '生成建议'}
        </button>
      </div>

      {!hasBody && (
        <p className="text-sm text-slate-500">采纳正文后才能生成回写建议。</p>
      )}

      {suggestion?.warning && (
        <p className="rounded border border-amber-900 bg-amber-950/40 p-2 text-xs text-amber-300">
          {suggestion.warning}
        </p>
      )}

      {suggestion?.warnings.map((warning) => (
        <p
          key={warning}
          className="rounded border border-amber-900 bg-amber-950/40 p-2 text-xs text-amber-300"
        >
          {warning}
        </p>
      ))}

      {suggestion?.llm_status === 'ok' && (
        <>
          <div className="space-y-1 rounded border border-slate-800 p-2">
            <label className="flex items-center gap-2 text-xs text-slate-400">
              <input
                type="checkbox"
                checked={useSummary}
                disabled={applying}
                onChange={(event) => setUseSummary(event.target.checked)}
              />
              应用章节摘要
            </label>
            <textarea
              value={summary}
              disabled={applying || !useSummary}
              onChange={(event) => setSummary(event.target.value)}
              rows={4}
              className="w-full rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200 disabled:opacity-60"
            />
          </div>

          {suggestion.character_updates.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs text-slate-500">人物状态</p>
              {suggestion.character_updates.map((item) => (
                <div key={item.entry_id} className="space-y-1 rounded border border-slate-800 p-2">
                  <label className="flex items-center gap-2 text-xs text-slate-300">
                    <input
                      type="checkbox"
                      checked={selectedCharacters.has(item.entry_id)}
                      disabled={applying}
                      onChange={() => toggleCharacter(item.entry_id)}
                    />
                    {item.name}
                  </label>
                  <input
                    value={stateById[item.entry_id] ?? ''}
                    disabled={applying || !selectedCharacters.has(item.entry_id)}
                    onChange={(event) =>
                      setStateById((current) => ({
                        ...current,
                        [item.entry_id]: event.target.value,
                      }))
                    }
                    className="w-full rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200 disabled:opacity-60"
                  />
                  {item.evidence && (
                    <p className="text-xs text-slate-500">依据：{item.evidence}</p>
                  )}
                </div>
              ))}
            </div>
          )}

          {suggestion.foreshadow_pays.length > 0 && (
            <div className="space-y-1">
              <p className="text-xs text-slate-500">实际回收的伏笔</p>
              {suggestion.foreshadow_pays.map((item) => (
                <label
                  key={item.foreshadow_id}
                  className="flex items-start gap-2 rounded border border-slate-800 p-2 text-xs text-slate-300"
                >
                  <input
                    type="checkbox"
                    checked={selectedForeshadows.has(item.foreshadow_id)}
                    disabled={applying}
                    onChange={() => toggleForeshadow(item.foreshadow_id)}
                  />
                  <span>
                    {item.name}
                    {item.evidence && (
                      <span className="block text-slate-500">依据：{item.evidence}</span>
                    )}
                  </span>
                </label>
              ))}
            </div>
          )}

          {suggestion.open_questions.length > 0 && (
            <div className="text-xs text-slate-500">
              <p>没把握的问题：</p>
              <ul className="list-inside list-disc">
                {suggestion.open_questions.map((question) => (
                  <li key={question}>{question}</li>
                ))}
              </ul>
            </div>
          )}

          <button
            type="button"
            disabled={!canApply}
            onClick={apply}
            className="rounded bg-teal-700 px-3 py-1 text-xs text-white hover:bg-teal-600 disabled:opacity-50"
          >
            {applying ? '应用中…' : '应用所选'}
          </button>
        </>
      )}
    </section>
  )
}
