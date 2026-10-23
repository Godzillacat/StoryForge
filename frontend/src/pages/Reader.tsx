import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, type BookResponse, type Project } from '../api/client'
import MarkdownBody from '../components/reading/MarkdownBody'
import { useSpeech } from '../components/reading/useSpeech'
import { parseMarkdown } from '../lib/markdown'
import {
  blockAtScroll,
  blockIndexOfChunk,
  findInBook,
  speechChunksOf,
} from '../lib/reading'

type Theme = 'paper' | 'night' | 'sepia'

const THEMES: { key: Theme; label: string; shell: string; body: string }[] = [
  {
    key: 'paper',
    label: '纸张',
    shell: 'bg-[#f6f1e6] text-[#2b2620]',
    body: 'bg-[#fbf8f1] text-[#2b2620]',
  },
  {
    key: 'night',
    label: '夜间',
    shell: 'bg-[#15130f] text-[#cfc7b8]',
    body: 'bg-[#1c1a15] text-[#cfc7b8]',
  },
  {
    key: 'sepia',
    label: '护眼',
    shell: 'bg-[#e9e3cf] text-[#3a3222]',
    body: 'bg-[#f0ead8] text-[#3a3222]',
  },
]

const SIZES = [
  { key: 'sm', label: '小', px: '16px' },
  { key: 'md', label: '中', px: '18px' },
  { key: 'lg', label: '大', px: '21px' },
  { key: 'xl', label: '特大', px: '24px' },
]

const LEADINGS = [
  { key: 'tight', label: '紧凑', value: '1.7' },
  { key: 'normal', label: '适中', value: '2' },
  { key: 'loose', label: '宽松', value: '2.3' },
]

const PREF_KEY = 'storyforge.reader.preferences'
const PROGRESS_PREFIX = 'storyforge.reader.progress.'
/** 上次在阅读器里打开的是哪一本 —— 刷新后要回到那里，而不是列表第一个。 */
const LAST_PROJECT_KEY = 'storyforge.reader.lastProject'

interface Preferences {
  theme: Theme
  size: string
  leading: string
}

function loadPreferences(): Preferences {
  try {
    const raw = localStorage.getItem(PREF_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<Preferences>
      return {
        theme: (parsed.theme as Theme) ?? 'paper',
        size: parsed.size ?? 'md',
        leading: parsed.leading ?? 'normal',
      }
    }
  } catch {
    // 偏好坏了不该让页面白屏，退回默认值即可。
  }
  return { theme: 'paper', size: 'md', leading: 'normal' }
}

interface Progress {
  chapterId: string
  scrollTop: number
}

function loadProgress(projectId: string): Progress | null {
  try {
    const raw = localStorage.getItem(PROGRESS_PREFIX + projectId)
    return raw ? (JSON.parse(raw) as Progress) : null
  } catch {
    return null
  }
}

export default function Reader() {
  const [projects, setProjects] = useState<Project[]>([])
  const [projectId, setProjectId] = useState('')
  const [book, setBook] = useState<BookResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [notice, setNotice] = useState('')
  const [prefs, setPrefs] = useState<Preferences>(loadPreferences)
  const [chapterId, setChapterId] = useState('')
  const [query, setQuery] = useState('')
  const [activeMatch, setActiveMatch] = useState<number | null>(null)
  const [resumeAt, setResumeAt] = useState<Progress | null>(null)
  // 检索跳转要跨章：切章后正文还没渲染，得等渲染完再滚。
  const [pendingJump, setPendingJump] = useState<{ chapterId: string; block: number } | null>(
    null,
  )
  // 切项目 / 切章时旧响应不能覆盖新的。
  const tokenRef = useRef(0)
  const scrollRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    api
      .listProjects()
      .then((list) => {
        setProjects(list)
        // 回到上次在阅读器里打开的那一本；书被删了就退回第一个。
        let last = ''
        try {
          last = localStorage.getItem(LAST_PROJECT_KEY) ?? ''
        } catch {
          // 读不到就当没记过。
        }
        const restored = list.find((row) => row.id === last) ?? list[0]
        if (restored) setProjectId(restored.id)
      })
      .catch((error) => setNotice((error as Error).message))
  }, [])

  useEffect(() => {
    if (!projectId) return
    try {
      localStorage.setItem(LAST_PROJECT_KEY, projectId)
    } catch {
      // 存不下不影响阅读。
    }
  }, [projectId])

  useEffect(() => {
    if (!projectId) return
    const token = ++tokenRef.current
    setLoading(true)
    setNotice('')
    setBook(null)
    setChapterId('')
    setActiveMatch(null)
    api
      .readBook(projectId)
      .then((value) => {
        if (tokenRef.current !== token) return
        setBook(value)
        const first = value.volumes
          .flatMap((volume) => volume.chapters)
          .find((chapter) => chapter.has_body)
        const saved = loadProgress(projectId)
        // 恢复上次读到的那一章；那一章被删或如今没有正文时退回第一本有正文的。
        const restored =
          saved &&
          value.volumes.some((v) =>
            v.chapters.some((c) => c.id === saved.chapterId && c.has_body),
          )
            ? saved
            : null
        setResumeAt(restored)
        setChapterId(restored?.chapterId ?? first?.id ?? '')
      })
      .catch((error) => {
        if (tokenRef.current === token) setNotice((error as Error).message)
      })
      .finally(() => {
        if (tokenRef.current === token) setLoading(false)
      })
  }, [projectId])

  useEffect(() => {
    try {
      localStorage.setItem(PREF_KEY, JSON.stringify(prefs))
    } catch {
      // 存不下不影响阅读。
    }
  }, [prefs])

  const chapters = useMemo(
    () => (book?.volumes ?? []).flatMap((volume) =>
      volume.chapters.map((chapter) => ({ ...chapter, volume })),
    ),
    [book],
  )
  const current = chapters.find((row) => row.id === chapterId)
  const blocks = useMemo(() => parseMarkdown(current?.content ?? ''), [current?.content])
  const chunks = useMemo(() => speechChunksOf(blocks), [blocks])
  // **整本检索**，不是只搜当前章 —— 在第三章搜「南滨」，第十二章里的命中不该被藏起来。
  const matches = useMemo(
    () =>
      findInBook(
        chapters.map((row) => ({
          id: row.id,
          title: row.title,
          content: row.content,
          volumeName: row.volume.name,
        })),
        query,
      ),
    [chapters, query],
  )
  const speech = useSpeech(chunks)
  // 朗读正在读的段落 —— 作者看得出念到哪；检索命中的高亮优先。
  const speakingBlock =
    speech.state.index >= 0 && speech.state.index < chunks.length
      ? blockIndexOfChunk(blocks, speech.state.index)
      : null
  const highlightBlock = activeMatch ?? speakingBlock

  const theme = THEMES.find((row) => row.key === prefs.theme) ?? THEMES[0]
  const size = SIZES.find((row) => row.key === prefs.size) ?? SIZES[1]
  const leading = LEADINGS.find((row) => row.key === prefs.leading) ?? LEADINGS[1]

  // 换章：回到顶部，停掉朗读（接着读上一章的话内容不对了）。
  useEffect(() => {
    speech.stop()
    setActiveMatch(null)
    if (scrollRef.current) scrollRef.current.scrollTop = 0
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chapterId])

  // 进度按帧节流：滚动事件一秒能来几十次，而只有最后那一次的位置有意义。
  const progressTimer = useRef<number | null>(null)
  const saveProgress = useCallback(() => {
    if (!projectId || !chapterId || !scrollRef.current) return
    if (progressTimer.current !== null) return
    progressTimer.current = window.setTimeout(() => {
      progressTimer.current = null
      if (!scrollRef.current) return
      try {
        localStorage.setItem(
          PROGRESS_PREFIX + projectId,
          JSON.stringify({ chapterId, scrollTop: scrollRef.current.scrollTop }),
        )
      } catch {
        // 存不下不影响阅读。
      }
    }, 200)
  }, [projectId, chapterId])

  useEffect(() => {
    return () => {
      if (progressTimer.current !== null) window.clearTimeout(progressTimer.current)
    }
  }, [])

  /** 从作者当前看得见的那一段开始念，而不是永远从第一段重来。 */
  const startSpeaking = useCallback(() => {
    if (!scrollRef.current) {
      speech.speakFrom(0)
      return
    }
    const container = scrollRef.current
    const containerTop = container.getBoundingClientRect().top
    const tops = blocks.map((_, index) => {
      const node = document.getElementById(`block-${index}`)
      return node ? node.getBoundingClientRect().top - containerTop + container.scrollTop : 0
    })
    const block = blockAtScroll(tops, container.scrollTop)
    // 块 → 朗读段的下标：列表被拆成逐项，两者不是一一对应，只能数一遍。
    let chunk = 0
    for (let index = 0; index < block; index += 1) {
      const item = blocks[index]
      chunk += item?.type === 'list' ? item.items.length : 1
    }
    speech.speakFrom(Math.min(chunk, chunks.length - 1))
  }, [blocks, chunks.length, speech])

  // 恢复上次的滚动位置。必须在正文渲染完之后做，否则 scrollTop 会被截断到 0。
  useEffect(() => {
    if (!resumeAt || !scrollRef.current || resumeAt.chapterId !== chapterId) return
    const target = resumeAt.scrollTop
    setResumeAt(null)
    requestAnimationFrame(() => {
      if (scrollRef.current) scrollRef.current.scrollTop = target
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chapterId, blocks.length])

  // 跨章检索跳转：章切过来了、块也渲染出来了，才滚得动。
  useEffect(() => {
    if (!pendingJump || pendingJump.chapterId !== chapterId || blocks.length === 0) return
    const block = pendingJump.block
    setPendingJump(null)
    requestAnimationFrame(() => jumpToMatch(block))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingJump, chapterId, blocks.length])

  function jumpToMatch(block: number) {
    setActiveMatch(block)
    const node = document.getElementById(`block-${block}`)
    node?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  /** 检索结果是整本的：先切到那一章，等它渲染出来再滚到那一块。 */
  function jumpToBookHit(targetChapterId: string, block: number) {
    setPendingJump({ chapterId: targetChapterId, block })
    if (targetChapterId === chapterId) {
      jumpToMatch(block)
      setPendingJump(null)
      return
    }
    setChapterId(targetChapterId)
  }

  return (
    <div className={`flex h-full min-h-0 gap-4 ${theme.shell}`}>
      <aside className="w-64 shrink-0 space-y-3 overflow-auto p-4">
        <select
          className="w-full rounded border border-current/30 bg-transparent px-2 py-1.5 text-sm"
          value={projectId}
          onChange={(event) => setProjectId(event.target.value)}
        >
          {projects.map((row) => (
            <option key={row.id} value={row.id} className="text-slate-900">
              {row.name}
            </option>
          ))}
        </select>

        {book && (
          <p className="text-xs opacity-60">
            {book.project_name} · 共 {book.total_words} 字 · 写完{' '}
            {book.written_chapters}/{book.total_chapters} 章
          </p>
        )}

        <nav className="space-y-2 text-sm">
          {(book?.volumes ?? []).map((volume) => (
            <div key={volume.id} className="space-y-1">
              <p className="text-xs opacity-50">
                第{volume.seq + 1}卷 {volume.name}
              </p>
              {volume.chapters.map((chapter) => (
                <button
                  key={chapter.id}
                  // 未写的章也列出来，但点不动 —— 作者要看得见这本书还差哪几章。
                  disabled={!chapter.has_body}
                  title={chapter.has_body ? '' : '这一章还没有已采纳正文'}
                  className={`block w-full rounded px-2 py-1 text-left ${
                    chapter.id === chapterId ? 'bg-black/10 font-medium' : ''
                  } ${
                    chapter.has_body
                      ? 'hover:bg-black/5'
                      : 'cursor-not-allowed opacity-40'
                  }`}
                  onClick={() => setChapterId(chapter.id)}
                >
                  第{chapter.seq + 1}章 {chapter.title}
                  <span className="ml-1 text-xs opacity-50">
                    {chapter.has_body ? chapter.word_count : '未写'}
                  </span>
                </button>
              ))}
            </div>
          ))}
        </nav>

        {book && book.total_chapters === 0 && (
          <p className="text-xs opacity-60">
            这本书还没有章节。去章节设计排好卷章后，这里就能读了。
          </p>
        )}
        {book && book.total_chapters > 0 && book.written_chapters === 0 && (
          <p className="text-xs opacity-60">
            还没有任何已采纳正文。去写作台采纳草稿后，这里就能读了。
          </p>
        )}
      </aside>

      <section className="flex min-h-0 flex-1 flex-col">
        <header className="flex flex-wrap items-center gap-2 border-b border-current/10 px-4 py-3 text-sm">
          <div className="flex gap-1">
            {THEMES.map((row) => (
              <button
                key={row.key}
                className={`rounded border border-current/30 px-2 py-1 ${
                  prefs.theme === row.key ? 'bg-black/10 font-medium' : ''
                }`}
                onClick={() => setPrefs((p) => ({ ...p, theme: row.key }))}
              >
                {row.label}
              </button>
            ))}
          </div>
          <select
            className="rounded border border-current/30 bg-transparent px-2 py-1"
            value={prefs.size}
            onChange={(event) => setPrefs((p) => ({ ...p, size: event.target.value }))}
          >
            {SIZES.map((row) => (
              <option key={row.key} value={row.key} className="text-slate-900">
                字号 {row.label}
              </option>
            ))}
          </select>
          <select
            className="rounded border border-current/30 bg-transparent px-2 py-1"
            value={prefs.leading}
            onChange={(event) => setPrefs((p) => ({ ...p, leading: event.target.value }))}
          >
            {LEADINGS.map((row) => (
              <option key={row.key} value={row.key} className="text-slate-900">
                行距 {row.label}
              </option>
            ))}
          </select>

          <div className="ml-auto flex items-center gap-2">
            <input
              className="rounded border border-current/30 bg-transparent px-2 py-1"
              placeholder="在整本书里找…"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value)
                setActiveMatch(null)
              }}
            />
            {speech.state.ready ? (
              <>
                <button
                  className="rounded border border-current/30 px-2 py-1"
                  onClick={() => (speech.state.speaking ? speech.stop() : startSpeaking())}
                  title="从你当前看到的位置开始读"
                >
                  {speech.state.speaking ? '停止朗读' : '朗读本章'}
                </button>
                {speech.state.speaking && (
                  <button
                    className="rounded border border-current/30 px-2 py-1"
                    onClick={() => (speech.state.paused ? speech.resume() : speech.pause())}
                  >
                    {speech.state.paused ? '继续' : '暂停'}
                  </button>
                )}
              </>
            ) : (
              <span className="text-xs opacity-60">
                {speech.state.supported
                  ? '系统没有可用的朗读语音'
                  : '这个环境不支持朗读'}
              </span>
            )}
          </div>
        </header>

        {notice && <p className="px-4 py-2 text-sm text-red-600">{notice}</p>}
        {loading && <p className="px-4 py-2 text-sm opacity-60">正在读取…</p>}

        {query.trim() && (
          <div className="max-h-40 overflow-auto border-b border-current/10 px-4 py-2 text-sm">
            {matches.length === 0 ? (
              <p className="opacity-60">整本书里没有「{query.trim()}」。</p>
            ) : (
              <ul className="space-y-1">
                {matches.map((hit) => (
                  <li key={`${hit.chapterId}-${hit.block}`}>
                    <button
                      className="text-left underline-offset-2 hover:underline"
                      onClick={() => jumpToBookHit(hit.chapterId, hit.block)}
                    >
                      {hit.volumeName} · 第{hit.chapterTitle}章 · 第 {hit.block + 1} 段 ·{' '}
                      {hit.snippet}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {current && (
          <div
            ref={scrollRef}
            className="min-h-0 flex-1 overflow-auto px-6 py-6"
            onScroll={saveProgress}
          >
            <article
              className={`mx-auto max-w-[42rem] rounded p-8 shadow-sm ${theme.body}`}
              style={{ fontSize: size.px, lineHeight: leading.value }}
            >
              <h1 className="mb-[1.2em] text-[1.5em] font-semibold">
                第{current.seq + 1}章 {current.title}
              </h1>
              <MarkdownBody blocks={blocks} highlightBlock={highlightBlock} />
              {speech.state.index >= 0 && speech.state.index < chunks.length && (
                <p className="mt-[1.5em] text-sm opacity-60">
                  正在朗读第 {speech.state.index + 1} / {chunks.length} 段
                </p>
              )}
            </article>
          </div>
        )}

        {!current && !loading && !notice && (
          <p className="px-6 py-10 text-sm opacity-60">从左侧选一章开始读。</p>
        )}
      </section>
    </div>
  )
}
