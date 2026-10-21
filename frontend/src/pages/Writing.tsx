import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  api,
  streamSceneGeneration,
  type AuditIssue,
  type AuditResolution,
  type BatchJob,
  type ContextPreview as ContextPreviewData,
  type LogicStage,
  type Project,
  type RevisionDetail,
  type SceneTextState,
  type VolumeNode,
  type WritebackApplyPayload,
  type WritebackSuggestion,
} from '../api/client'
import AuditPanel from '../components/writing/AuditPanel'
import BatchPanel from '../components/writing/BatchPanel'
import ContextPreview from '../components/writing/ContextPreview'
import DiffPanel from '../components/writing/DiffPanel'
import GenerationStream from '../components/writing/GenerationStream'
import LogicPanel from '../components/writing/LogicPanel'
import RevisionHistory from '../components/writing/RevisionHistory'
import SceneTextView from '../components/writing/SceneTextView'
import WritebackPanel from '../components/writing/WritebackPanel'
import WritingTree from '../components/writing/WritingTree'

interface RunInfo {
  run_id: string
  model: string
  agent: string
  estimated_tokens: number
  trimmed: Record<string, string>
  status?: string
  prompt_tokens?: number
  completion_tokens?: number
  cost_estimate?: number
  duration_ms?: number
  chars?: number
  error?: { kind: string; message: string }
}

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
  const navigate = useNavigate()
  const [projects, setProjects] = useState<Project[]>([])
  const [projectsLoading, setProjectsLoading] = useState(true)
  const [projectId, setProjectId] = useState('')
  const [volumes, setVolumes] = useState<VolumeNode[]>([])
  const [treeLoading, setTreeLoading] = useState(false)
  const [textLoading, setTextLoading] = useState(false)
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
  const [runInfo, setRunInfo] = useState<RunInfo | null>(null)
  const [stopCooldown, setStopCooldown] = useState(false)
  const [auditIssues, setAuditIssues] = useState<AuditIssue[]>([])
  const [auditLastAt, setAuditLastAt] = useState<string | null>(null)
  const [auditLoading, setAuditLoading] = useState(false)
  const [auditWarning, setAuditWarning] = useState('')
  const [logicStage, setLogicStage] = useState<LogicStage>('text')
  const [logicIssues, setLogicIssues] = useState<AuditIssue[]>([])
  const [logicLastAt, setLogicLastAt] = useState<string | null>(null)
  const [logicLoading, setLogicLoading] = useState(false)
  const [logicWarning, setLogicWarning] = useState('')
  const [writeback, setWriteback] = useState<WritebackSuggestion | null>(null)
  const [writebackLoading, setWritebackLoading] = useState(false)
  const [writebackApplying, setWritebackApplying] = useState(false)
  const [batchJob, setBatchJob] = useState<BatchJob | null>(null)
  const [batchLoading, setBatchLoading] = useState(false)
  const [batchBusy, setBatchBusy] = useState(false)

  const writebackBusy = writebackLoading || writebackApplying

  const treeToken = useRef(0)
  const sceneToken = useRef(0)
  const logicToken = useRef(0)
  const batchToken = useRef(0)
  const generateToken = useRef(0)
  const abortRef = useRef<AbortController | null>(null)
  const streamTextRef = useRef('')
  const runIdRef = useRef('')
  const cooldownTimerRef = useRef<number | null>(null)

  const clearStopCooldown = () => {
    if (cooldownTimerRef.current !== null) {
      window.clearTimeout(cooldownTimerRef.current)
      cooldownTimerRef.current = null
    }
    setStopCooldown(false)
  }

  const startStopCooldown = () => {
    if (cooldownTimerRef.current !== null) window.clearTimeout(cooldownTimerRef.current)
    setStopCooldown(true)
    cooldownTimerRef.current = window.setTimeout(() => {
      cooldownTimerRef.current = null
      setStopCooldown(false)
    }, 1000)
  }

  useEffect(() => {
    api
      .listProjects()
      .then((list) => {
        setProjects(list)
        if (list[0]) setProjectId(list[0].id)
      })
      .catch((error) => setNotice((error as Error).message))
      .finally(() => setProjectsLoading(false))
  }, [])

  // 页面卸载时中止在途生成，避免流读取器悬挂或向已卸载组件写状态。
  useEffect(
    () => () => {
      generateToken.current += 1
      abortRef.current?.abort()
      if (cooldownTimerRef.current !== null) {
        window.clearTimeout(cooldownTimerRef.current)
        cooldownTimerRef.current = null
      }
    },
    [],
  )

  useEffect(() => {
    if (!projectId) return
    const token = ++treeToken.current
    sceneToken.current += 1
    logicToken.current += 1
    batchToken.current += 1
    generateToken.current += 1
    abortRef.current?.abort()
    runIdRef.current = ''
    streamTextRef.current = ''
    clearStopCooldown()
    setVolumes([])
    setSelectedSceneId('')
    setText(null)
    setTextLoading(false)
    setPreview(null)
    setPreviewLoading(false)
    setPreviewError('')
    setBodyDraft('')
    setAiDraft('')
    setStreamText('')
    setRunInfo(null)
    setGenerating(false)
    setRevision(null)
    setNotice('')
    setAuditIssues([])
    setAuditLastAt(null)
    setAuditWarning('')
    setAuditLoading(false)
    setLogicStage('text')
    setLogicIssues([])
    setLogicLastAt(null)
    setLogicWarning('')
    setLogicLoading(false)
    setWriteback(null)
    setWritebackLoading(false)
    setWritebackApplying(false)
    setBatchJob(null)
    setBatchLoading(false)
    setBatchBusy(false)

    setTreeLoading(true)
    api
      .getChapterTree(projectId)
      .then((data) => {
        if (treeToken.current === token) setVolumes(data.volumes)
      })
      .catch((error) => {
        if (treeToken.current === token) setNotice((error as Error).message)
      })
      .finally(() => {
        if (treeToken.current === token) setTreeLoading(false)
      })
    api
      .getLatestBatch(projectId)
      .then((job) => {
        if (treeToken.current === token) setBatchJob(job)
      })
      .catch(() => {
        // 最近任务读不到不影响写作；作者仍可新建批量任务。
      })
  }, [projectId])

  // 活动任务每 2 秒拉一次进度；完成或停止后自动结束轮询并刷新树。
  useEffect(() => {
    if (!batchJob || batchJob.status !== 'running') return
    const jobId = batchJob.id
    let cancelled = false
    const token = batchToken.current
    const timer = window.setInterval(() => {
      api
        .getBatch(jobId)
        .then((next) => {
          if (cancelled || batchToken.current !== token) return
          setBatchJob(next)
          if (next.status !== 'running') void refreshTree()
        })
        .catch(() => {
          // 轮询失败不打扰作者；下一次继续。
        })
    }, 2000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [batchJob?.id, batchJob?.status])

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
    const logicSeq = ++logicToken.current
    setTextLoading(true)
    setPreviewLoading(true)
    setPreviewError('')
    setPreview(null)
    setAuditIssues([])
    setAuditLastAt(null)
    setAuditWarning('')
    setLogicIssues([])
    setLogicLastAt(null)
    setLogicWarning('')
    try {
      const [stateResult, contextResult, auditResult, logicResult] =
        await Promise.allSettled([
          api.getSceneText(sceneId),
          api.getSceneContextPreview(sceneId),
          api.getSceneAudit(sceneId),
          api.getSceneLogicCheck(sceneId, logicStage),
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
      if (auditResult.status === 'fulfilled') {
        setAuditIssues(auditResult.value.issues)
        setAuditLastAt(auditResult.value.last_audited_at)
      } else {
        setAuditWarning((auditResult.reason as Error).message)
      }
      if (logicResult.status === 'fulfilled') {
        if (logicToken.current === logicSeq) {
          setLogicIssues(logicResult.value.issues)
          setLogicLastAt(logicResult.value.last_checked_at)
        }
      } else if (logicToken.current === logicSeq) {
        setLogicWarning((logicResult.reason as Error).message)
      }
    } catch (error) {
      if (sceneToken.current === token) setNotice((error as Error).message)
    } finally {
      if (sceneToken.current === token) {
        setPreviewLoading(false)
        setTextLoading(false)
      }
    }
  }

  const selectScene = (sceneId: string) => {
    if (sceneId === selectedSceneId) return
    if (hasUnsaved && !window.confirm('当前场景有未保存的修改，确定切换吗？')) return
    abortRef.current?.abort()
    generateToken.current += 1
    logicToken.current += 1
    clearStopCooldown()
    runIdRef.current = ''
    streamTextRef.current = ''
    // 切换场景必须先清空上一个场景的正文、草稿与修订，否则加载期间
    // 作者看到的仍是旧场景内容，编辑会落到旧场景的 text.scene_id 上。
    setGenerating(false)
    setStreamText('')
    setRunInfo(null)
    setText(null)
    setBodyDraft('')
    setAiDraft('')
    setMode('body')
    setRevision(null)
    setPreview(null)
    setPreviewError('')
    setNotice('')
    setAuditIssues([])
    setAuditLastAt(null)
    setAuditWarning('')
    setLogicIssues([])
    setLogicLastAt(null)
    setLogicWarning('')
    // 在途审校属于上一个场景：loadScene 会递增 sceneToken 让它作废，
    // 那份响应不会再清 loading，必须在这里收掉。
    setAuditLoading(false)
    setLogicLoading(false)
    setWriteback(null)
    setWritebackLoading(false)
    setWritebackApplying(false)
    setSelectedSceneId(sceneId)
    void loadScene(sceneId)
  }

  // 正文写入后刷新左侧树，让「未写 / 已写」标记跟上；
  // 不递增 treeToken，切项目时由 effect 递增它来废弃这次刷新。
  const refreshTree = async () => {
    if (!projectId) return
    const token = treeToken.current
    try {
      const data = await api.getChapterTree(projectId)
      if (treeToken.current !== token) return
      setVolumes(data.volumes)
    } catch (error) {
      if (treeToken.current === token) setNotice((error as Error).message)
    }
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

  // 停止后运行记录可能还在服务端收尾，从运行列表里按 run_id 补拉一次。
  const refreshRunRecord = async (targetProjectId: string, runId: string, token: number) => {
    try {
      const runs = await api.listRuns(targetProjectId)
      if (generateToken.current !== token) return
      const found = runs.find((item) => item.id === runId)
      if (!found) return
      setRunInfo((current) =>
        current && current.run_id === runId
          ? {
              ...current,
              status: found.status,
              prompt_tokens: found.prompt_tokens,
              completion_tokens: found.completion_tokens,
              cost_estimate: found.cost_estimate,
              duration_ms: found.duration_ms,
              error: found.error ?? current.error,
            }
          : current,
      )
    } catch {
      // 运行记录补拉失败不应覆盖正文刷新结果。
    }
  }

  const saveBody = async () => {
    if (!text) return
    const token = sceneToken.current
    const sceneId = text.scene_id
    setBusy(true)
    setNotice('')
    try {
      const state = await api.saveSceneBody(sceneId, bodyDraft)
      if (sceneToken.current !== token) return
      setText(state)
      setBodyDraft(state.body ?? '')
      // 服务端会把旧问题标为 superseded；本地也立即清掉，避免对旧文本处理问题。
      setAuditIssues([])
      setAuditWarning('')
      if (logicStage === 'text') {
        setLogicIssues([])
        setLogicWarning('')
      }
      setNotice(auditIssues.length > 0 ? '正文已保存；之前的审校结果已失效，请重新审校' : '正文已保存')
      void refreshTree()
    } catch (error) {
      if (sceneToken.current === token) setNotice((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const saveDraft = async () => {
    if (!text?.draft) return
    const token = sceneToken.current
    const sceneId = text.scene_id
    setBusy(true)
    setNotice('')
    try {
      const saved = await api.saveSceneDraft(sceneId, aiDraft)
      if (sceneToken.current !== token) return
      setAiDraft(saved.content)
      setText((current) =>
        current && current.draft
          ? { ...current, draft: { ...current.draft, content: saved.content } }
          : current,
      )
      setNotice('草稿已保存')
    } catch (error) {
      if (sceneToken.current === token) setNotice((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const adopt = async () => {
    if (!text?.draft) return
    if (!window.confirm('采纳后会用草稿整份替换已采纳正文，并生成修订快照。继续？')) return
    const token = sceneToken.current
    const sceneId = text.scene_id
    const needsSave = aiDraft !== text.draft.content
    setBusy(true)
    setNotice('')
    try {
      // 采纳作用于服务端存着的草稿；界面上的修改必须先落库，
      // 否则作者改过的文字会被静默丢掉。
      if (needsSave) {
        try {
          await api.saveSceneDraft(sceneId, aiDraft)
        } catch (error) {
          if (sceneToken.current === token) {
            setNotice(`草稿保存失败，未采纳：${(error as Error).message}`)
          }
          return
        }
        if (sceneToken.current !== token) return
      }
      const state = await api.adoptSceneDraft(sceneId)
      if (sceneToken.current !== token) return
      setText(state)
      setBodyDraft(state.body ?? '')
      setAiDraft('')
      setMode('body')
      setAuditIssues([])
      setAuditWarning('')
      if (logicStage === 'text') {
        setLogicIssues([])
        setLogicWarning('')
      }
      setNotice(
        auditIssues.length > 0
          ? '已采纳，已生成修订快照；之前的审校结果已失效，请重新审校'
          : '已采纳，已生成修订快照',
      )
      void refreshTree()
    } catch (error) {
      if (sceneToken.current === token) setNotice((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const discard = async () => {
    if (!text?.draft) return
    if (!window.confirm('丢弃这份 AI 草稿？此操作不可撤销。')) return
    const token = sceneToken.current
    const sceneId = text.scene_id
    setBusy(true)
    setNotice('')
    try {
      await api.discardSceneDraft(sceneId)
      if (sceneToken.current !== token) return
      setAiDraft('')
      const state = await refreshText(sceneId)
      if (sceneToken.current !== token || !state) return
      setMode('body')
      setNotice('草稿已丢弃')
    } catch (error) {
      if (sceneToken.current === token) setNotice((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const runAudit = async () => {
    if (
      !selectedSceneId ||
      !text?.has_body ||
      generating ||
      busy ||
      auditLoading ||
      logicLoading ||
      writebackBusy
    ) {
      return
    }
    const token = sceneToken.current
    const sceneId = selectedSceneId
    setAuditLoading(true)
    setNotice('')
    try {
      const result = await api.runSceneAudit(sceneId)
      if (sceneToken.current !== token) return
      setAuditIssues(result.issues)
      setAuditWarning(result.warning)
      setAuditLastAt(new Date().toISOString())
      if (result.llm_status !== 'ok') {
        setNotice(
          `${result.warning || '语义审计未完成'}${
            result.issues.length > 0 ? `（规则层发现 ${result.issues.length} 条问题）` : ''
          }`,
        )
      } else if (result.suppressed > 0) {
        setNotice(`审校完成；${result.suppressed} 条问题已记为特例，不再重复上报`)
      } else if (result.issues.length > 0) {
        setNotice(`审校完成，发现 ${result.issues.length} 条问题`)
      } else {
        setNotice('审校完成，没有发现问题')
      }
    } catch (error) {
      if (sceneToken.current === token) setNotice((error as Error).message)
    } finally {
      if (sceneToken.current === token) setAuditLoading(false)
    }
  }

  const runLogic = async () => {
    if (!selectedSceneId || generating || busy || auditLoading || logicLoading || writebackBusy) return
    if (logicStage === 'text' && !text?.has_body) return
    const token = sceneToken.current
    const sceneId = selectedSceneId
    const stage = logicStage
    setLogicLoading(true)
    setNotice('')
    try {
      const result = await api.runSceneLogicCheck(sceneId, stage)
      if (sceneToken.current !== token) return
      setLogicIssues(result.issues)
      setLogicWarning(result.warning)
      setLogicLastAt(new Date().toISOString())
      if (result.llm_status !== 'ok') {
        setNotice(result.warning || '逻辑自检未完成')
      } else if (result.suppressed > 0) {
        setNotice(`逻辑自检完成；${result.suppressed} 条问题已记为特例，不再重复上报`)
      } else if (result.issues.length > 0) {
        setNotice(`逻辑自检完成，发现 ${result.issues.length} 条问题`)
      } else {
        setNotice('逻辑自检完成，没有发现问题')
      }
    } catch (error) {
      if (sceneToken.current === token) setNotice((error as Error).message)
    } finally {
      if (sceneToken.current === token) setLogicLoading(false)
    }
  }

  const changeLogicStage = (next: LogicStage) => {
    if (next === logicStage || logicLoading) return
    setLogicStage(next)
    setLogicIssues([])
    setLogicLastAt(null)
    setLogicWarning('')
    if (!selectedSceneId) return
    const sceneSeq = sceneToken.current
    const seq = ++logicToken.current
    setLogicLoading(true)
    api
      .getSceneLogicCheck(selectedSceneId, next)
      .then((data) => {
        if (sceneToken.current !== sceneSeq || logicToken.current !== seq) return
        setLogicIssues(data.issues)
        setLogicLastAt(data.last_checked_at)
      })
      .catch((error) => {
        if (sceneToken.current === sceneSeq && logicToken.current === seq) {
          setLogicWarning((error as Error).message)
        }
      })
      .finally(() => {
        if (sceneToken.current === sceneSeq && logicToken.current === seq) {
          setLogicLoading(false)
        }
      })
  }

  const applyResolution = async (
    issue: AuditIssue,
    resolution: AuditResolution,
    removeIssue: (id: string) => void,
  ) => {
    if (busy || auditLoading || logicLoading || writebackBusy) return
    const token = sceneToken.current
    setBusy(true)
    setNotice('')
    try {
      const updated = await api.resolveAuditIssue(issue.id, resolution)
      if (sceneToken.current !== token) return
      if (updated.status !== 'open') removeIssue(issue.id)
      if (resolution === 'story') {
        setNotice('已标记为改故事，请在正文中修改')
      } else if (resolution === 'exception') {
        setNotice('已记为特例，后续检查不再重复上报')
      } else {
        const target = issue.target_entry_id
        const entryParam = target ? `&entry=${encodeURIComponent(target)}` : ''
        // 带上当前项目：世界观页默认打开最新项目，不传项目会让深链落到别处。
        navigate(`/world?project=${encodeURIComponent(projectId)}${entryParam}`)
      }
    } catch (error) {
      if (sceneToken.current === token) setNotice((error as Error).message)
    } finally {
      if (sceneToken.current === token) setBusy(false)
    }
  }

  const resolveIssue = (issue: AuditIssue, resolution: AuditResolution) =>
    applyResolution(issue, resolution, (id) =>
      setAuditIssues((current) => current.filter((item) => item.id !== id)),
    )

  const resolveLogicIssue = (issue: AuditIssue, resolution: AuditResolution) =>
    applyResolution(issue, resolution, (id) =>
      setLogicIssues((current) => current.filter((item) => item.id !== id)),
    )

  const runWriteback = async () => {
    if (
      !selectedSceneId ||
      !text?.has_body ||
      generating ||
      busy ||
      auditLoading ||
      logicLoading ||
      writebackBusy
    ) {
      return
    }
    const token = sceneToken.current
    const sceneId = selectedSceneId
    setWritebackLoading(true)
    setNotice('')
    try {
      const result = await api.runSceneWriteback(sceneId)
      if (sceneToken.current !== token) return
      setWriteback(result)
      if (result.llm_status === 'ok') {
        setNotice('回写建议已生成，请在右栏逐项确认后应用')
      } else {
        setNotice(result.warning || '回写建议未生成')
      }
    } catch (error) {
      if (sceneToken.current === token) setNotice((error as Error).message)
    } finally {
      if (sceneToken.current === token) setWritebackLoading(false)
    }
  }

  const applyWriteback = async (payload: WritebackApplyPayload) => {
    if (
      !selectedSceneId ||
      busy ||
      generating ||
      auditLoading ||
      logicLoading ||
      writebackApplying
    ) {
      return
    }
    const token = sceneToken.current
    const sceneId = selectedSceneId
    setWritebackApplying(true)
    setNotice('')
    try {
      const result = await api.applySceneWriteback(sceneId, payload)
      if (sceneToken.current !== token) return
      setWriteback(null)
      setNotice(
        `已写回：章节摘要${result.chapter_summary ? '已更新' : '未改'}，` +
          `${result.character_updates.length} 个人物状态、` +
          `${result.foreshadow_pays.length} 条伏笔回收`,
      )
      void refreshTree()
    } catch (error) {
      if (sceneToken.current === token) setNotice((error as Error).message)
    } finally {
      if (sceneToken.current === token) setWritebackApplying(false)
    }
  }

  const startBatch = async (scopeType: 'chapter' | 'volume', scopeId: string) => {
    if (!projectId || batchLoading || batchBusy) return
    const token = batchToken.current
    setBatchLoading(true)
    setNotice('')
    try {
      const created = await api.createBatch(projectId, {
        scope_type: scopeType,
        scope_id: scopeId,
      })
      if (batchToken.current !== token) return
      const started = await api.resumeBatch(created.id)
      if (batchToken.current !== token) return
      setBatchJob(started)
      setNotice('批量生成已开始；你可以随时暂停或取消')
    } catch (error) {
      if (batchToken.current === token) setNotice((error as Error).message)
    } finally {
      if (batchToken.current === token) setBatchLoading(false)
    }
  }

  const controlBatch = async (
    action: (jobId: string) => Promise<BatchJob>,
  ) => {
    if (!batchJob || batchBusy) return
    const token = batchToken.current
    setBatchBusy(true)
    setNotice('')
    try {
      const next = await action(batchJob.id)
      if (batchToken.current !== token) return
      setBatchJob(next)
      if (next.status !== 'running') void refreshTree()
    } catch (error) {
      if (batchToken.current === token) setNotice((error as Error).message)
    } finally {
      if (batchToken.current === token) setBatchBusy(false)
    }
  }

  const generate = async () => {
    if (
      !selectedSceneId ||
      generating ||
      textLoading ||
      auditLoading ||
      logicLoading ||
      writebackBusy
    ) {
      return
    }
    if (
      hasUnsaved &&
      !window.confirm('生成完成后会刷新场景内容，当前未保存的修改将被覆盖。继续？')
    ) {
      return
    }
    const sceneId = selectedSceneId
    const currentProjectId = projectId
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    const token = ++generateToken.current
    clearStopCooldown()
    runIdRef.current = ''
    streamTextRef.current = ''
    setGenerating(true)
    setStreamText('')
    setRunInfo(null)
    setNotice('')

    try {
      await streamSceneGeneration(
        sceneId,
        {
          onRun: (data) => {
            if (generateToken.current !== token) return
            runIdRef.current = data.run_id
            setRunInfo({
              run_id: data.run_id,
              model: data.model,
              agent: data.agent,
              estimated_tokens: data.estimated_tokens,
              trimmed: data.trimmed,
            })
          },
          onDelta: (delta) => {
            if (generateToken.current !== token) return
            streamTextRef.current += delta
            setStreamText(streamTextRef.current)
          },
          onDone: (data) => {
            if (generateToken.current !== token) return
            setNotice('生成完成，草稿已更新')
            setRunInfo((current) =>
              current && current.run_id === data.run_id
                ? {
                    ...current,
                    status: data.status,
                    prompt_tokens: data.prompt_tokens,
                    completion_tokens: data.completion_tokens,
                    cost_estimate: data.cost_estimate,
                    duration_ms: data.duration_ms,
                    chars: data.chars,
                  }
                : current,
            )
          },
          onError: (data) => {
            if (generateToken.current !== token) return
            setNotice(`${data.message}（已保留 ${data.chars} 字）`)
            setRunInfo((current) =>
              current && current.run_id === data.run_id
                ? {
                    ...current,
                    error: { kind: data.kind, message: data.message },
                    chars: data.chars,
                  }
                : current,
            )
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
        // 停止/生成按钮共用同一位置：生成刚结束时给 1 秒冷却，
        // 避免作者点击「停止」时按钮已翻回「生成正文」而误发起新请求。
        startStopCooldown()
        try {
          let state = await refreshText(sceneId)
          if (state && !state.draft && streamTextRef.current) {
            // 服务端收尾与客户端 abort 存在竞态：稍等再回读一次，
            // 避免把已经落库的部分草稿误判为「没有草稿」。
            await new Promise((resolve) => setTimeout(resolve, 500))
            state = generateToken.current === token ? await refreshText(sceneId) : null
          }
          // 刷新返回 null 说明场景已切换，模式属于新场景，不能覆盖。
          if (state) setMode(state.draft ? 'draft' : 'body')
        } catch (error) {
          if (generateToken.current === token) setNotice((error as Error).message)
        }
        if (runIdRef.current) {
          await refreshRunRecord(currentProjectId, runIdRef.current, token)
        }
      }
    }
  }

  const stop = () => {
    // 这里的 abort 刻意不递增 generateToken：中止后仍要让 finally 按原 token
    // 回读服务端已保留的部分内容并补拉运行终态；立即失效会把这两件事一起丢掉。
    abortRef.current?.abort()
    setNotice('已请求停止；已生成的内容会尽量保留。')
  }

  const openRevision = async (revisionId: string) => {
    if (!text) return
    const token = sceneToken.current
    const sceneId = text.scene_id
    setBusy(true)
    setNotice('')
    try {
      const detail = await api.getSceneRevision(sceneId, revisionId)
      if (sceneToken.current !== token) return
      setRevision(detail)
    } catch (error) {
      if (sceneToken.current === token) setNotice((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const restoreRevision = async (revisionId: string) => {
    if (!text) return
    if (!window.confirm('恢复这个修订？当前正文会被替换，并生成一条新的恢复修订。')) return
    const token = sceneToken.current
    const sceneId = text.scene_id
    setBusy(true)
    setNotice('')
    try {
      const state = await api.restoreSceneRevision(sceneId, revisionId)
      if (sceneToken.current !== token) return
      setText(state)
      setBodyDraft(state.body ?? '')
      setMode('body')
      setRevision(null)
      setAuditIssues([])
      setAuditWarning('')
      if (logicStage === 'text') {
        setLogicIssues([])
        setLogicWarning('')
      }
      setNotice(
        auditIssues.length > 0
          ? '已恢复旧版并生成新的修订；之前的审校结果已失效，请重新审校'
          : '已恢复旧版并生成新的修订',
      )
      void refreshTree()
    } catch (error) {
      if (sceneToken.current === token) setNotice((error as Error).message)
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

      {projectsLoading ? (
        <p className="rounded border border-slate-800 p-4 text-sm text-slate-500">加载中…</p>
      ) : !projectId ? (
        <p className="rounded border border-slate-800 p-4 text-sm text-slate-500">
          先创建一个项目。
        </p>
      ) : (
        <div className="grid gap-4 xl:grid-cols-[240px_minmax(0,1fr)_320px]">
          <aside className="rounded border border-slate-800 p-3">
            {treeLoading ? (
              <p className="text-sm text-slate-500">章节树加载中…</p>
            ) : (
              <WritingTree
                volumes={volumes}
                selectedSceneId={selectedSceneId}
                onSelect={selectScene}
              />
            )}
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
                    {text ? `${text.word_count} 字` : '—'}
                  </p>
                </section>

                {textLoading ? (
                  <p className="rounded border border-slate-800 p-4 text-sm text-slate-500">
                    正在载入正文与上下文…
                  </p>
                ) : !text ? (
                  <p className="rounded border border-slate-800 p-4 text-sm text-amber-300">
                    正文状态未能加载，请重新选择场景。
                  </p>
                ) : (
                  <>
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
                          disabled={busy || stopCooldown || auditLoading || logicLoading || writebackBusy}
                          title={stopCooldown ? '生成刚结束，请稍候' : undefined}
                          className="rounded bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-500 disabled:opacity-50"
                        >
                          生成正文
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={runAudit}
                        disabled={busy || generating || auditLoading || logicLoading || writebackBusy || !text.has_body}
                        title={text.has_body ? undefined : '采纳正文后才能审校'}
                        className="rounded border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:text-white disabled:opacity-50"
                      >
                        {auditLoading ? '审校中…' : '审校'}
                      </button>
                      <button
                        type="button"
                        onClick={runLogic}
                        disabled={
                          busy ||
                          generating ||
                          auditLoading ||
                          logicLoading ||
                          writebackBusy ||
                          (logicStage === 'text' && !text.has_body)
                        }
                        title={
                          logicStage === 'text' && !text.has_body
                            ? '采纳正文后才能检查正文'
                            : undefined
                        }
                        className="rounded border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:text-white disabled:opacity-50"
                      >
                        {logicLoading ? '逻辑检查中…' : '逻辑自检'}
                      </button>
                      <button
                        type="button"
                        onClick={runWriteback}
                        disabled={
                          busy ||
                          generating ||
                          auditLoading ||
                          logicLoading ||
                          writebackBusy ||
                          !text.has_body
                        }
                        title={text.has_body ? undefined : '采纳正文后才能生成回写建议'}
                        className="rounded border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:text-white disabled:opacity-50"
                      >
                        {writebackLoading ? '生成中…' : '回写建议'}
                      </button>
                      <button
                        type="button"
                        onClick={saveBody}
                        disabled={
                          busy ||
                          generating ||
                          auditLoading ||
                          logicLoading ||
                          writebackBusy ||
                          mode !== 'body' ||
                          bodyDraft === (text.body ?? '')
                        }
                        className="rounded border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:text-white disabled:opacity-50"
                      >
                        保存正文
                      </button>
                      <button
                        type="button"
                        onClick={() => setBodyDraft(text.body ?? '')}
                        disabled={
                          busy ||
                          generating ||
                          auditLoading ||
                          logicLoading ||
                          writebackBusy ||
                          mode !== 'body' ||
                          bodyDraft === (text.body ?? '')
                        }
                        className="rounded border border-slate-700 px-3 py-1.5 text-sm text-slate-400 hover:text-white disabled:opacity-50"
                      >
                        取消修改
                      </button>
                      <button
                        type="button"
                        onClick={saveDraft}
                        disabled={busy || generating || auditLoading || logicLoading || writebackBusy || !text.draft || mode !== 'draft'}
                        className="rounded border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:text-white disabled:opacity-50"
                      >
                        保存草稿
                      </button>
                      <button
                        type="button"
                        onClick={adopt}
                        disabled={busy || generating || auditLoading || logicLoading || writebackBusy || !text.draft}
                        className="rounded bg-emerald-600 px-3 py-1.5 text-sm text-white hover:bg-emerald-500 disabled:opacity-50"
                      >
                        采纳为正文
                      </button>
                      <button
                        type="button"
                        onClick={discard}
                        disabled={busy || generating || auditLoading || logicLoading || writebackBusy || !text.draft}
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
                        disabled={!text.draft}
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

                    {text.draft && !generating && (
                      <DiffPanel oldText={text.body ?? ''} newText={aiDraft} />
                    )}
                  </>
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
            <AuditPanel
              issues={auditIssues}
              lastAuditedAt={auditLastAt}
              running={auditLoading || busy || writebackBusy}
              warning={auditWarning}
              canRun={Boolean(text?.has_body) && !generating && !busy && !auditLoading && !logicLoading && !writebackBusy}
              hasBody={Boolean(text?.has_body)}
              onRun={runAudit}
              onResolve={resolveIssue}
            />
            <LogicPanel
              stage={logicStage}
              issues={logicIssues}
              lastCheckedAt={logicLastAt}
              running={logicLoading || busy || writebackBusy}
              warning={logicWarning}
              canRun={
                Boolean(selectedSceneId) &&
                !generating &&
                !busy &&
                !auditLoading &&
                !logicLoading &&
                !writebackBusy
              }
              hasBody={Boolean(text?.has_body)}
              onStageChange={changeLogicStage}
              onRun={runLogic}
              onResolve={resolveLogicIssue}
            />
            <WritebackPanel
              suggestion={writeback}
              loading={writebackLoading}
              applying={writebackApplying}
              canRun={
                Boolean(selectedSceneId) &&
                !generating &&
                !busy &&
                !auditLoading &&
                !logicLoading &&
                !writebackBusy
              }
              hasBody={Boolean(text?.has_body)}
              onRun={runWriteback}
              onApply={applyWriteback}
            />
            <BatchPanel
              job={batchJob}
              loading={batchLoading}
              busy={batchBusy}
              canStart={Boolean(selected)}
              chapterId={selected?.chapter.id ?? ''}
              chapterLabel={
                selected ? `第${selected.chapter.seq + 1}章 ${selected.chapter.title}` : ''
              }
              volumeId={selected?.volume.id ?? ''}
              volumeLabel={
                selected ? `第${selected.volume.seq + 1}卷 ${selected.volume.name}` : ''
              }
              onStart={startBatch}
              onPause={() => controlBatch(api.pauseBatch)}
              onResume={() => controlBatch(api.resumeBatch)}
              onCancel={() => controlBatch(api.cancelBatch)}
              onRetryFailed={() => controlBatch(api.retryBatchFailed)}
            />
            {runInfo && (
              <section className="space-y-1 rounded border border-slate-800 p-3 text-xs text-slate-400">
                <h3 className="text-sm font-medium text-slate-300">本次运行</h3>
                <p>
                  {runInfo.agent} · {runInfo.model}
                </p>
                <p className="text-slate-500">run {runInfo.run_id.slice(0, 8)}</p>
                <p>估算 {runInfo.estimated_tokens} tokens</p>
                {runInfo.status && <p>状态：{runInfo.status}</p>}
                {runInfo.prompt_tokens !== undefined && (
                  <p>
                    tokens：{runInfo.prompt_tokens} + {runInfo.completion_tokens ?? 0}
                  </p>
                )}
                {runInfo.cost_estimate !== undefined && (
                  <p>费用估算：${runInfo.cost_estimate.toFixed(4)}</p>
                )}
                {runInfo.duration_ms !== undefined && (
                  <p>耗时：{(runInfo.duration_ms / 1000).toFixed(1)} 秒</p>
                )}
                {runInfo.chars !== undefined && <p>已生成 {runInfo.chars} 字</p>}
                {runInfo.error && (
                  <p className="text-amber-300">
                    {runInfo.error.kind}：{runInfo.error.message}
                  </p>
                )}
                {Object.keys(runInfo.trimmed).length > 0 && (
                  <details>
                    <summary className="cursor-pointer text-slate-500">上下文裁剪</summary>
                    <ul className="mt-1 space-y-1">
                      {Object.entries(runInfo.trimmed).map(([key, note]) => (
                        <li key={key}>
                          {key}：{note}
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
              </section>
            )}
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
                  disabled={busy || auditLoading || logicLoading || writebackBusy}
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
