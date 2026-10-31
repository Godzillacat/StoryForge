import { useEffect, useState } from 'react'
import type {
  WritebackApplyPayload,
  WritebackSuggestion,
} from '../../api/client'
import { Button } from '../../ui/Button'
import { Input, Textarea } from '../../ui/Field'

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
    <section className="space-y-3 text-[13.5px]">
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-medium text-ink-2">回写建议</h3>
        <Button
          size="sm"
          disabled={loading || applying || !canRun || !hasBody}
          onClick={onRun}
          title={hasBody ? undefined : '采纳正文后才能生成回写建议'}
        >
          {loading ? '生成中…' : suggestion ? '重新生成' : '生成建议'}
        </Button>
      </div>

      {!hasBody && (
        <p className="text-[13.5px] text-muted">采纳正文后才能生成回写建议。</p>
      )}

      {suggestion?.warning && (
        <p className="rounded-control border border-warn bg-warn-soft p-2 text-[11.5px] text-warn">
          {suggestion.warning}
        </p>
      )}

      {suggestion?.warnings.map((warning) => (
        <p
          key={warning}
          className="rounded-control border border-warn bg-warn-soft p-2 text-[11.5px] text-warn"
        >
          {warning}
        </p>
      ))}

      {suggestion?.llm_status === 'ok' && (
        <>
          <div className="space-y-1 rounded-control border border-line p-2">
            <label className="flex items-center gap-2 text-[11.5px] text-muted">
              <input
                type="checkbox"
                checked={useSummary}
                disabled={applying}
                onChange={(event) => setUseSummary(event.target.checked)}
              />
              应用章节摘要
            </label>
            <Textarea
              value={summary}
              disabled={applying || !useSummary}
              onChange={(event) => setSummary(event.target.value)}
              rows={4}
            />
          </div>

          {suggestion.character_updates.length > 0 && (
            <div className="space-y-2">
              <p className="text-[11.5px] text-muted">人物状态</p>
              {suggestion.character_updates.map((item) => (
                <div key={item.entry_id} className="space-y-1 rounded-control border border-line p-2">
                  <label className="flex items-center gap-2 text-[11.5px] text-ink-2">
                    <input
                      type="checkbox"
                      checked={selectedCharacters.has(item.entry_id)}
                      disabled={applying}
                      onChange={() => toggleCharacter(item.entry_id)}
                    />
                    {item.name}
                  </label>
                  <Input
                    value={stateById[item.entry_id] ?? ''}
                    disabled={applying || !selectedCharacters.has(item.entry_id)}
                    onChange={(event) =>
                      setStateById((current) => ({
                        ...current,
                        [item.entry_id]: event.target.value,
                      }))
                    }
                  />
                  {item.evidence && (
                    <p className="text-[11.5px] text-muted">依据：{item.evidence}</p>
                  )}
                </div>
              ))}
            </div>
          )}

          {suggestion.foreshadow_pays.length > 0 && (
            <div className="space-y-1">
              <p className="text-[11.5px] text-muted">实际回收的伏笔</p>
              {suggestion.foreshadow_pays.map((item) => (
                <label
                  key={item.foreshadow_id}
                  className="flex items-start gap-2 rounded-control border border-line p-2 text-[11.5px] text-ink-2"
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
                      <span className="block text-muted">依据：{item.evidence}</span>
                    )}
                  </span>
                </label>
              ))}
            </div>
          )}

          {suggestion.open_questions.length > 0 && (
            <div className="text-[11.5px] text-muted">
              <p>没把握的问题：</p>
              <ul className="list-inside list-disc">
                {suggestion.open_questions.map((question) => (
                  <li key={question}>{question}</li>
                ))}
              </ul>
            </div>
          )}

          <Button
            variant="primary"
            disabled={!canApply}
            onClick={apply}
          >
            {applying ? '应用中…' : '应用所选'}
          </Button>
        </>
      )}
    </section>
  )
}
