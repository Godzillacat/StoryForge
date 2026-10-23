/** 朗读与检索的纯函数。UI 只负责「什么时候调」，逻辑都在这里，能被 vitest 覆盖。 */

import type { MdBlock } from './markdown'
import { blockText } from './markdown'

/** 把正文块拍平成可朗读的段落。
 *
 * **按段落排队，不拼成一整条**：单条长 utterance 在很多系统上会在中途断掉，
 * 也无法可靠地暂停与继续；分段排队才能做「暂停 / 跳到下一段」与高亮跟随。
 *
 * 空段（分隔线、空引用）不进队列 —— 让朗读停顿一下没有意义。
 */
export function speechChunksOf(blocks: MdBlock[]): string[] {
  return blocks
    .flatMap((block) => {
      // 列表逐项朗读：一条 utterance 里塞换行，某些系统会念成一个长句，
      // 也没法在项与项之间暂停。
      if (block.type === 'list') {
        return block.items.map((item) =>
          item.map((span) => span.text).join(''),
        )
      }
      return [blockText(block)]
    })
    .map((text) => text.trim())
    .filter((text) => text.length > 0)
}

export interface MatchHit {
  /** 命中在第几块（`parseMarkdown` 的下标）。 */
  block: number
  /** 命中处前后的片段，供结果列表显示。 */
  snippet: string
}

/** 在块的纯文本里找查询词，返回块序号与片段。
 *
 * 检索复用的是同一个项目已经建好的 FTS 索引（P2a 起覆盖正文）；这里只**定位**，
 * 不重新实现检索。大小写不敏感，纯文本直接匹配 —— 正文是中文，分词在这里
 * 没有收益。
 */
export function findMatches(
  blocks: MdBlock[],
  query: string,
  width = 24,
): MatchHit[] {
  const needle = query.trim().toLowerCase()
  if (!needle) return []
  const hits: MatchHit[] = []
  blocks.forEach((block, index) => {
    const text = blockText(block)
    const at = text.toLowerCase().indexOf(needle)
    if (at === -1) return
    const start = Math.max(0, at - width)
    const end = Math.min(text.length, at + needle.length + width)
    const prefix = start > 0 ? '…' : ''
    const suffix = end < text.length ? '…' : ''
    hits.push({ block: index, snippet: prefix + text.slice(start, end) + suffix })
  })
  return hits
}
