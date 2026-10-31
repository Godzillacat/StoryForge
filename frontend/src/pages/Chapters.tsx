import { useEffect, useRef, useState } from 'react'
import {
  api,
  type CausalMapData,
  type ChapterNode,
  type ChapterPlanResponse,
  type ChapterStatusOption,
  type CharacterDriftData,
  type Foreshadow,
  type ForeshadowSummary,
  type PlanScene,
  type PlanVolume,
  type ReviewMark,
  type ScenePlanResponse,
  type SettingEntry,
  type SettingLoadData,
  type VolumeNode,
} from '../api/client'
import RunTrace from '../components/RunTrace'
import { useCurrentProject } from '../state/ProjectContext'
import {
  ImpactPanel,
  LockToggle,
  ReviewMarkBadge,
  ReviewMarkList,
} from '../components/Locking'
import ChapterPlanDraft from '../components/chapters/ChapterPlanDraft'
import ScenePlanDraft from '../components/chapters/ScenePlanDraft'
import ChapterTree, { type Selection } from '../components/chapters/ChapterTree'
import ChapterEditor from '../components/chapters/ChapterEditor'
import SceneEditor from '../components/chapters/SceneEditor'
import VolumeEditor from '../components/chapters/VolumeEditor'
import ForeshadowLedger from '../components/chapters/ForeshadowLedger'
import RhythmCurve from '../components/chapters/RhythmCurve'
import Swimlanes from '../components/chapters/Swimlanes'
import CausalMap from '../components/chapters/CausalMap'
import SettingLoadCurve from '../components/chapters/SettingLoadCurve'
import CharacterDrift from '../components/chapters/CharacterDrift'
import { VIEW_GROUPS, groupOfView, subViewsOf, viewOfGroup, type ViewTab } from '../lib/chapterTabs'
import { Button } from '../ui/Button'
import { Panel } from '../ui/Card'
import { Skeleton } from '../ui/Skeleton'
import { Tabs } from '../ui/Tabs'

export default function Chapters() {
  // 当前项目由外壳持有；页面只读，切换入口在侧栏。
  const { projectId } = useCurrentProject()
  const [statuses, setStatuses] = useState<ChapterStatusOption[]>([])
  const [volumes, setVolumes] = useState<VolumeNode[]>([])
  const [entries, setEntries] = useState<SettingEntry[]>([])
  // 条目属于哪个项目：entries 是异步加载的，空列表并不等于「这个项目没有条目」。
  // 只有 entriesProjectId === projectId 时，场景编辑器才敢用 entries 映射名称。
  const [entriesProjectId, setEntriesProjectId] = useState('')
  const [foreshadows, setForeshadows] = useState<Foreshadow[]>([])
  // 伏笔的生命周期词表与章节状态**不是同一份**（章节的 confirmed 与伏笔的
  // paid 语义不同），各自从后端拉，界面不硬编。
  const [foreshadowStatuses, setForeshadowStatuses] = useState<ChapterStatusOption[]>([])
  const [foreshadowSummary, setForeshadowSummary] = useState<ForeshadowSummary | null>(null)
  const [causal, setCausal] = useState<CausalMapData | null>(null)
  // 因果链属于哪个项目：切项目时先清空，不能让上一本的图冒充这一本。
  const [causalProjectId, setCausalProjectId] = useState('')
  const [causalError, setCausalError] = useState('')
  const [settingLoad, setSettingLoad] = useState<SettingLoadData | null>(null)
  // 设定投放与因果链同理：数据属于哪个项目、错误只归它自己的视图。
  const [settingLoadProjectId, setSettingLoadProjectId] = useState('')
  const [settingLoadError, setSettingLoadError] = useState('')
  const [characterDrift, setCharacterDrift] = useState<CharacterDriftData | null>(null)
  // 性格漂移单独一份项目归属与错误：格子里的保存只重拉这张表，
  // 失败也不该把结构树或另外两张统计判为失败。
  const [characterDriftProjectId, setCharacterDriftProjectId] = useState('')
  const [characterDriftError, setCharacterDriftError] = useState('')
  const [selected, setSelected] = useState<Selection | null>(null)
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [chapterPlan, setChapterPlan] = useState<ChapterPlanResponse | null>(null)
  // 场景草稿必须记住它是为哪一章生成的：作者可能生成后切换选中的章再写入，
  // 此时绝不能把这一章的草稿写进另一章。
  const [scenePlan, setScenePlan] = useState<{
    data: ScenePlanResponse
    chapterId: string
    chapterTitle: string
  } | null>(null)
  const [planning, setPlanning] = useState(false)
  const [view, setView] = useState<ViewTab>('structure')
  const [reviewMarks, setReviewMarks] = useState<ReviewMark[]>([])
  // 数据属于哪个项目：用它与 projectId 的差异推导加载态，
  // 避免切项目时先闪一帧上一个项目的数据。
  const [dataProjectId, setDataProjectId] = useState('')
  const runToken = useRef(0)
  // 每次项目级请求自增；迟到的旧项目响应凭 token 失效，
  // 不能覆盖当前项目的树、条目或伏笔。
  const dataRequestRef = useRef(0)
  // 性格漂移自己的 token：保存格子后的重取不能把整页刷新的 token 撞掉。
  const characterDriftRequestRef = useRef(0)
  // 与 projectId 同步的即时值：保存后的 refresh 是旧渲染的闭包，
  // 只有它能在切项目后认出「这是旧项目的请求」。
  const projectIdRef = useRef('')

  useEffect(() => {
    api.listChapterTypes().then((data) => setStatuses(data.statuses))
      .catch((error) => setNotice((error as Error).message))
    api.listForeshadowTypes().then((data) => setForeshadowStatuses(data.statuses))
      .catch((error) => setNotice((error as Error).message))
  }, [])

  useEffect(() => {
    if (!projectId) return
    projectIdRef.current = projectId
    setSelected(null)
    setNotice('')
    setVolumes([])
    setEntries([])
    setEntriesProjectId('')
    setForeshadows([])
    setForeshadowSummary(null)
    setCausal(null)
    setCausalProjectId('')
    setCausalError('')
    setSettingLoad(null)
    setSettingLoadProjectId('')
    setSettingLoadError('')
    setCharacterDrift(null)
    setCharacterDriftProjectId('')
    setCharacterDriftError('')
    // 让上一本在途的漂移响应过期：它不能落到新项目的表格里。
    characterDriftRequestRef.current += 1
    setReviewMarks([])
    setDataProjectId('')
    runToken.current++
    setChapterPlan(null)
    setScenePlan(null)
    setPlanning(false)
    const token = ++dataRequestRef.current
    Promise.allSettled([
      api.getChapterTree(projectId),
      api.listForeshadows(projectId),
      api.listReviewMarks(projectId),
      api.foreshadowSummary(projectId),
      api.causalMap(projectId),
      api.settingLoad(projectId),
      api.characterDrift(projectId),
    ]).then((results) => {
      const [
        treeResult,
        foreshadowResult,
        markResult,
        summaryResult,
        causalResult,
        settingLoadResult,
        characterDriftResult,
      ] = results
      if (dataRequestRef.current !== token) return
      const errors: string[] = []
      if (treeResult.status === 'fulfilled') {
        setVolumes(treeResult.value.volumes)
      } else {
        errors.push((treeResult.reason as Error).message)
      }
      if (foreshadowResult.status === 'fulfilled') {
        setForeshadows(foreshadowResult.value)
      } else {
        errors.push((foreshadowResult.reason as Error).message)
      }
      if (summaryResult.status === 'fulfilled') {
        setForeshadowSummary(summaryResult.value)
      } else {
        errors.push((summaryResult.reason as Error).message)
      }
      if (markResult.status === 'fulfilled') {
        setReviewMarks(markResult.value)
      }
      // 因果链只在它自己的视图里报错，不混进页头的伏笔/树错误。
      if (causalResult.status === 'fulfilled') {
        setCausal(causalResult.value)
        setCausalError('')
      } else {
        setCausalError((causalResult.reason as Error).message)
      }
      // 设定投放同样独立报错：统计失败不该连带把结构树判为失败。
      if (settingLoadResult.status === 'fulfilled') {
        setSettingLoad(settingLoadResult.value)
        setSettingLoadError('')
      } else {
        setSettingLoadError((settingLoadResult.reason as Error).message)
      }
      // 性格漂移同理：读失败只在它自己的页签里说，不牵连别的视图。
      if (characterDriftResult.status === 'fulfilled') {
        setCharacterDrift(characterDriftResult.value)
        setCharacterDriftError('')
      } else {
        setCharacterDriftError((characterDriftResult.reason as Error).message)
      }
      if (errors.length > 0) setNotice(errors.join('；'))
      // 两份都已有结果就结束加载态：部分失败时显示已有数据 + 页头提示。
      setDataProjectId(projectId)
      setCausalProjectId(projectId)
      setSettingLoadProjectId(projectId)
      setCharacterDriftProjectId(projectId)
    })
    api
      .listEntries(projectId)
      .then((list) => {
        if (dataRequestRef.current !== token) return
        setEntries(list)
        setEntriesProjectId(projectId)
      })
      .catch((error) => {
        if (dataRequestRef.current === token) setNotice((error as Error).message)
      })
    return () => {
      // 切项目或卸载时让在途响应过期。
      dataRequestRef.current += 1
    }
  }, [projectId])

  async function refresh() {
    const requestProjectId = projectId
    // 保存动作可能在新项目已经加载后才落回（闭包里还是旧的 projectId）。
    // 这类旧请求连 token 都不能动，否则会把新项目的装载判为过期，
    // 让 dataProjectId 永远停在旧值、页签一直卡在加载态。
    if (projectIdRef.current !== requestProjectId) return
    const token = ++dataRequestRef.current
    try {
      const [tree, entryList, foreshadowList, marks, summary] = await Promise.all([
        api.getChapterTree(requestProjectId),
        api.listEntries(requestProjectId),
        api.listForeshadows(requestProjectId),
        api.listReviewMarks(requestProjectId),
        api.foreshadowSummary(requestProjectId),
      ])
      // 期间切了项目（或又发起了一次刷新）：这批数据属于旧请求，整批丢弃。
      if (dataRequestRef.current !== token) return
      if (projectIdRef.current !== requestProjectId) return
      setVolumes(tree.volumes)
      setEntries(entryList)
      setEntriesProjectId(requestProjectId)
      setForeshadows(foreshadowList)
      setForeshadowSummary(summary)
      setReviewMarks(marks)
    } finally {
      // 当前项目的刷新无论成败都要结束加载态；旧项目不发结果，也不许碰它。
      if (
        dataRequestRef.current === token &&
        projectIdRef.current === requestProjectId
      ) {
        setDataProjectId(requestProjectId)
        setCausalProjectId(requestProjectId)
        setSettingLoadProjectId(requestProjectId)
      }
    }
    // 因果链单独取：这张图失败只该让它的视图报错，不该把保存后的整页刷新一起拖垮。
    api
      .causalMap(requestProjectId)
      .then((map) => {
        if (dataRequestRef.current !== token) return
        if (projectIdRef.current !== requestProjectId) return
        setCausal(map)
        setCausalError('')
      })
      .catch((error) => {
        if (dataRequestRef.current !== token) return
        if (projectIdRef.current !== requestProjectId) return
        setCausalError((error as Error).message)
      })
    // 设定投放同样是「只服务一个视图」的统计：保存正文后要重算，失败也只报自己的错。
    api
      .settingLoad(requestProjectId)
      .then((load) => {
        if (dataRequestRef.current !== token) return
        if (projectIdRef.current !== requestProjectId) return
        setSettingLoad(load)
        setSettingLoadError('')
      })
      .catch((error) => {
        if (dataRequestRef.current !== token) return
        if (projectIdRef.current !== requestProjectId) return
        setSettingLoadError((error as Error).message)
      })
    // 性格漂移也一样：章序或人物改过之后要重排，失败只报它自己的错。
    void loadCharacterDrift(requestProjectId)
  }

  /** 只重拉性格漂移。**保存 / 删除一格后走这条** —— 变化标记由后端重算，前端不猜。 */
  async function loadCharacterDrift(requestProjectId: string) {
    if (!requestProjectId) return
    // 保存动作落回时可能已经切了项目：旧项目的请求连 token 都不该动。
    if (projectIdRef.current !== requestProjectId) return
    const token = ++characterDriftRequestRef.current
    try {
      const data = await api.characterDrift(requestProjectId)
      if (token !== characterDriftRequestRef.current) return
      if (projectIdRef.current !== requestProjectId) return
      setCharacterDrift(data)
      setCharacterDriftError('')
    } catch (error) {
      if (token !== characterDriftRequestRef.current) return
      if (projectIdRef.current !== requestProjectId) return
      setCharacterDriftError((error as Error).message)
    } finally {
      // 失败也要结束加载态（显示错误），不能一直转圈。
      if (
        token === characterDriftRequestRef.current &&
        projectIdRef.current === requestProjectId
      ) {
        setCharacterDriftProjectId(requestProjectId)
      }
    }
  }

  async function run(action: () => Promise<void>) {
    setBusy(true)
    setNotice('')
    try {
      await action()
    } catch (error) {
      setNotice((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const volume = selected?.kind === 'volume' ? volumes.find((v) => v.id === selected.id) : undefined
  const chapter =
    selected?.kind === 'chapter'
      ? volumes.flatMap((v) => v.chapters).find((c) => c.id === selected.id)
      : undefined
  const scene =
    selected?.kind === 'scene'
      ? volumes.flatMap((v) => v.chapters).flatMap((c) => c.scenes).find((s) => s.id === selected.id)
      : undefined
  const parentChapter =
    selected?.kind === 'scene'
      ? volumes.flatMap((v) => v.chapters).find((c) => c.scenes.some((s) => s.id === selected?.id))
      : undefined
  const activeChapter = chapter ?? parentChapter

  async function runChapterPlan() {
    setPlanning(true)
    setNotice('')
    const token = runToken.current
    try {
      const result = await api.planChapters(projectId)
      if (token !== runToken.current) return
      setChapterPlan(result)
      if (!result.structured) setNotice(result.parse_error ?? '模型没有按契约返回')
    } catch (error) {
      if (token === runToken.current) setNotice((error as Error).message)
    } finally {
      if (token === runToken.current) setPlanning(false)
    }
  }

  async function runScenePlan(chapter: ChapterNode) {
    setPlanning(true)
    setNotice('')
    const token = runToken.current
    try {
      const result = await api.planScenes(chapter.id)
      if (token !== runToken.current) return
      setScenePlan({
        data: result,
        chapterId: chapter.id,
        chapterTitle: `第${chapter.seq + 1}章 ${chapter.title}`,
      })
      if (!result.structured) setNotice(result.parse_error ?? '模型没有按契约返回')
    } catch (error) {
      if (token === runToken.current) setNotice((error as Error).message)
    } finally {
      if (token === runToken.current) setPlanning(false)
    }
  }

  async function writeChapterPlan(volumes: PlanVolume[], mode: 'replace' | 'append') {
    if (!chapterPlan) return
    const token = runToken.current
    setPlanning(true)
    setNotice('')
    try {
      const result = await api.writeChapterPlan(projectId, {
        mode,
        source_run_id: chapterPlan.run.id,
        volumes,
      })
      if (token !== runToken.current) return
      setVolumes(result.volumes)
      setChapterPlan(null)
      setNotice('章纲已写入')
    } catch (error) {
      if (token === runToken.current) setNotice((error as Error).message)
    } finally {
      if (token === runToken.current) setPlanning(false)
    }
  }

  async function writeScenePlan(scenes: PlanScene[], mode: 'replace' | 'append') {
    if (!scenePlan) return
    const token = runToken.current
    const { chapterId, chapterTitle } = scenePlan
    // 草稿生成后章可能已被替换或删除。此时保留草稿并说明原因，
    // 绝不退回到「当前选中的章」——那会把场景写进另一章。
    if (!volumes.flatMap((v) => v.chapters).some((c) => c.id === chapterId)) {
      setNotice(`「${chapterTitle}」已不在当前结构里（可能已被替换或删除），草稿仍保留。请重新运行场景策划。`)
      return
    }
    setPlanning(true)
    setNotice('')
    try {
      const result = await api.writeScenes(chapterId, {
        mode,
        source_run_id: scenePlan.data.run.id,
        scenes,
      })
      if (token !== runToken.current) return
      setVolumes(result.volumes)
      setScenePlan(null)
      await refresh()
      if (token !== runToken.current) return
      setNotice('场景已写入')
    } catch (error) {
      if (token === runToken.current) setNotice((error as Error).message)
    } finally {
      if (token === runToken.current) setPlanning(false)
    }
  }

  async function addVolume() {
    await run(async () => {
      const created = await api.createVolume(projectId, { name: '新卷' })
      await refresh()
      setSelected({ kind: 'volume', id: created.id })
    })
  }

  async function addChapter(volumeId: string) {
    await run(async () => {
      const created = await api.createChapter(volumeId, { title: '新章' })
      await refresh()
      setSelected({ kind: 'chapter', id: created.id })
    })
  }

  async function addScene(chapterId: string) {
    await run(async () => {
      const created = await api.createScene(chapterId, { goal: '' })
      await refresh()
      setSelected({ kind: 'scene', id: created.id })
    })
  }

  async function move(kind: Selection['kind'], id: string, direction: 'up' | 'down') {
    await run(async () => {
      if (kind === 'volume') await api.moveVolume(id, direction)
      else if (kind === 'chapter') await api.moveChapter(id, direction)
      else await api.moveScene(id, direction)
      await refresh()
    })
  }

  async function deleteSelected() {
    if (!selected) return
    if (!window.confirm('删除这一项？子项会一并删除。')) return
    await run(async () => {
      if (selected.kind === 'volume') await api.deleteVolume(selected.id)
      else if (selected.kind === 'chapter') await api.deleteChapter(selected.id)
      else await api.deleteScene(selected.id)
      setSelected(null)
      await refresh()
    })
  }

  function openInStructure(selection: Selection) {
    const chapters = volumes.flatMap((volume) => volume.chapters)
    const found =
      selection.kind === 'volume'
        ? volumes.some((volume) => volume.id === selection.id)
        : selection.kind === 'chapter'
          ? chapters.some((chapter) => chapter.id === selection.id)
          : chapters.some((chapter) =>
              chapter.scenes.some((scene) => scene.id === selection.id),
            )
    if (!found) {
      setNotice('这一项已不在当前结构里。')
      return
    }
    setSelected(selection)
    setView('structure')
  }

  const viewsLoading = Boolean(projectId) && dataProjectId !== projectId
  // 因果链单独判加载态：它只服务一个视图，失败也不该拖住别的视图。
  const causalLoading = Boolean(projectId) && causalProjectId !== projectId
  const settingLoadLoading = Boolean(projectId) && settingLoadProjectId !== projectId
  const characterDriftLoading = Boolean(projectId) && characterDriftProjectId !== projectId

  // 页签分两层，但**只有一个状态**：一级组的选中态由 `view` 投影得出，
  // 所以重组没有引入新状态，八个 `view === 'xxx'` 渲染分支一行未动。
  const activeGroup = groupOfView(view)
  const subViews = subViewsOf(activeGroup)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="font-serif text-[19px] font-semibold text-ink">章节设计</h2>
        <div className="ml-auto flex items-center gap-2">
          {view === 'structure' && (
            <Button
              variant="primary"
              disabled={!projectId || planning}
              onClick={runChapterPlan}
            >
              {planning ? '生成中…' : 'AI 排卷章'}
            </Button>
          )}
        </div>
      </div>

      {notice && <p className="text-[13px] text-muted">{notice}</p>}

      {projectId && reviewMarks.length > 0 && (
        <ReviewMarkList
          projectId={projectId}
          marks={reviewMarks}
          onReload={refresh}
        />
      )}

      <div className="space-y-2 border-b border-line pb-2">
        <Tabs
          items={VIEW_GROUPS.map((group) => ({ key: group.key, label: group.label }))}
          active={activeGroup}
          onChange={(key) => {
            const next = viewOfGroup(key)
            if (next) setView(next)
          }}
        />
        {subViews.length > 0 && (
          <Tabs
            items={subViews.map((item) => ({ key: item.key, label: item.label }))}
            active={view}
            onChange={(key) => {
              const next = subViews.find((item) => item.key === key)
              if (next) setView(next.key)
            }}
          />
        )}
      </div>

      {view === 'structure' && (
        <>
          {chapterPlan && (
            <>
              <ChapterPlanDraft
                key={chapterPlan.run.id}
                volumes={chapterPlan.volumes}
                statuses={statuses}
                warnings={chapterPlan.warnings}
                openQuestions={chapterPlan.open_questions}
                busy={planning}
                onWrite={writeChapterPlan}
                onClose={() => setChapterPlan(null)}
              />
              <RunTrace run={chapterPlan.run} />
            </>
          )}
          {scenePlan && (
            <>
              <ScenePlanDraft
                key={scenePlan.data.run.id}
                chapterTitle={scenePlan.chapterTitle}
                scenes={scenePlan.data.scenes}
                warnings={scenePlan.data.warnings}
                openQuestions={scenePlan.data.open_questions}
                busy={planning}
                onWrite={writeScenePlan}
                onClose={() => setScenePlan(null)}
              />
              <RunTrace run={scenePlan.data.run} />
            </>
          )}

          <div className="grid grid-cols-[308px_1fr] items-start gap-4">
            <Panel className="max-h-[70vh]">
              <div className="p-3">
                <ChapterTree
                  volumes={volumes}
                  selected={selected}
                  onSelect={setSelected}
                  onAddVolume={addVolume}
                  onAddChapter={addChapter}
                  onAddScene={addScene}
                  onMove={move}
                />
              </div>
            </Panel>

            <div className="space-y-4">
              {activeChapter && (
                <div className="flex justify-end">
                  <Button
                    variant="primary"
                    disabled={planning}
                    onClick={() => runScenePlan(activeChapter)}
                  >
                    AI 写场景卡
                  </Button>
                </div>
              )}
              {!selected && (
                <p className="rounded-card border border-line bg-surface p-4 text-[13.5px] text-muted">
                  从左边选一卷、一章或一个场景开始编辑；也可以先手工建卷。
                </p>
              )}
              {selected && (volume || chapter || scene) && (
                <div className="space-y-2 rounded-card border border-line bg-surface p-3">
                  <div className="flex flex-wrap items-center gap-3 text-[13px]">
                    {(() => {
                      const mark = reviewMarks.find(
                        (row) =>
                          row.target_type === selected.kind && row.target_id === selected.id,
                      )
                      return mark ? (
                        <ReviewMarkBadge
                          marked
                          reason={mark.reason}
                          onClick={async () => {
                            await api.clearReviewMark(mark.id)
                            await refresh()
                          }}
                        />
                      ) : null
                    })()}
                    {/* 按钮自己写着「锁定 / 已锁定」，不再另加一个「锁定」标签。 */}
                    <LockToggle
                      targetType={selected.kind}
                      targetId={selected.id}
                      locked={(volume ?? chapter ?? scene)?.locked === true}
                      inheritedLabel={(() => {
                        // 有效锁定向下继承，界面必须与之一致：章被卷锁住时若
                        // 仍显示可点的「锁定」，作者点它只会写一条冗余的章锁，
                        // 之后「解锁」也解不掉那份有效锁。
                        const own = volume ?? chapter ?? scene
                        if (!own || own.locked) return undefined
                        if (selected.kind === 'chapter' || selected.kind === 'scene') {
                          const owner =
                            selected.kind === 'scene'
                              ? volumes.find((v) => v.id === parentChapter?.volume_id)
                              : volumes.find((v) => v.id === chapter?.volume_id)
                          if (owner?.locked) return `第${owner.seq + 1}卷（${owner.name}）`
                        }
                        if (selected.kind === 'scene' && parentChapter?.locked) {
                          return `第${parentChapter.seq + 1}章（${parentChapter.title}）`
                        }
                        return undefined
                      })()}
                      onChanged={refresh}
                    />
                  </div>
                  {projectId && (
                    <ImpactPanel
                      projectId={projectId}
                      targetType={selected.kind}
                      targetId={selected.id}
                      onMarksChanged={refresh}
                    />
                  )}
                </div>
              )}
              {volume && (
                <VolumeEditor
                  key={volume.id}
                  volume={volume}
                  statuses={statuses}
                  busy={busy}
                  onSave={async (fields) =>
                    run(async () => {
                      await api.updateVolume(volume.id, fields)
                      await refresh()
                      setNotice('已保存')
                    })
                  }
                  onDelete={deleteSelected}
                />
              )}
              {chapter && (
                <ChapterEditor
                  key={chapter.id}
                  chapter={chapter}
                  statuses={statuses}
                  busy={busy}
                  onSave={async (fields) =>
                    run(async () => {
                      await api.updateChapter(chapter.id, fields)
                      await refresh()
                      setNotice('已保存')
                    })
                  }
                  onDelete={deleteSelected}
                />
              )}
              {scene && (
                <SceneEditor
                  key={scene.id}
                  scene={scene}
                  statuses={statuses}
                  entries={entries}
                  entriesReady={entriesProjectId === projectId}
                  foreshadows={foreshadows}
                  busy={busy}
                  onSave={async (fields) =>
                    run(async () => {
                      await api.updateScene(scene.id, fields)
                      await refresh()
                      setNotice('已保存')
                    })
                  }
                  onDelete={deleteSelected}
                />
              )}
            </div>
          </div>
        </>
      )}

      {view !== 'structure' && (
        <section className="space-y-4">
          {!projectId ? (
            <p className="rounded-card border border-line bg-surface p-4 text-[13.5px] text-muted">
              先选一个项目。
            </p>
          ) : viewsLoading ? (
            <div className="rounded-card border border-line bg-surface p-4">
              <span className="sr-only">正在读取章节结构…</span>
              <Skeleton lines={6} />
            </div>
          ) : (
            <>
              {view === 'rhythm' && (
                <RhythmCurve
                  volumes={volumes}
                  onSelectChapter={(id) =>
                    openInStructure({ kind: 'chapter', id })
                  }
                />
              )}
              {view === 'foreshadows' && (
                <ForeshadowLedger
                  volumes={volumes}
                  foreshadows={foreshadows}
                  statuses={foreshadowStatuses}
                  summary={foreshadowSummary}
                  onSelectScene={(id) => openInStructure({ kind: 'scene', id })}
                  onChanged={refresh}
                  onNotice={setNotice}
                  busy={busy}
                />
              )}
              {view === 'lanes' && (
                <Swimlanes
                  volumes={volumes}
                  onSelectChapter={(id) =>
                    openInStructure({ kind: 'chapter', id })
                  }
                />
              )}
              {view === 'causal' && (
                <CausalMap
                  data={causal}
                  loading={causalLoading}
                  error={causalError}
                  logicChecked={causal?.logic_checked ?? false}
                  onSelectScene={(id) =>
                    openInStructure({ kind: 'scene', id })
                  }
                />
              )}
              {view === 'settingLoad' && (
                <SettingLoadCurve
                  data={settingLoad}
                  loading={settingLoadLoading}
                  error={settingLoadError}
                  onSelectChapter={(id) =>
                    openInStructure({ kind: 'chapter', id })
                  }
                />
              )}
              {view === 'characterDrift' && (
                // key：切项目时重挂载，编辑中的格子不会跟着旧项目的行带到新项目。
                <CharacterDrift
                  key={projectId}
                  data={characterDrift}
                  loading={characterDriftLoading}
                  error={characterDriftError}
                  onReload={() => loadCharacterDrift(projectId)}
                  onNotice={setNotice}
                />
              )}
            </>
          )}
        </section>
      )}
    </div>
  )
}
