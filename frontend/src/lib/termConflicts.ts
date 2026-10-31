import type { TermRow } from '../api/client'

/**
 * 同一写法被多个条目共用时，返回「写法 → 条目名列表」（按出现顺序、去重）。
 *
 * 后端术语投影不做歧义标记（P1b-1 的已知 Minor），但作者在术语表上必须看得出
 * 「老师」到底指向谁。这里只做展示用分组，不改变投影本身。
 */
export function ambiguousForms(terms: TermRow[]): Map<string, string[]> {
  const byForm = new Map<string, string[]>()
  for (const term of terms) {
    const names = byForm.get(term.form) ?? []
    if (!names.includes(term.entry_name)) names.push(term.entry_name)
    byForm.set(term.form, names)
  }
  return new Map([...byForm].filter(([, names]) => names.length > 1))
}
