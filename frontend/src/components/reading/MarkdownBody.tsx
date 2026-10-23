import type { MdBlock, MdInline } from '../../lib/markdown'

/** 把解析出来的块画成 React 元素。
 *
 * **不用 `dangerouslySetInnerHTML`**：正文里出现 `<script>` 时它只会是一段文字。
 * 节点树渲染天然安全，不需要一遍转义。
 */

function Inline({ spans }: { spans: MdInline[] }) {
  return (
    <>
      {spans.map((span, index) => {
        if (span.type === 'strong') {
          return (
            <strong key={index} className="font-semibold">
              {span.text}
            </strong>
          )
        }
        if (span.type === 'em') {
          return (
            <em key={index} className="italic">
              {span.text}
            </em>
          )
        }
        if (span.type === 'code') {
          return (
            <code key={index} className="rounded bg-black/10 px-1 py-0.5 text-[0.9em]">
              {span.text}
            </code>
          )
        }
        return <span key={index}>{span.text}</span>
      })}
    </>
  )
}

const HEADING_CLASS: Record<number, string> = {
  1: 'mb-[1em] mt-[1.6em] text-[1.6em] font-semibold',
  2: 'mb-[0.9em] mt-[1.5em] text-[1.4em] font-semibold',
  3: 'mb-[0.8em] mt-[1.3em] text-[1.2em] font-semibold',
  4: 'mb-[0.7em] mt-[1.2em] text-[1.05em] font-semibold',
}

export default function MarkdownBody({
  blocks,
  highlightBlock,
}: {
  blocks: MdBlock[]
  /** 检索命中要跳到的那一块；给它一个底色，让作者一眼看见。 */
  highlightBlock?: number | null
}) {
  return (
    <div className="space-y-[0.9em]">
      {blocks.map((block, index) => {
        const marked = highlightBlock === index
        const markClass = marked ? 'rounded bg-amber-300/30 px-1' : ''
        const anchor = index === highlightBlock ? 'scroll-mt-24' : ''

        switch (block.type) {
          case 'heading':
            return (
              <h2
                key={index}
                id={`block-${index}`}
                className={`${HEADING_CLASS[block.level]} ${markClass} ${anchor}`}
              >
                <Inline spans={block.inline} />
              </h2>
            )
          case 'paragraph':
            return (
              <p
                key={index}
                id={`block-${index}`}
                className={`indent-[2em] leading-[inherit] ${markClass} ${anchor}`}
              >
                <Inline spans={block.inline} />
              </p>
            )
          case 'quote':
            return (
              <blockquote
                key={index}
                id={`block-${index}`}
                className={`border-l-2 border-current/30 pl-[1em] opacity-80 ${markClass} ${anchor}`}
              >
                <Inline spans={block.inline} />
              </blockquote>
            )
          case 'list':
            return (
              <ul
                key={index}
                id={`block-${index}`}
                className={`list-disc space-y-[0.3em] pl-[1.6em] ${markClass} ${anchor}`}
              >
                {block.items.map((item, itemIndex) => (
                  <li key={itemIndex}>
                    <Inline spans={item} />
                  </li>
                ))}
              </ul>
            )
          case 'divider':
            return (
              <hr
                key={index}
                id={`block-${index}`}
                className={`my-[1.6em] border-current/20 ${anchor}`}
              />
            )
        }
      })}
    </div>
  )
}
