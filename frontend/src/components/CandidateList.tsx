import { useState } from 'react'
import type { EntryTypesResponse, SettingEntry, SuggestedEntry } from '../api/client'
import EntryEditor, { joinList, type EntryDraft } from './EntryEditor'

function draftOf(candidate: SuggestedEntry): EntryDraft {
  return {
    type: candidate.type ?? 'concept',
    name: candidate.name ?? '',
    aliases: joinList(candidate.aliases),
    tags: '',
    summary: candidate.summary ?? '',
    description: candidate.description ?? '',
    hardness: candidate.hardness ?? '',
  }
}

export default function CandidateList({
  candidates,
  types,
  existing,
  busy,
  onAdopt,
  onDiscard,
}: {
  candidates: SuggestedEntry[]
  types: EntryTypesResponse | null
  existing: SettingEntry[]
  busy: boolean
  onAdopt: (draft: EntryDraft) => Promise<void>
  onDiscard: (index: number) => void
}) {
  const [openIndex, setOpenIndex] = useState<number | null>(null)
  const [draft, setDraft] = useState<EntryDraft | null>(null)

  const takenNames = new Set(existing.map((e) => e.name))

  function toggle(index: number, candidate: SuggestedEntry) {
    if (openIndex === index) {
      setOpenIndex(null)
      setDraft(null)
      return
    }
    setOpenIndex(index)
    setDraft(draftOf(candidate))
  }

  return (
    <section className="space-y-3 rounded border border-slate-800 p-4">
      <h3 className="text-sm font-medium text-slate-300">
        候选（{candidates.length} 条，逐条审）
      </h3>

      <ul className="space-y-2 text-sm">
        {candidates.map((candidate, index) => {
          const duplicated = takenNames.has(candidate.name ?? '')
          return (
            <li key={`${candidate.name}-${index}`} className="space-y-2 border-b border-slate-800 pb-2 last:border-0">
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-xs text-slate-500">{candidate.type ?? '?'}</span>
                <span className="font-medium">{candidate.name}</span>
                {duplicated && <span className="text-xs text-amber-400">已存在，默认跳过</span>}
                <button className="text-xs text-indigo-400" onClick={() => toggle(index, candidate)}>
                  {openIndex === index ? '收起' : '改后采纳'}
                </button>
                <button className="text-xs text-slate-500" onClick={() => onDiscard(index)}>
                  丢弃
                </button>
                {!duplicated && (
                  <button
                    className="text-xs text-emerald-400 disabled:opacity-50"
                    disabled={busy}
                    onClick={() => onAdopt(draftOf(candidate))}
                  >
                    采纳
                  </button>
                )}
              </div>
              <p className="text-xs text-slate-400">{candidate.summary}</p>

              {openIndex === index && draft && (
                <div className="space-y-3 rounded bg-slate-900/60 p-3">
                  <EntryEditor draft={draft} types={types} onChange={setDraft} />
                  <button
                    className="rounded bg-emerald-700 px-4 py-2 text-sm disabled:opacity-50"
                    disabled={busy}
                    onClick={async () => {
                      await onAdopt(draft)
                      setOpenIndex(null)
                      setDraft(null)
                    }}
                  >
                    按改后的内容采纳
                  </button>
                </div>
              )}
            </li>
          )
        })}
      </ul>
    </section>
  )
}
