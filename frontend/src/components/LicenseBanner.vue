<template>
  <div v-if="visible" class="license-banner" :class="bannerClass">
    <span class="text">{{ message }}</span>
    <button v-if="actionLabel" class="btn-link" @click="handleAction">
      {{ actionLabel }}
    </button>
    <button class="btn-close" aria-label="关闭" @click="dismiss">×</button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useMedcommLicenseStore } from '@/stores/medcommLicense'

const router = useRouter()
const store = useMedcommLicenseStore()

const bannerType = computed<'expired' | 'reminder' | 'software-update' | 'force-update' | null>(() => {
  if (store.forcedUpdatePolicies.length > 0) return 'force-update'
  if (store.showExpiredBanner) return 'expired'
  if (store.hasSoftwareUpdate) return 'software-update'
  if (store.showExpiryReminder) return 'reminder'
  return null
})

const visible = computed(() => bannerType.value !== null)

const bannerClass = computed(() => {
  switch (bannerType.value) {
    case 'expired': return 'expired'
    case 'force-update': return 'expired'
    case 'software-update': return 'update'
    case 'reminder': return 'reminder'
    default: return ''
  }
})

const message = computed(() => {
  switch (bannerType.value) {
    case 'force-update': {
      const p = store.forcedUpdatePolicies[0]
      return p?.policy_message || `学科包「${p?.specialty_id}」需要强制更新，请及时更新后继续使用。`
    }
    case 'expired':
      return '授权已到期，软件可继续使用，但无法获取主程序更新。'
    case 'software-update':
      return `MedComm 新版本 ${store.softwareUpdate?.latest_version || ''} 已发布，前往设置页更新。`
    case 'reminder': {
      const d = store.daysRemaining
      return `授权将在 ${d} 天后到期，请及时续费。`
    }
    default:
      return ''
  }
})

const actionLabel = computed(() => {
  switch (bannerType.value) {
    case 'expired':
    case 'reminder':
      return '前往续费'
    case 'software-update':
      return '前往设置'
    case 'force-update':
      return '查看详情'
    default:
      return ''
  }
})

async function handleAction() {
  const api = window.electronAPI
  if (!api?.openExternal) return

  if (bannerType.value === 'software-update') {
    router.push('/settings')
    return
  }

  if (api.getPortalActivateUrl) {
    const url = await api.getPortalActivateUrl()
    if (url) await api.openExternal(url)
  }
}

function dismiss() {
  switch (bannerType.value) {
    case 'expired':
    case 'reminder':
      store.dismissBanner()
      break
    case 'software-update':
      store.dismissSoftwareUpdate()
      break
    default:
      store.dismissBanner()
  }
}
</script>

<style scoped>
.license-banner {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 0.5rem 1rem;
  font-size: 0.875rem;
  flex-wrap: wrap;
}

.license-banner.reminder {
  background: #fef3c7;
  color: #92400e;
}

.license-banner.expired {
  background: #fee2e2;
  color: #991b1b;
}

.license-banner.update {
  background: #dbeafe;
  color: #1e40af;
}

.text {
  flex: 1;
  min-width: 0;
}

.btn-link {
  background: none;
  border: none;
  color: inherit;
  text-decoration: underline;
  cursor: pointer;
  font-size: inherit;
}

.btn-link:hover {
  opacity: 0.9;
}

.btn-close {
  background: none;
  border: none;
  color: inherit;
  cursor: pointer;
  font-size: 1.25rem;
  line-height: 1;
  padding: 0 0.25rem;
  opacity: 0.8;
}

.btn-close:hover {
  opacity: 1;
}
</style>
