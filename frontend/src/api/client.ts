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
