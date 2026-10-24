import { createSseParser } from '../lib/sse'

const JSON_HEADERS = { 'content-type': 'application/json' }

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(detail.detail ?? `请求失败：${response.status}`)
  }
  return response.status === 204 ? (undefined as T) : response.json()
}

export const api = {
  health: () => request<{ status: string; data_dir: string }>('/api/health'),

  listProjects: () => request<Project[]>('/api/projects'),
  createProject: (body: { name: string; genre?: string; tone?: string }) =>
    request<Project>('/api/projects', { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify(body) }),

  listIdeas: (projectId: string) => request<Idea[]>(`/api/projects/${projectId}/ideas`),
  createIdea: (projectId: string, rawText: string) =>
    request<Idea>(`/api/projects/${projectId}/ideas`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify({ raw_text: rawText }),
    }),
  parseIdea: (projectId: string, ideaId: string) =>
    request<{ run: RunView; structured: boolean; parse_error: string | null; idea: Idea }>(
      `/api/projects/${projectId}/ideas/${ideaId}/parse`,
      { method: 'POST' },
    ),

  getArchitecture: (projectId: string) =>
    request<{ architecture: Architecture | null; acts: Act[] }>(`/api/projects/${projectId}/architecture`),
  recommendArchitecture: (projectId: string) =>
    request<RecommendResponse>(`/api/projects/${projectId}/architecture/recommend`, { method: 'POST' }),
  adoptArchitecture: (projectId: string, body: AdoptPayload) =>
    request<{ architecture: Architecture; acts: Act[] }>(`/api/projects/${projectId}/architecture`, {
      method: 'PUT',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),

  listAgents: () => request<Agent[]>('/api/agents'),
  updateAgent: (agentId: string, body: Record<string, unknown>) =>
    request<Agent>(`/api/agents/${agentId}`, {
      method: 'PATCH',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  listSlots: () => request<SlotSpec[]>('/api/slots'),
  listVersions: (agentId: string) => request<AgentVersion[]>(`/api/agents/${agentId}/versions`),
  createVersion: (agentId: string, body: Record<string, unknown>) =>
    request<AgentVersion>(`/api/agents/${agentId}/versions`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  rollback: (agentId: string, versionId: string) =>
    request<Agent>(`/api/agents/${agentId}/rollback/${versionId}`, { method: 'POST' }),
  applyPreset: (agentId: string) =>
    request<Agent>(`/api/agents/${agentId}/apply-preset`, { method: 'POST' }),

  listRuns: (projectId?: string, agentId?: string) => {
    const params = new URLSearchParams()
    if (projectId) params.set('project_id', projectId)
    if (agentId) params.set('agent_id', agentId)
    const query = params.toString()
    return request<RunView[]>(`/api/runs${query ? `?${query}` : ''}`)
  },
  runAgent: (projectId: string, agentId: string) =>
    request<{ run: RunView; parse_error: string | null; trimmed: Record<string, string> }>('/api/runs', {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify({ project_id: projectId, agent_id: agentId }),
    }),

  listTools: () => request<Tool[]>('/api/tools'),

  listEntryTypes: () => request<EntryTypesResponse>('/api/entry-types'),

  listEntries: (projectId: string, type?: string) =>
    request<SettingEntry[]>(
      `/api/projects/${projectId}/entries${type ? `?type=${encodeURIComponent(type)}` : ''}`,
    ),
  createEntry: (projectId: string, body: Record<string, unknown>) =>
    request<SettingEntry>(`/api/projects/${projectId}/entries`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  updateEntry: (entryId: string, body: Record<string, unknown>) =>
    request<SettingEntry>(`/api/entries/${entryId}`, {
      method: 'PATCH',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  deleteEntry: (entryId: string) => request<void>(`/api/entries/${entryId}`, { method: 'DELETE' }),

  listRelations: (projectId: string) =>
    request<EntryRelation[]>(`/api/projects/${projectId}/relations`),
  createRelation: (projectId: string, body: Record<string, unknown>) =>
    request<EntryRelation>(`/api/projects/${projectId}/relations`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  updateRelation: (relationId: string, body: Record<string, unknown>) =>
    request<EntryRelation>(`/api/relations/${relationId}`, {
      method: 'PATCH',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  deleteRelation: (relationId: string) =>
    request<void>(`/api/relations/${relationId}`, { method: 'DELETE' }),

  listTerms: (projectId: string) => request<TermRow[]>(`/api/projects/${projectId}/terms`),
  listTimeline: (projectId: string) =>
    request<TimelineEvent[]>(`/api/projects/${projectId}/timeline`),
  createTimelineEvent: (projectId: string, body: Record<string, unknown>) =>
    request<TimelineEvent>(`/api/projects/${projectId}/timeline`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  updateTimelineEvent: (eventId: string, body: Record<string, unknown>) =>
    request<TimelineEvent>(`/api/timeline/${eventId}`, {
      method: 'PATCH',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  moveTimelineEvent: (eventId: string, direction: 'up' | 'down') =>
    request<TimelineEvent>(`/api/timeline/${eventId}/move`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify({ direction }),
    }),
  deleteTimelineEvent: (eventId: string) =>
    request<void>(`/api/timeline/${eventId}`, { method: 'DELETE' }),
  suggestEntries: (projectId: string) =>
    request<SuggestResponse>(`/api/projects/${projectId}/entries/suggest`, { method: 'POST' }),

  listChapterTypes: () => request<ChapterTypesResponse>('/api/chapter-types'),
  listForeshadowTypes: () =>
    request<ChapterTypesResponse>('/api/foreshadow-types'),
  getChapterTree: (projectId: string) =>
    request<{ volumes: VolumeNode[] }>(`/api/projects/${projectId}/chapters/tree`),
  createVolume: (projectId: string, body: Record<string, unknown>) =>
    request<VolumeView>(`/api/projects/${projectId}/volumes`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  updateVolume: (volumeId: string, body: Record<string, unknown>) =>
    request<VolumeView>(`/api/volumes/${volumeId}`, {
      method: 'PATCH',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  deleteVolume: (volumeId: string) => request<void>(`/api/volumes/${volumeId}`, { method: 'DELETE' }),
  moveVolume: (volumeId: string, direction: 'up' | 'down') =>
    request<VolumeView>(`/api/volumes/${volumeId}/move`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify({ direction }),
    }),
  createChapter: (volumeId: string, body: Record<string, unknown>) =>
    request<ChapterView>(`/api/volumes/${volumeId}/chapters`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  updateChapter: (chapterId: string, body: Record<string, unknown>) =>
    request<ChapterView>(`/api/chapters/${chapterId}`, {
      method: 'PATCH',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  deleteChapter: (chapterId: string) =>
    request<void>(`/api/chapters/${chapterId}`, { method: 'DELETE' }),
  moveChapter: (chapterId: string, direction: 'up' | 'down') =>
    request<ChapterView>(`/api/chapters/${chapterId}/move`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify({ direction }),
    }),
  createScene: (chapterId: string, body: Record<string, unknown>) =>
    request<SceneNode>(`/api/chapters/${chapterId}/scenes`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  updateScene: (sceneId: string, body: Record<string, unknown>) =>
    request<SceneNode>(`/api/scenes/${sceneId}`, {
      method: 'PATCH',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  deleteScene: (sceneId: string) => request<void>(`/api/scenes/${sceneId}`, { method: 'DELETE' }),
  moveScene: (sceneId: string, direction: 'up' | 'down') =>
    request<SceneNode>(`/api/scenes/${sceneId}/move`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify({ direction }),
    }),

  planChapters: (projectId: string) =>
    request<ChapterPlanResponse>(`/api/projects/${projectId}/chapters/plan`, { method: 'POST' }),
  planScenes: (chapterId: string) =>
    request<ScenePlanResponse>(`/api/chapters/${chapterId}/scenes/plan`, { method: 'POST' }),
  writeChapterPlan: (projectId: string, body: Record<string, unknown>) =>
    request<{ volumes: VolumeNode[] }>(`/api/projects/${projectId}/chapters`, {
      method: 'PUT',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  writeScenes: (chapterId: string, body: Record<string, unknown>) =>
    request<{ volumes: VolumeNode[] }>(`/api/chapters/${chapterId}/scenes`, {
      method: 'PUT',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),

  getSceneText: (sceneId: string) =>
    request<SceneTextState>(`/api/scenes/${sceneId}/text`),
  saveSceneBody: (sceneId: string, content: string) =>
    request<SceneTextState>(`/api/scenes/${sceneId}/body`, {
      method: 'PUT',
      headers: JSON_HEADERS,
      body: JSON.stringify({ content }),
    }),
  saveSceneDraft: (sceneId: string, content: string) =>
    request<SceneTextDraft>(`/api/scenes/${sceneId}/draft`, {
      method: 'PUT',
      headers: JSON_HEADERS,
      body: JSON.stringify({ content }),
    }),
  discardSceneDraft: (sceneId: string) =>
    request<{ ok: boolean }>(`/api/scenes/${sceneId}/draft`, { method: 'DELETE' }),
  adoptSceneDraft: (sceneId: string) =>
    request<SceneTextState>(`/api/scenes/${sceneId}/adopt`, { method: 'POST' }),
  listSceneRevisions: (sceneId: string) =>
    request<RevisionSummary[]>(`/api/scenes/${sceneId}/revisions`),
  getSceneRevision: (sceneId: string, revisionId: string) =>
    request<RevisionDetail>(`/api/scenes/${sceneId}/revisions/${revisionId}`),
  restoreSceneRevision: (sceneId: string, revisionId: string) =>
    request<SceneTextState>(
      `/api/scenes/${sceneId}/revisions/${revisionId}/restore`,
      { method: 'POST' },
    ),
  getSceneContextPreview: (sceneId: string) =>
    request<ContextPreview>(`/api/scenes/${sceneId}/context-preview`),
  runSceneAudit: (sceneId: string) =>
    request<AuditResult>(`/api/scenes/${sceneId}/audit`, { method: 'POST' }),
  getSceneAudit: (sceneId: string) =>
    request<AuditView>(`/api/scenes/${sceneId}/audit`),
  runSceneLogicCheck: (sceneId: string, stage: LogicStage) =>
    request<LogicCheckResult>(`/api/scenes/${sceneId}/logic-check`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify({ stage }),
    }),
  getSceneLogicCheck: (sceneId: string, stage: LogicStage) =>
    request<LogicCheckView>(
      `/api/scenes/${sceneId}/logic-check?stage=${encodeURIComponent(stage)}`,
    ),
  runSceneWriteback: (sceneId: string) =>
    request<WritebackSuggestion>(`/api/scenes/${sceneId}/writeback`, {
      method: 'POST',
    }),
  applySceneWriteback: (sceneId: string, payload: WritebackApplyPayload) =>
    request<WritebackApplyResult>(`/api/scenes/${sceneId}/writeback/apply`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify(payload),
    }),
  createBatch: (
    projectId: string,
    body: { scope_type: 'chapter' | 'volume'; scope_id: string },
  ) =>
    request<BatchJob>(`/api/projects/${projectId}/batches`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  getBatch: (jobId: string) => request<BatchJob>(`/api/batches/${jobId}`),
  getLatestBatch: (projectId: string) =>
    request<BatchJob | null>(`/api/projects/${projectId}/batches/latest`),
  pauseBatch: (jobId: string) =>
    request<BatchJob>(`/api/batches/${jobId}/pause`, { method: 'POST' }),
  resumeBatch: (jobId: string) =>
    request<BatchJob>(`/api/batches/${jobId}/resume`, { method: 'POST' }),
  cancelBatch: (jobId: string) =>
    request<BatchJob>(`/api/batches/${jobId}/cancel`, { method: 'POST' }),
  retryBatchFailed: (jobId: string) =>
    request<BatchJob>(`/api/batches/${jobId}/retry-failed`, { method: 'POST' }),
  getExportReport: (projectId: string) =>
    request<ExportReport>(`/api/projects/${projectId}/export/report`),
  readBook: (projectId: string) =>
    request<BookResponse>(`/api/projects/${projectId}/book`),
  exportUrl: (projectId: string, format: 'md' | 'txt' | 'epub', template?: string) =>
    `/api/projects/${projectId}/export?format=${format}` +
    (format === 'epub' && template ? `&template=${encodeURIComponent(template)}` : ''),
  uploadCover: async (projectId: string, file: File) => {
    const body = new FormData()
    body.append('file', file)
    // 不能带 content-type：浏览器要自己算 multipart 的 boundary。
    const response = await fetch(`/api/projects/${projectId}/cover`, {
      method: 'PUT',
      body,
    })
    if (!response.ok) {
      const detail = await response.json().catch(() => null)
      throw new Error(detail?.detail ?? `上传失败（${response.status}）`)
    }
    return (await response.json()) as { has_cover: boolean; size: number }
  },
  removeCover: (projectId: string) =>
    request<void>(`/api/projects/${projectId}/cover`, { method: 'DELETE' }),
  resolveAuditIssue: (issueId: string, resolution: AuditResolution) =>
    request<AuditIssue>(`/api/audit/issues/${issueId}`, {
      method: 'PATCH',
      headers: JSON_HEADERS,
      body: JSON.stringify({ resolution }),
    }),

  foreshadowSummary: (projectId: string) =>
    request<ForeshadowSummary>(`/api/projects/${projectId}/foreshadows/summary`),
  causalMap: (projectId: string) =>
    request<CausalMapData>(`/api/projects/${projectId}/causal-map`),
  settingLoad: (projectId: string) =>
    request<SettingLoadData>(`/api/projects/${projectId}/setting-load`),
  characterDrift: (projectId: string) =>
    request<CharacterDriftData>(`/api/projects/${projectId}/character-drift`),
  // 同一章同一人重复写是 upsert（不是再记一条），所以 PUT 而不是 POST。
  putCharacterState: (chapterId: string, entryId: string, note: string) =>
    request<CharacterStateRecord>(
      `/api/chapters/${chapterId}/character-states/${entryId}`,
      {
        method: 'PUT',
        headers: JSON_HEADERS,
        body: JSON.stringify({ note }),
      },
    ),
  deleteCharacterState: (chapterId: string, entryId: string) =>
    request<void>(`/api/chapters/${chapterId}/character-states/${entryId}`, {
      method: 'DELETE',
    }),
  logicChain: (sceneId: string) =>
    request<LogicChainResponse>(`/api/scenes/${sceneId}/logic-chain`),
  listForeshadows: (projectId: string) =>
    request<Foreshadow[]>(`/api/projects/${projectId}/foreshadows`),
  createForeshadow: (projectId: string, body: Record<string, unknown>) =>
    request<Foreshadow>(`/api/projects/${projectId}/foreshadows`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  updateForeshadow: (foreshadowId: string, body: Record<string, unknown>) =>
    request<Foreshadow>(`/api/foreshadows/${foreshadowId}`, {
      method: 'PATCH',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  deleteForeshadow: (foreshadowId: string) =>
    request<void>(`/api/foreshadows/${foreshadowId}`, { method: 'DELETE' }),

  listProviders: () => request<ProviderView[]>('/api/providers'),
  createProvider: (body: Record<string, unknown>) =>
    request<ProviderView>('/api/providers', {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  testProvider: (id: string, model?: string) =>
    request<{ ok: boolean; message: string }>(`/api/providers/${id}/test`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify({ model: model ?? null }),
    }),
  updateProvider: (id: string, body: Record<string, unknown>) =>
    request<ProviderView>(`/api/providers/${id}`, {
      method: 'PATCH',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  deleteProvider: (id: string) => request<void>(`/api/providers/${id}`, { method: 'DELETE' }),

  getSettings: () => request<Settings>('/api/settings'),
  updateSettings: (values: Record<string, unknown>) =>
    request<Settings>('/api/settings', {
      method: 'PUT',
      headers: JSON_HEADERS,
      body: JSON.stringify({ values }),
    }),
  projectCost: (projectId: string) => request<CostSummary>(`/api/projects/${projectId}/cost`),

  getPipeline: (projectId: string) =>
    request<Pipeline>(`/api/projects/${projectId}/pipeline`),
  updatePipeline: (projectId: string, body: Record<string, unknown>) =>
    request<Pipeline>(`/api/projects/${projectId}/pipeline`, {
      method: 'PUT',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  resetPipeline: (projectId: string) =>
    request<Pipeline>(`/api/projects/${projectId}/pipeline/reset`, { method: 'POST' }),
  startPipelineRun: (projectId: string) =>
    request<PipelineRun>(`/api/projects/${projectId}/pipeline/runs`, { method: 'POST' }),
  latestPipelineRun: (projectId: string) =>
    request<PipelineRun | null>(`/api/projects/${projectId}/pipeline/runs/latest`),
  getPipelineRun: (runId: string) => request<PipelineRun>(`/api/pipeline-runs/${runId}`),
  pausePipelineRun: (runId: string) =>
    request<PipelineRun>(`/api/pipeline-runs/${runId}/pause`, { method: 'POST' }),
  resumePipelineRun: (runId: string) =>
    request<PipelineRun>(`/api/pipeline-runs/${runId}/resume`, { method: 'POST' }),
  cancelPipelineRun: (runId: string) =>
    request<PipelineRun>(`/api/pipeline-runs/${runId}/cancel`, { method: 'POST' }),

  listModelPrices: () => request<ModelPrice[]>('/api/model-prices'),
  upsertModelPrice: (body: Record<string, unknown>) =>
    request<ModelPrice>('/api/model-prices', {
      method: 'PUT',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  deleteModelPrice: (id: string) =>
    request<void>(`/api/model-prices/${id}`, { method: 'DELETE' }),

  listLockTargets: () => request<LockTargetsResponse>('/api/lock-targets'),
  getLock: (targetType: string, targetId: string) =>
    request<LockState>(`/api/locks/${targetType}/${targetId}`),
  setLock: (targetType: string, targetId: string, locked: boolean) =>
    request<LockState>(`/api/locks/${targetType}/${targetId}`, {
      method: 'PATCH',
      headers: JSON_HEADERS,
      body: JSON.stringify({ locked }),
    }),
  getParagraphLocks: (sceneId: string) =>
    request<{ scene_id: string; paragraphs: string[] }>(
      `/api/scenes/${sceneId}/paragraph-locks`,
    ),
  setParagraphLocks: (sceneId: string, paragraphs: string[]) =>
    request<{ scene_id: string; paragraphs: string[] }>(
      `/api/scenes/${sceneId}/paragraph-locks`,
      {
        method: 'PUT',
        headers: JSON_HEADERS,
        body: JSON.stringify({ paragraphs }),
      },
    ),
  getImpact: (projectId: string, targetType: string, targetId: string) =>
    request<ImpactReport>(
      `/api/projects/${projectId}/impact?target_type=${targetType}&target_id=${targetId}`,
    ),
  generateRevisions: (
    projectId: string,
    body: { target_type: string; target_id: string },
  ) =>
    request<RevisionResult>(`/api/projects/${projectId}/impact/revisions`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  // 请求只带下标：写入内容由服务端从运行记录里读回，前端决定不了写什么。
  applyRevisions: (
    projectId: string,
    body: { run_id: string; accepted: number[] },
  ) =>
    request<RevisionApplyResult>(`/api/projects/${projectId}/impact/revisions/apply`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  listReviewMarks: (projectId: string) =>
    request<ReviewMark[]>(`/api/projects/${projectId}/review-marks`),
  addReviewMarks: (
    projectId: string,
    items: { target_type: string; target_id: string; reason?: string }[],
  ) =>
    request<{ added: number; marks: ReviewMark[] }>(
      `/api/projects/${projectId}/review-marks`,
      {
        method: 'POST',
        headers: JSON_HEADERS,
        body: JSON.stringify({ items }),
      },
    ),
  clearReviewMark: (markId: string) =>
    request<void>(`/api/review-marks/${markId}`, { method: 'DELETE' }),
  listBranches: (sceneId: string) =>
    request<BranchSummary[]>(`/api/scenes/${sceneId}/branches`),
  // `parent_id` 给定时是派生：新分支复制父分支正文，最多三层。
  createBranch: (
    sceneId: string,
    body: { name: string; note?: string; parent_id?: string },
  ) =>
    request<BranchDetail>(`/api/scenes/${sceneId}/branches`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  getBranch: (branchId: string) =>
    request<BranchDetail>(`/api/branches/${branchId}`),
  updateBranch: (branchId: string, body: Record<string, unknown>) =>
    request<BranchDetail>(`/api/branches/${branchId}`, {
      method: 'PATCH',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  saveBranchBody: (branchId: string, content: string) =>
    request<BranchDetail>(`/api/branches/${branchId}/body`, {
      method: 'PUT',
      headers: JSON_HEADERS,
      body: JSON.stringify({ content }),
    }),
  saveBranchDraft: (branchId: string, content: string) =>
    request<BranchDetail>(`/api/branches/${branchId}/draft`, {
      method: 'PUT',
      headers: JSON_HEADERS,
      body: JSON.stringify({ content }),
    }),
  adoptBranchDraft: (branchId: string) =>
    request<BranchDetail>(`/api/branches/${branchId}/adopt`, { method: 'POST' }),
  mergeBranch: (branchId: string) =>
    request<{ branch: BranchDetail; scene_id: string; body: string; chars: number }>(
      `/api/branches/${branchId}/merge`,
      { method: 'POST' },
    ),
  listBranchRevisions: (branchId: string) =>
    request<BranchRevisionRow[]>(`/api/branches/${branchId}/revisions`),
  discardBranch: (branchId: string) =>
    request<void>(`/api/branches/${branchId}`, { method: 'DELETE' }),
  // ---- A/B 并排：两版就是两条带 ab_group 的分支，生成仍走分支的流式链路 ----
  getAb: (sceneId: string) => request<AbSession>(`/api/scenes/${sceneId}/ab`),
  createAb: async (sceneId: string): Promise<AbSession> => {
    // POST 的 label 是侧别（A/B），GET 的 label 是库名 —— 在这里归一成 AbBranch，
    // 面板只认一种形状。刚建组时还没有草稿，字数由随后的 getAb 补上。
    const created = await request<{
      group: string
      branches: { id: string; label: string }[]
    }>(`/api/scenes/${sceneId}/ab`, { method: 'POST' })
    return {
      group: created.group,
      branches: created.branches.map((item) => ({
        id: item.id,
        label: item.label,
        side: item.label,
        has_draft: false,
        chars: 0,
      })),
    }
  },
  adoptAb: (sceneId: string, branchId: string) =>
    request<{ revision_created: boolean; body: string; chars: number; discarded: string[] }>(
      `/api/scenes/${sceneId}/ab/${branchId}/adopt`,
      { method: 'POST' },
    ),
  discardAb: (sceneId: string, branchId: string) =>
    request<{ removed: string[] }>(`/api/scenes/${sceneId}/ab/${branchId}/discard`, {
      method: 'POST',
    }),
  listSnapshots: (projectId: string) =>
    request<SnapshotView[]>(`/api/projects/${projectId}/snapshots`),
  createSnapshot: (projectId: string, body: { name: string; note?: string }) =>
    request<SnapshotView>(`/api/projects/${projectId}/snapshots`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  getSnapshot: (snapshotId: string) =>
    request<SnapshotDetail>(`/api/snapshots/${snapshotId}`),
  restoreSnapshot: (snapshotId: string) =>
    request<{
      snapshot: SnapshotView
      backup: SnapshotView | null
      scale: Record<string, number>
    }>(
      `/api/snapshots/${snapshotId}/restore`,
      { method: 'POST' },
    ),
  deleteSnapshot: (snapshotId: string) =>
    request<void>(`/api/snapshots/${snapshotId}`, { method: 'DELETE' }),
  listChanges: (
    projectId: string,
    params?: { target_type?: string; target_id?: string; limit?: number; offset?: number },
  ) => {
    const query = new URLSearchParams()
    if (params?.target_type) query.set('target_type', params.target_type)
    if (params?.target_id) query.set('target_id', params.target_id)
    if (params?.limit) query.set('limit', String(params.limit))
    if (params?.offset) query.set('offset', String(params.offset))
    const suffix = query.toString()
    return request<ChangeList>(`/api/projects/${projectId}/changes${suffix ? `?${suffix}` : ''}`)
  },
  clearReviewMarks: (
    projectId: string,
    items: { target_type: string; target_id: string }[],
  ) =>
    request<{ removed: number; marks: ReviewMark[] }>(
      `/api/projects/${projectId}/review-marks/clear`,
      {
        method: 'POST',
        headers: JSON_HEADERS,
        body: JSON.stringify({ items }),
      },
    ),
}

export interface Project {
  id: string
  name: string
  genre: string | null
  tone: string | null
  target_length: number | null
  logic_check_level: string
  /** 有没有封面图；EPUB 会带上它。 */
  has_cover?: boolean
}

export interface Idea {
  id: string
  project_id: string
  raw_text: string
  tags: string[]
  parsed_json: Record<string, unknown> | null
  status: string
}

export interface RunView {
  id: string
  agent_id: string
  model: string
  params: Record<string, unknown>
  rendered_prompt: string
  raw_output: string
  parsed_json: Record<string, unknown> | null
  structured: boolean
  parse_error: string | null
  prompt_tokens: number
  completion_tokens: number
  cost_estimate: number
  usage_source: string
  duration_ms: number
  status: string
  error: { kind: string; message: string } | null
  trimmed: Record<string, string>
  created_at: string
}

export interface ArchitectureOption {
  tool: string
  reason: string
  fit_score: number
  risks: string[]
  length_plan?: string
  rhythm_shape?: string
}

export interface StoryBibleV0 {
  logline?: string
  theme?: string
  premise?: string
  acts?: { name: string; purpose?: string; target_word_ratio?: number }[]
  main_characters?: { name: string; role?: string; desire?: string }[]
  ending_direction?: string
}

export interface RecommendResponse {
  run: RunView
  options: ArchitectureOption[]
  story_bible_v0: StoryBibleV0
  structured: boolean
  parse_error: string | null
  raw_text: string
}

export interface Architecture {
  id: string
  tool_ref: string | null
  logline: string | null
  theme: string | null
  premise: string | null
  ending_direction: string | null
  locked: boolean
}

export interface Act {
  id: string
  seq: number
  name: string
  purpose: string | null
  target_word_ratio: number | null
  summary: string | null
}

export interface AdoptPayload {
  tool_ref?: string
  logline?: string
  theme?: string
  premise?: string
  ending_direction?: string
  acts: { seq: number; name: string; purpose?: string; target_word_ratio?: number }[]
}

export interface AgentVersion {
  id: string
  version_no: number
  system_prompt: string
  model_binding_json: Record<string, unknown>
  param_profile: string
  context_slots_json: string[]
  output_schema_json: Record<string, unknown> | null
  skills_json: string[]
  trigger_mode: string
  note: string
}

export interface AgentPresetStatus {
  key: string | null
  update_available: boolean
  can_restore: boolean
  up_to_date: boolean
}

export interface Agent {
  id: string
  name: string
  role_label: string
  color: string
  task_type: string
  enabled: boolean
  builtin: boolean
  preset: AgentPresetStatus
  current_version: AgentVersion | null
}

export interface Tool {
  id: string
  key: string
  category: string
  name: string
  description: string
  definition: { slots?: { key: string; label: string; hint?: string }[] }
  checklist: string[]
}

export interface ProviderView {
  id: string
  name: string
  kind: string
  base_url: string
  api_key_masked: string
  enabled: boolean
  priority: number
}

export interface Settings {
  context_token_budget: number
  default_params: { temperature: number; max_tokens: number }
  model_routing: Record<string, unknown>
  default_model?: string | null
  budget_alert: number | null
  request_timeout_seconds: number
}

export interface CostSummary {
  runs: number
  prompt_tokens: number
  completion_tokens: number
  cost_estimate: number
  unpriced_runs: number
  by_agent: CostBreakdown[]
  by_task: CostBreakdown[]
}

export interface CostBreakdown {
  runs: number
  prompt_tokens: number
  completion_tokens: number
  cost_estimate: number
  unpriced_runs: number
  agent_id?: string
  name?: string
  task_type?: string
  label?: string
}

export interface ModelPrice {
  id: string
  provider_id: string
  model: string
  input_price: number
  output_price: number
  currency: string
}

export interface SlotSpec {
  key: string
  label: string
  priority: number
  over_budget: 'never' | 'summarize' | 'drop'
}

export interface EntryTypeOption {
  key: string
  label: string
}

export interface EntryTypesResponse {
  types: EntryTypeOption[]
  hardness: EntryTypeOption[]
  character_fields: { key: string; label: string; multiline: boolean }[]
}

export interface SettingEntry {
  id: string
  project_id: string
  type: string
  name: string
  aliases: string[]
  tags: string[]
  summary: string
  description: string
  hardness: string | null
  source_run_id: string | null
  locked?: boolean
  appearance: string | null
  personality: string | null
  desire: string | null
  fear: string | null
  arc_type: string | null
  abilities: string | null
  speech_style: string | null
  current_state: string | null
  created_at: string
}

export interface EntryRelation {
  id: string
  project_id: string
  from_id: string
  to_id: string
  kind: string
  strength: number | null
  note: string
}

export interface TermRow {
  entry_id: string
  entry_name: string
  type: string
  form: string
  is_primary: boolean
}

export interface TimelineEvent {
  id: string
  project_id: string
  title: string
  story_time: string
  description: string
  participants: string[]
  location_id: string | null
  order_index: number
  created_at: string
}

export interface SuggestedEntry {
  type?: string
  name?: string
  aliases?: string[]
  summary?: string
  description?: string
  hardness?: string | null
  appearance?: string | null
  personality?: string | null
  desire?: string | null
  fear?: string | null
  arc_type?: string | null
  abilities?: string | null
  speech_style?: string | null
  current_state?: string | null
}

export interface SuggestResponse {
  run: RunView
  entries: SuggestedEntry[]
  open_questions: string[]
  structured: boolean
  parse_error: string | null
  raw_text: string
}

export interface ChapterStatusOption {
  key: string
  label: string
}

export interface ChapterTypesResponse {
  statuses: ChapterStatusOption[]
}

export interface SceneNode {
  id: string
  chapter_id: string
  seq: number
  goal: string
  conflict: string
  turn: string
  characters: string[]
  location_id: string | null
  story_time: string
  pov: string
  target_words_min: number | null
  target_words_max: number | null
  status: string
  source_run_id: string | null
  locked?: boolean
  has_body: boolean
  foreshadows: {
    plants: { id: string; name: string }[]
    pays: { id: string; name: string }[]
    actual_pays: { id: string; name: string }[]
  }
}

export interface ForeshadowSummary {
  total: number
  planned: number
  planted: number
  paid: number
  dropped: number
  rate: number
}

export interface LogicChainItem {
  paragraph: number
  sentence: string
  kind: string
  kind_label: string
  marker: string
}

export interface LogicChainResponse {
  chain: LogicChainItem[]
  summary: { total: number; cause: number; turn: number; reveal: number }
  reason: string
  // 正文段数：图形要按它铺出空列，才能看出「这一段没有逻辑链」。
  paragraphs: number
}

export type CausalBreak = 'missing_goal' | 'missing_turn' | 'causality_issue'

export interface CausalIssue {
  id: string
  layer: string
  layer_label: string
  severity: string
  title: string
}

export interface CausalScene {
  id: string
  seq: number
  label: string
  goal: string
  turn: string
  status: string
  locked: boolean
  // 结构断点与已报过的因果问题分开给：前者作者自己能补，后者要去处理面板看。
  breaks: CausalBreak[]
  issues: CausalIssue[]
}

export interface CausalChapter {
  id: string
  label: string
  volume_label: string
  scenes: CausalScene[]
}

export interface CausalMapData {
  chapters: CausalChapter[]
  totals: { scenes: number; breaks: number; chapters: number }
  // false = 从没跑过场景卡阶段的逻辑自检，图里只有结构断点。
  logic_checked: boolean
}

export interface SettingLoadTerm {
  entry_id: string
  name: string
  form: string
}

export interface SettingLoadChapter {
  id: string
  label: string
  volume_label: string
  // false = 这一章还没有已采纳正文；此时 new_count / density 一定是 0，
  // 但界面上不能画成 0 柱 —— 「还没写」不是「没投放」。
  has_body: boolean
  chars: number
  new_terms: SettingLoadTerm[]
  new_count: number
  mentions: number
  density: number
}

export interface SettingLoadTotals {
  entries: number
  delivered: number
  never_seen: number
  // 同一个 form（名字或别名）对应多个条目的处数；命中归属由后端裁定。
  ambiguities: number
}

export interface SettingLoadData {
  chapters: SettingLoadChapter[]
  totals: SettingLoadTotals
  // 非空 = 曲线没有可比的意义（没有条目 / 没有正文），直接用后端的文案做空态。
  reason: string
}

/** 性格漂移里的一格：某人某一章手记的一行状态（`changed` 由后端判定）。 */
export interface CharacterDriftCell {
  chapter_id: string
  label: string
  note: string
  // 与该人物的**上一条**记录比较（不是与上一章）；首条恒 false。
  changed: boolean
}

export interface CharacterDriftRow {
  entry_id: string
  name: string
  // 只含有记录的章；前端按 `chapters` 对齐后缺格留空。
  cells: CharacterDriftCell[]
  changes: number
  recorded: number
}

export interface CharacterDriftTotals {
  characters: number
  changes: number
  /** 只有一条记录的人数 —— 看不出漂移，顶部汇总要点出来。 */
  sparse: number
}

export interface CharacterDriftData {
  // 只列有记录的人物；没记过的人不占一行空白。
  characters: CharacterDriftRow[]
  // 全项目章列表（卷序 → 章序），与有无记录无关：它负责给表格对齐列。
  // 两卷都可能有「第1章 雨夜」，多卷时靠 `volume_label` 区分（缺了也能用）。
  chapters: { id: string; label: string; volume_label?: string }[]
  totals: CharacterDriftTotals
  // 非空 = 没东西可画（无人物 / 无记录），直接用后端的文案做空态。
  reason: string
}

/** PUT 的返回体。界面不用它拼格子（保存后整本重取），只当作写入回执。 */
export interface CharacterStateRecord {
  chapter_id: string
  entry_id: string
  note: string
  created_at: string
  updated_at: string
}

export interface Foreshadow {
  id: string
  project_id: string
  name: string
  note: string
  plant_scene_id: string | null
  plan_pay_scene_id: string | null
  actual_pay_scene_id: string | null
  status: string
  effective_status?: string
  status_is_derived?: boolean
  status_is_legacy?: boolean
  status_label?: string
  source_run_id: string | null
}

export interface ChapterNode {
  id: string
  volume_id: string
  seq: number
  title: string
  pov: string
  target_words: number | null
  emotional_tone: string
  lines: string[]
  hook: string
  summary: string
  conflict_level: number | null
  dialogue_ratio: number | null
  hook_strength: number | null
  status: string
  source_run_id: string | null
  locked?: boolean
  scenes: SceneNode[]
}

export interface VolumeNode {
  id: string
  project_id: string
  seq: number
  name: string
  purpose: string
  summary: string
  act_seq: number | null
  target_words: number | null
  status: string
  source_run_id: string | null
  locked?: boolean
  chapters: ChapterNode[]
}

export type VolumeView = Omit<VolumeNode, 'chapters'>
export type ChapterView = Omit<ChapterNode, 'scenes'>

export interface PlanChapter {
  title: string
  pov: string
  target_words: number | null
  emotional_tone: string
  lines: string[]
  hook: string
  summary: string
  conflict_level: number | null
  dialogue_ratio: number | null
  hook_strength: number | null
  status: string
}

export interface PlanVolume {
  name: string
  purpose: string
  summary: string
  act_seq: number | null
  target_words: number | null
  status: string
  chapters: PlanChapter[]
}

export interface ChapterPlanResponse {
  run: RunView
  volumes: PlanVolume[]
  open_questions: string[]
  warnings: string[]
  structured: boolean
  parse_error: string | null
  raw_text: string
}

export interface PlanScene {
  goal: string
  conflict: string
  turn: string
  characters: string[]
  location: string
  story_time: string
  pov: string
  target_words_min: number | null
  target_words_max: number | null
  foreshadow_plants: string[]
  foreshadow_pays: string[]
}

export interface ScenePlanResponse {
  run: RunView
  scenes: PlanScene[]
  open_questions: string[]
  warnings: string[]
  structured: boolean
  parse_error: string | null
  raw_text: string
}

export interface SceneTextDraft {
  id: string
  content: string
  run_id: string | null
  updated_at: string
}

export interface RevisionSummary {
  id: string
  source: string
  run_id: string | null
  note: string
  chars: number
  created_at: string
  preview: string
}

export interface SceneTextState {
  scene_id: string
  body: string | null
  has_body: boolean
  word_count: number
  draft: SceneTextDraft | null
  revisions: RevisionSummary[]
}

export interface RevisionDetail {
  id: string
  source: string
  run_id: string | null
  note: string
  content: string
  created_at: string
}

export interface ContextSlotPreview {
  key: string
  label: string
  priority: number
  over_budget: string
  text: string | null
  estimated_tokens: number
}

export interface ContextPreview {
  agent: { id: string; name: string; version_no: number }
  token_budget: number
  estimated_tokens: number
  over_budget: boolean
  slots: ContextSlotPreview[]
  trimmed: Record<string, string>
}

export type AuditResolution = 'story' | 'setting' | 'character' | 'exception'

export interface AuditIssue {
  id: string
  source: string
  source_label: string
  check_type?: string
  kind: string
  kind_label: string
  layer?: string | null
  layer_label?: string | null
  stage?: string
  severity: string
  severity_label: string
  quote: string
  rule_ref: string
  explanation: string
  reader_impact: string
  options: string[]
  target_entry_id: string | null
  target_entry_name: string | null
  status: string
  resolution: string | null
  created_at: string
}

export interface AuditResult {
  run_id: string | null
  issues: AuditIssue[]
  suppressed: number
  llm_status: 'ok' | 'skipped' | 'unstructured' | 'error'
  warning: string
}

export interface AuditView {
  issues: AuditIssue[]
  last_audited_at: string | null
}

export type LogicStage = 'plan' | 'text'

export interface LogicCheckResult {
  stage: string
  run_id: string | null
  issues: AuditIssue[]
  suppressed: number
  llm_status: 'ok' | 'skipped' | 'unstructured' | 'error'
  warning: string
}

export interface LogicCheckView {
  stage: string
  issues: AuditIssue[]
  last_checked_at: string | null
}

export interface WritebackCharacterCandidate {
  entry_id: string
  name: string
  current_state: string
  evidence: string
}

export interface WritebackForeshadowCandidate {
  foreshadow_id: string
  name: string
  evidence: string
}

export interface WritebackSuggestion {
  run_id: string | null
  llm_status: 'ok' | 'skipped' | 'unstructured' | 'error'
  warning: string
  chapter_summary: string
  character_updates: WritebackCharacterCandidate[]
  foreshadow_pays: WritebackForeshadowCandidate[]
  open_questions: string[]
  warnings: string[]
}

export interface WritebackApplyPayload {
  chapter_summary?: string
  character_updates: { entry_id: string; current_state: string }[]
  foreshadow_pays: { foreshadow_id: string }[]
}

export interface WritebackApplyResult {
  chapter_summary: string
  character_updates: { entry_id: string; name: string; current_state: string }[]
  foreshadow_pays: {
    foreshadow_id: string
    name: string
    actual_pay_scene_id: string
  }[]
}

export interface BatchFailure {
  scene_id: string
  message: string
}

export interface BatchJob {
  id: string
  project_id: string
  scope_type: 'chapter' | 'volume'
  scope_id: string
  status: 'running' | 'paused' | 'completed' | 'cancelled' | 'failed'
  cursor: number
  total: number
  current_scene_id: string | null
  failures: BatchFailure[]
  created_at: string
  updated_at: string
}

export interface ExportReport {
  project_id: string
  project_name: string
  total_words: number
  volumes: number
  chapters: number
  scenes: number
  scenes_without_body: { volume: string; chapter: string; scene: number; goal: string }[]
  unrecovered_foreshadows: {
    name: string
    planted: boolean
    planted_at: string
    planned_pay_at: string
  }[]
  open_audit_issues: number
  open_logic_issues: number
  locked_counts?: {
    architecture: number
    entries: number
    volumes: number
    chapters: number
    scenes: number
  }
  review_marks?: number
  exportable: boolean
}

export interface GenerationRunEvent {
  run_id: string
  model: string
  agent: string
  estimated_tokens: number
  trimmed: Record<string, string>
}

export interface GenerationDoneEvent {
  run_id: string
  status: string
  prompt_tokens: number
  completion_tokens: number
  cost_estimate: number
  duration_ms: number
  chars: number
  draft_id: string | null
}

export interface GenerationErrorEvent {
  run_id: string
  kind: string
  message: string
  chars: number
}

export interface GenerationHandlers {
  onRun?: (data: GenerationRunEvent) => void
  onDelta?: (text: string) => void
  onDone?: (data: GenerationDoneEvent) => void
  onError?: (data: GenerationErrorEvent) => void
}

export async function streamSceneGeneration(
  sceneId: string,
  handlers: GenerationHandlers,
  signal: AbortSignal,
  branchId?: string,
): Promise<void> {
  // 分支与主版走同一条流式链路，只是 URL 不同 —— 事件与解析完全一样。
  const url = branchId
    ? `/api/branches/${branchId}/generate`
    : `/api/scenes/${sceneId}/generate`
  const response = await fetch(url, {
    method: 'POST',
    signal,
  })
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(detail.detail ?? `请求失败：${response.status}`)
  }
  if (!response.body) throw new Error('当前环境不支持流式读取')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  const parser = createSseParser()

  const dispatch = (event: string, data: string) => {
    let parsed: unknown
    try {
      parsed = JSON.parse(data)
    } catch {
      return
    }
    if (event === 'run') handlers.onRun?.(parsed as GenerationRunEvent)
    else if (event === 'delta') {
      const payload = parsed as { text?: string }
      if (payload.text) handlers.onDelta?.(payload.text)
    } else if (event === 'done') handlers.onDone?.(parsed as GenerationDoneEvent)
    else if (event === 'error') handlers.onError?.(parsed as GenerationErrorEvent)
  }

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    for (const event of parser.push(decoder.decode(value, { stream: true }))) {
      dispatch(event.event, event.data)
    }
  }
  const tail = decoder.decode()
  if (tail) {
    for (const event of parser.push(tail)) dispatch(event.event, event.data)
  }
}

export interface PipelineNodeSpec {
  id: string
  seq: number
  name: string
  task_type: string
  agent_id: string | null
  checkpoint: boolean
  enabled: boolean
}

export interface Pipeline {
  id: string
  project_id: string
  policy: string
  nodes: PipelineNodeSpec[]
  node_types: { task_type: string; label: string }[]
  policies: { value: string; label: string }[]
}

export interface PipelineRunNode {
  id: string
  seq: number
  name: string
  task_type: string
  agent_id: string | null
  status: string
  generation_run_id: string | null
  summary: Record<string, unknown>
  message: string
}

export interface PipelineRun {
  id: string
  project_id: string
  policy: string
  status: string
  cursor: number
  message: string
  nodes: PipelineRunNode[]
  created_at: string
}

export interface LockTargetOption {
  key: string
  label: string
}

export interface LockTargetsResponse {
  targets: LockTargetOption[]
}

export interface LockState {
  target_type: string
  target_id: string
  own_locked: boolean
  locked: boolean
  source: string | null
  source_id: string | null
  label: string
}

export interface ImpactItem {
  type: string
  id: string
  label: string
  detail: string
  locked: boolean
  locked_by?: string
  path: string
}

export interface ImpactGroup {
  key: string
  label: string
  total: number
  locked: number
  items: ImpactItem[]
  note: string
}

export interface ImpactReport {
  project_id: string
  target: {
    type: string
    type_label: string
    id: string
    label: string
    locked: boolean
  }
  groups: ImpactGroup[]
  totals: { all: number; locked: number }
}

/** 一条待勾选的修订建议；`index` 就是应用时 `accepted` 里的那个下标。 */
export interface RevisionSuggestion {
  index: number
  target_type: string
  target_id: string
  /** 会改哪个对象，例如「第1卷 第3章 场景2」。 */
  target_label: string
  field: string
  /** 字段的中文名，例如「目标」。 */
  field_label: string
  /** 生成时服务端现取的现值（模型给的 before 不被采信）。 */
  before: string
  after: string
  reason: string
}

export interface RevisionResult {
  run_id: string | null
  llm_status: 'ok' | 'skipped' | 'error'
  suggestions: RevisionSuggestion[]
  /** 对不上对象、字段不可改或超过上限而被丢弃的条数。 */
  dropped: number
  /** 失败或空态的**中文**说明；界面直接显示它，不解析任何 JSON。 */
  warning: string
}

export interface RevisionAppliedRow {
  index: number
  target_label: string
  field: string
  field_label: string
}

export interface RevisionSkippedRow {
  index: number
  /** 「下标无效」「已锁定」「现值已变化」「已应用」等中文原因。 */
  reason: string
}

export interface RevisionApplyResult {
  applied: RevisionAppliedRow[]
  skipped: RevisionSkippedRow[]
}

export interface ReviewMark {
  id: string
  project_id: string
  target_type: string
  type_label: string
  target_id: string
  label: string
  reason: string
  path: string
  created_at: string
}

export interface SnapshotView {
  id: string
  project_id: string
  name: string
  note: string
  volumes: number
  chapters: number
  scenes: number
  words: number
  auto: boolean
  created_at: string
}

export interface SnapshotDetail extends SnapshotView {
  preview: {
    entries: number
    relations: number
    timeline: number
    foreshadows: number
    has_architecture: boolean
    volume_names: string[]
  }
}

export interface ChangeRow {
  id: string
  project_id: string
  target_type: string
  target_type_label: string
  target_id: string
  target_label: string
  action: string
  action_label: string
  source: string
  source_label: string
  summary: string
  created_at: string
}

export interface ChangeList {
  changes: ChangeRow[]
  target_types: { key: string; label: string }[]
}

export interface BranchSummary {
  id: string
  scene_id: string
  name: string
  /** 派生自哪条分支；根分支为 null。 */
  parent_id: string | null
  /** 根 = 1，最多 3 层。由服务层沿父链算好下发。 */
  depth: number
  note: string
  chars: number
  has_draft: boolean
  created_at: string
  updated_at: string
}

export interface BranchDetail extends BranchSummary {
  content: string
  draft: { content: string; run_id: string | null } | null
}

export interface BranchRevisionRow {
  id: string
  source: string
  note: string
  chars: number
  created_at: string
  preview: string
}

/** A/B 并排里的一版。`label` 是库名（`A/B · A`），两栏标题用 `side`。 */
export interface AbBranch {
  id: string
  label: string
  side: string
  has_draft: boolean
  chars: number
}

/** 该场景**最近一组**未处理的 A/B；没有组时 `group` 为 null、`branches` 为空。 */
export interface AbSession {
  group: string | null
  branches: AbBranch[]
}

export interface BookChapter {
  id: string
  seq: number
  title: string
  word_count: number
  /** 有没有已采纳正文。没有的章阅读器要标「未写」而不是藏起来。 */
  has_body: boolean
  /** Markdown 原文；没有正文时为空串。 */
  content: string
}

export interface BookVolume {
  id: string
  seq: number
  name: string
  chapters: BookChapter[]
}

export interface BookResponse {
  project_id: string
  project_name: string
  total_words: number
  written_chapters: number
  total_chapters: number
  /** 空章也在里面 —— 作者要看得见这本书还差哪几章。 */
  volumes: BookVolume[]
}
