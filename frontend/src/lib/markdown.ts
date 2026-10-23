/** Markdown 子集解析：阅读器只需要标题 / 段落 / 引用 / 列表 / 分隔线 / 行内强调。
 *
 * **不用 `dangerouslySetInnerHTML`**：正文里出现 `<script>` 时，把它当文字渲染出来
 * 比执行它安全，也省掉一遍转义。节点树天然安全。
 *
 * 这是纯函数、可被 vitest 覆盖 —— 渲染规则不该落在「UI 不写自动化测试」的盲区里。
 */

export type MdInline =
  | { type: 'text'; text: string }
  | { type: 'strong'; text: string }
  | { type: 'em'; text: string }
  | { type: 'code'; text: string }

export type MdBlock =
  | { type: 'heading'; level: 1 | 2 | 3 | 4; inline: MdInline[] }
  | { type: 'paragraph'; inline: MdInline[] }
  | { type: 'quote'; inline: MdInline[] }
  | { type: 'list'; ordered: boolean; items: MdInline[][] }
  | { type: 'divider' }

const HEADING = /^\s{0,3}(#{1,6})\s+(.*)$/
const DIVIDER = /^\s{0,3}([-*_])(\s*\1){2,}\s*$/
const QUOTE = /^\s{0,3}>\s?(.*)$/
const UNORDERED = /^\s{0,3}[-*+]\s+(.*)$/
const ORDERED = /^\s{0,3}\d+[.)]\s+(.*)$/

/** 行内标记。先切代码，再切粗体与斜体 —— 顺序反了会把 `` `**x**` `` 里的星号吃掉。 */
export function parseInline(text: string): MdInline[] {
  const spans: MdInline[] = []
  let rest = text
  const push = (span: MdInline) => {
    if (!span.text) return
    // 相邻的纯文字合并：未闭合的 `**` 会切成两个文字块，拆开对渲染没好处，
    // 对朗读更没好处（会在中间断一下）。
    const last = spans[spans.length - 1]
    if (span.type === 'text' && last?.type === 'text') {
      last.text += span.text
      return
    }
    spans.push(span)
  }

  while (rest) {
    const code = rest.match(/^`([^`]+)`/)
    if (code) {
      push({ type: 'code', text: code[1] })
      rest = rest.slice(code[0].length)
      continue
    }
    const strong = rest.match(/^(\*\*|__)([\s\S]+?)\1/)
    if (strong) {
      push({ type: 'strong', text: strong[2] })
      rest = rest.slice(strong[0].length)
      continue
    }
    const em = rest.match(/^([*_])([^*_]+?)\1/)
    if (em) {
      push({ type: 'em', text: em[2] })
      rest = rest.slice(em[0].length)
      continue
    }
    // 没有任何标记：把到下一个标记之前的一段整体当文字，避免逐字符循环。
    const next = rest.slice(1).search(/[`*_]/)
    const end = next === -1 ? rest.length : next + 1
    push({ type: 'text', text: rest.slice(0, end) })
    rest = rest.slice(end)
  }
  return spans
}

/** 把一段连续的行合并成一行：Markdown 里段内换行是软换行，不该断段。
 *
 * 软换行在 CommonMark 里渲染成一个空格。两行紧邻的英文没有空格会粘成一个
 * 词；中文之间补空格反而难看，所以只在两侧都是非空白、且**至少一侧不是
 * 中日韩字符**时补一个空格。
 */
// 汉字 / 假名 / 谚文 / 全角标点：这些字符之间断行不该补空格。
const CJK = /[　-ヿ㐀-䶿一-鿿가-힯豈-﫿＀-￯]/

function joinSoft(lines: string[]): string {
  let result = ''
  for (const raw of lines) {
    const line = raw.trim()
    if (!line) continue
    if (result) {
      const left = result[result.length - 1]
      const right = line[0]
      if (!CJK.test(left) || !CJK.test(right)) result += ' '
    }
    result += line
  }
  return result.trim()
}

export function parseMarkdown(text: string | null | undefined): MdBlock[] {
  if (!text) return []
  const lines = text.replace(/\r\n?/g, '\n').split('\n')
  const blocks: MdBlock[] = []
  let index = 0

  while (index < lines.length) {
    const line = lines[index]

    if (!line.trim()) {
      index += 1
      continue
    }

    if (DIVIDER.test(line)) {
      blocks.push({ type: 'divider' })
      index += 1
      continue
    }

    const heading = line.match(HEADING)
    if (heading) {
      const level = Math.min(heading[1].length, 4) as 1 | 2 | 3 | 4
      blocks.push({ type: 'heading', level, inline: parseInline(heading[2].trim()) })
      index += 1
      continue
    }

    if (QUOTE.test(line)) {
      const buffer: string[] = []
      while (index < lines.length && QUOTE.test(lines[index])) {
        buffer.push(lines[index].match(QUOTE)![1])
        index += 1
      }
      blocks.push({ type: 'quote', inline: parseInline(joinSoft(buffer)) })
      continue
    }

    const ordered = ORDERED.test(line)
    if (ordered || UNORDERED.test(line)) {
      const pattern = ordered ? ORDERED : UNORDERED
      const items: MdInline[][] = []
      while (index < lines.length) {
        const hit = lines[index].match(pattern)
        if (!hit) break
        items.push(parseInline(hit[1].trim()))
        index += 1
      }
      blocks.push({ type: 'list', ordered, items })
      continue
    }

    const buffer: string[] = []
    while (index < lines.length) {
      const row = lines[index]
      if (
        !row.trim() ||
        HEADING.test(row) ||
        DIVIDER.test(row) ||
        QUOTE.test(row) ||
        UNORDERED.test(row) ||
        ORDERED.test(row)
      ) {
        break
      }
      buffer.push(row)
      index += 1
    }
    blocks.push({ type: 'paragraph', inline: parseInline(joinSoft(buffer)) })
  }

  return blocks
}

/** 把块拍平成纯文本：朗读要的是去掉标记的字，不是渲染结果。 */
export function blockText(block: MdBlock): string {
  const inlineText = (spans: MdInline[]) => spans.map((span) => span.text).join('')
  switch (block.type) {
    case 'heading':
    case 'paragraph':
    case 'quote':
      return inlineText(block.inline)
    case 'list':
      return block.items.map(inlineText).join('\n')
    case 'divider':
      return ''
  }
}
