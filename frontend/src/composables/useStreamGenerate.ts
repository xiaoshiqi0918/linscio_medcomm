/**
 * SSE 流式生成 - 章节 AI 写作
 */
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

import { API_BASE, getAuthToken, getLocalApiKeyHeaderForFetch } from '@/api'

const BASE_URL = API_BASE

export function useStreamGenerate() {
  const generating = ref(false)
  const error = ref<string | null>(null)
  const streamedText = ref('')
  const streamPhase = ref<'writing' | 'rewriting' | null>(null)

  const ollamaWarning = ref<string | null>(null)

  async function generateSection(
    sectionId: number,
    callbacks: {
      onStart?: (data: { task_id?: string; content_format?: string }) => void
      onDelta?: (text: string) => void
      onDone?: (content: string) => void
      onError?: (msg: string) => void
      onVerifyReport?: (report: unknown) => void
      onOllamaWarning?: (message: string) => void
      onLiteratureWarning?: (data: { level: string; bound_count: number; message: string }) => void
      onClaimSkipped?: (reason: string) => void
      onReadingLevelSkipped?: (reason: string) => void
      onTitleGenerated?: (title: string) => void
      onImageSuggestions?: (suggestions: Array<Record<string, unknown>>) => void
      onRewriting?: (message: string) => void
      onRewrittenContent?: (content: string) => void
    } = {}
  ) {
    generating.value = true
    error.value = null
    streamedText.value = ''
    streamPhase.value = 'writing'
    ollamaWarning.value = null

    try {
      const localApiHeader = await getLocalApiKeyHeaderForFetch()
      const token = getAuthToken()
      const headers: Record<string, string> = {
        ...localApiHeader,
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      }
      const res = await fetch(`${BASE_URL}/api/v1/medcomm/sections/${sectionId}/generate`, {
        method: 'POST',
        headers,
      })
      if (!res.ok) {
        let detail = ''
        try {
          detail = await res.text()
        } catch {
          detail = ''
        }
        throw new Error(`HTTP ${res.status}${detail ? `: ${detail}` : ''}`)
      }

      const reader = res.body?.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      if (reader) {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n\n')
          buffer = lines.pop() || ''
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const evt = JSON.parse(line.slice(6))
                if (evt.type === 'start') {
                  callbacks.onStart?.({ task_id: evt.task_id, content_format: evt.content_format })
                } else if (evt.type === 'delta' && evt.text) {
                  streamedText.value += evt.text
                  callbacks.onDelta?.(evt.text)
                } else if (evt.type === 'done' && evt.content) {
                  if (Array.isArray(evt.image_suggestions) && evt.image_suggestions.length) {
                    callbacks.onImageSuggestions?.(evt.image_suggestions)
                  }
                  callbacks.onDone?.(evt.content)
                } else if (evt.type === 'verify_report' && evt.report) {
                  callbacks.onVerifyReport?.(evt.report)
                } else if (evt.type === 'literature_warning') {
                  const level = evt.level === 'critical' ? 'error' : 'warning'
                  ElMessage({ type: level, message: evt.message, duration: 8000, showClose: true })
                  callbacks.onLiteratureWarning?.({
                    level: evt.level,
                    bound_count: evt.bound_count,
                    message: evt.message,
                  })
                } else if (evt.type === 'rewriting' && evt.message) {
                  streamPhase.value = 'rewriting'
                  streamedText.value = ''
                  callbacks.onRewriting?.(evt.message)
                } else if (evt.type === 'rewritten_content' && evt.content) {
                  streamedText.value = evt.content
                  callbacks.onRewrittenContent?.(evt.content)
                } else if (evt.type === 'ollama_warning' && evt.message) {
                  ollamaWarning.value = evt.message
                  callbacks.onOllamaWarning?.(evt.message)
                } else if (evt.type === 'claim_skipped' && evt.reason) {
                  callbacks.onClaimSkipped?.(evt.reason)
                } else if (evt.type === 'reading_level_skipped' && evt.reason) {
                  callbacks.onReadingLevelSkipped?.(evt.reason)
                } else if (evt.type === 'title_generated' && evt.title) {
                  callbacks.onTitleGenerated?.(evt.title)
                } else if (evt.type === 'error') {
                  error.value = evt.message
                  ElMessage.error(evt.message || 'AI 生成失败')
                  callbacks.onError?.(evt.message)
                }
              } catch (_) {}
            }
          }
        }
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      error.value = msg
      ElMessage.error(msg || 'AI 生成失败')
      callbacks.onError?.(msg)
    } finally {
      generating.value = false
      streamPhase.value = null
    }
  }

  return { generating, error, streamedText, streamPhase, ollamaWarning, generateSection }
}
