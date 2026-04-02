import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '@/api'

export interface PresetDoc {
  specialty: string
  name: string
  chunk_count?: number
  updated_at?: string
}

export interface SpecialtyStats {
  terms: number
  examples: number
  docs: number
  updated_at?: string
}

export interface LicenseInfo {
  type: 'basic' | 'custom'
  customSpecialties: string[]
  serviceExpiry: string | null
  contentVersion: string
  nextContentUpdate: string | null
  presetDocs: PresetDoc[]
  specialtyStats: Record<string, SpecialtyStats>
}

const DEFAULT_LICENSE: LicenseInfo = {
  type: 'basic',
  customSpecialties: [],
  serviceExpiry: null,
  contentVersion: '1.0',
  nextContentUpdate: null,
  presetDocs: [],
  specialtyStats: {},
}

export const useSettingsStore = defineStore('settings', () => {
  const persistedDefaultModel =
    typeof window !== 'undefined' ? window.localStorage.getItem('medcomm_default_model') : null
  const defaultModel = ref(persistedDefaultModel || 'gpt-4o-mini')
  const preferredImageProvider = ref(
    typeof window !== 'undefined' ? window.localStorage.getItem('medcomm_preferred_image_provider') || 'auto' : 'auto'
  )
  const siliconflowImageModel = ref(
    typeof window !== 'undefined' ? window.localStorage.getItem('medcomm_siliconflow_image_model') || 'Kwai-Kolors/Kolors' : 'Kwai-Kolors/Kolors'
  )
  const comfyWorkflowPath = ref(
    typeof window !== 'undefined' ? window.localStorage.getItem('medcomm_comfy_workflow_path') || '' : ''
  )
  const comfyBaseUrl = ref(
    typeof window !== 'undefined' ? window.localStorage.getItem('medcomm_comfy_base_url') || '' : ''
  )
  const comfyPromptNodeId = ref(
    typeof window !== 'undefined' ? window.localStorage.getItem('medcomm_comfy_prompt_node_id') || '6' : '6'
  )
  const comfyPromptInputKey = ref(
    typeof window !== 'undefined' ? window.localStorage.getItem('medcomm_comfy_prompt_input_key') || 'text' : 'text'
  )
  const comfyNegativeNodeId = ref(
    typeof window !== 'undefined' ? window.localStorage.getItem('medcomm_comfy_negative_node_id') || '' : ''
  )
  const comfyNegativeInputKey = ref(
    typeof window !== 'undefined' ? window.localStorage.getItem('medcomm_comfy_negative_input_key') || 'text' : 'text'
  )
  const comfyKsamplerNodeId = ref(
    typeof window !== 'undefined' ? window.localStorage.getItem('medcomm_comfy_ksampler_node_id') || '' : ''
  )
  const openaiKey = ref('')
  const anthropicKey = ref('')
  const license = ref<LicenseInfo>({ ...DEFAULT_LICENSE })
  const licenseLoaded = ref(false)

  const isBasic = computed(() => license.value.type === 'basic')
  const isCustom = computed(() => license.value.type === 'custom')
  const showUpgradeHint = computed(() => license.value.type === 'basic')
  const hasCustomSpecialty = (specialty: string) =>
    license.value.type === 'custom' && license.value.customSpecialties.includes(specialty)

  async function loadLicense() {
    try {
      const res = await api.auth.getLicense()
      const d = res.data
      license.value = {
        type: d?.type ?? 'basic',
        customSpecialties: d?.custom_specialties ?? [],
        serviceExpiry: d?.service_expiry ?? null,
        contentVersion: d?.content_version ?? '1.0',
        nextContentUpdate: d?.next_content_update ?? null,
        presetDocs: d?.preset_docs ?? [],
        specialtyStats: d?.specialty_stats ?? {},
      }
    } catch {
      license.value = { ...DEFAULT_LICENSE }
    } finally {
      licenseLoaded.value = true
    }
  }

  function setDefaultModel(model: string) {
    defaultModel.value = model
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('medcomm_default_model', model)
    }
    api.system.setDefaultModel(model).catch(() => {})
  }

  async function loadDefaultModelFromServer() {
    try {
      const res = await api.system.getDefaultModel()
      const serverModel = res.data?.model
      if (serverModel) {
        defaultModel.value = serverModel
        if (typeof window !== 'undefined') {
          window.localStorage.setItem('medcomm_default_model', serverModel)
        }
      }
    } catch {
      // fallback to localStorage value
    }
  }

  function setPreferredImageProvider(provider: string) {
    preferredImageProvider.value = provider
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('medcomm_preferred_image_provider', provider)
    }
  }

  function setSiliconflowImageModel(model: string) {
    siliconflowImageModel.value = model
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('medcomm_siliconflow_image_model', model)
    }
  }

  function setComfyWorkflowPath(v: string) {
    comfyWorkflowPath.value = v
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('medcomm_comfy_workflow_path', v)
    }
  }

  function setComfyBaseUrl(v: string) {
    comfyBaseUrl.value = v
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('medcomm_comfy_base_url', v)
    }
  }

  function setComfyPromptNodeId(v: string) {
    comfyPromptNodeId.value = v
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('medcomm_comfy_prompt_node_id', v)
    }
  }

  function setComfyPromptInputKey(v: string) {
    comfyPromptInputKey.value = v
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('medcomm_comfy_prompt_input_key', v)
    }
  }

  function setComfyNegativeNodeId(v: string) {
    comfyNegativeNodeId.value = v
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('medcomm_comfy_negative_node_id', v)
    }
  }

  function setComfyNegativeInputKey(v: string) {
    comfyNegativeInputKey.value = v
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('medcomm_comfy_negative_input_key', v)
    }
  }

  function setComfyKsamplerNodeId(v: string) {
    comfyKsamplerNodeId.value = v
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('medcomm_comfy_ksampler_node_id', v)
    }
  }

  return {
    defaultModel,
    setDefaultModel,
    preferredImageProvider,
    setPreferredImageProvider,
    siliconflowImageModel,
    setSiliconflowImageModel,
    comfyWorkflowPath,
    comfyBaseUrl,
    comfyPromptNodeId,
    comfyPromptInputKey,
    comfyNegativeNodeId,
    comfyNegativeInputKey,
    comfyKsamplerNodeId,
    setComfyWorkflowPath,
    setComfyBaseUrl,
    setComfyPromptNodeId,
    setComfyPromptInputKey,
    setComfyNegativeNodeId,
    setComfyNegativeInputKey,
    setComfyKsamplerNodeId,
    openaiKey,
    anthropicKey,
    license,
    licenseLoaded,
    isBasic,
    isCustom,
    showUpgradeHint,
    hasCustomSpecialty,
    loadLicense,
    loadDefaultModelFromServer,
  }
})
