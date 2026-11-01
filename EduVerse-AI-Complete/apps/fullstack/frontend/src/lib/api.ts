import type {
  AnswerResult, AuthResponse, Card, Chat, ChatMessage, Concept, Dashboard, DashboardStats, DueCounts, Excerpt, Folder,
  Job, KnowledgeGapSummary, Note, QuizDone, QuizQuestion, QuizResults, ReviewResult, RevisionRecommendation, RevisionSession, SearchHit,
  Segment, SettingsPayload, Source, SourceDetail, TopicGap, Usage, User,
  LlmStatus,
} from './types'

const BASE = '/api/v1'

/** An API error carrying the server's actionable message rather than a status code. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly kind: string = 'Error',
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      signal: init?.signal ?? AbortSignal.timeout(path.startsWith('/quiz/') || path.startsWith('/chat/') ? 360000 : 30000),
      headers: {
        ...(typeof localStorage !== 'undefined' && localStorage.getItem('eduverse_token')
          ? { Authorization: `Bearer ${localStorage.getItem('eduverse_token')}` }
          : {}),
        ...(init?.body instanceof FormData || init?.body instanceof Blob
          ? init?.headers
          : { 'Content-Type': 'application/json', ...(init?.headers ?? {}) }),
      },
    })
  } catch {
    throw new ApiError(
      'Could not reach the quicklearn server. Is it still running?',
      0,
      'NetworkError',
    )
  }

  if (!response.ok) {
    if (response.status === 401 && !path.startsWith('/auth/')) {
      window.dispatchEvent(new Event('eduverse:unauthorized'))
    }
    // The backend's error taxonomy puts a human-readable message in `message`; surface that
    // rather than "Request failed with status 502".
    let message = `Request failed (${response.status})`
    let kind = 'Error'
    try {
      const body = await response.json()
      if (typeof body?.message === 'string') message = body.message
      else if (typeof body?.detail === 'string') message = body.detail
      if (typeof body?.error === 'string') kind = body.error
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(message, response.status, kind)
  }

  if (response.status === 204) return undefined as T
  const contentType = response.headers.get('content-type') ?? ''
  if (!contentType.includes('application/json')) return (await response.text()) as T
  return (await response.json()) as T
}

const get = <T>(path: string) => request<T>(path)
const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })
const patch = <T>(path: string, body: unknown) =>
  request<T>(path, { method: 'PATCH', body: JSON.stringify(body) })
const put = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'PUT', body: body === undefined ? undefined : JSON.stringify(body) })
const del = <T>(path: string) => request<T>(path, { method: 'DELETE' })

const qs = (params: Record<string, string | number | boolean | undefined | null>) => {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') search.set(key, String(value))
  }
  const encoded = search.toString()
  return encoded ? `?${encoded}` : ''
}

export const api = {
  // ---------------------------------------------------------------- sources
  listSources: (params: { folder_id?: number; status?: string; tag?: string; q?: string } = {}) =>
    get<{ sources: Source[]; total: number }>(`/sources${qs(params)}`),
  getSource: (id: number) => get<SourceDetail>(`/sources/${id}`),
  updateSource: (id: number, body: { title?: string; folder_id?: number | null; tags?: string[] }) =>
    patch<Source>(`/sources/${id}`, body),
  deleteSource: (id: number) => del<{ deleted: boolean }>(`/sources/${id}`),
  getSegments: (id: number) => get<{ segments: Segment[] }>(`/sources/${id}/segments`),
  getTranscript: (id: number) =>
    get<{ segments: Segment[]; text: string }>(`/sources/${id}/transcript`),
  getConcepts: (id: number) => get<{ concepts: Concept[] }>(`/sources/${id}/concepts`),
  addUrl: (url: string, folder_id?: number | null) =>
    post<{ source_id: number; job_id: number; kind: string }>('/sources/url', { url, folder_id }),
  addText: (title: string, content: string, folder_id?: number | null) =>
    post<{ source_id: number; job_id: number }>('/sources/text', { title, content, folder_id }),
  regenerate: (
    id: number,
    body: { target: 'notes' | 'concepts' | 'cards' | 'quiz' | 'all'; style?: string; count?: number },
  ) => post<{ job_ids: number[]; note_was_edited: boolean }>(`/sources/${id}/regenerate`, body),
  reprocess: (id: number) => post<{ job_id: number }>(`/sources/${id}/reprocess`),
  mediaUrl: (id: number) => {
    return `${BASE}/sources/${id}/media`
  },
  audioUrl: (id: number) => {
    return `${BASE}/sources/${id}/audio`
  },

  /** Upload with progress. Uses XHR because fetch cannot report upload progress. */
  upload: (
    file: File,
    opts: { folderId?: number | null; onProgress?: (percent: number) => void } = {},
  ) =>
    new Promise<{ source_id: number; job_id: number }>((resolve, reject) => {
      const form = new FormData()
      form.append('file', file)
      if (opts.folderId != null) form.append('folder_id', String(opts.folderId))

      const xhr = new XMLHttpRequest()
      xhr.open('POST', `${BASE}/sources/upload`)
      const token = typeof localStorage !== 'undefined' ? localStorage.getItem('eduverse_token') : null
      if (token) {
        xhr.setRequestHeader('Authorization', `Bearer ${token}`)
      }
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) opts.onProgress?.((event.loaded / event.total) * 100)
      }
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.responseText))
        } else {
          let message = `Upload failed (${xhr.status})`
          try {
            message = JSON.parse(xhr.responseText).message ?? message
          } catch { /* non-JSON */ }
          reject(new ApiError(message, xhr.status))
        }
      }
      xhr.onerror = () => reject(new ApiError('Upload failed — connection lost.', 0))
      xhr.send(form)
    }),

  // ---------------------------------------------------------------- notes
  getNote: (id: number) => get<Note>(`/notes/${id}`),
  saveNote: (id: number, doc: unknown) => patch<Note>(`/notes/${id}`, { doc }),
  renameNote: (id: number, title: string) => patch<Note>(`/notes/${id}`, { title }),
  noteSegments: (id: number) => get<{ segments: Segment[] }>(`/notes/${id}/segments`),
  aiAction: (id: number, action: string, selection: string, context = '') =>
    post<{ action: string; result: string }>(`/notes/${id}/ai-action`, { action, selection, context }),
  makeCardsFromSelection: (id: number, selection: string) =>
    post<{ created: number; card_ids: number[] }>(`/notes/${id}/make-cards`, {
      action: 'key_points',
      selection,
    }),
  exportUrl: (id: number, format: string) => `${BASE}/notes/${id}/export?format=${format}`,
  blockSegments: (blockId: number) => get<{ segments: Segment[] }>(`/blocks/${blockId}/segments`),

  // ---------------------------------------------------------------- cards
  dueCards: (params: { folder_id?: number; source_id?: number; limit?: number } = {}) =>
    get<{ cards: Card[]; counts: DueCounts }>(`/cards/due${qs(params)}`),
  cardCounts: (folder_id?: number) => get<DueCounts>(`/cards/counts${qs({ folder_id })}`),
  reviewCard: (id: number, rating: number, duration_ms?: number) =>
    post<ReviewResult>(`/cards/${id}/review`, { rating, duration_ms }),
  undoReview: (id: number) => post<{ undone: boolean }>(`/cards/${id}/undo`),
  listCards: (source_id?: number) => get<{ cards: Card[] }>(`/cards${qs({ source_id })}`),
  editCard: (id: number, body: { front?: string; back?: string; suspended?: boolean }) =>
    patch<Card>(`/cards/${id}`, body),
  deleteCard: (id: number) => del<{ deleted: boolean }>(`/cards/${id}`),
  forecast: (days = 30, folder_id?: number) =>
    get<{ forecast: { date: string; count: number; offset: number }[] }>(
      `/cards/forecast${qs({ days, folder_id })}`,
    ),
  cardStats: () => get<Dashboard['stats']>('/cards/stats'),
  optimizeFsrs: () => post<{ parameters: number[]; count: number }>('/cards/optimize-fsrs'),
  importCards: async (file: File, folderId?: number | null) => {
    const form = new FormData()
    form.append('file', file)
    if (folderId != null) form.append('folder_id', String(folderId))
    return request<{ imported: number; skipped: number; source_id: number }>('/cards/import', {
      method: 'POST',
      body: form,
    })
  },
  exportAnki: async (body: { source_ids?: number[]; folder_id?: number | null; deck_name?: string }) => {
    const response = await fetch(`${BASE}/cards/export/anki`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!response.ok) {
      let message = 'Export failed.'
      try {
        message = (await response.json()).message ?? message
      } catch { /* non-JSON */ }
      throw new ApiError(message, response.status)
    }
    return { blob: await response.blob(), count: response.headers.get('X-Card-Count') }
  },

  // ---------------------------------------------------------------- quiz
  createQuizSession: (body: {
    mode: 'practice' | 'test' | 'cumulative'
    source_ids?: number[]
    folder_id?: number | null
    length?: number | null
  }) => post<{ session_id: number; mode: string; length: number | null; concepts: number }>(
    '/quiz/session',
    body,
  ),
  nextQuestion: (sessionId: number) =>
    get<QuizQuestion | QuizDone>(`/quiz/session/${sessionId}/next`),
  answerQuestion: (sessionId: number, item_id: number, response: string) =>
    post<AnswerResult>(`/quiz/session/${sessionId}/answer`, { item_id, response }),
  quizResults: (sessionId: number) => get<QuizResults>(`/quiz/session/${sessionId}/results`),
  resetMastery: (source_id: number) => post<{ reset: number }>(`/quiz/reset-mastery${qs({ source_id })}`),

  // ---------------------------------------------------------------- chat
  listChats: () => get<{ chats: Chat[] }>('/chat'),
  createChat: (scope_type: 'source' | 'folder' | 'global', scope_id?: number | null, title = '') =>
    post<Chat>('/chat', { scope_type, scope_id, title }),
  chatMessages: (id: number) => get<{ chat: Chat; messages: ChatMessage[] }>(`/chat/${id}/messages`),
  sendChatMessage: (id: number, content: string) =>
    post<ChatMessage & { excerpts: Excerpt[] }>(`/chat/${id}/message`, { content }),
  deleteChat: (id: number) => del<{ deleted: boolean }>(`/chat/${id}`),
  resolveCitations: (ids: number[]) =>
    get<{ segments: Segment[] }>(`/chat/citations${qs({ ids: ids.join(',') })}`),

  // ---------------------------------------------------------------- library
  listFolders: () => get<{ folders: Folder[]; unfiled_count: number }>('/folders'),
  createFolder: (name: string, parent_id?: number | null, color?: string) =>
    post<Folder>('/folders', { name, parent_id, color }),
  updateFolder: (id: number, body: { name?: string; parent_id?: number | null; color?: string }) =>
    patch<Folder>(`/folders/${id}`, body),
  deleteFolder: (id: number, deleteSources = false) =>
    del<{ deleted: boolean }>(`/folders/${id}${qs({ delete_sources: deleteSources })}`),
  listTags: () => get<{ tags: { id: number; name: string; color: string | null }[] }>('/tags'),
  search: (q: string, semantic = false) =>
    get<{ query: string; results: SearchHit[]; semantic: boolean }>(`/search${qs({ q, semantic })}`),
  dashboard: () => get<Dashboard>('/dashboard'),

  // ---------------------------------------------------------------- system
  jobs: (activeOnly = false) => get<{ jobs: Job[] }>(`/jobs${qs({ active_only: activeOnly })}`),
  job: (id: number) => get<Job>(`/jobs/${id}`),
  cancelJob: (id: number) => post<{ cancelled: boolean }>(`/jobs/${id}/cancel`),
  retryJob: (id: number) => post<{ retried: boolean }>(`/jobs/${id}/retry`),
  settings: () => get<SettingsPayload>('/settings'),
  saveSettings: (values: Record<string, unknown>) =>
    patch<SettingsPayload>('/settings', { values }),
  testProvider: (body: { provider: string; kind: string; api_key?: string; base_url?: string }) =>
    post<{ ok: boolean; message: string; models: { id: string; name: string; context_window: number }[] }>(
      '/settings/test-provider',
      body,
    ),
  models: (kind: string, provider?: string) =>
    get<{ kind: string; providers: Record<string, { ok: boolean; message?: string; models: { id: string; name: string }[] }> }>(
      `/settings/models${qs({ kind, provider })}`,
    ),
  usage: () => get<Usage>('/usage'),
  estimate: (body: { text?: string; tokens?: number; audio_seconds?: number }) =>
    post<{ estimated_usd: number; known: boolean; breakdown: Record<string, { usd: number; known: boolean }> }>(
      '/usage/estimate',
      body,
    ),
  health: () => get<Record<string, unknown>>('/health'),
  healthLlm: () => get<LlmStatus>('/health/llm'),

  // ---------------------------------------------------------------- eduverse auth & learning
  login: (body: { username: string; password: string }) => post<AuthResponse>('/auth/login', body),
  register: (body: { email: string; username: string; password: string; full_name?: string }) =>
    post<AuthResponse>('/auth/register', body),
  logout: () => post<{ message: string }>('/auth/logout', {}),
  changePassword: (body: { current_password: string; new_password: string }) =>
    post<{ message: string }>('/auth/change-password', body),
  forgotPassword: (email: string) => post<{ message: string }>('/auth/forgot-password', { email }),
  resetPassword: (body: { token: string; new_password: string }) =>
    post<{ message: string }>('/auth/reset-password', body),
  me: () => get<User>('/auth/me'),
  dashboardStats: () => get<DashboardStats>('/dashboard/stats'),
  knowledgeGapSummary: () => get<KnowledgeGapSummary>('/knowledge-gap/summary'),
  knowledgeGapTopics: () => get<TopicGap[]>('/knowledge-gap/topics'),
  revisionRecommendations: () => get<RevisionRecommendation[]>('/revision-planner/recommendations'),
  revisionSessions: (status?: string) => get<RevisionSession[]>(`/revision-planner/sessions${qs({ status })}`),
  scheduleRevisionSession: (body: {
    topic: string
    priority?: string
    recommended_duration_min?: number
    reason?: string
    source_id?: number | null
    concept_id?: number | null
    scheduled_date?: string
  }) => post<RevisionSession>('/revision-planner/schedule', body),
  updateRevisionSession: (id: number, body: { status?: string; notes?: string }) =>
    patch<RevisionSession>(`/revision-planner/sessions/${id}`, body),
  deleteRevisionSession: (id: number) => del<{ message: string }>(`/revision-planner/sessions/${id}`),

  // ---------------------------------------------------------------- podcasts
  listPodcasts: () => get<{ podcasts: any[] }>('/podcasts'),
  getPodcast: (id: number) => get<any>(`/podcasts/${id}`),
  createPodcast: (body: any) => post<{ podcast_id: number; job_id: number }>('/podcasts', body),
  deletePodcast: (id: number) => del<{ deleted: boolean }>(`/podcasts/${id}`),
  regeneratePodcast: (id: number) => post<{ job_id: number }>(`/podcasts/${id}/regenerate`, {}),
  podcastVoices: () => get<{ voices: any[]; error?: string }>('/podcasts/voices'),
  feedUrl: () => '/api/v1/podcasts/feed.xml',
  podcastAudioUrl: (id: number) => `/api/v1/podcasts/${id}/audio`,

  // ---------------------------------------------------------------- recordings
  unfinishedRecordings: () => get<{ recordings: any[] }>('/sources/recordings/unfinished'),
  startRecording: (title = '', folderId?: number) =>
    post<{ source_id: number; upload_token: string; warning?: string }>('/sources/record/start', { title, folder_id: folderId }),
  sendRecordingChunk: (token: string, chunk: Blob) => {
    return fetch('/api/v1/sources/record/chunk', {
      method: 'POST',
      body: chunk,
      headers: {
        'X-Upload-Token': token,
        ...(localStorage.getItem('eduverse_token') ? { Authorization: `Bearer ${localStorage.getItem('eduverse_token')}` } : {})
      }
    }).then(async r => {
      if (!r.ok) throw new Error('Chunk upload failed');
      return r.json();
    });
  },
  addMarker: (sourceId: number, positionMs: number) =>
    post<{ markers: any }>(`/sources/${sourceId}/marker`, { position_ms: positionMs }),
  stopRecording: (token: string) =>
    post<{ source_id: number; job_id: number }>('/sources/record/stop', { token }),
  processUnfinished: (sourceId: number) =>
    post<{ source_id: number; job_id: number }>(`/sources/${sourceId}/process-unfinished`, {}),
  discardUnfinished: (sourceId: number) =>
    del<{ deleted: boolean }>(`/sources/recordings/unfinished/${sourceId}`),

  // ---------------------------------------------------------------- academic intelligence
  listCourses: () => get<any[]>('/courses'),
  createCourse: (data: { code: string; name: string; semester?: string; academic_year?: string; description?: string; target_exam_date?: string }) =>
    post<any>('/courses', data),
  getCourse: (courseId: number) => get<any>(`/courses/${courseId}`),
  deleteCourse: (courseId: number) => del<any>(`/courses/${courseId}`),
  linkCourseMaterial: (courseId: number, data: { source_id: number; unit_id?: number }) =>
    post<any>(`/courses/${courseId}/materials`, data),

  getSyllabus: (courseId: number) => get<any>(`/courses/${courseId}/syllabus`),
  addUnit: (courseId: number, data: { unit_number: number; title: string; description?: string; weightage_percent?: number }) =>
    post<any>(`/courses/${courseId}/syllabus/units`, data),
  addTopic: (courseId: number, data: { unit_id: number; name: string; bloom_level?: string; importance_score?: number }) =>
    post<any>(`/courses/${courseId}/syllabus/topics`, data),
  deleteTopic: (courseId: number, topicId: number) =>
    del<any>(`/courses/${courseId}/syllabus/topics/${topicId}`),
  extractSyllabus: (courseId: number, data: { source_id?: number; raw_text?: string }) =>
    post<any>(`/courses/${courseId}/syllabus/extract`, data),

  listPapers: (courseId: number) => get<any[]>(`/courses/${courseId}/papers`),
  createPaper: (courseId: number, data: { title: string; exam_term?: string; exam_year?: number; total_marks?: number; duration_minutes?: number; source_id?: number }) =>
    post<any>(`/courses/${courseId}/papers`, data),
  getPaper: (courseId: number, paperId: number) => get<any>(`/courses/${courseId}/papers/${paperId}`),
  deletePaper: (courseId: number, paperId: number) => del<any>(`/courses/${courseId}/papers/${paperId}`),
  extractPaperQuestions: (courseId: number, data: { paper_id: number; source_id?: number; raw_text?: string }) =>
    post<any>(`/courses/${courseId}/papers/extract`, data),
  getPaperAnalytics: (courseId: number) => get<any>(`/courses/${courseId}/papers/analytics/overview`),

  generateSimulation: (courseId: number, data: { title?: string; max_score?: number; question_count?: number }) =>
    post<any>(`/simulator/courses/${courseId}/generate`, data),
  getSimulationSession: (sessionId: number) => get<any>(`/simulator/sessions/${sessionId}`),
  submitExam: (sessionId: number, answers: Array<{ question_id: number; student_answer: string }>) =>
    post<any>(`/simulator/sessions/${sessionId}/submit`, { answers }),
  gradeExam: (sessionId: number) => post<any>(`/simulator/sessions/${sessionId}/grade`, {}),
  getExamHistory: () => get<any[]>('/simulator/history'),

  getMasteryProfile: (courseId: number) => get<any>(`/adaptive/courses/${courseId}/mastery`),
  generateAdaptivePlan: (courseId: number, data: { title?: string; target_date?: string }) =>
    post<any>(`/adaptive/courses/${courseId}/plan`, data),
  getCurrentPlan: (courseId: number) => get<any>(`/adaptive/courses/${courseId}/plan`),
  toggleTask: (taskId: number) => post<any>(`/adaptive/tasks/${taskId}/toggle`, {}),
  remediateTask: (taskId: number, data: { action_type?: string; delta?: number }) =>
    post<any>(`/adaptive/tasks/${taskId}/remediate`, data),

  // ---------------------------------------------------------------- automation
  getAutomationJobs: (params?: { status?: string; job_type?: string; limit?: number }) =>
    get<any>(`/automation/jobs${params?.status ? `?status=${params.status}` : ''}`),
  getAutomationJobDetail: (jobId: number) => get<any>(`/automation/jobs/${jobId}`),
  retryAutomationJob: (jobId: number) => post<any>(`/automation/jobs/${jobId}/retry`, {}),
  cancelAutomationJob: (jobId: number) => post<any>(`/automation/jobs/${jobId}/cancel`, {}),
  getAutomationRules: () => get<any[]>('/automation/rules'),
  toggleAutomationRule: (ruleName: string, data: { is_enabled: boolean; config?: any }) =>
    put<any>(`/automation/rules/${ruleName}`, data),
  triggerAutomationWorkflow: (data: { event_name: string; payload?: any; course_id?: number }) =>
    post<any>('/automation/trigger', data),
  getAuditIssues: (status?: string) => get<any[]>(`/automation/audit${status ? `?status=${status}` : ''}`),
  resolveAuditIssue: (issueId: number, action?: string) =>
    post<any>(`/automation/audit/${issueId}/resolve${action ? `?action=${action}` : ''}`, {}),
  getNotifications: () => get<any[]>('/automation/notifications'),
  markNotificationRead: (id: number) => post<any>(`/automation/notifications/${id}/read`, {}),
  markAllNotificationsRead: () => post<any>('/automation/notifications/read-all', {}),
  getSystemHealth: () => get<any>('/automation/health'),
}
