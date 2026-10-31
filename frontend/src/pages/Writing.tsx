import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  api,
  streamSceneGeneration,
  type AuditIssue,
  type AuditResolution,
  type BatchJob,
  type ContextPreview as ContextPreviewData,
  type BranchDetail,
  type ChangeRow,
  type LockState,
  type LogicStage,
  type RevisionDetail,
  type SceneTextState,
  type VolumeNode,
  type WritebackApplyPayload,
  type WritebackSuggestion,
} from '../api/client'
import AbPanel from '../components/writing/AbPanel'
import AuditPanel from '../components/writing/AuditPanel'
import BatchPanel from '../components/writing/BatchPanel'
import ContextPreview from '../components/writing/ContextPreview'
import BranchPanel, { BranchBodyEditor } from '../components/writing/BranchPanel'
import { ChangeList } from '../components/Snapshots'
import { setProjectGuard } from '../lib/projectGuard'
import { useCurrentProject } from '../state/ProjectContext'
import ParagraphLocks from '../components/writing/ParagraphLocks'
import DiffPanel from '../components/writing/DiffPanel'
import GenerationStream from '../components/writing/GenerationStream'
import LogicChain from '../components/writing/LogicChain'
import LogicPanel from '../components/writing/LogicPanel'
import RevisionHistory from '../components/writing/RevisionHistory'
import SceneTextView from '../components/writing/SceneTextView'
import WritebackPanel from '../components/writing/WritebackPanel'
import WritingTree from '../components/writing/WritingTree'
import {
  ASIDE_TABS,
  readAsideTab,
  readRightCollapsed,
  readStoredMode,
  resolveMode,
  shapeFor,
  writeAsideTab,
  writeMode,
  writeRightCollapsed,
  type AsideTab,
  type WritingMode,
} from '../lib/writingLayout'
import { Button, IconButton } from '../ui/Button'
import { Icon } from '../ui/icons'
import { Skeleton } from '../ui/Skeleton'
import { Tabs } from '../ui/Tabs'

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
  // 当前项目由外壳持有；这里只读。切换项目前的「未保存」确认由 projectGuard 承担。
  const { projectId, loading: projectsLoading } = useCurrentProject()
  // 布局：工作态 / 专注态、右栏折叠、左树抽屉。宽度只在**作者没表达过偏好**时
  // 决定模式；他手动切过就永远以他为准（拉一下窗口不该把他的选择冲掉）。
  // 注意与下面的 `mode`（正文 / AI 草稿）不是一回事，所以这里叫 layoutMode。
  const [storedLayoutMode, setStoredLayoutMode] = useState<WritingMode | null>(() =>
    readStoredMode(),
  )
  const [width, setWidth] = useState(() => window.innerWidth)
  const [rightCollapsed, setRightCollapsed] = useState(() => readRightCollapsed())
  const [drawerOpen, setDrawerOpen] = useState(false)
  // 右栏的四个页签：上下文 / 分支 / 审校 / 日志。
  const [asideTab, setAsideTab] = useState<AsideTab>(() => readAsideTab())
  // 工具栏的「更多」：次要动作收在这里，免得一行放九个按钮。
  const [moreOpen, setMoreOpen] = useState(false)
  const moreRef = useRef<HTMLDivElement | null>(null)
  const layoutMode = resolveMode(storedLayoutMode, width)
  const shape = shapeFor(layoutMode, rightCollapsed)
  const [volumes, setVolumes] = useState<VolumeNode[]>([])
  const [treeLoading, setTreeLoading] = useState(false)
  const [textLoading, setTextLoading] = useState(false)
  const [selectedSceneId, setSelectedSceneId] = useState('')
  // 有效锁定（含卷 / 章继承）与段落锁：AI 写路径会被服务端拒绝，界面要
  // 提前把按钮关掉并说清为什么，让作者不用点一次才知道。
  const [sceneLock, setSceneLock] = useState<LockState | null>(null)
  const [paragraphLocks, setParagraphLocks] = useState<string[]>([])
  const [sceneChanges, setSceneChanges] = useState<ChangeRow[]>([])
  // 正文目标：null = 主版，否则是某条分支。分支与主版各自一条正文，
  // 界面必须始终显示出「你正在看哪一条」。
  const [branchId, setBranchId] = useState<string | null>(null)
  const [branch, setBranch] = useState<BranchDetail | null>(null)
  const [branchBusy, setBranchBusy] = useState(false)
  // 分支载入时的正文快照：用来判断「分支里有没有未保存的改动」。
  const branchOriginal = useRef('')
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

  // 宽度只在作者没表达过偏好时才影响模式，所以存过就根本不挂这个监听。
  useEffect(() => {
    if (storedLayoutMode) return
    const onResize = () => setWidth(window.innerWidth)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [storedLayoutMode])

  // 抽屉：ESC 关闭。只在打开时挂监听，不在页面上常驻一个 keydown。
  useEffect(() => {
    if (!drawerOpen) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setDrawerOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [drawerOpen])

  // 「更多」：点面板外或按 ESC 关掉。点面板内的条目由面板自己的 onClick 收
  // —— 那样每个条目仍能保留原来的 `onClick={handler}`，不必包一层箭头函数。
  useEffect(() => {
    if (!moreOpen) return
    const onDown = (event: MouseEvent) => {
      if (!moreRef.current?.contains(event.target as Node)) setMoreOpen(false)
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMoreOpen(false)
    }
    window.addEventListener('mousedown', onDown)
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('mousedown', onDown)
      window.removeEventListener('keydown', onKey)
    }
  }, [moreOpen])

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

  // 分支正文也要算进来：在分支里改了字没保存就切场景 / 切项目 / 点「主版」，
  // 那份改动会静默丢掉。branch 的 content 由编辑器直接改本地副本。
  const branchDirty =
    branch !== null && branch.content !== branchOriginal.current
  const hasUnsaved =
    (Boolean(text) &&
      (bodyDraft !== (text?.body ?? '') || aiDraft !== (text?.draft?.content ?? ''))) ||
    branchDirty

  // 切项目的入口在外壳里；这里登记一次「还有未保存的改动就别走」。
  useEffect(() => {
    setProjectGuard(() =>
      hasUnsaved ? window.confirm('当前场景有未保存的修改，确定切换项目吗？') : true,
    )
    return () => setProjectGuard(null)
  }, [hasUnsaved])

  async function loadBranch(id: string) {
    // 持场景令牌：切场景后迟到的响应不许把旧场景的分支挂到新场景上。
    const token = sceneToken.current
    setBranchBusy(true)
    try {
      const row = await api.getBranch(id)
      if (sceneToken.current === token) {
        setBranch(row)
        branchOriginal.current = row.content
      }
    } catch (error) {
      if (sceneToken.current === token) {
        setNotice((error as Error).message)
        setBranch(null)
        setBranchId(null)
      }
    } finally {
      if (sceneToken.current === token) setBranchBusy(false)
    }
  }

  useEffect(() => {
    if (!branchId) {
      setBranch(null)
      return
    }
    void loadBranch(branchId)
    // loadBranch 是闭包，只按 branchId 触发。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [branchId])

  async function refreshSceneChanges(sceneId: string, token: number) {
    try {
      const body = await api.listChanges(projectId, {
        target_type: 'scene',
        target_id: sceneId,
        limit: 20,
      })
      if (sceneToken.current === token) setSceneChanges(body.changes)
    } catch {
      // 历史是辅助信息，取不到不影响写作。
    }
  }

  const loadScene = async (sceneId: string) => {
    const token = ++sceneToken.current
    const logicSeq = ++logicToken.current
    setTextLoading(true)
    setPreviewLoading(true)
    setPreviewError('')
    setPreview(null)
    // 先清空上一场的锁定状态：留着会让新场景短暂地显示上一场的横幅。
    setSceneLock(null)
    setParagraphLocks([])
    setSceneChanges([])
    setBranchId(null)
    setBranch(null)
    branchOriginal.current = ''
    setAuditIssues([])
    setAuditLastAt(null)
    setAuditWarning('')
    setLogicIssues([])
    setLogicLastAt(null)
    setLogicWarning('')
    try {
      const [stateResult, contextResult, auditResult, logicResult, lockResult, paraResult] =
        await Promise.allSettled([
          api.getSceneText(sceneId),
          api.getSceneContextPreview(sceneId),
          api.getSceneAudit(sceneId),
          api.getSceneLogicCheck(sceneId, logicStage),
          api.getLock('scene', sceneId),
          api.getParagraphLocks(sceneId),
        ])
      if (sceneToken.current !== token) return
      setSceneLock(lockResult.status === 'fulfilled' ? lockResult.value : null)
      setParagraphLocks(paraResult.status === 'fulfilled' ? paraResult.value.paragraphs : [])
      void refreshSceneChanges(sceneId, token)
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
      void refreshSceneChanges(sceneId, token)
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
      void refreshSceneChanges(sceneId, token)
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
      void refreshSceneChanges(sceneId, token)
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

  // 列宽取自 spec §8.2 的预算。注意 spec 那句验算（1440 − 外壳 236 − 左树 236 −
  // 右栏 336 − 32 间隙 = 600）**漏了页面内边距**：本页由 App 给 p-6（48px），
  // 实际正文列是 1440 − 236 − 48 − 236 − 336 − 32 = 552，低于 §11 验收的 560 下限。
  // 故本页不用 App 的 p-6（与阅读器同一例外）、自带 p-4（左右各 16），于是 = 568，
  // 过了下限；但仍低于 §8.2 写的 600–680 目标区 —— 要达 600 得把右栏缩到 288，
  // 留待作者裁决。
  const gridClass =
    shape.tree === 'drawer'
      ? shape.aside === 'none'
        ? 'grid-cols-[minmax(0,1fr)]'
        : 'grid-cols-[minmax(0,1fr)] pr-[336px]'
      : shape.aside === 'rail'
        ? 'grid-cols-[236px_minmax(0,1fr)_44px]'
        : 'grid-cols-[236px_minmax(0,1fr)_336px]'
  // 同一棵树要出现在两处（工作态的常驻列 / 专注态的抽屉），抽出来免得写两份。
  const treePane = treeLoading ? (
    <div>
      <span className="sr-only">章节树加载中…</span>
      <Skeleton lines={5} />
    </div>
  ) : (
    <WritingTree volumes={volumes} selectedSceneId={selectedSceneId} onSelect={selectScene} />
  )

  function toggleLayoutMode() {
    const next: WritingMode = layoutMode === 'work' ? 'focus' : 'work'
    setStoredLayoutMode(next)
    writeMode(next)
  }

  function setRightCollapsedPersisted(collapsed: boolean) {
    setRightCollapsed(collapsed)
    writeRightCollapsed(collapsed)
  }

  function setAsideTabPersisted(next: AsideTab) {
    setAsideTab(next)
    writeAsideTab(next)
  }

  // 工具栏的字数跟着**当前在编的那一份**走：正文模式数正文、草稿模式数草稿。
  // 口径与原先编辑器里那个一致（去掉空白后计字符）—— 只是搬到了工具栏。
  const editorChars = (mode === 'body' ? bodyDraft : aiDraft).replace(/\s/g, '').length

  // 「更多」面板里的条目：左对齐、可禁用，与 `Button` 的中置对齐不同，所以不用
  // 组件而直接写类名。**文字色不写在这里**，由每个条目自己给一个 —— 同一元素上
  // 两个 text-* 谁生效取决于 CSS 顺序（`cn` 不消解冲突）。
  const moreItemClass =
    'rounded-control px-2.5 py-1.5 text-left text-[12.5px] transition-colors duration-[120ms] hover:bg-sunken disabled:cursor-not-allowed disabled:opacity-45'

  return (
    /* 本页自带内边距（App 不对 /write 加 p-6）：三栏宽度按 spec §8.2 的预算算，
       48px 的内边距会把正文压到验收下限以下，见上面 gridClass 的注释。 */
    <div className="space-y-4 p-4">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="font-serif text-[19px] font-semibold text-ink">写作台</h2>
        {shape.tree === 'drawer' && (
          <Button size="sm" onClick={() => setDrawerOpen(true)}>
            章节
          </Button>
        )}
        <div className="ml-auto flex items-center gap-2">
          {/* 两种模式都给开关：专注态收起右栏后要能再打开，否则浮层一旦收起就回不来。 */}
          <Button size="sm" onClick={() => setRightCollapsedPersisted(!rightCollapsed)}>
            {rightCollapsed ? '展开右栏' : '收起右栏'}
          </Button>
          <Button size="sm" onClick={toggleLayoutMode}>
            {layoutMode === 'work' ? '专注模式' : '工作模式'}
          </Button>
        </div>
      </div>

      {notice && <p className="text-[13px] text-muted">{notice}</p>}

      {projectsLoading ? (
        <p className="rounded-card border border-line bg-surface p-4 text-[13.5px] text-muted">
          加载中…
        </p>
      ) : !projectId ? (
        <p className="rounded-card border border-line bg-surface p-4 text-[13.5px] text-muted">
          先在左侧项目选择器里新建一个项目。
        </p>
      ) : (
        <div className={`grid items-start gap-4 ${gridClass}`}>
          {shape.tree === 'column' && (
            <aside className="rounded-card border border-line bg-surface p-3">{treePane}</aside>
          )}

          {/* 正文列的宽度上限：工作态 680、专注态 620（spec §8.2 的区间），
              余量作左右页边 —— 所以这里居中而不是撑满。 */}
          <section
            className={`mx-auto w-full min-w-0 space-y-3 ${
              layoutMode === 'work' ? 'max-w-[680px]' : 'max-w-[620px]'
            }`}
          >
            {!selected ? (
              <p className="rounded-card border border-line bg-surface p-4 text-[13.5px] text-muted">
                从左侧选择一个场景开始写作。
              </p>
            ) : (
              <>
                {sceneLock?.locked && (
                  <p className="rounded-control bg-warn-soft p-3 text-[13.5px] text-warn">
                    这一场已锁定（{sceneLock.label || '上级'}）：AI 不会生成或采纳正文。
                    作者仍可手工编辑与保存。要重新生成，请先在章节页解锁。
                  </p>
                )}

                <section className="space-y-1 rounded-card border border-line bg-surface p-3 text-[13.5px]">
                  <p className="text-ink-2">
                    目标：{selected.scene.goal || '（未写目标）'}
                  </p>
                  <p className="text-muted">冲突：{selected.scene.conflict || '（未写）'}</p>
                  <p className="text-muted">转折：{selected.scene.turn || '（未写）'}</p>
                  {/* 字数已移到工具栏（跟着当前在编的那一份走），这里只留目标。 */}
                  <p className="text-[11.5px] text-muted">
                    目标字数：{selected.scene.target_words_min ?? '?'}–
                    {selected.scene.target_words_max ?? '?'}
                  </p>
                </section>

                {textLoading ? (
                  <div className="rounded-card border border-line bg-surface p-4">
                    <span className="sr-only">正在载入正文与上下文…</span>
                    <Skeleton lines={8} />
                  </div>
                ) : !text ? (
                  <p className="rounded-card border-l-2 border-danger bg-surface p-4 text-[13.5px] text-danger">
                    正文状态未能加载，请重新选择场景。
                  </p>
                ) : (
                  <>
                    {/* 工具栏收成一行（spec §9.9）：面包屑 · 保存状态 · 字数 |
                        生成正文 · 采纳为正文 · 更多。次要动作收进「更多」——
                        每个按钮的 onClick 与 disabled 表达式逐字保留，只换位置。 */}
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[13px] text-ink-2">{sceneLabel}</span>
                      <span className="text-[11.5px] text-muted">
                        {hasUnsaved ? '有未保存的改动' : '已保存'}
                      </span>
                      <span className="text-[11.5px] text-faint tabular-nums">
                        {editorChars} 字
                      </span>

                      <div className="ml-auto flex items-center gap-2">
                        {generating ? (
                          <Button variant="warn" onClick={stop}>
                            停止
                          </Button>
                        ) : (
                          <Button
                            variant="primary"
                            onClick={generate}
                            disabled={
                              busy ||
                              stopCooldown ||
                              auditLoading ||
                              logicLoading ||
                              writebackBusy ||
                              sceneLock?.locked === true
                            }
                            title={
                              sceneLock?.locked
                                ? '这一场已锁定，AI 不会改动它'
                                : stopCooldown
                                  ? '生成刚结束，请稍候'
                                  : undefined
                            }
                          >
                            生成正文
                          </Button>
                        )}
                        {/* 采纳用 secondary：生成是入口动作、最常点，让它独占主色，
                            两个同色主按钮会互相稀释。 */}
                        <Button
                          onClick={adopt}
                          disabled={
                            busy ||
                            generating ||
                            auditLoading ||
                            logicLoading ||
                            writebackBusy ||
                            !text.draft ||
                            sceneLock?.locked === true
                          }
                          title={
                            sceneLock?.locked
                              ? '这一场已锁定，AI 草稿不能采纳'
                              : undefined
                          }
                        >
                          采纳为正文
                        </Button>
                        <div className="relative" ref={moreRef}>
                          <Button
                            onClick={() => setMoreOpen((open) => !open)}
                            aria-expanded={moreOpen}
                          >
                            更多
                          </Button>
                          {moreOpen && (
                            /* 点面板里任意一条即收起（靠冒泡），所以每个条目仍能
                               直接写 onClick={handler}，不必包一层箭头函数。 */
                            <div
                              className="absolute right-0 top-9 z-20 flex w-44 flex-col items-stretch gap-0.5 rounded-card border border-line bg-surface p-1.5 shadow-overlay"
                              onClick={() => setMoreOpen(false)}
                            >
                              <button
                                type="button"
                                onClick={runAudit}
                                disabled={busy || generating || auditLoading || logicLoading || writebackBusy || !text.has_body}
                                title={text.has_body ? undefined : '采纳正文后才能审校'}
                                className={`${moreItemClass} text-ink-2`}
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
                                className={`${moreItemClass} text-ink-2`}
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
                                className={`${moreItemClass} text-ink-2`}
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
                                className={`${moreItemClass} text-ink-2`}
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
                                className={`${moreItemClass} text-ink-2`}
                              >
                                取消修改
                              </button>
                              <button
                                type="button"
                                onClick={saveDraft}
                                disabled={busy || generating || auditLoading || logicLoading || writebackBusy || !text.draft || mode !== 'draft'}
                                className={`${moreItemClass} text-ink-2`}
                              >
                                保存草稿
                              </button>
                              <button
                                type="button"
                                onClick={discard}
                                disabled={busy || generating || auditLoading || logicLoading || writebackBusy || !text.draft}
                                className={`${moreItemClass} text-warn`}
                              >
                                丢弃草稿
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>

                    <GenerationStream text={streamText} generating={generating} />

                    {branch && (
                      <>
                        <BranchBodyEditor
                          branch={branch}
                          sceneId={selectedSceneId}
                          busy={branchBusy || busy}
                          onChange={(content) =>
                            setBranch((current) =>
                              current ? { ...current, content } : current,
                            )
                          }
                          onSaved={() => void loadBranch(branch.id)}
                        />
                        <DiffPanel oldText={text.body ?? ''} newText={branch.content} />
                        <p className="text-[11.5px] text-muted">
                          与主版对比在上面。要换掉主版正文，用右栏「合入」。
                        </p>
                      </>
                    )}

                    {!branch && (
                      <>
                    <div className="flex gap-1">
                      <button
                        type="button"
                        onClick={() => setMode('body')}
                        className={`rounded-control px-3 py-1 text-[13px] transition-colors duration-[120ms] ${
                          mode === 'body'
                            ? 'bg-accent-soft font-semibold text-accent-ink'
                            : 'text-muted hover:bg-sunken'
                        }`}
                      >
                        已采纳正文
                      </button>
                      <button
                        type="button"
                        onClick={() => setMode('draft')}
                        disabled={!text.draft}
                        className={`rounded-control px-3 py-1 text-[13px] transition-colors duration-[120ms] disabled:opacity-40 ${
                          mode === 'draft'
                            ? 'bg-accent-soft font-semibold text-accent-ink'
                            : 'text-muted hover:bg-sunken'
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
              </>
            )}
          </section>

          {shape.aside === 'rail' ? (
            <aside className="flex flex-col items-center gap-2 rounded-card border border-line bg-surface py-3">
              <IconButton label="展开右栏" onClick={() => setRightCollapsedPersisted(false)}>
                <Icon name="chevron" className="rotate-180" />
              </IconButton>
            </aside>
          ) : shape.aside === 'none' ? null : (
            /* 专注态下右栏是浮层：正文已经居中收窄（620），浮层落在右侧留白里，
               不盖住稿子 —— spec §8.2 的「正文让位、不遮挡」。
               top-20 是给页头留出的高度：浮层若从 top-4 起会盖住页头右侧的
               模式切换，作者就回不到工作态了。 */
            <aside
              className={
                shape.aside === 'overlay'
                  ? 'fixed bottom-4 right-4 top-20 z-30 w-[320px] space-y-4 overflow-auto rounded-card border border-line bg-surface p-3 shadow-overlay'
                  : 'min-w-0 space-y-4'
              }
            >
            <Tabs
              items={ASIDE_TABS.map((tab) => ({ key: tab.key, label: tab.label }))}
              active={asideTab}
              onChange={(key) => {
                const next = ASIDE_TABS.find((tab) => tab.key === key)
                if (next) setAsideTabPersisted(next.key)
              }}
            />

            {/* 四组都**保持挂载**，只切可见性（`hidden`）—— 面板里各有自己的
                effect 与在途请求（A/B 与分支的 SSE、批量的轮询），按页签卸载会
                打断正在跑的那一条。 */}
            <div className={asideTab === 'context' ? 'space-y-4' : 'hidden'}>
              {selectedSceneId && (
                <ParagraphLocks
                  sceneId={selectedSceneId}
                  body={text?.body ?? null}
                  locks={paragraphLocks}
                  disabled={busy || generating}
                  onChanged={setParagraphLocks}
                />
              )}
              <ContextPreview
                data={preview}
                loading={previewLoading}
                error={previewError}
              />
            </div>

            <div className={asideTab === 'branch' ? 'space-y-4' : 'hidden'}>
              {selectedSceneId && (
                <AbPanel
                  sceneId={selectedSceneId}
                  locked={sceneLock?.locked === true}
                  disabled={busy || generating || branchBusy}
                  onAdopted={() => {
                    // 采纳会换正文、删掉两条 A/B 分支：正文、改动历史与左树都要跟上。
                    // 在途请求可能属于刚切走的场景，捕获当前令牌再比对。
                    const token = sceneToken.current
                    const sceneId = selectedSceneId
                    void refreshText(sceneId).then((state) => {
                      if (state !== null && sceneToken.current === token) {
                        void refreshSceneChanges(sceneId, token)
                      }
                    })
                    void refreshTree()
                  }}
                />
              )}
              {selectedSceneId && (
                <BranchPanel
                  sceneId={selectedSceneId}
                  selectedBranchId={branchId}
                  onSelect={(next) => {
                    // 离开分支时若有未保存的改动，先问一句 —— 分支正文的
                    // 编辑器是本地副本，切走就没了。
                    if (branchDirty && !window.confirm('这条分支有未保存的修改，确定离开吗？')) {
                      return
                    }
                    setBranchId(next)
                  }}
                  onMerged={() => {
                    // 合并请求在途时作者可能切了场景：捕获当时的令牌，
                    // 迟到时用它比对，别把旧场景的正文写进新场景。
                    const token = sceneToken.current
                    const sceneId = selectedSceneId
                    void refreshText(sceneId).then((state) => {
                      if (state !== null && sceneToken.current === token) {
                        void refreshSceneChanges(sceneId, token)
                      }
                    })
                    void refreshTree()
                  }}
                  disabled={busy || generating}
                />
              )}
            </div>

            <div className={asideTab === 'review' ? 'space-y-4' : 'hidden'}>
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
              {selectedSceneId && (
                <LogicChain sceneId={selectedSceneId} body={text?.body} />
              )}
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
            </div>

            <div className={asideTab === 'log' ? 'space-y-4' : 'hidden'}>
              {selectedSceneId && sceneChanges.length > 0 && (
                <section className="space-y-2 rounded-card border border-line bg-surface p-3">
                  <h3 className="text-[14px] font-semibold text-ink">这一场的改动</h3>
                  <ChangeList projectId={projectId} changes={sceneChanges} />
                </section>
              )}
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
                <section className="space-y-1 rounded-card border border-line bg-surface p-3 text-[11.5px] text-muted">
                  <h3 className="text-[14px] font-semibold text-ink">本次运行</h3>
                  <p>
                    {runInfo.agent} · {runInfo.model}
                  </p>
                  <p className="text-faint">run {runInfo.run_id.slice(0, 8)}</p>
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
                    <p className="text-warn">
                      {runInfo.error.kind}：{runInfo.error.message}
                    </p>
                  )}
                  {Object.keys(runInfo.trimmed).length > 0 && (
                    <details>
                      <summary className="cursor-pointer text-muted">上下文裁剪</summary>
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
                <section className="space-y-2 rounded-card border border-line bg-surface p-3 text-[13.5px]">
                  <div className="flex items-center justify-between gap-2">
                    <h3 className="font-semibold text-ink">修订全文</h3>
                    <button
                      type="button"
                      onClick={() => setRevision(null)}
                      className="text-[11.5px] text-muted transition-colors duration-[120ms] hover:text-ink-2"
                    >
                      关闭
                    </button>
                  </div>
                  <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words text-[11.5px] text-ink-2">
                    {revision.content}
                  </pre>
                  <button
                    type="button"
                    disabled={busy || auditLoading || logicLoading || writebackBusy}
                    onClick={() => restoreRevision(revision.id)}
                    className="rounded-control border border-line-strong px-2 py-1 text-[11.5px] text-ink-2 transition-colors duration-[120ms] hover:bg-sunken disabled:opacity-50"
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
            </div>
            </aside>
          )}
        </div>
      )}

      {/* 底部状态条：只在专注态出现（工作态的字数在工具栏里）。用 sticky 而不是
          fixed —— fixed 要写死侧栏宽度，而侧栏是可以折叠的。 */}
      {shape.statusBar && selected && (
        <div className="sticky bottom-0 z-20 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-card border border-line bg-surface px-3 py-1.5 text-[11.5px] text-muted shadow-overlay">
          <span className="tabular-nums">{editorChars} 字</span>
          <span className="tabular-nums">
            目标 {selected.scene.target_words_min ?? '?'}–
            {selected.scene.target_words_max ?? '?'}
          </span>
          {/* spec 写的是「分支数」，但分支列表在 BranchPanel 内部、页面上没有这个
              计数（要它得给面板加一个回调）。这里改显示「正在看哪一条」—— 对作者
              更有用，且只用现有状态。 */}
          <span>{branch ? `分支「${branch.name}」` : '主版'}</span>
          <span>{sceneLock?.locked ? '已锁定' : '未锁定'}</span>
        </div>
      )}

      {/* 专注态的左树：浮层抽屉。ESC 关闭，点遮罩也关。 */}
      {shape.tree === 'drawer' && drawerOpen && (
        <div className="fixed inset-0 z-40">
          <div
            className="absolute inset-0 bg-ink/20"
            onClick={() => setDrawerOpen(false)}
            aria-hidden="true"
          />
          <aside className="relative h-full w-[236px] overflow-auto border-r border-line bg-surface p-3 shadow-overlay">
            {treePane}
          </aside>
        </div>
      )}
    </div>
  )
}
