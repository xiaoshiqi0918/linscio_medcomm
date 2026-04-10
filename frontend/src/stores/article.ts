import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface ArticleSummary {
  id: number
  topic: string
  title?: string
  content_format: string
  platform: string
  status?: string
}

export interface ArticleDetail {
  id: number
  topic: string
  title?: string
  content_format: string
  platform: string
  target_audience?: string
  sections?: Array<{ id: number; section_type: string; title?: string; order_num: number }>
  content_json?: any
  current_section_id?: number
  /** 当前章节内容关联的核实报告（服务端 ArticleContent.verify_report） */
  verify_report?: any
}

export const useArticleStore = defineStore('article', () => {
  const current = ref<ArticleDetail | null>(null)
  const currentSectionId = ref<number | null>(null)
  const contentJson = ref<any>(null)
  const verificationReport = ref<any>(null)
  const ollamaWarning = ref<string | null>(null)
  const editorLocatePayload = ref<{ text: string; nonce: number } | null>(null)
  const imageSuggestions = ref<Array<Record<string, unknown>>>([])

  /** 编辑器当前选区信息 */
  const editorSelection = ref<{
    text: string
    from: number
    to: number
    contextBefore: string
    contextAfter: string
  } | null>(null)

  /** AI 辅助写作结果（用于 RightPanel 和编辑器交互） */
  const aiAssistResult = ref<string>('')
  const aiAssistAction = ref<string>('')

  /** 编辑器文本替换/插入请求（RightPanel → Store → Article.vue → MedCommEditor） */
  const editorReplaceRequest = ref<{ from: number; to: number; text: string; nonce: number } | null>(null)
  const editorInsertRequest = ref<{ text: string; nonce: number } | null>(null)

  /** 通知 Article.vue 重新加载文章内容（如恢复版本/快照后） */
  const reloadNonce = ref(0)

  function setCurrent(a: ArticleDetail | null) {
    current.value = a
    contentJson.value = a?.content_json ?? { type: 'doc', content: [] }
  }

  function setVerificationReport(r: any) {
    verificationReport.value = r
  }

  function setOllamaWarning(msg: string | null) {
    ollamaWarning.value = msg
  }

  function setImageSuggestions(list: Array<Record<string, unknown>>) {
    imageSuggestions.value = list
  }

  function setEditorSelection(sel: typeof editorSelection.value) {
    editorSelection.value = sel
  }

  function setAiAssistResult(text: string, action: string = '') {
    aiAssistResult.value = text
    if (action) aiAssistAction.value = action
  }

  function clearAiAssist() {
    aiAssistResult.value = ''
    aiAssistAction.value = ''
  }

  function requestEditorReplace(from: number, to: number, text: string) {
    const prev = editorReplaceRequest.value?.nonce ?? 0
    editorReplaceRequest.value = { from, to, text, nonce: prev + 1 }
  }

  function requestEditorInsert(text: string) {
    const prev = editorInsertRequest.value?.nonce ?? 0
    editorInsertRequest.value = { text, nonce: prev + 1 }
  }

  function requestEditorLocate(text: string) {
    const t = (text || '').trim()
    if (!t) return
    const prev = editorLocatePayload.value?.nonce ?? 0
    editorLocatePayload.value = { text: t, nonce: prev + 1 }
  }

  function setSectionId(id: number | null) {
    currentSectionId.value = id
  }

  function setContentJson(json: any) {
    contentJson.value = json
  }

  function requestReload() {
    reloadNonce.value++
  }

  function clear() {
    current.value = null
    currentSectionId.value = null
    contentJson.value = null
    verificationReport.value = null
    ollamaWarning.value = null
    editorLocatePayload.value = null
    imageSuggestions.value = []
    editorSelection.value = null
    aiAssistResult.value = ''
    aiAssistAction.value = ''
    editorReplaceRequest.value = null
    editorInsertRequest.value = null
    reloadNonce.value = 0
  }

  return {
    current,
    currentSectionId,
    contentJson,
    verificationReport,
    ollamaWarning,
    imageSuggestions,
    editorSelection,
    aiAssistResult,
    aiAssistAction,
    editorLocatePayload,
    reloadNonce,
    setCurrent,
    setSectionId,
    setContentJson,
    setVerificationReport,
    setOllamaWarning,
    setImageSuggestions,
    setEditorSelection,
    setAiAssistResult,
    clearAiAssist,
    editorReplaceRequest,
    editorInsertRequest,
    requestEditorLocate,
    requestEditorReplace,
    requestEditorInsert,
    requestReload,
    clear,
  }
})
