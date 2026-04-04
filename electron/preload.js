/**
 * Preload - 暴露安全的 API 给渲染进程
 */
const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  platform: process.platform,
  isElectron: true,
  getLocalApiKey: () => ipcRenderer.invoke('get-local-api-key'),
  saveApiKey: (account, value) => ipcRenderer.invoke('save-api-key', account, value),
  reloadBackendEnv: () => ipcRenderer.invoke('reload-backend-env'),
  getApiKey: (account) => ipcRenderer.invoke('get-api-key', account),
  backupFull: () => ipcRenderer.invoke('backup-full'),
  backupDbOnly: () => ipcRenderer.invoke('backup-db-only'),
  restoreFromZip: (zipPath, strategy) => ipcRenderer.invoke('restore-from-zip', zipPath, strategy),
  listBackups: () => ipcRenderer.invoke('list-backups'),
  showOpenBackupDialog: () => ipcRenderer.invoke('show-open-backup-dialog'),

  // MedComm v3 授权相关 IPC
  onShowActivationGuide: (cb) => {
    ipcRenderer.on('show-activation-guide', () => cb && cb())
  },
  onLicenseActivated: (cb) => {
    ipcRenderer.on('license-activated', (_, payload) => cb && cb(payload))
  },
  onLicenseExpired: (cb) => {
    ipcRenderer.on('license-expired', (_, payload) => cb && cb(payload))
  },
  onLicenseValid: (cb) => {
    ipcRenderer.on('license-valid', (_, payload) => cb && cb(payload))
  },
  onLicenseExpiryReminder: (cb) => {
    ipcRenderer.on('license-expiry-reminder', (_, payload) => cb && cb(payload))
  },
  onSpecialtyStatusUpdate: (cb) => {
    ipcRenderer.on('specialty-status-update', (_, payload) => cb && cb(payload))
  },
  onNewSpecialtiesAvailable: (cb) => {
    ipcRenderer.on('new-specialties-available', (_, payload) => cb && cb(payload))
  },
  onVersionPolicies: (cb) => {
    ipcRenderer.on('version-policies', (_, payload) => cb && cb(payload))
  },
  onImportDocumentPrompt: (cb) => {
    ipcRenderer.on('import-document-prompt', (_, payload) => cb && cb(payload))
  },
  onActivationError: (cb) => {
    ipcRenderer.on('activation-error', (_, payload) => cb && cb(payload))
  },
  onSoftwareUpdateAvailable: (cb) => {
    ipcRenderer.on('software-update-available', (_, payload) => cb && cb(payload))
  },
  onSpecialtyDownloadProgress: (cb) => {
    ipcRenderer.on('specialty-download-progress', (_, payload) => cb && cb(payload))
  },
  openExternal: (url) => ipcRenderer.invoke('open-external-url', url),
  getPortalActivateUrl: () => ipcRenderer.invoke('get-portal-activate-url'),
  portalLogin: (email, password) => ipcRenderer.invoke('portal-login', email, password),
  deactivateLicense: () => ipcRenderer.invoke('deactivate-license'),
  downloadSpecialty: (specialtyId, specialtyName, version, fromVersion) =>
    ipcRenderer.invoke('download-specialty', specialtyId, specialtyName, version, fromVersion),
  getPackStatus: () => ipcRenderer.invoke('get-pack-status'),
  checkForUpdate: () => ipcRenderer.invoke('check-for-update'),
  importLocalPack: () => ipcRenderer.invoke('import-local-pack'),
  getAppVersion: () => ipcRenderer.invoke('get-app-version'),

  // ComfyUI 管理
  getComfyUIStatus: () => ipcRenderer.invoke('get-comfyui-status'),
  getComfyUIUrl: () => ipcRenderer.invoke('get-comfyui-url'),
  restartComfyUI: () => ipcRenderer.invoke('restart-comfyui'),
})
