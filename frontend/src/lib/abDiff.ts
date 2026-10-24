/** A/B 两版的段落差异统计：`same` 是相同的段数，`changed` 是不相同（含多出来）的段数。 */
export interface ParagraphDiff {
  same: number
  changed: number
}

/**
 * 按空行切段：Markdown 里空行就是段落边界，作者看的是「几段不一样」，
 * 不是「几行不一样」。逐段 trim 后再比 —— 行尾空白与缩进不该算成差异。
 */
function toParagraphs(text: string): string[] {
  return text
    .replace(/\r\n/g, '\n')
    .split(/\n[ \t]*\n/)
    .map((paragraph) => paragraph.trim())
    .filter((paragraph) => paragraph !== '')
}

/**
 * 逐段按位置比较（不做跨段对齐）：第 i 段两边都有且相等记 same，其余记 changed。
 * 两边段数不同时，多出来的段全部算 changed。
 */
export function diffParagraphs(a: string, b: string): ParagraphDiff {
  const left = toParagraphs(a)
  const right = toParagraphs(b)
  const total = Math.max(left.length, right.length)
  let same = 0
  for (let index = 0; index < total; index += 1) {
    if (index < left.length && index < right.length && left[index] === right[index]) {
      same += 1
    }
  }
  return { same, changed: total - same }
}
