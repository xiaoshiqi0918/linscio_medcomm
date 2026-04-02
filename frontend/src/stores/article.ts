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
  /** 右侧核实面板等触发：在编辑器内定位声明原文 */
  const editorLocatePayload = ref<{ text: string; nonce: number } | null>(null)

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

  function clear() {
    current.value = null
    currentSectionId.value = null
    contentJson.value = null
    verificationReport.value = null
    ollamaWarning.value = null
    editorLocatePayload.value = null
  }

  return {
    current,
    currentSectionId,
    contentJson,
    verificationReport,
    ollamaWarning,
    editorLocatePayload,
    setCurrent,
    setSectionId,
    setContentJson,
    setVerificationReport,
    setOllamaWarning,
    requestEditorLocate,
    clear,
  }
})
