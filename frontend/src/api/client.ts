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

  listRuns: (projectId?: string) =>
    request<RunView[]>(`/api/runs${projectId ? `?project_id=${projectId}` : ''}`),
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
}

export interface Project {
  id: string
  name: string
  genre: string | null
  tone: string | null
  target_length: number | null
  logic_check_level: string
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
  rendered_prompt: string
  raw_output: string
  parsed_json: Record<string, unknown> | null
  structured: boolean
  parse_error: string | null
  prompt_tokens: number
  completion_tokens: number
  cost_estimate: number
  duration_ms: number
  status: string
  error: { kind: string; message: string } | null
  trimmed: Record<string, string>
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
  model_routing: Record<string, string>
  budget_alert: number | null
  request_timeout_seconds: number
}

export interface CostSummary {
  runs: number
  prompt_tokens: number
  completion_tokens: number
  cost_estimate: number
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
  has_body: boolean
  foreshadows: { plants: { id: string; name: string }[]; pays: { id: string; name: string }[] }
}

export interface Foreshadow {
  id: string
  project_id: string
  name: string
  note: string
  plant_scene_id: string | null
  plan_pay_scene_id: string | null
  status: string
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
): Promise<void> {
  const response = await fetch(`/api/scenes/${sceneId}/generate`, {
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
