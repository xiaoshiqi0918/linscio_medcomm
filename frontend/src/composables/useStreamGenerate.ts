/**
 * SSE 流式生成 - 章节 AI 写作
 */
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

const BASE_URL = 'http://127.0.0.1:8765'

export function useStreamGenerate() {
  const generating = ref(false)
  const error = ref<string | null>(null)
  const streamedText = ref('')

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
      onClaimSkipped?: (reason: string) => void
      onReadingLevelSkipped?: (reason: string) => void
      onTitleGenerated?: (title: string) => void
    } = {}
  ) {
    generating.value = true
    error.value = null
    streamedText.value = ''
    ollamaWarning.value = null

    try {
      const headers: Record<string, string> = {}
      const electron = typeof window !== 'undefined' && (window as any).electronAPI
      if (electron?.getLocalApiKey) {
        const key = await electron.getLocalApiKey()
        if (key) headers['X-Local-Api-Key'] = key
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
                  callbacks.onDone?.(evt.content)
                } else if (evt.type === 'verify_report' && evt.report) {
                  callbacks.onVerifyReport?.(evt.report)
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
    }
  }

  return { generating, error, streamedText, ollamaWarning, generateSection }
}
