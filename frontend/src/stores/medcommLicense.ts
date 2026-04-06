import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { SpecialtyStatusItem, VersionPolicyItem, SoftwareUpdateInfo } from '@/composables/useElectron'

export interface MedcommLicenseBase {
  valid: boolean
  is_trial?: boolean
  expires_at?: string | null
  days_remaining?: number | null
  device_name?: string | null
  rebind_remaining?: number
}

export const useMedcommLicenseStore = defineStore('medcommLicense', () => {
  const base = ref<MedcommLicenseBase | null>(null)
  const bannerDismissed = ref(false)

  // P0: 学科包状态
  const specialties = ref<SpecialtyStatusItem[]>([])

  // P0: 主程序更新
  const softwareUpdate = ref<SoftwareUpdateInfo | null>(null)
  const softwareUpdateDismissed = ref(false)

  // 应用内更新下载状态
  const updateDownloadStatus = ref<'idle' | 'downloading' | 'downloaded' | 'installing' | 'error'>('idle')
  const updateDownloadProgress = ref(0)
  const updateDownloadError = ref('')

  // P2: 版本策略
  const versionPolicies = ref<VersionPolicyItem[]>([])

  const isValid = computed(() => base.value?.valid ?? false)
  const daysRemaining = computed(() => base.value?.days_remaining ?? null)
  const expiresAt = computed(() => base.value?.expires_at ?? null)
  const showExpiryReminder = computed(
    () => isValid.value && daysRemaining.value != null && daysRemaining.value <= 14 && daysRemaining.value > 0
  )
  const showExpiredBanner = computed(
    () => !isValid.value && base.value != null && !bannerDismissed.value
  )

  const hasSoftwareUpdate = computed(
    () => !!softwareUpdate.value?.has_software_update && !softwareUpdateDismissed.value
  )

  const updatableSpecialties = computed(
    () => specialties.value.filter(s => s.remote_version && s.local_version && s.remote_version !== s.local_version)
  )

  const forcedUpdatePolicies = computed(() => {
    if (!versionPolicies.value.length || !specialties.value.length) return []
    return versionPolicies.value.filter(p => {
      if (!p.force_min_version) return false
      const spec = specialties.value.find(s => s.id === p.specialty_id)
      if (!spec?.local_version) return false
      return compareVersions(spec.local_version, p.force_min_version) < 0
    })
  })

  function setBase(payload: MedcommLicenseBase | null) {
    base.value = payload
  }

  function setSpecialties(list: SpecialtyStatusItem[]) {
    specialties.value = list
  }

  function setSoftwareUpdate(info: SoftwareUpdateInfo | null) {
    softwareUpdate.value = info
    softwareUpdateDismissed.value = false
  }

  function dismissSoftwareUpdate() {
    softwareUpdateDismissed.value = true
  }

  function setUpdateDownloadStatus(status: 'idle' | 'downloading' | 'downloaded' | 'installing' | 'error', error?: string) {
    updateDownloadStatus.value = status
    if (error !== undefined) updateDownloadError.value = error
    if (status === 'idle') {
      updateDownloadProgress.value = 0
      updateDownloadError.value = ''
    }
  }

  function setUpdateDownloadProgress(percent: number) {
    updateDownloadProgress.value = percent
  }

  function setVersionPolicies(list: VersionPolicyItem[]) {
    versionPolicies.value = list
  }

  function dismissBanner() {
    bannerDismissed.value = true
  }

  function resetBannerDismiss() {
    bannerDismissed.value = false
  }

  function $reset() {
    base.value = null
    bannerDismissed.value = false
    specialties.value = []
    softwareUpdate.value = null
    softwareUpdateDismissed.value = false
    updateDownloadStatus.value = 'idle'
    updateDownloadProgress.value = 0
    updateDownloadError.value = ''
    versionPolicies.value = []
  }

  return {
    base,
    specialties,
    softwareUpdate,
    versionPolicies,
    isValid,
    daysRemaining,
    expiresAt,
    showExpiryReminder,
    showExpiredBanner,
    hasSoftwareUpdate,
    updatableSpecialties,
    forcedUpdatePolicies,
    setBase,
    setSpecialties,
    updateDownloadStatus,
    updateDownloadProgress,
    updateDownloadError,
    setSoftwareUpdate,
    dismissSoftwareUpdate,
    setUpdateDownloadStatus,
    setUpdateDownloadProgress,
    setVersionPolicies,
    dismissBanner,
    resetBannerDismiss,
    $reset,
  }
})

function compareVersions(a: string, b: string): number {
  const pa = a.split('.').map(Number)
  const pb = b.split('.').map(Number)
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const na = pa[i] ?? 0
    const nb = pb[i] ?? 0
    if (na < nb) return -1
    if (na > nb) return 1
  }
  return 0
}
