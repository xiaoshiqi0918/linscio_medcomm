import axios from 'axios'

export const API_BASE = 'http://127.0.0.1:8765'

/** LLM / long-running MedPic calls (local models often exceed 30s) */
export const MEDPIC_LLM_TIMEOUT_MS = 180000

export const http = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

const AUTH_TOKEN_KEY = 'linscio_auth_token'
let _authToken: string | null = null
let _loginPromise: Promise<string> | null = null

export function setAuthToken(token: string | null) {
  _authToken = token
  try {
    if (token) window.localStorage.setItem(AUTH_TOKEN_KEY, token)
    else window.localStorage.removeItem(AUTH_TOKEN_KEY)
  } catch {
    // ignore
  }
}

export function getAuthToken(): string | null {
  if (_authToken != null) return _authToken
  try {
    _authToken = window.localStorage.getItem(AUTH_TOKEN_KEY)
  } catch {
    _authToken = null
  }
  return _authToken
}

async function getLocalApiKeyHeader(): Promise<Record<string, string>> {
  try {
    const electron = (typeof window !== 'undefined' && (window as any).electronAPI)
    if (electron?.getLocalApiKey) {
      const key = await electron.getLocalApiKey()
      if (key) return { 'X-Local-Api-Key': key }
    }
  } catch {
    // ignore
  }
  return {}
}

export async function getLocalApiKeyHeaderForFetch(): Promise<Record<string, string>> {
  return getLocalApiKeyHeader()
}

// 本机隔离：Electron 模式下添加 X-Local-Api-Key
http.interceptors.request.use(async (config) => {
  if (_authToken == null) {
    try {
      _authToken = window.localStorage.getItem(AUTH_TOKEN_KEY)
    } catch {
      _authToken = null
    }
  }

  const electron = (typeof window !== 'undefined' && (window as any).electronAPI)
  if (electron?.getLocalApiKey) {
    const key = await electron.getLocalApiKey()
    if (key) config.headers.set('X-Local-Api-Key', key)
  }

  // 统一会话：没有 token 时静默登录（兼容现有“无登录 UI”）
  if (!_authToken) {
    if (!_loginPromise) {
      const localHeader = await getLocalApiKeyHeader()
      const raw = axios.create({
        baseURL: API_BASE,
        timeout: 30000,
        headers: { 'Content-Type': 'application/json', ...localHeader },
      })
      _loginPromise = raw
        .post('/api/v1/auth/login', {})
        .then((res) => String(res.data?.token || ''))
        .finally(() => {
          _loginPromise = null
        })
    }
    const tk = await _loginPromise
    if (tk) {
      _authToken = tk
      try {
        window.localStorage.setItem(AUTH_TOKEN_KEY, tk)
      } catch {
        // ignore
      }
    }
  }
  if (_authToken) config.headers.set('Authorization', `Bearer ${_authToken}`)
  return config
})

http.interceptors.response.use(
  (resp) => resp,
  async (error) => {
    const status = error?.response?.status
    const cfg = error?.config as any
    if (status === 401 && cfg && !cfg.__retried) {
      cfg.__retried = true
      // token 可能过期/被清空：清掉并重新静默登录后重试一次
      setAuthToken(null)
      _authToken = null
      const localHeader = await getLocalApiKeyHeader()
      const raw = axios.create({
        baseURL: API_BASE,
        timeout: 30000,
        headers: { 'Content-Type': 'application/json', ...localHeader },
      })
      try {
        const res = await raw.post('/api/v1/auth/login', {})
        const tk = String(res.data?.token || '')
        if (tk) {
          setAuthToken(tk)
          _authToken = tk
          cfg.headers = cfg.headers || {}
          cfg.headers.Authorization = `Bearer ${tk}`
          return http.request(cfg)
        }
      } catch {
        // fall through
      }
    }
    return Promise.reject(error)
  }
)

/** 解析 axios 错误信息（含 responseType: blob 时 JSON 错误体会落在 Blob 中） */
export async function axiosErrorDetail(error: unknown): Promise<string> {
  const err = error as { message?: string; response?: { status?: number; data?: unknown } }
  const fallback = err?.message || '请求失败'
  const res = err?.response
  if (!res) return fallback

  const pickDetail = (body: unknown): string | null => {
    if (body == null) return null
    if (typeof body === 'string') return body
    if (typeof body === 'object' && body !== null && 'detail' in body) {
      const det = (body as { detail: unknown }).detail
      if (typeof det === 'string') return det
      if (Array.isArray(det))
        return det.map((x: { msg?: string }) => x?.msg || JSON.stringify(x)).join('；')
      if (det != null) return String(det)
    }
    return null
  }

  const { data, status } = res
  if (data instanceof Blob) {
    try {
      const text = await data.text()
      try {
        const parsed = JSON.parse(text) as unknown
        const d = pickDetail(parsed)
        if (d) return d
      } catch {
        if (text?.trim()) return text.slice(0, 240)
      }
    } catch {
      return fallback
    }
  } else {
    const d = pickDetail(data)
    if (d) return d
  }

  return status != null ? `${fallback}（HTTP ${status}）` : fallback
}

// API 模块
export const api = {
  system: {
    testApiKey: (apiKey?: string) =>
      http.post("/api/v1/system/apikey/test", { api_key: apiKey || "" }),
    getLlmModels: () =>
      http.get<{ models: Array<{ id: string; name: string; provider: string }> }>("/api/v1/system/llm-models"),
    getOllamaStatus: () => http.get<{ available: boolean }>("/api/v1/system/ollama/status"),
    selfCheck: () =>
      http.get<{
        ollama: { available: boolean }
        llm_env_keys: Record<string, boolean>
        llm_any_configured: boolean
        translate_env_keys: Record<string, boolean>
        translate_note: string
        translate_dedicated_configured: boolean
        image_env_keys: Record<string, boolean>
        ollama_embed_model: string
      }>("/api/v1/system/self-check"),
    getUserSettingsSummary: () => http.get<{
      ncbi_key: { has_value: boolean; masked: string };
      s2_key:   { has_value: boolean; masked: string };
    }>("/api/v1/system/user-settings/summary"),
    getNcbiKey: () => http.get<{ has_value: boolean; masked: string }>("/api/v1/system/user-settings/ncbi-key"),
    setNcbiKey: (apiKey: string) => http.put("/api/v1/system/user-settings/ncbi-key", { api_key: apiKey || "" }),
    clearNcbiKey: () => http.delete("/api/v1/system/user-settings/ncbi-key"),
    getS2Key: () => http.get<{ has_value: boolean; masked: string }>("/api/v1/system/user-settings/s2-key"),
    setS2Key: (apiKey: string) => http.put("/api/v1/system/user-settings/s2-key", { api_key: apiKey || "" }),
    clearS2Key: () => http.delete("/api/v1/system/user-settings/s2-key"),
    getDefaultModel: () => http.get<{ model: string }>("/api/v1/system/user-settings/default-model"),
    setDefaultModel: (model: string) => http.put("/api/v1/system/user-settings/default-model", { model }),
  },
  tasks: {
    cancelTask: (taskId: string) => http.post(`/api/v1/tasks/${taskId}/cancel`),
  },
  translate: {
    translate: (text: string, targetLang = 'zh', sourceLang = 'en') =>
      http.post<{ text: string; provider: string; fallback_reason?: string }>(
        '/api/v1/translate',
        { text, target_lang: targetLang, source_lang: sourceLang },
      ),
    status: () =>
      http.get<{ providers: Array<{ id: string; name: string; available: boolean }>; active: string }>(
        '/api/v1/translate/status',
      ),
  },
  medcomm: {
    saveSection: (sectionId: number, contentJson: any) =>
      http.post(`/api/v1/medcomm/sections/${sectionId}/save`, { content_json: contentJson }),
    getSectionVersions: (sectionId: number, platform?: string) =>
      http.get(`/api/v1/medcomm/sections/${sectionId}/versions`, { params: platform ? { platform } : {} }),
    revertSection: (sectionId: number, verId: number) =>
      http.post(`/api/v1/medcomm/sections/${sectionId}/revert/${verId}`),
    listSnapshots: (articleId: number) =>
      http.get<{ items: Array<{ id: number; label: string; note: string; created_at: string | null }> }>(
        `/api/v1/medcomm/articles/${articleId}/snapshots`
      ),
    createSnapshot: (articleId: number, body: { label?: string; note?: string }) =>
      http.post(`/api/v1/medcomm/articles/${articleId}/snapshots`, body),
    restoreSnapshot: (articleId: number, snapshotId: number) =>
      http.post(`/api/v1/medcomm/articles/${articleId}/snapshots/${snapshotId}/restore`),
    deleteSnapshot: (articleId: number, snapshotId: number) =>
      http.delete(`/api/v1/medcomm/articles/${articleId}/snapshots/${snapshotId}`),
    updateImageStage: (articleId: number, imageStage: string) =>
      http.patch(`/api/v1/medcomm/articles/${articleId}/image-stage`, { image_stage: imageStage }),
    patchArticleVisualContinuity: (
      articleId: number,
      data: { visual_continuity_prompt: string; image_series_seed_base: number | null }
    ) => http.patch(`/api/v1/medcomm/articles/${articleId}/visual-continuity`, data),
    getArticles: (contentFormat?: string, platform?: string) =>
      http.get('/api/v1/medcomm/articles', {
        params: Object.fromEntries(
          [['content_format', contentFormat], ['platform', platform]]
            .filter(([, v]) => v != null && v !== '')
        ),
      }),
    getArticle: (id: number, sectionId?: number) =>
      http.get(`/api/v1/medcomm/articles/${id}`, { params: { section_id: sectionId } }),
    createArticle: (data: any) => http.post('/api/v1/medcomm/articles', data),
    generateArticleTitle: (id: number) => http.post(`/api/v1/medcomm/articles/${id}/generate-title`),
    patchArticleTitle: (id: number, title: string) =>
      http.patch(`/api/v1/medcomm/articles/${id}/title`, { title }),
    updateArticleContent: (id: number, contentJson: any, sectionId?: number) =>
      http.patch(`/api/v1/medcomm/articles/${id}`, { content_json: contentJson }, { params: { section_id: sectionId } }),
    recheckSection: (sectionId: number) =>
      http.post<{ ok: boolean; verify_report: any }>(`/api/v1/medcomm/sections/${sectionId}/recheck`),
    skipSection: (sectionId: number) =>
      http.patch<{ ok: boolean; status: string }>(`/api/v1/medcomm/sections/${sectionId}/skip`),
    unskipSection: (sectionId: number) =>
      http.patch<{ ok: boolean; status: string }>(`/api/v1/medcomm/sections/${sectionId}/unskip`),
    deleteArticle: (id: number) => http.delete(`/api/v1/medcomm/articles/${id}`),
    batchDeleteArticles: (ids: number[]) =>
      http.post<{ ok: boolean; deleted: number }>('/api/v1/medcomm/articles/batch-delete', { ids }),
    aiAssistStream: (data: {
      selected_text: string
      action: string
      context_before?: string
      context_after?: string
      custom_instruction?: string
      article_id?: number
    }, onToken: (text: string) => void, onDone: () => void, onError: (msg: string) => void) => {
      const ctrl = new AbortController()
      ;(async () => {
        try {
          const headers: Record<string, string> = { 'Content-Type': 'application/json' }
          const localHeader = await getLocalApiKeyHeader()
          Object.assign(headers, localHeader)
          if (_authToken) headers['Authorization'] = `Bearer ${_authToken}`
          const resp = await fetch(`${API_BASE}/api/v1/medcomm/ai-assist`, {
            method: 'POST',
            headers,
            body: JSON.stringify(data),
            signal: ctrl.signal,
          })
          if (!resp.ok || !resp.body) { onError(`HTTP ${resp.status}`); return }
          const reader = resp.body.getReader()
          const decoder = new TextDecoder()
          let buf = ''
          while (true) {
            const { done, value } = await reader.read()
            if (done) break
            buf += decoder.decode(value, { stream: true })
            const lines = buf.split('\n')
            buf = lines.pop() || ''
            for (const line of lines) {
              if (!line.startsWith('data: ')) continue
              try {
                const evt = JSON.parse(line.slice(6))
                if (evt.type === 'token') onToken(evt.content || '')
                else if (evt.type === 'done') onDone()
                else if (evt.type === 'error') onError(evt.message || '未知错误')
              } catch { /* skip malformed */ }
            }
          }
        } catch (e: any) {
          if (e.name !== 'AbortError') onError(e.message || '请求失败')
        }
      })()
      return ctrl
    },
    exportCheck: (id: number) =>
      http.get<{ can_export: boolean; data_warnings?: any[]; absolute_terms?: any[]; message?: string }>(
        `/api/v1/medcomm/articles/${id}/export-check`
      ),
    exportArticle: (id: number, format: string) =>
      http.get(`/api/v1/medcomm/articles/${id}/export`, { params: { format }, responseType: 'blob' }),
  },
  formats: {
    getFormats: () => http.get('/api/v1/formats'),
    getSections: (format: string) => http.get(`/api/v1/formats/${format}/sections`),
  },
  literature: {
    getPapers: (params?: {
      q?: string; page?: number; page_size?: number; trashed?: boolean;
      year_from?: number; year_to?: number; collection_id?: number; read_status?: string;
      tag_ids?: number[]; sort_by?: string; sort_dir?: 'asc' | 'desc';
    }) => http.get('/api/v1/literature/papers', { params: params ?? {} }),
    batchOperation: (data: {
      operation: 'tag' | 'move' | 'delete' | 'read_status' | 'restore' | 'permanent';
      paper_ids: number[];
      payload?: Record<string, unknown>;
    }) => http.post('/api/v1/literature/papers/batch', data),
    getPaper: (id: number) => http.get(`/api/v1/literature/papers/${id}`),
    createPaper: (data: any) => http.post('/api/v1/literature/papers', data),
    updatePaper: (id: number, data: any) => http.put(`/api/v1/literature/papers/${id}`, data),
    deletePaper: (id: number) => http.delete(`/api/v1/literature/papers/${id}`),
    restorePaper: (id: number) => http.post(`/api/v1/literature/papers/${id}/restore`),
    permanentDeletePaper: (id: number) => http.delete(`/api/v1/literature/papers/${id}/permanent`),
    fetchMetadata: (data: { doi?: string; pmid?: string }) =>
      http.post('/api/v1/literature/papers/fetch-metadata', data),
    checkDuplicate: (data: { doi?: string; title?: string; authors?: any[]; year?: number }) =>
      http.post('/api/v1/literature/papers/check-duplicate', data),
    recommendSimilar: (paperId: number, topK?: number) =>
      http.get(`/api/v1/literature/papers/${paperId}/similar`, { params: { top_k: topK ?? 5 } }),
    suggestTags: (paperId: number) =>
      http.get(`/api/v1/literature/papers/${paperId}/suggest-tags`),
    browserCapture: (data: {
      title: string; url: string; doi?: string; abstract?: string; selected_text?: string;
    }) => http.post('/api/v1/literature/papers/browser-capture', data),
    searchPapers: (query: string, topK?: number) =>
      http.get('/api/v1/literature/papers/search', { params: { q: query, top_k: topK ?? 10 } }),
    uploadPaper: (form: FormData) =>
      http.post('/api/v1/literature/papers/upload', form, { headers: { 'Content-Type': 'multipart/form-data' } }),
    uploadPaperPdf: (paperId: number, form: FormData) =>
      http.post(`/api/v1/literature/papers/${paperId}/pdf`, form, { headers: { 'Content-Type': 'multipart/form-data' } }),
    deletePaperPdf: (paperId: number) =>
      http.delete(`/api/v1/literature/papers/${paperId}/pdf`),
    resolveFulltext: (paperId: number) =>
      http.post<{ paper_id: number; status: string }>(
        `/api/v1/literature/papers/${paperId}/resolve-fulltext`,
      ),
    batchResolveFulltext: (collectionId?: number) =>
      http.post<{ queued: number; paper_ids: number[] }>(
        '/api/v1/literature/papers/batch-resolve-fulltext',
        null,
        { params: collectionId ? { collection_id: collectionId } : {} },
      ),
    deleteNoFulltextPapers: (collectionId?: number) =>
      http.delete<{ deleted: number; paper_ids: number[] }>(
        '/api/v1/literature/papers/no-fulltext',
        { params: collectionId ? { collection_id: collectionId } : {} },
      ),
    importPapers: (form: FormData) =>
      http.post('/api/v1/literature/papers/import', form, { headers: { 'Content-Type': 'multipart/form-data' } }),
    getImportTask: (taskId: string) =>
      http.get(`/api/v1/literature/papers/import-tasks/${taskId}`),
    exportCitation: (id: number, format?: string) =>
      http.get(`/api/v1/literature/papers/${id}/export`, { params: { format: format ?? 'apa' } }),
    exportBatch: (data: { ids: number[]; format?: 'apa' | 'bibtex' | 'nlm' | 'gbt7714' }) =>
      http.post('/api/v1/literature/papers/export-batch', { ids: data.ids, format: data.format ?? 'apa' }),
    getCollections: () => http.get('/api/v1/literature/collections/tree'),
    createCollection: (data: any) => http.post('/api/v1/literature/collections', data),
    updateCollection: (id: number, data: { name?: string; parent_id?: number | null; color?: string; icon?: string; sort_order?: number }) =>
      http.put(`/api/v1/literature/collections/${id}`, data),
    deleteCollection: (id: number) => http.delete(`/api/v1/literature/collections/${id}`),
    getTags: () => http.get('/api/v1/literature/tags'),
    createTag: (data: any) => http.post('/api/v1/literature/tags', data),
    updateTag: (id: number, data: { name?: string; color?: string }) =>
      http.put(`/api/v1/literature/tags/${id}`, data),
    deleteTag: (id: number) => http.delete(`/api/v1/literature/tags/${id}`),
    getBindings: (articleId: number, params?: { section_id?: number; scope?: 'article' | 'section' }) =>
      http.get(`/api/v1/literature/articles/${articleId}/bindings`, { params: params ?? {} }),
    getExternalRefs: (articleId: number, params?: { section_id?: number; scope?: 'article' | 'section' }) =>
      http.get(`/api/v1/literature/articles/${articleId}/external-refs`, { params: params ?? {} }),
    getPaperBindings: (paperId: number) =>
      http.get(`/api/v1/literature/papers/${paperId}/bindings`),
    bindPapers: (articleId: number, data: { paper_ids: number[]; section_id?: number; priority?: number }) =>
      http.post(`/api/v1/literature/articles/${articleId}/bindings`, data),
    bindExternalRefs: (articleId: number, data: { items: any[]; section_id?: number }) =>
      http.post(`/api/v1/literature/articles/${articleId}/external-refs`, data),
    deleteExternalRef: (articleId: number, refId: number) =>
      http.delete(`/api/v1/literature/articles/${articleId}/external-refs/${refId}`),
    fetchSearchAbstract: (params: { pmid?: string; doi?: string }) =>
      http.get('/api/v1/literature/search/abstract', { params }),
    fetchPubmedAbstract: (pmid: string) =>
      http.get(`/api/v1/literature/search/pubmed/${encodeURIComponent(pmid)}/abstract`),
    deleteBinding: (articleId: number, bindingId: number) =>
      http.delete(`/api/v1/literature/articles/${articleId}/bindings/${bindingId}`),
    updatePaperTags: (paperId: number, tagIds: number[]) =>
      http.patch(`/api/v1/literature/papers/${paperId}/tags`, { tag_ids: tagIds }),
    getChunks: (paperId: number) =>
      http.get(`/api/v1/literature/papers/${paperId}/chunks`),
    getAttachments: (paperId: number) =>
      http.get(`/api/v1/literature/papers/${paperId}/attachments`),
    uploadAttachment: (paperId: number, form: FormData) =>
      http.post(`/api/v1/literature/papers/${paperId}/attachments`, form, { headers: { 'Content-Type': 'multipart/form-data' } }),
    deleteAttachment: (paperId: number, attId: number) =>
      http.delete(`/api/v1/literature/papers/${paperId}/attachments/${attId}`),
    getAnnotations: (paperId: number) =>
      http.get(`/api/v1/literature/papers/${paperId}/annotations`),
    createAnnotation: (paperId: number, data: { annotation_type: string; page_number: number; rect: { x1: number; y1: number; x2: number; y2: number } | string; color?: string; content?: string; selected_text?: string }) =>
      http.post(`/api/v1/literature/papers/${paperId}/annotations`, data),
    updateAnnotation: (paperId: number, annId: number, data: { annotation_type?: string; page_number?: number; rect?: { x1: number; y1: number; x2: number; y2: number } | string; color?: string; content?: string; selected_text?: string }) =>
      http.put(`/api/v1/literature/papers/${paperId}/annotations/${annId}`, data),
    deleteAnnotation: (paperId: number, annId: number) =>
      http.delete(`/api/v1/literature/papers/${paperId}/annotations/${annId}`),
    getPdfUrl: (paperId: number) => `${API_BASE}/api/v1/literature/papers/${paperId}/pdf`,
    searchExternal: (data: {
      query: string;
      sources: Array<'pubmed' | 'crossref' | 'semantic_scholar'>;
      year_from?: number;
      year_to?: number;
      pub_types?: string[];
      max_per_source?: number;
      language?: 'all' | 'en' | 'zh';
    }) => http.post('/api/v1/literature/search', data),
    getSearchSources: () => http.get('/api/v1/literature/search/sources'),
    getSearchHistory: (limit?: number) => http.get('/api/v1/literature/search/history', { params: { limit: limit ?? 30 } }),
    deleteSearchHistory: (id: number) => http.delete(`/api/v1/literature/search/history/${id}`),
    saveSearchResults: (data: {
      items: any[];
      collection_id?: number | null;
      tag_ids?: number[];
    }) => http.post('/api/v1/literature/search/save', data),
    analyzeLiterature: (data: { paper_ids: number[]; topic_hint?: string }) =>
      http.post('/api/v1/literature/analyze', data, {
        responseType: 'text',
        headers: { Accept: 'text/event-stream' },
        timeout: 180000,
      }),
  },
  knowledge: {
    getDocs: () => http.get('/api/v1/knowledge/docs'),
    uploadDoc: (form: FormData) =>
      http.post('/api/v1/knowledge/docs/upload', form, { headers: { 'Content-Type': 'multipart/form-data' } }),
    deleteDoc: (id: number) => http.delete(`/api/v1/knowledge/docs/${id}`),
  },
  templates: {
    getTemplates: (contentFormat?: string) =>
      http.get('/api/v1/templates', { params: contentFormat ? { content_format: contentFormat } : {} }),
    createTemplate: (data: { name: string; content_format?: string; platform?: string; specialty?: string; structure?: any; description?: string }) =>
      http.post('/api/v1/templates', data),
  },
  auth: {
    login: (data?: { username?: string; password?: string }) =>
      http.post('/api/v1/auth/login', data ?? {}),
    me: () => http.get('/api/v1/auth/me'),
    getLicense: () =>
      http.get<{
        type: 'basic' | 'custom'
        custom_specialties: string[]
        service_expiry: string | null
        content_version: string
        next_content_update: string | null
        preset_docs?: Array<{ specialty: string; name: string; chunk_count?: number; updated_at?: string }>
        specialty_stats?: Record<string, { terms: number; examples: number; docs: number; updated_at?: string }>
      }>('/api/v1/auth/license'),
  },
  examples: {
    list: (params?: { content_format?: string; section_type?: string; platform?: string }) =>
      http.get('/api/v1/examples', { params: params ?? {} }),
    create: (data: { content_format: string; section_type: string; target_audience?: string; platform?: string; specialty?: string; content_text?: string; content_json?: string }) =>
      http.post('/api/v1/examples', data),
    get: (id: number) => http.get(`/api/v1/examples/${id}`),
    delete: (id: number) => http.delete(`/api/v1/examples/${id}`),
  },
  terms: {
    list: (params?: { audience_level?: string; specialty?: string }) =>
      http.get('/api/v1/terms', { params: params ?? {} }),
    create: (data: { term: string; abbreviation?: string; layman_explain?: string; analogy?: string; specialty?: string; audience_level?: string }) =>
      http.post('/api/v1/terms', data),
    get: (id: number) => http.get(`/api/v1/terms/${id}`),
    delete: (id: number) => http.delete(`/api/v1/terms/${id}`),
  },
  personalCorpus: {
    list: (enabledOnly?: boolean) =>
      http.get<{ items: Array<{ id: number; kind: string; anchor: string; content: string; source: string; enabled: boolean; created_at: string | null }> }>(
        '/api/v1/personal-corpus',
        { params: enabledOnly ? { enabled_only: true } : {} }
      ),
    create: (data: { kind: string; anchor?: string; content?: string; source?: string }) =>
      http.post('/api/v1/personal-corpus', data),
    capture: (data: { kind?: string; anchor: string; content?: string }) =>
      http.post('/api/v1/personal-corpus/capture', data),
    patch: (id: number, data: { anchor?: string; content?: string; enabled?: boolean; kind?: string }) =>
      http.patch(`/api/v1/personal-corpus/${id}`, data),
    delete: (id: number) => http.delete(`/api/v1/personal-corpus/${id}`),
  },
  polish: {
    run: (data: { session_id: number }) => http.post('/api/v1/polish/run', data),
    createSession: (data: { section_id: number; polish_type?: string }) =>
      http.post('/api/v1/polish/sessions', data),
    getChanges: (sessionId: number) => http.get(`/api/v1/polish/sessions/${sessionId}/changes`),
    acceptChange: (changeId: number) => http.post(`/api/v1/polish/changes/${changeId}/accept`),
    rejectChange: (changeId: number) => http.post(`/api/v1/polish/changes/${changeId}/reject`),
  },
  imagegen: {
    getImageTypes: () =>
      http.get<{
        image_types: { id: string; name: string; formats: string }[]
        image_styles: { id: string; name: string }[]
        format_default_image_type: Record<string, string>
        format_default_style: Record<string, string>
      }>('/api/v1/imagegen/image-types'),
    getProviders: () => http.get('/api/v1/imagegen/providers'),
    createTask: (data: {
      prompt: string
      user_positive_prompt?: string
      user_negative_prompt?: string
      style?: string
      width?: number
      height?: number
      batch_count?: number
      seed?: number
      steps?: number
      cfg_scale?: number
      sampler_name?: string
      content_format?: string
      image_type?: string
      specialty?: string
      target_audience?: string
      preferred_provider?: string
      siliconflow_image_model?: string
      comfy_workflow_path?: string
      comfy_mode?: string
      comfy_base_url?: string
      comfy_prompt_node_id?: string
      comfy_prompt_input_key?: string
      comfy_negative_node_id?: string
      comfy_negative_input_key?: string
      comfy_ksampler_node_id?: string
      article_id?: number
      visual_continuity_prompt?: string | null
      seed_base?: number | null
      panel_index?: number | null
    }) => http.post<{ task_id: string }>('/api/v1/imagegen/tasks', data),
    getTaskStatus: (taskId: string) =>
      http.get<{
        status: string
        images?: { path: string }[]
        error?: string
        provider_fallback?: string
        seeds?: number[]
      }>(`/api/v1/imagegen/tasks/${taskId}`),
    cancelTask: (taskId: string) => http.delete(`/api/v1/imagegen/tasks/${taskId}`),
    listImages: (params?: { article_id?: number; section_id?: number }) =>
      http.get<{ items: Array<{ id: number; file_path: string; article_id?: number; section_id?: number; image_type?: string; style?: string; created_at?: string }> }>(
        '/api/v1/imagegen/images',
        { params: params ?? {} }
      ),
    getImage: (id: number) => http.get(`/api/v1/imagegen/images/${id}`),
    deleteImage: (id: number) => http.delete(`/api/v1/imagegen/images/${id}`),
    attachImage: (id: number, data: { article_id: number; section_id?: number }) =>
      http.post(`/api/v1/imagegen/images/${id}/attach`, data),
    comicBatch: (data: {
      article_id: number
      panels: Array<{ panel_index: number; scene_desc: string; dialogue?: string }>
      style?: string
      seed_base?: number | null
      preferred_provider?: string
      comfy_workflow_path?: string
      comfy_mode?: string
      comfy_base_url?: string
      comfy_prompt_node_id?: string
      comfy_prompt_input_key?: string
      comfy_negative_node_id?: string
      comfy_negative_input_key?: string
      comfy_ksampler_node_id?: string
    }) => http.post<{ tasks: Array<{ task_id: string; panel_index: number }> }>('/api/v1/imagegen/comic/batch', data),
    getSuggestions: (sectionId: number, enhance = false) =>
      http.get<{ suggestions: Array<{ anchor_text: string; image_type: string; style: string; index?: number }>; fallback: boolean }>(
        `/api/v1/imagegen/suggestions/${sectionId}`, { params: enhance ? { enhance: 1 } : undefined }
      ),
    generate: (data: {
      prompt: string
      user_positive_prompt?: string
      user_negative_prompt?: string
      style?: string
      width?: number
      height?: number
      batch_count?: number
      seed?: number
      steps?: number
      cfg_scale?: number
      sampler_name?: string
      content_format?: string
      image_type?: string
      specialty?: string
      target_audience?: string
      preferred_provider?: string
      siliconflow_image_model?: string
      comfy_workflow_path?: string
      comfy_mode?: string
      comfy_base_url?: string
      comfy_prompt_node_id?: string
      comfy_prompt_input_key?: string
      comfy_negative_node_id?: string
      comfy_negative_input_key?: string
      comfy_ksampler_node_id?: string
      article_id?: number
      visual_continuity_prompt?: string | null
      seed_base?: number | null
      panel_index?: number | null
      loras?: Array<[string, number]>
    }) => http.post<{ urls: string[]; is_fallback?: boolean; provider?: string; provider_fallback?: string; seeds?: number[] }>('/api/v1/imagegen/generate', data),
    aiPrompts: (data: {
      scene_idea: string
      style?: string
      image_type?: string
      target_audience?: string
      content_format?: string
      provider?: string
    }) =>
      http.post<{
        positive: string
        negative: string
        used_template_fallback?: boolean
      }>('/api/v1/imagegen/ai-prompts', data),
    /**
     * medcomm-image → 可展示 URL。
     * Electron 已注册 medcomm-image:// 协议，img 直接走协议即可，避免 HTTP 请求无法带 X-Local-Api-Key 导致 403。
     * 纯浏览器开发时用 HTTP /serve。
     */
    imageUrl: (medcommPath: string) => {
      if (medcommPath.startsWith('medcomm-image://')) {
        const electron = typeof window !== 'undefined' && (window as any).electronAPI
        if (electron?.isElectron) return medcommPath
        const p = medcommPath.replace('medcomm-image://', '')
        return `${API_BASE}/api/v1/imagegen/serve?path=${encodeURIComponent(p)}`
      }
      return medcommPath
    },
  },
  data: {
    getContentStats: () =>
      http.get<{ terms: number; examples: number; docs: number; by_specialty: Record<string, { terms: number; examples: number; docs: number; updated_at?: string }> }>(
        '/api/v1/data/content-stats'
      ),
  },
  medpic: {
    buildPrompt: (data: {
      scene: string
      topic: string
      variant?: string
      specialty?: string
      target_audience?: string
      style?: string
      color_tone?: string
      subject?: string
      extra_prompt?: string
      hardware_tier?: string
      aspect?: string
      reference_image?: string
      ipadapter_weight?: number
      character_preset?: string
      segment_index?: number
      segment_count?: number
      seed_mode?: string
      lora_overrides?: Array<{ id: string; strength: number }>
    }) => http.post<{
      positive_prompt: string
      negative_prompt: string
      width: number
      height: number
      steps: number
      cfg_scale: number
      sampler_name: string
      scheduler: string
      workflow_path: string
      special: string | null
      reference_image: string | null
      output_width: number | null
      output_height: number | null
      process_mode: string
      recommended_seed: number | null
      seed_library_version: string
      loras: Array<{
        id: string
        name: string
        category: string
        filename: string
        strength: number
      }>
      model_id: string
      ipadapter_weight: number | null
    }>('/api/v1/medpic/build-prompt', data),
    getLoraRegistry: (params?: { arch?: string; tier?: string }) =>
      http.get<{
        loras: Array<{
          id: string
          name: string
          category: string
          filename: string
          arch: string
          weight_range: [number, number]
          default_weight: number
          tiers: string[]
          trigger_words: string
          auto_select_styles: string[]
          auto_select_scenes: string[]
          is_base_pack: boolean
          notes: string
        }>
      }>('/api/v1/medpic/lora-registry', { params: params ?? {} }),
    getModelRegistry: (params?: { tier?: string }) =>
      http.get<{
        models: Array<{
          id: string
          name: string
          arch: string
          filename: string
          license: string
          license_commercial: boolean
          size_gb: number
          tiers: string[]
        }>
        tier_model_map: Record<string, string>
      }>('/api/v1/medpic/model-registry', { params: params ?? {} }),
    getPresetCharacters: (params?: { scene?: string }) =>
      http.get<{
        characters: Array<{
          id: string
          name: string
          description: string
          reference_path: string
          thumbnail_url: string
          prompt_tags: string
          scenes: string[]
          available: boolean
        }>
      }>('/api/v1/medpic/preset-characters', { params: params ?? {} }),
    getVariants: (params?: { scene?: string; hardware_tier?: string }) =>
      http.get<{
        variants: Array<{
          id: string
          scene: string
          name: string
          description: string
          style: string
          aspects: string[]
          available: boolean
          tier_exclude: string[]
          special: string | null
          supports_character: boolean
        }>
      }>('/api/v1/medpic/variants', { params: params ?? {} }),
    uploadReferenceImage: (file: File) => {
      const form = new FormData()
      form.append('file', file)
      return http.post<{ path: string; serve_url: string }>(
        '/api/v1/medpic/reference-image', form,
        { headers: { 'Content-Type': 'multipart/form-data' } },
      )
    },
    referenceFromGenerated: (imagePath: string) =>
      http.post<{ path: string; serve_url: string }>(
        '/api/v1/medpic/reference-from-generated', null,
        { params: { image_path: imagePath } },
      ),
    listReferenceImages: () =>
      http.get<{ items: Array<{ path: string; serve_url: string; filename: string }> }>(
        '/api/v1/medpic/reference-images',
      ),
    finalize: (data: { image_path: string; target_width: number; target_height: number; hardware_tier?: string }) =>
      http.post<{
        path: string
        serve_url: string
        method: string
        width: number
        height: number
      }>('/api/v1/medpic/finalize', data),
    upscale: (data: { image_path: string; print_size?: string; aspect?: string }) =>
      http.post<{
        path: string
        serve_url: string
        method: string
        width: number
        height: number
      }>('/api/v1/medpic/upscale', data),
    stitch: (data: { segment_paths: string[]; variant_id?: string; output_width?: number }) =>
      http.post<{
        stitched_path: string
        stitched_url: string
        slices: Array<{ path: string; serve_url: string }>
        segment_count: number
      }>('/api/v1/medpic/stitch', data),
    longSegments: (data: { topic: string; segment_count?: number; variant_id?: string }) =>
      http.post<{ segment_prompts: string[]; count: number }>(
        '/api/v1/medpic/long-segments', data,
      ),
    compose: (data: {
      image_path: string
      scene: string
      texts: Record<string, string>
    }) => http.post<{
      composed_path: string
      serve_url: string
    }>('/api/v1/medpic/compose', data),
    getLayouts: () =>
      http.get<{ layouts: Array<{ scene_id: string; zones: string[] }> }>('/api/v1/medpic/layouts'),
    saveHistory: (data: {
      variant_id?: string
      scene: string
      style?: string
      hardware_tier?: string
      topic?: string
      specialty?: string
      positive_prompt?: string
      negative_prompt?: string
      seed?: number
      seed_mode?: string
      model_id?: string
      loras?: unknown[]
      width?: number
      height?: number
      output_width?: number
      output_height?: number
      base_image_path: string
      composed_image_path?: string
      upscaled_image_path?: string
      ipadapter_weight?: number
      character_preset?: string
      reference_image_path?: string
    }) => http.post<{ id: number; created_at: string }>('/api/v1/medpic/history', data),
    getHistory: (params?: { scene?: string; limit?: number; offset?: number }) =>
      http.get<{
        items: Array<{
          id: number
          variant_id: string | null
          scene: string
          style: string
          topic: string
          specialty: string | null
          seed: number | null
          base_image_path: string
          composed_image_path: string | null
          upscaled_image_path: string | null
          serve_url: string | null
          created_at: string
        }>
        total: number
      }>('/api/v1/medpic/history', { params: params ?? {} }),
    deleteHistory: (id: number) => http.delete<{ ok: boolean }>(`/api/v1/medpic/history/${id}`),
    updateHistory: (id: number, data: { composed_image_path?: string; upscaled_image_path?: string }) =>
      http.patch<{ ok: boolean }>(`/api/v1/medpic/history/${id}`, data),
    getWorkflow: (variantId: string) =>
      http.get<{ workflow: Record<string, unknown>; variant_id: string; format: string }>(
        `/api/v1/medpic/workflow/${variantId}`,
      ),
    comfyuiPrompt: (data: {
      scene: string
      topic: string
      variant?: string
      specialty?: string
      target_audience?: string
      style?: string
      color_tone?: string
      subject?: string
      extra_prompt?: string
      hardware_tier?: string
      aspect?: string
      reference_image?: string
      ipadapter_weight?: number
      character_preset?: string
      seed?: number | null
      seed_mode?: string
      lora_overrides?: Array<{ id: string; strength: number }>
    }) => http.post<{
      prompt: Record<string, unknown>
      client_id: string
      params_used: {
        positive_prompt: string
        negative_prompt: string
        width: number
        height: number
        steps: number
        cfg_scale: number
        seed: number
        model_id: string
        loras: Array<{ id: string; name: string; category: string; filename: string; strength: number }>
      }
    }>('/api/v1/medpic/comfyui-prompt', data),

    aiPrompt: (data: {
      description: string
      specialty?: string
      context_hint?: string
      stream?: boolean
    }) => http.post<{
      positive: string
      negative: string
      params: { scene?: string; style?: string; aspect?: string; audience?: string; color_tone?: string }
      explanation?: string
    }>('/api/v1/medpic/ai-prompt', data, { timeout: MEDPIC_LLM_TIMEOUT_MS }),

    aiPromptRefine: (data: {
      current_positive: string
      current_negative: string
      current_params?: Record<string, string>
      instruction: string
      stream?: boolean
    }) => http.post<{
      positive: string
      negative: string
      params: { scene?: string; style?: string; aspect?: string; audience?: string; color_tone?: string }
      explanation?: string
    }>('/api/v1/medpic/ai-prompt/refine', data, { timeout: MEDPIC_LLM_TIMEOUT_MS }),
  },
}
