import { useEffect, useRef, useState } from 'react'
import {
  api,
  streamSceneGeneration,
  type ContextPreview as ContextPreviewData,
  type Project,
  type RevisionDetail,
  type SceneTextState,
  type VolumeNode,
} from '../api/client'
import ContextPreview from '../components/writing/ContextPreview'
import DiffPanel from '../components/writing/DiffPanel'
import GenerationStream from '../components/writing/GenerationStream'
import RevisionHistory from '../components/writing/RevisionHistory'
import SceneTextView from '../components/writing/SceneTextView'
import WritingTree from '../components/writing/WritingTree'

function findScene(volumes: VolumeNode[], sceneId: string) {
  for (const volume of volumes) {
    for (const chapter of volume.chapters) {
      const scene = chapter.scenes.find((item) => item.id === sceneId)
      if (scene) return { volume, chapter, scene }
    }
  }
  return null
}

export default function Writing() {
  const [projects, setProjects] = useState<Project[]>([])
  const [projectId, setProjectId] = useState('')
  const [volumes, setVolumes] = useState<VolumeNode[]>([])
  const [selectedSceneId, setSelectedSceneId] = useState('')
  const [text, setText] = useState<SceneTextState | null>(null)
  const [preview, setPreview] = useState<ContextPreviewData | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState('')
  const [bodyDraft, setBodyDraft] = useState('')
  const [aiDraft, setAiDraft] = useState('')
  const [mode, setMode] = useState<'body' | 'draft'>('body')
  const [generating, setGenerating] = useState(false)
  const [streamText, setStreamText] = useState('')
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const [revision, setRevision] = useState<RevisionDetail | null>(null)

  const treeToken = useRef(0)
  const sceneToken = useRef(0)
  const generateToken = useRef(0)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    api
      .listProjects()
      .then((list) => {
        setProjects(list)
        if (list[0]) setProjectId(list[0].id)
      })
      .catch((error) => setNotice((error as Error).message))
  }, [])

  useEffect(() => {
    if (!projectId) return
    const token = ++treeToken.current
    sceneToken.current += 1
    generateToken.current += 1
    abortRef.current?.abort()
    setVolumes([])
    setSelectedSceneId('')
    setText(null)
    setPreview(null)
    setPreviewError('')
    setBodyDraft('')
    setAiDraft('')
    setStreamText('')
    setGenerating(false)
    setRevision(null)
    setNotice('')

    api
      .getChapterTree(projectId)
      .then((data) => {
        if (treeToken.current === token) setVolumes(data.volumes)
      })
      .catch((error) => {
        if (treeToken.current === token) setNotice((error as Error).message)
      })
  }, [projectId])

  const hasUnsaved =
    Boolean(text) &&
    (bodyDraft !== (text?.body ?? '') || aiDraft !== (text?.draft?.content ?? ''))

  const changeProject = (nextId: string) => {
    if (nextId === projectId) return
    if (hasUnsaved && !window.confirm('当前场景有未保存的修改，确定切换项目吗？')) return
    setProjectId(nextId)
  }

  const loadScene = async (sceneId: string) => {
    const token = ++sceneToken.current
    setPreviewLoading(true)
    setPreviewError('')
    setPreview(null)
    try {
      const [stateResult, contextResult] = await Promise.allSettled([
        api.getSceneText(sceneId),
        api.getSceneContextPreview(sceneId),
      ])
      if (sceneToken.current !== token) return
      if (stateResult.status === 'fulfilled') {
        const state = stateResult.value
        setText(state)
        setBodyDraft(state.body ?? '')
        setAiDraft(state.draft?.content ?? '')
        setMode(state.draft ? 'draft' : 'body')
      } else {
        setNotice((stateResult.reason as Error).message)
      }
      if (contextResult.status === 'fulfilled') {
        setPreview(contextResult.value)
      } else {
        setPreviewError((contextResult.reason as Error).message)
      }
    } catch (error) {
      if (sceneToken.current === token) setNotice((error as Error).message)
    } finally {
      if (sceneToken.current === token) setPreviewLoading(false)
    }
  }

  const selectScene = (sceneId: string) => {
    if (sceneId === selectedSceneId) return
    if (hasUnsaved && !window.confirm('当前场景有未保存的修改，确定切换吗？')) return
    abortRef.current?.abort()
    generateToken.current += 1
    setGenerating(false)
    setStreamText('')
    setSelectedSceneId(sceneId)
    void loadScene(sceneId)
  }

  const refreshText = async (sceneId: string): Promise<SceneTextState | null> => {
    const token = sceneToken.current
    const state = await api.getSceneText(sceneId)
    if (sceneToken.current !== token) return null
    setText(state)
    setBodyDraft(state.body ?? '')
    setAiDraft(state.draft?.content ?? '')
    return state
  }

  const saveBody = async () => {
    if (!text) return
    setBusy(true)
    setNotice('')
    try {
      const state = await api.saveSceneBody(text.scene_id, bodyDraft)
      setText(state)
      setBodyDraft(state.body ?? '')
      setNotice('正文已保存')
    } catch (error) {
      setNotice((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const saveDraft = async () => {
    if (!text?.draft) return
    setBusy(true)
    setNotice('')
    try {
      const saved = await api.saveSceneDraft(text.scene_id, aiDraft)
      setAiDraft(saved.content)
      setText((current) =>
        current && current.draft
          ? { ...current, draft: { ...current.draft, content: saved.content } }
          : current,
      )
      setNotice('草稿已保存')
    } catch (error) {
      setNotice((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const adopt = async () => {
    if (!text?.draft) return
    if (!window.confirm('采纳后会用草稿整份替换已采纳正文，并生成修订快照。继续？')) return
    setBusy(true)
    setNotice('')
    try {
      const state = await api.adoptSceneDraft(text.scene_id)
      setText(state)
      setBodyDraft(state.body ?? '')
      setAiDraft('')
      setMode('body')
      setNotice('已采纳，已生成修订快照')
    } catch (error) {
      setNotice((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const discard = async () => {
    if (!text?.draft) return
    if (!window.confirm('丢弃这份 AI 草稿？此操作不可撤销。')) return
    setBusy(true)
    setNotice('')
    try {
      await api.discardSceneDraft(text.scene_id)
      setAiDraft('')
      await refreshText(text.scene_id)
      setMode('body')
      setNotice('草稿已丢弃')
    } catch (error) {
      setNotice((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const generate = async () => {
    if (!selectedSceneId || generating) return
    const sceneId = selectedSceneId
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    const token = ++generateToken.current
    setGenerating(true)
    setStreamText('')
    setNotice('')

    try {
      await streamSceneGeneration(
        sceneId,
        {
          onDelta: (delta) => {
            if (generateToken.current === token) {
              setStreamText((current) => current + delta)
            }
          },
          onDone: () => {
            if (generateToken.current === token) setNotice('生成完成，草稿已更新')
          },
          onError: (data) => {
            if (generateToken.current === token) {
              setNotice(`${data.message}（已保留 ${data.chars} 字）`)
            }
          },
        },
        controller.signal,
      )
    } catch (error) {
      if ((error as Error).name !== 'AbortError' && generateToken.current === token) {
        setNotice((error as Error).message)
      }
    } finally {
      if (generateToken.current === token) {
        setGenerating(false)
        try {
          const state = await refreshText(sceneId)
          setMode(state?.draft ? 'draft' : 'body')
        } catch (error) {
          setNotice((error as Error).message)
        }
      }
    }
  }

  const stop = () => {
    abortRef.current?.abort()
    setNotice('已请求停止；已生成的内容会尽量保留。')
  }

  const openRevision = async (revisionId: string) => {
    if (!text) return
    setBusy(true)
    setNotice('')
    try {
      setRevision(await api.getSceneRevision(text.scene_id, revisionId))
    } catch (error) {
      setNotice((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const restoreRevision = async (revisionId: string) => {
    if (!text) return
    if (!window.confirm('恢复这个修订？当前正文会被替换，并生成一条新的恢复修订。')) return
    setBusy(true)
    setNotice('')
    try {
      const state = await api.restoreSceneRevision(text.scene_id, revisionId)
      setText(state)
      setBodyDraft(state.body ?? '')
      setMode('body')
      setRevision(null)
      setNotice('已恢复旧版并生成新的修订')
    } catch (error) {
      setNotice((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const selected = findScene(volumes, selectedSceneId)
  const sceneLabel = selected
    ? `第${selected.volume.seq + 1}卷 第${selected.chapter.seq + 1}章 场景${selected.scene.seq + 1}`
    : ''

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-xl font-semibold">写作台</h2>
        <select
          value={projectId}
          onChange={(event) => changeProject(event.target.value)}
          className="rounded border border-slate-700 bg-slate-900 px-3 py-1.5 text-sm"
        >
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </select>
        {sceneLabel && <span className="text-xs text-slate-500">{sceneLabel}</span>}
      </div>

      {notice && (
        <p className="rounded border border-slate-800 bg-slate-900 px-3 py-2 text-sm text-slate-300">
          {notice}
        </p>
      )}

      {!projectId ? (
        <p className="rounded border border-slate-800 p-4 text-sm text-slate-500">
          先创建一个项目。
        </p>
      ) : (
        <div className="grid gap-4 xl:grid-cols-[240px_minmax(0,1fr)_320px]">
          <aside className="rounded border border-slate-800 p-3">
            <WritingTree
              volumes={volumes}
              selectedSceneId={selectedSceneId}
              onSelect={selectScene}
            />
          </aside>

          <section className="min-w-0 space-y-3">
            {!selected ? (
              <p className="rounded border border-slate-800 p-4 text-sm text-slate-500">
                从左侧选择一个场景开始写作。
              </p>
            ) : (
              <>
                <section className="space-y-1 rounded border border-slate-800 p-3 text-sm">
                  <p className="text-slate-300">
                    目标：{selected.scene.goal || '（未写目标）'}
                  </p>
                  <p className="text-slate-400">冲突：{selected.scene.conflict || '（未写）'}</p>
                  <p className="text-slate-400">转折：{selected.scene.turn || '（未写）'}</p>
                  <p className="text-xs text-slate-500">
                    目标字数：{selected.scene.target_words_min ?? '?'}–
                    {selected.scene.target_words_max ?? '?'} · 正文{' '}
                    {text?.word_count ?? 0} 字
                  </p>
                </section>

                <div className="flex flex-wrap items-center gap-2">
                  {generating ? (
                    <button
                      type="button"
                      onClick={stop}
                      className="rounded bg-amber-600 px-3 py-1.5 text-sm text-white hover:bg-amber-500"
                    >
                      停止
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={generate}
                      disabled={busy}
                      className="rounded bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-500 disabled:opacity-50"
                    >
                      生成正文
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={saveBody}
                    disabled={busy || generating || mode !== 'body'}
                    className="rounded border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:text-white disabled:opacity-50"
                  >
                    保存正文
                  </button>
                  <button
                    type="button"
                    onClick={saveDraft}
                    disabled={busy || generating || !text?.draft || mode !== 'draft'}
                    className="rounded border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:text-white disabled:opacity-50"
                  >
                    保存草稿
                  </button>
                  <button
                    type="button"
                    onClick={adopt}
                    disabled={busy || generating || !text?.draft}
                    className="rounded bg-emerald-600 px-3 py-1.5 text-sm text-white hover:bg-emerald-500 disabled:opacity-50"
                  >
                    采纳为正文
                  </button>
                  <button
                    type="button"
                    onClick={discard}
                    disabled={busy || generating || !text?.draft}
                    className="rounded border border-amber-800 px-3 py-1.5 text-sm text-amber-300 hover:text-amber-200 disabled:opacity-50"
                  >
                    丢弃草稿
                  </button>
                </div>

                <GenerationStream text={streamText} generating={generating} />

                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setMode('body')}
                    className={`rounded px-3 py-1 text-sm ${
                      mode === 'body' ? 'bg-slate-800 text-white' : 'text-slate-400'
                    }`}
                  >
                    已采纳正文
                  </button>
                  <button
                    type="button"
                    onClick={() => setMode('draft')}
                    disabled={!text?.draft}
                    className={`rounded px-3 py-1 text-sm disabled:opacity-40 ${
                      mode === 'draft' ? 'bg-slate-800 text-white' : 'text-slate-400'
                    }`}
                  >
                    AI 草稿
                  </button>
                </div>

                {mode === 'body' ? (
                  <SceneTextView
                    title="已采纳正文"
                    value={bodyDraft}
                    onChange={setBodyDraft}
                    disabled={busy || generating}
                    placeholder="还没有正文。可以先点「生成正文」，也可以直接手写。"
                  />
                ) : (
                  <SceneTextView
                    title="AI 草稿"
                    value={aiDraft}
                    onChange={setAiDraft}
                    disabled={busy || generating}
                    placeholder="AI 草稿会出现在这里，可先修改再采纳。"
                  />
                )}

                {text?.draft && !generating && (
                  <DiffPanel oldText={text.body ?? ''} newText={aiDraft} />
                )}
              </>
            )}
          </section>

          <aside className="min-w-0 space-y-4">
            <ContextPreview
              data={preview}
              loading={previewLoading}
              error={previewError}
            />
            {revision ? (
              <section className="space-y-2 rounded border border-slate-800 p-3 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="font-medium text-slate-300">修订全文</h3>
                  <button
                    type="button"
                    onClick={() => setRevision(null)}
                    className="text-xs text-slate-400 hover:text-white"
                  >
                    关闭
                  </button>
                </div>
                <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words text-xs text-slate-300">
                  {revision.content}
                </pre>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => restoreRevision(revision.id)}
                  className="rounded border border-slate-700 px-2 py-1 text-xs text-slate-300 hover:text-white disabled:opacity-50"
                >
                  恢复此版本
                </button>
              </section>
            ) : (
              <RevisionHistory
                revisions={text?.revisions ?? []}
                busy={busy}
                onOpen={openRevision}
                onRestore={restoreRevision}
              />
            )}
          </aside>
        </div>
      )}
    </div>
  )
}
