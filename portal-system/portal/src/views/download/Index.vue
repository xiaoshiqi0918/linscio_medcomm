<template>
  <div class="page">
    <h1 class="page__title">下载客户端</h1>

    <div v-if="loading" class="text-center text-muted mt-3">加载中...</div>

    <!-- 下载成功 -->
    <div v-else-if="downloadUrl" class="card text-center">
      <div class="alert alert--success">正在为您下载 v{{ productVersion }}...</div>
      <p class="mt-2 text-muted">如果下载没有自动开始，请
        <a :href="downloadUrl" target="_blank">点击此处</a>
      </p>
    </div>

    <!-- 错误 -->
    <div v-else-if="error" class="card">
      <div class="alert alert--error">{{ error }}</div>
      <p v-if="needLicense" class="mt-2 text-muted">
        您还没有授权码。请在 <a href="http://localhost:5173/#/settings" target="_blank">SaaS 平台设置页</a> 使用积分兑换授权码后再来下载。
      </p>
    </div>

    <!-- 产品信息 -->
    <template v-if="!loading && !downloadUrl && !error">
      <section v-if="productInfo" class="section">
        <h2 class="section__title">
          {{ productInfo.name || 'LinScio MedComm' }}
          <span class="version-tag">v{{ productInfo.latest_version }}</span>
        </h2>
        <p v-if="productInfo.release_notes" class="release-notes">{{ productInfo.release_notes }}</p>

        <div class="download-grid">
          <div
            v-for="p in clientPlatforms"
            :key="p.id"
            class="download-item"
            :class="{ 'download-item--disabled': p.status === 'suspended' }"
          >
            <div class="download-item__icon">{{ platformIcon(p.id) }}</div>
            <div class="download-item__name">{{ p.name }}</div>
            <div class="download-item__meta">{{ p.filename || '' }}</div>
            <button
              v-if="p.status !== 'suspended'"
              class="btn btn--primary btn--sm"
              :disabled="downloading"
              @click="startDownload(p.id)"
            >
              {{ downloading ? '准备中...' : '下载' }}
            </button>
            <span v-else class="text-muted" style="font-size: 13px;">暂未开放</span>
          </div>
        </div>
      </section>

      <!-- 系统要求 -->
      <section v-if="sysReqs" class="section">
        <h2 class="section__title">系统要求</h2>
        <div class="req-grid">
          <div v-for="(val, key) in sysReqs" :key="key" class="req-item">
            <span class="req-key">{{ key }}</span>
            <span class="req-val">{{ val }}</span>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { getProductInfo, downloadSoftware } from '@/api'

const auth = useAuthStore()
const loading = ref(true)
const downloading = ref(false)
const error = ref('')
const needLicense = ref(false)
const downloadUrl = ref('')
const productVersion = ref('')
const productInfo = ref<any>(null)

interface ClientPlatform { id: string; name: string; filename: string; status: string }
const clientPlatforms = ref<ClientPlatform[]>([])

const sysReqs = computed(() => productInfo.value?.system_requirements || null)

const platformLabels: Record<string, string> = {
  'mac-arm64': 'macOS（Apple Silicon）',
  'mac-x64': 'macOS（Intel）',
  'win-x64': 'Windows（x64）',
}

function platformIcon(id: string): string {
  if (id.startsWith('mac')) return '🍎'
  if (id.startsWith('win')) return '🪟'
  return '💻'
}

onMounted(async () => {
  try {
    const { data } = await getProductInfo()
    const products = data.products || {}
    const matched = products.MedComm || products.medcomm || Object.values(products)[0]
    if (matched) {
      productVersion.value = matched.latest_version || ''
      productInfo.value = matched

      const files = matched.download_files || {}
      const statusMap = matched.platform_status || {}
      const platIds = matched.platforms || Object.keys(files)
      const allPlats = new Set([...platIds, ...Object.keys(statusMap)])
      clientPlatforms.value = [...allPlats].map(pid => ({
        id: pid,
        name: platformLabels[pid] || pid,
        filename: files[pid] || '',
        status: statusMap[pid] || 'available',
      }))
    }
  } catch {
    /* product-info is public, should rarely fail */
  }
  loading.value = false
})

async function startDownload(platform: string) {
  downloading.value = true
  error.value = ''
  needLicense.value = false
  try {
    const { data } = await downloadSoftware({ product_id: 'medcomm', platform })
    downloadUrl.value = data.download_url
    productVersion.value = data.version || productVersion.value
    window.location.href = data.download_url
  } catch (e: any) {
    const detail = e.response?.data?.detail || ''
    if (detail === 'no_valid_license') {
      error.value = '您尚未拥有客户端授权码，无法下载。'
      needLicense.value = true
    } else {
      error.value = detail || '下载失败，请稍后重试'
    }
  }
  downloading.value = false
}
</script>

<style scoped lang="scss">
.section { margin-top: 28px; }
.section__title { font-size: 16px; font-weight: 600; margin-bottom: 14px; }
.version-tag {
  font-size: 12px; font-weight: 400; color: #6b7280;
  background: #f3f4f6; padding: 2px 8px; border-radius: 4px; margin-left: 8px;
}
.release-notes {
  font-size: 13px; color: var(--text-muted); margin-bottom: 16px; line-height: 1.7;
}
.download-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 14px;
}
.download-item {
  border: 1px solid var(--border, #e5e7eb); border-radius: 10px; padding: 20px;
  text-align: center;
  &--disabled { opacity: 0.5; }
}
.download-item__icon { font-size: 28px; margin-bottom: 8px; }
.download-item__name { font-size: 14px; font-weight: 500; margin-bottom: 4px; }
.download-item__meta { font-size: 11px; color: #9ca3af; margin-bottom: 12px; min-height: 16px; }
.btn--sm { padding: 8px 24px; font-size: 13px; }

.req-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 8px;
}
.req-item {
  display: flex; gap: 8px; font-size: 13px;
}
.req-key { color: var(--text-muted); min-width: 60px; }
.req-val { color: var(--text-secondary); }
</style>
