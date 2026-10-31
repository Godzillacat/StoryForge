import type { EntryTypesResponse } from '../api/client'
import { Field, Input, Select, Textarea } from '../ui/Field'

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
    <div className="space-y-3 text-[13.5px]">
      <div className="flex flex-wrap items-start gap-3">
        <div className="w-40">
          <Field label="类型">
            <Select
              options={(types?.types ?? []).map((t) => ({ value: t.key, label: t.label }))}
              value={draft.type}
              onChange={(e) => set({ type: e.target.value })}
            />
          </Field>
        </div>

        <div className="min-w-56 flex-1">
          <Field label="标准写法">
            <Input value={draft.name} onChange={(e) => set({ name: e.target.value })} />
          </Field>
        </div>

        {draft.type === 'rule' && (
          <div className="w-40">
            <Field label="硬度">
              <Select
                options={[
                  { value: '', label: '（未定）' },
                  ...(types?.hardness ?? []).map((h) => ({ value: h.key, label: h.label })),
                ]}
                value={draft.hardness}
                onChange={(e) => set({ hardness: e.target.value })}
              />
            </Field>
          </div>
        )}
      </div>

      {/* 类型专属字段由接口下发的清单驱动，前端不硬编 —— 后端加第九项时自动跟上。
          单列排：八项里七项是多行长文本（见 `CHARACTER_FIELDS`），两列栅格只会
          留下一个孤立的半宽字段，其余与单列无异。 */}
      {draft.type === 'character' &&
        (types?.character_fields ?? []).map((field) => (
          <Field key={field.key} label={field.label}>
            {field.multiline ? (
              <Textarea
                className="min-h-[80px]"
                value={draft.fields[field.key] ?? ''}
                onChange={(e) => set({ fields: { ...draft.fields, [field.key]: e.target.value } })}
              />
            ) : (
              <Input
                value={draft.fields[field.key] ?? ''}
                onChange={(e) => set({ fields: { ...draft.fields, [field.key]: e.target.value } })}
              />
            )}
          </Field>
        ))}

      <Field label="别名与称呼（顿号分隔）">
        <Input value={draft.aliases} onChange={(e) => set({ aliases: e.target.value })} />
      </Field>

      <Field label="标签（顿号分隔）">
        <Input value={draft.tags} onChange={(e) => set({ tags: e.target.value })} />
      </Field>

      <Field label="一句话概述">
        <Textarea
          className="min-h-[64px]"
          value={draft.summary}
          onChange={(e) => set({ summary: e.target.value })}
        />
      </Field>

      <Field label="详细说明">
        <Textarea
          className="min-h-[160px]"
          value={draft.description}
          onChange={(e) => set({ description: e.target.value })}
        />
      </Field>

      {draft.type === 'rule' && (
        <p className="text-[11.5px] text-muted">
          硬规则是体系根基、不可违反；软规则需大体一致；氛围只为质感。这条标注决定日后检查环节的严格程度。
        </p>
      )}
    </div>
  )
}
