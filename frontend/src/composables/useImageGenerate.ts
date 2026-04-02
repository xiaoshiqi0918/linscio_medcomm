import { ref } from 'vue'
import { api } from '@/api'
import { usePollingGuard } from './usePollingGuard'
import { useSettingsStore } from '@/stores/settings'

const POLL_INTERVAL_MS = 2000
/** ComfyUI 本地/GPU 或云端排队可能较慢 */
const POLL_TIMEOUT_MS = 300_000

type SettingsStore = ReturnType<typeof useSettingsStore>

/** 与后端 /imagegen/tasks 对齐的提供商与 ComfyUI 配置（条漫单格等复用） */
export function buildImageGenBackendOptions(store: SettingsStore) {
  return {
    preferred_provider: store.preferredImageProvider,
    siliconflow_image_model: store.siliconflowImageModel,
    ...(store.comfyWorkflowPath.trim()
      ? { comfy_workflow_path: store.comfyWorkflowPath.trim() }
      : {}),
    ...(store.comfyBaseUrl.trim() ? { comfy_base_url: store.comfyBaseUrl.trim() } : {}),
    ...(store.comfyPromptNodeId.trim()
      ? { comfy_prompt_node_id: store.comfyPromptNodeId.trim() }
      : {}),
    ...(store.comfyPromptInputKey.trim()
      ? { comfy_prompt_input_key: store.comfyPromptInputKey.trim() }
      : {}),
    ...(store.comfyNegativeNodeId.trim()
      ? { comfy_negative_node_id: store.comfyNegativeNodeId.trim() }
      : {}),
    ...(store.comfyNegativeInputKey.trim()
      ? { comfy_negative_input_key: store.comfyNegativeInputKey.trim() }
      : {}),
    ...(store.comfyKsamplerNodeId.trim()
      ? { comfy_ksampler_node_id: store.comfyKsamplerNodeId.trim() }
      : {}),
  }
}

export interface ImageGenParams {
  /** 场景描述；与 user_positive_prompt 二选一或同时填（优先正向框） */
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
  /** 条漫等：从文章读连贯配置；与 panel_index/seed_base 配合 */
  article_id?: number
  visual_continuity_prompt?: string | null
  seed_base?: number | null
  panel_index?: number | null
}

export interface GeneratedImage {
  path: string
}

export function useImageGenerate() {
  const settingsStore = useSettingsStore()
  const generating = ref(false)
  const images = ref<GeneratedImage[]>([])
  const error = ref<string | null>(null)
  const isFallback = ref(false)
  const lastSeeds = ref<number[]>([])

  async function generate(params: ImageGenParams | string, style?: string) {
    generating.value = true
    images.value = []
    error.value = null
    isFallback.value = false
    lastSeeds.value = []

    const p: ImageGenParams =
      typeof params === 'string'
        ? { prompt: params, style: style || 'medical_illustration' }
        : { ...params, style: params.style || 'medical_illustration' }
    const scene = (p.prompt || '').trim()
    const direct = (p.user_positive_prompt || '').trim()
    if (!scene && !direct) {
      error.value = '请填写场景描述或正向提示词'
      generating.value = false
      return
    }
    const payload = { ...p, ...buildImageGenBackendOptions(settingsStore) }

    try {
      const res = await api.imagegen.createTask(payload)
      const taskId = res.data?.task_id
      if (!taskId) {
        error.value = '创建任务失败'
        return
      }

      await usePollingGuard({
        pollFn: async () => {
          const r = await api.imagegen.getTaskStatus(taskId)
          return r.data as {
            status: string
            images?: { path: string }[]
            error?: string
            provider_fallback?: string
            seeds?: number[]
          }
        },
        interval: POLL_INTERVAL_MS,
        timeout: POLL_TIMEOUT_MS,
        isDone: (s) => s.status === 'done',
        isFailed: (s) => s.status === 'failed',
        onDone: (s) => {
          images.value = s.images || []
          isFallback.value = s.provider_fallback === 'pollinations'
          lastSeeds.value = Array.isArray(s.seeds) ? s.seeds : []
        },
        onFailed: (s) => {
          error.value = s.error || '生成失败'
        },
        onTimeout: () => {
          error.value = '图像生成超时，请重试'
        },
      })
    } finally {
      generating.value = false
    }
  }

  function imageUrl(path: string) {
    return path.startsWith('medcomm-image://')
      ? api.imagegen.imageUrl(path)
      : path
  }

  return {
    generating,
    images,
    error,
    isFallback,
    lastSeeds,
    generate,
    imageUrl,
  }
}
