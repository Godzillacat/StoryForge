/** 朗读与检索的纯函数。UI 只负责「什么时候调」，逻辑都在这里，能被 vitest 覆盖。 */

import type { MdBlock } from './markdown'
import { blockText, parseMarkdown } from './markdown'

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
      // 也没法在项与项之间暂停。**空列表项不念** —— 它会在 `chunkCountOf`
      // 里被算作 0，这里也必须跳过，否则块↔段的下标会错位。
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

/** 朗读队列的下标 → 正文块的下标。
 *
 * `speechChunksOf` 会把列表拆成逐项，所以两者不是一一对应；高亮跟随要的是
 * 「现在念的是正文里的哪一块」。找不到时返回 null（分隔线不成段）。
 */
export function blockIndexOfChunk(blocks: MdBlock[], chunk: number): number | null {
  if (chunk < 0) return null
  let seen = 0
  for (let index = 0; index < blocks.length; index += 1) {
    const size = chunkCountOf(blocks[index])
    if (size === 0) continue
    if (chunk < seen + size) return index
    seen += size
  }
  return null
}

/** 一块正文会产生几段朗读。**必须与 `speechChunksOf` 用同一份规则**，
 * 否则「从第几块起读」与「高亮第几块」会各算各的、越读越偏。
 *
 * 分隔线、空块不产生朗读段；列表逐项各算一段。
 */
export function chunkCountOf(block: MdBlock): number {
  if (block.type === 'list') {
    return block.items.filter((item) =>
      item.some((span) => span.text.trim().length > 0),
    ).length
  }
  return blockText(block).trim() ? 1 : 0
}

/** 第 `block` 块之前一共产生了几段朗读 —— 「从可见块起读」要用它。 */
export function chunkIndexAtBlock(blocks: MdBlock[], block: number): number {
  let chunk = 0
  for (let index = 0; index < Math.min(block, blocks.length); index += 1) {
    chunk += chunkCountOf(blocks[index])
  }
  return chunk
}

/** 当前滚动到第几块 —— 朗读从「作者看得见的地方」开始，而不是永远从第一段。
 *
 * `tops` 是每块的文档偏移（块顶距离页面顶部），`scrollTop` 是容器已滚动的距离。
 * 取第一块底边还没滚过去的块。
 */
export function blockAtScroll(tops: number[], scrollTop: number): number {
  if (tops.length === 0) return 0
  for (let index = 0; index < tops.length; index += 1) {
    if (tops[index] >= scrollTop - 8) return index
  }
  return tops.length - 1
}

export interface BookHit {
  chapterId: string
  chapterSeq: number
  chapterTitle: string
  volumeName: string
  /** 命中处在 `parseMarkdown(chapter.content)` 里的块序号。 */
  block: number
  snippet: string
}

export interface SearchableChapter {
  id: string
  seq: number
  title: string
  content: string
  volumeName: string
}

/** 整本检索：逐章在正文里找，返回章 + 块。
 *
 * **不复用 `/search`**：那个接口返回的是场景级命中（`entity_id` 是场景 id），
 * 而阅读器要跳到「章里的第几段」。两者对不上，硬接还得再查一次场景属于哪一章、
 * 那一章的场景顺序如何 —— 直接在已加载的正文里找更直接，且正文本来就全在手上。
 *
 * 每章每个命中块只报一次（同一块里出现三次不该列出三条）。
 */
export function findInBook(chapters: SearchableChapter[], query: string): BookHit[] {
  const needle = query.trim()
  if (!needle) return []
  const hits: BookHit[] = []
  for (const chapter of chapters) {
    if (!chapter.content) continue
    for (const hit of findMatches(parseMarkdown(chapter.content), needle)) {
      hits.push({
        chapterId: chapter.id,
        chapterSeq: chapter.seq,
        chapterTitle: chapter.title,
        volumeName: chapter.volumeName,
        block: hit.block,
        snippet: hit.snippet,
      })
    }
  }
  return hits
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
