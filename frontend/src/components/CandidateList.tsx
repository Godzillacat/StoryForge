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

/** 候选行的稳定标识。由 World 页在拿到候选时生成 —— 展开态靠它定位，
 *  所以它必须在整份候选的生命周期里不变。 */
export interface CandidateRow {
  key: string
  entry: SuggestedEntry
}

export default function CandidateList({
  candidates,
  types,
  existing,
  busy,
  onAdopt,
  onDiscard,
}: {
  candidates: CandidateRow[]
  types: EntryTypesResponse | null
  existing: SettingEntry[]
  busy: boolean
  onAdopt: (draft: EntryDraft) => Promise<boolean>
  onDiscard: (key: string) => void
}) {
  // 展开态按候选的**稳定 key** 记，不按数组下标 —— 丢弃上方一行、或再点一次
  // 「让 AI 提候选」，下标都会整体前移，草稿于是漂到别的候选上，点采纳提交的
  // 是作者没在改的那条，source_run_id 还对不上。这直接打在「作者裁决」上。
  const [openKey, setOpenKey] = useState<string | null>(null)
  const [draft, setDraft] = useState<EntryDraft | null>(null)

  const takenNames = new Set(existing.map((e) => e.name))

  function toggle(key: string, candidate: SuggestedEntry) {
    if (openKey === key) {
      setOpenKey(null)
      setDraft(null)
      return
    }
    setOpenKey(key)
    setDraft(draftOf(candidate))
  }

  return (
    <section className="space-y-3 rounded border border-slate-800 p-4">
      <h3 className="text-sm font-medium text-slate-300">
        候选（{candidates.length} 条，逐条审）
      </h3>

      <ul className="space-y-2 text-sm">
        {candidates.map(({ key, entry: candidate }) => {
          const duplicated = takenNames.has(candidate.name ?? '')
          return (
            <li key={key} className="space-y-2 border-b border-slate-800 pb-2 last:border-0">
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-xs text-slate-500">{candidate.type ?? '?'}</span>
                <span className="font-medium">{candidate.name}</span>
                {duplicated && <span className="text-xs text-amber-400">已存在，默认跳过</span>}
                <button className="text-xs text-indigo-400" onClick={() => toggle(key, candidate)}>
                  {openKey === key ? '收起' : '改后采纳'}
                </button>
                <button className="text-xs text-slate-500" onClick={() => onDiscard(key)}>
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

              {openKey === key && draft && (
                <div className="space-y-3 rounded bg-slate-900/60 p-3">
                  <EntryEditor draft={draft} types={types} onChange={setDraft} />
                  <button
                    className="rounded bg-emerald-700 px-4 py-2 text-sm disabled:opacity-50"
                    disabled={busy}
                    onClick={async () => {
                      // 采纳**失败时不收**展开区：失败恰恰常发生在作者刚把撞名的
                      // 候选改了名、而新名字仍然撞名时，把编辑内容收掉等于让他重敲。
                      if (await onAdopt(draft)) {
                        setOpenKey(null)
                        setDraft(null)
                      }
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
