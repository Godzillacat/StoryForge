import type { EntryTypesResponse } from '../api/client'

/** 条目的草稿表单。受控、不调接口 —— 由 World 页与候选行各自决定怎么提交。 */
export interface EntryDraft {
  type: string
  name: string
  aliases: string
  tags: string
  summary: string
  description: string
  hardness: string
}

export const EMPTY_DRAFT: EntryDraft = {
  type: 'place',
  name: '',
  aliases: '',
  tags: '',
  summary: '',
  description: '',
  hardness: '',
}

/** 界面上别名与标签用顿号分隔 —— 作者一次输入一串比逐个添加省事。 */
export function splitList(text: string): string[] {
  return text
    .split(/[、,，]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

export function joinList(items: string[] | null | undefined): string {
  return (items ?? []).join('、')
}

export default function EntryEditor({
  draft,
  types,
  onChange,
}: {
  draft: EntryDraft
  types: EntryTypesResponse | null
  onChange: (next: EntryDraft) => void
}) {
  const set = (patch: Partial<EntryDraft>) => onChange({ ...draft, ...patch })

  return (
    <div className="space-y-3 text-sm">
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-slate-400">类型</label>
        <select
          className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
          value={draft.type}
          onChange={(e) => set({ type: e.target.value })}
        >
          {(types?.types ?? []).map((t) => (
            <option key={t.key} value={t.key}>
              {t.label}
            </option>
          ))}
        </select>

        <label className="text-slate-400">标准写法</label>
        <input
          className="w-72 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
          value={draft.name}
          onChange={(e) => set({ name: e.target.value })}
        />

        {draft.type === 'rule' && (
          <>
            <label className="text-slate-400">硬度</label>
            <select
              className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
              value={draft.hardness}
              onChange={(e) => set({ hardness: e.target.value })}
            >
              <option value="">（未定）</option>
              {(types?.hardness ?? []).map((h) => (
                <option key={h.key} value={h.key}>
                  {h.label}
                </option>
              ))}
            </select>
          </>
        )}
      </div>

      <label className="block">
        <span className="text-slate-500">别名与称呼（顿号分隔）</span>
        <input
          className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
          value={draft.aliases}
          onChange={(e) => set({ aliases: e.target.value })}
        />
      </label>

      <label className="block">
        <span className="text-slate-500">标签（顿号分隔）</span>
        <input
          className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
          value={draft.tags}
          onChange={(e) => set({ tags: e.target.value })}
        />
      </label>

      <label className="block">
        <span className="text-slate-500">一句话概述</span>
        <textarea
          className="mt-1 h-16 w-full rounded border border-slate-700 bg-slate-900 p-3 text-sm"
          value={draft.summary}
          onChange={(e) => set({ summary: e.target.value })}
        />
      </label>

      <label className="block">
        <span className="text-slate-500">详细说明</span>
        <textarea
          className="mt-1 h-40 w-full rounded border border-slate-700 bg-slate-900 p-3 text-sm"
          value={draft.description}
          onChange={(e) => set({ description: e.target.value })}
        />
      </label>

      {draft.type === 'rule' && (
        <p className="text-xs text-slate-500">
          硬规则是体系根基、不可违反；软规则需大体一致；氛围只为质感。这条标注决定日后检查环节的严格程度。
        </p>
      )}
    </div>
  )
}
