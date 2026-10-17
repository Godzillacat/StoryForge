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
  /** 类型专属字段（今天只有人物用），键与值都来自接口下发的清单 */
  fields: Record<string, string>
}

export const EMPTY_DRAFT: EntryDraft = {
  type: 'place',
  name: '',
  aliases: '',
  tags: '',
  summary: '',
  description: '',
  hardness: '',
  fields: {},
}

/** 从一条已存条目里取类型专属字段 —— World 页与候选行共用，避免两份。
 *
 *  键由接口下发的清单决定，不在这里硬编：后端加第九项时，已有条目也能
 *  带上它的已存值；硬编的话那一项会显示为空，作者编辑不到且没人报错。 */
export function characterFieldsOf(
  entry: object,
  fields: { key: string }[],
): Record<string, string> {
  const source = entry as Record<string, unknown>
  return Object.fromEntries(fields.map((field) => [field.key, String(source[field.key] ?? '')]))
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

      {/* 类型专属字段由接口下发的清单驱动，前端不硬编 —— 后端加第九项时自动跟上。 */}
      {draft.type === 'character' &&
        (types?.character_fields ?? []).map((field) => (
          <label className="block" key={field.key}>
            <span className="text-slate-500">{field.label}</span>
            {field.multiline ? (
              <textarea
                className="mt-1 h-20 w-full rounded border border-slate-700 bg-slate-900 p-3 text-sm"
                value={draft.fields[field.key] ?? ''}
                onChange={(e) => set({ fields: { ...draft.fields, [field.key]: e.target.value } })}
              />
            ) : (
              <input
                className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                value={draft.fields[field.key] ?? ''}
                onChange={(e) => set({ fields: { ...draft.fields, [field.key]: e.target.value } })}
              />
            )}
          </label>
        ))}

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
