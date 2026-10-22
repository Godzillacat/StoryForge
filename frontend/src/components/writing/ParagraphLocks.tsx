import { useEffect, useState } from 'react'
import { api } from '../../api/client'

/** 按空行切段；与服务端的 `paragraphs_of` 同一条规则，界面看到的就是被锁的。 */
export function splitParagraphs(text: string | null | undefined): string[] {
  if (!text) return []
  return text
    .split(/\n\s*\n/)
    .map((part) => part.trim())
    .filter(Boolean)
}

export default function ParagraphLocks({
  sceneId,
  body,
  locks,
  disabled,
  onChanged,
}: {
  sceneId: string
  body: string | null
  locks: string[]
  disabled: boolean
  onChanged: (next: string[]) => void
}) {
  const [draft, setDraft] = useState<string[]>(locks)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  // 切场景或服务端刷新时以服务端为准：本地草稿不该跨场景存活。
  useEffect(() => {
    setDraft(locks)
    setError('')
  }, [sceneId, locks])

  const paragraphs = splitParagraphs(body)
  const locked = new Set(draft)

  async function save(next: string[]) {
    setBusy(true)
    setError('')
    try {
      const result = await api.setParagraphLocks(sceneId, next)
      setDraft(result.paragraphs)
      onChanged(result.paragraphs)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function toggle(text: string) {
    if (busy || disabled) return
    const next = locked.has(text)
      ? draft.filter((item) => item !== text)
      : [...draft, text]
    void save(next)
  }

  const missing = paragraphs.length === 0 ? draft : draft.filter((t) => !paragraphs.includes(t))

  return (
    <section className="space-y-2 rounded border border-slate-800 p-3 text-sm">
      <div className="flex items-center gap-2">
        <h3 className="font-medium text-slate-300">锁定段落</h3>
        <span className="text-xs text-slate-500">
          {draft.length > 0 ? `已锁 ${draft.length} 段` : '未锁段落'}
        </span>
      </div>
      <p className="text-xs text-slate-500">
        锁定的段落在采纳 AI 草稿时必须原样保留；缺少任一段会被拒绝采纳。
      </p>

      {error && <p className="text-xs text-red-400">{error}</p>}

      {paragraphs.length === 0 ? (
        <p className="text-xs text-slate-500">还没有已采纳正文，没有可锁的段落。</p>
      ) : (
        <ul className="max-h-64 space-y-1 overflow-auto">
          {paragraphs.map((text, index) => (
            <li key={`${index}-${text.slice(0, 12)}`} className="flex items-start gap-2">
              <input
                type="checkbox"
                className="mt-1"
                checked={locked.has(text)}
                disabled={busy || disabled}
                onChange={() => toggle(text)}
              />
              <span className="flex-1 text-xs text-slate-400">
                {text.length > 60 ? `${text.slice(0, 60)}…` : text}
              </span>
            </li>
          ))}
        </ul>
      )}

      {missing.length > 0 && (
        <div className="rounded bg-amber-950/30 p-2 text-xs text-amber-300">
          <p>以下已锁段落不在当前正文里（正文被改过）：</p>
          <ul className="mt-1 space-y-0.5">
            {missing.map((text) => (
              <li key={text}>「{text.length > 40 ? `${text.slice(0, 40)}…` : text}」</li>
            ))}
          </ul>
          <button
            className="mt-1 text-amber-200 underline"
            disabled={busy || disabled}
            onClick={() => void save(draft.filter((text) => !missing.includes(text)))}
          >
            移除这些失效的锁
          </button>
        </div>
      )}
    </section>
  )
}
