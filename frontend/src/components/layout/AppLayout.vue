<template>
  <div class="app-layout">
    <AppTitleBar />
    <LicenseBanner />
    <div class="app-body">
      <AppSidebar />
      <div class="main-wrapper">
        <main class="main-content">
          <router-view />
        </main>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppTitleBar from './AppTitleBar.vue'
import AppSidebar from './AppSidebar.vue'
import LicenseBanner from '@/components/LicenseBanner.vue'
import { useSettingsStore } from '@/stores/settings'
import { useMedcommLicenseStore } from '@/stores/medcommLicense'
import { ElMessageBox } from 'element-plus'
import { useAuthStore, AUTH_PREFERRED_USERNAME_KEY } from '@/stores/auth'

const router = useRouter()
const settingsStore = useSettingsStore()
const licenseStore = useMedcommLicenseStore()
const authStore = useAuthStore()

let startupCheckDone = false
async function checkUninstalledPacks(list: Array<{ id: string; name: string; local_version?: string | null }>) {
  if (startupCheckDone) return
  startupCheckDone = true
  const uninstalled = list.filter(s => !s.local_version)
  if (!uninstalled.length) return

  const names = uninstalled.map(s => s.name || s.id).join('、')
  try {
    await ElMessageBox.confirm(
      `检测到已购学科包尚未安装：${names}，是否前往设置页安装？`,
      '学科包可安装',
      { confirmButtonText: '前往安装', cancelButtonText: '稍后', type: 'info' }
    )
    router.push('/settings')
  } catch {
    // user dismissed
  }
}

onMounted(async () => {
  settingsStore.loadLicense()
  let preferred = ''
  try {
    preferred = window.localStorage.getItem(AUTH_PREFERRED_USERNAME_KEY) || ''
  } catch {
    preferred = ''
  }
  if (preferred) {
    try {
      await authStore.switchUser(preferred)
    } catch {
      // ignore and fall through to prompt
    }
  }
  if (!preferred) {
    try {
      const { value } = await ElMessageBox.prompt(
        '请输入用户名（用于隔离个人配置，如 NCBI Key、检索历史等）',
        '选择/创建用户',
        {
          confirmButtonText: '进入',
          cancelButtonText: '暂不',
          inputPlaceholder: '例如：张三',
        }
      )
      const name = String(value || '').trim()
      if (name) await authStore.switchUser(name)
    } catch {
      // 用户取消
    }
  }

  settingsStore.loadDefaultModelFromServer()

  const eApi = window.electronAPI
  if (!eApi) return

  eApi.onLicenseValid?.((p) => {
    licenseStore.resetBannerDismiss()
    licenseStore.setBase({ valid: true, ...p })
  })
  eApi.onLicenseExpired?.((p) => {
    licenseStore.resetBannerDismiss()
    licenseStore.setBase({ valid: false, ...p })
  })
  eApi.onLicenseExpiryReminder?.((p) => {
    const prev = licenseStore.base ?? {}
    licenseStore.setBase({
      ...prev,
      valid: true,
      days_remaining: p.days_remaining,
      expires_at: p.expires_at,
    })
  })

  eApi.onSpecialtyStatusUpdate?.((list) => {
    licenseStore.setSpecialties(list)
    checkUninstalledPacks(list)
  })

  eApi.onSoftwareUpdateAvailable?.((info) => {
    licenseStore.setSoftwareUpdate(info)
  })

  eApi.onVersionPolicies?.((list) => {
    licenseStore.setVersionPolicies(list)
  })
})
</script>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

.app-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.main-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.main-content {
  flex: 1;
  overflow: auto;
  background: #f5f5f7;
}
</style>
