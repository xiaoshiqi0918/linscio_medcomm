<template>
  <div class="app-layout">
    <AppTitleBar />
    <LicenseBanner v-if="isElectron" />
    <div class="app-body">
      <transition name="slide-nav">
        <AppSidebar v-if="sidebarVisible" />
      </transition>
      <button
        class="sidebar-toggle"
        :class="{ collapsed: !sidebarVisible }"
        :title="sidebarVisible ? '隐藏导航栏' : '展开导航栏'"
        @click="toggleSidebar"
      >
        <svg viewBox="0 0 16 16" width="14" height="14">
          <path
            v-if="sidebarVisible"
            d="M6.5 3L2 8l4.5 5"
            stroke="currentColor" stroke-width="1.5" fill="none"
            stroke-linecap="round" stroke-linejoin="round"
          />
          <path
            v-else
            d="M9.5 3L14 8l-4.5 5"
            stroke="currentColor" stroke-width="1.5" fill="none"
            stroke-linecap="round" stroke-linejoin="round"
          />
        </svg>
      </button>
      <div class="main-wrapper">
        <main class="main-content">
          <router-view />
        </main>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
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
const isElectron = typeof window !== 'undefined' && !!window.electronAPI?.isElectron

const STORAGE_KEY_SIDEBAR = 'app_sidebar_visible'
const sidebarVisible = ref(
  localStorage.getItem(STORAGE_KEY_SIDEBAR) !== 'false'
)
function toggleSidebar() {
  sidebarVisible.value = !sidebarVisible.value
  localStorage.setItem(STORAGE_KEY_SIDEBAR, String(sidebarVisible.value))
}

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

  if (isElectron) {
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

  // 主动拉取一次当前授权缓存，修复 ActivationGuide 登录后事件丢失的时序问题
  if (eApi.getLicenseCache) {
    try {
      const cache = await eApi.getLicenseCache()
      if (cache?.base) {
        if (cache.base.valid) {
          licenseStore.setBase({ valid: true, ...cache.base })
        } else {
          licenseStore.setBase({ valid: false, ...cache.base })
        }
      }
    } catch { /* ignore */ }
  }
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
  position: relative;
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

.sidebar-toggle {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  z-index: 30;
  width: 20px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #e5e7eb;
  border-left: none;
  border-radius: 0 6px 6px 0;
  background: #fff;
  color: #9ca3af;
  cursor: pointer;
  padding: 0;
  transition: left 0.25s ease, background 0.15s, color 0.15s;
}
.sidebar-toggle:not(.collapsed) {
  left: 240px;
}
.sidebar-toggle:hover {
  background: #f3f4f6;
  color: #374151;
}

.slide-nav-enter-active,
.slide-nav-leave-active {
  transition: all 0.25s ease;
}
.slide-nav-enter-from,
.slide-nav-leave-to {
  width: 0 !important;
  min-width: 0 !important;
  overflow: hidden;
  opacity: 0;
}
</style>
