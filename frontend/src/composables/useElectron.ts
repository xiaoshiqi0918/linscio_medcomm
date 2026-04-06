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

export interface BundleUpdateInfo {
  bundle_id: string
  latest_version?: string | null
  download_url?: string | null
  size_bytes?: number
  sha256?: string
  platform?: string | null
  changelog?: string[]
}

export interface SoftwareUpdateInfo {
  base_valid: boolean
  has_software_update: boolean
  latest_version?: string | null
  download_url?: string | null
  update_download_url?: string | null
  update_filename?: string | null
  update_size_bytes?: number
  update_sha256?: string | null
  release_notes?: string | null
  force_update?: boolean
  force_update_message?: string
  bundle_updates?: BundleUpdateInfo[]
}

export interface SoftwareUpdateProgress {
  percent: number
  downloaded: number
  total: number
  status: 'downloading' | 'verifying' | 'done' | 'error'
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

      // 应用内静默更新
      downloadSoftwareUpdate?: (opts: {
        url: string; filename: string; size_bytes?: number; sha256?: string
      }) => Promise<{ ok: boolean; filePath?: string; error?: string }>
      installSoftwareUpdate?: () => Promise<{ ok: boolean; error?: string }>
      cancelSoftwareUpdate?: () => Promise<{ ok: boolean }>
      getUpdateStatus?: () => Promise<{ status: string; filePath?: string | null }>
      onSoftwareUpdateProgress?: (cb: (payload: SoftwareUpdateProgress) => void) => void

      // 本地导入扩展包
      importLocalPack?: () => Promise<{ ok: boolean; error?: string }>

      // 应用版本
      getAppVersion?: () => Promise<string>

      // ComfyUI 管理
      getComfyUIStatus?: () => Promise<{
        running: boolean; port: number; pid: number | null;
        dir: string | null; available: boolean;
        bundleInstalled: boolean; bundleVersion: string | null;
      }>
      getComfyUIUrl?: () => Promise<string>
      restartComfyUI?: () => Promise<{ ok: boolean }>

      // ComfyUI Bundle 管理
      getComfyUIBundleInfo?: () => Promise<{
        version: string; platform: string; installed_at: string; dir: string;
      } | null>
      installComfyUIBundle?: (opts: {
        download_url: string; version: string; platform: string;
        size_bytes?: number; sha256?: string;
      }) => Promise<{ ok: boolean; error?: string; code?: string; version?: string }>
      uninstallComfyUIBundle?: () => Promise<{ ok: boolean }>
      onComfyUIBundleProgress?: (cb: (payload: {
        status: 'downloading' | 'verifying' | 'extracting' | 'done' | 'error';
        percent?: number; downloaded?: number; total?: number;
      }) => void) => void

      // 启动自检
      runStartupCheck?: () => Promise<{
        allPassed: boolean;
        summary: string;
        failures: Array<{
          key: string; ok: boolean; code: string | null;
          message: string; suggestion: string | null;
        }>;
        results: Record<string, {
          ok: boolean; code: string | null;
          message: string; suggestion: string | null;
        }>;
      }>
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
