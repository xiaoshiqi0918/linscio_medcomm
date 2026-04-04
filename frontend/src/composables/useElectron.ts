import { computed } from 'vue'

export interface SpecialtyStatusItem {
  id: string
  name: string
  remote_version?: string | null
  local_version?: string | null
  purchased_at?: string | null
}

export interface VersionPolicyItem {
  specialty_id: string
  force_min_version?: string | null
  force_max_version?: string | null
  policy_message?: string | null
}

export interface SoftwareUpdateInfo {
  base_valid: boolean
  has_software_update: boolean
  latest_version?: string | null
  download_url?: string | null
}

declare global {
  interface Window {
    electronAPI?: {
      platform: string
      isElectron: boolean
      getLocalApiKey?: () => Promise<string | undefined>
      saveApiKey?: (account: string, value: string) => Promise<{ ok: boolean; error?: string }>
      getApiKey?: (account: string) => Promise<string | null>
      reloadBackendEnv?: () => Promise<{ ok: boolean; error?: string }>
      backupFull?: () => Promise<{ ok: boolean; error?: string }>
      backupDbOnly?: () => Promise<{ ok: boolean; error?: string }>
      restoreFromZip?: (zipPath: string, strategy: string) => Promise<{ ok: boolean; error?: string }>
      listBackups?: () => Promise<Array<{ name: string; path: string }>>
      showOpenBackupDialog?: () => Promise<string | null>
      openExternal?: (url: string) => Promise<void>
      getPortalActivateUrl?: () => Promise<string>

      // 授权相关 IPC 监听
      onShowActivationGuide?: (cb: () => void) => void
      onLicenseActivated?: (cb: (payload: { token?: string }) => void) => void
      onLicenseExpired?: (cb: (payload: { valid?: boolean; expires_at?: string }) => void) => void
      onLicenseValid?: (cb: (payload: { valid?: boolean; expires_at?: string; days_remaining?: number }) => void) => void
      onLicenseExpiryReminder?: (cb: (payload: { days_remaining?: number; expires_at?: string }) => void) => void
      onSpecialtyStatusUpdate?: (cb: (payload: SpecialtyStatusItem[]) => void) => void
      onNewSpecialtiesAvailable?: (cb: (payload: { ids: string[] }) => void) => void
      onVersionPolicies?: (cb: (payload: VersionPolicyItem[]) => void) => void
      onImportDocumentPrompt?: (cb: (payload: { specialty?: string; url?: string; title?: string }) => void) => void
      onActivationError?: (cb: (payload: { message: string }) => void) => void

      // 软件更新检查
      onSoftwareUpdateAvailable?: (cb: (payload: SoftwareUpdateInfo) => void) => void

      // 授权管理
      portalLogin?: (email: string, password: string) => Promise<{
        ok: boolean; error?: string; email?: string; expires_at?: string; days_remaining?: number
      }>
      deactivateLicense?: () => Promise<{ ok: boolean }>

      // 学科包下载 + 安装
      downloadSpecialty?: (specialtyId: string, specialtyName: string, version: string, fromVersion?: string) => Promise<{ ok: boolean; error?: string }>
      onSpecialtyDownloadProgress?: (cb: (payload: {
        specialty_id: string; name?: string; percent: number;
        status: 'requesting' | 'downloading' | 'extracting' | 'installing' | 'done' | 'error';
        detail?: string;
      }) => void) => void
      getPackStatus?: () => Promise<Array<{
        specialty_id: string; name: string;
        local_version?: string | null; remote_version?: string | null;
        status: string; knowledge_docs: number; terms: number; examples: number;
      }>>

      // 手动检查更新
      checkForUpdate?: () => Promise<{ ok: boolean }>

      // 本地导入扩展包
      importLocalPack?: () => Promise<{ ok: boolean; error?: string }>

      // 应用版本
      getAppVersion?: () => Promise<string>

      // ComfyUI 管理
      getComfyUIStatus?: () => Promise<{
        running: boolean; port: number; pid: number | null;
        dir: string | null; available: boolean
      }>
      getComfyUIUrl?: () => Promise<string>
      restartComfyUI?: () => Promise<{ ok: boolean }>
    }
  }
}

export function useElectron() {
  const isElectron = computed(() => typeof window !== 'undefined' && !!window.electronAPI?.isElectron)
  const platform = computed(() => window.electronAPI?.platform ?? '')
  const hasKeychain = computed(() => !!window.electronAPI?.saveApiKey)

  async function saveApiKey(account: string, value: string) {
    if (!window.electronAPI?.saveApiKey) return { ok: false, error: 'Not in Electron' }
    return window.electronAPI.saveApiKey(account, value)
  }

  async function getApiKey(account: string) {
    if (!window.electronAPI?.getApiKey) return null
    return window.electronAPI.getApiKey(account)
  }

  return {
    isElectron,
    platform,
    hasKeychain,
    saveApiKey,
    getApiKey,
  }
}
