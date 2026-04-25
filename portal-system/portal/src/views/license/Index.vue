<template>
  <div class="page">
    <h1 class="page__title">我的授权</h1>
    <p class="page__subtitle">以下是你名下所有产品的授权状态。</p>

    <div v-if="loading" class="text-muted mt-3">加载中...</div>

    <div v-else class="license-list">
      <div v-for="lic in licenses" :key="lic.product_id" class="license-card card">
        <!-- Card header -->
        <div class="lc-header">
          <div class="lc-name">
            <span class="dot" :class="dotClass(lic.status)"></span>
            <span>{{ lic.product_name }}</span>
          </div>
          <span class="badge" :class="badgeClass(lic.status)">{{ statusText(lic.status) }}</span>
        </div>

        <!-- Info grid -->
        <div class="lc-info">
          <div class="lc-info__item">
            <span class="lc-label">到期时间</span>
            <span class="lc-value" :class="{ 'lc-value--danger': lic.status === 'expired' }">
              {{ lic.status !== 'not_activated' && lic.expires_at ? formatDate(lic.expires_at) : '--' }}
            </span>
          </div>
          <div class="lc-info__item">
            <span class="lc-label">{{ lic.status === 'expired' ? '已过期' : '剩余天数' }}</span>
            <span class="lc-value" :class="{ 'lc-value--danger': lic.status === 'expired' }">
              {{ lic.status !== 'not_activated' ? daysDisplay(lic) : '--' }}
            </span>
          </div>
          <div class="lc-info__item">
            <span class="lc-label">授权类型</span>
            <span class="lc-value">{{ licenseType(lic) }}</span>
          </div>
        </div>

        <!-- Footer -->
        <div class="lc-footer">
          <p class="lc-hint">{{ hintText(lic.status) }}</p>
          <router-link to="/license/activate" class="btn btn--ghost">
            {{ lic.status === 'not_activated' ? '激活授权码' : '激活续费码' }}
          </router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { licenseStatusAll } from '@/api'

interface LicenseInfo {
  product_id: string
  product_name: string
  status: string
  is_trial: boolean
  expires_at: string | null
  days_remaining: number | null
  device_name: string | null
  rebind_remaining: number | null
}

const loading = ref(true)
const licenses = ref<LicenseInfo[]>([])

onMounted(async () => {
  try {
    const { data } = await licenseStatusAll()
    licenses.value = data.licenses
  } catch { /* handled by interceptor */ }
  loading.value = false
})

function dotClass(s: string) {
  return { valid: 'dot--green', expired: 'dot--red', trial: 'dot--yellow', not_activated: 'dot--gray' }[s] || ''
}

function badgeClass(s: string) {
  return { valid: 'badge--valid', expired: 'badge--expired', trial: 'badge--trial', not_activated: 'badge--inactive' }[s] || ''
}

function statusText(s: string) {
  return { valid: '授权有效', expired: '授权已到期', trial: '试用中', not_activated: '未激活' }[s] || s
}

function licenseType(lic: LicenseInfo) {
  if (lic.status === 'not_activated') return '--'
  return lic.is_trial ? '试用版' : '正式版'
}

function daysDisplay(lic: LicenseInfo) {
  if (lic.days_remaining === null || lic.days_remaining === undefined) return '--'
  if (lic.status === 'expired') return `${Math.abs(lic.days_remaining)} 天`
  return `${lic.days_remaining} 天`
}

function hintText(s: string) {
  const hints: Record<string, string> = {
    valid: '续费请联系我们获取授权码，激活后有效期自动叠加。',
    expired: '软件仍可正常使用，续费后恢复更新通道。',
    trial: '试用期间可体验全部功能，到期后需激活正式授权码。',
    not_activated: '尚未激活此产品。如需使用请联系我们获取授权码。',
  }
  return hints[s] || ''
}

function formatDate(iso: string) {
  return iso.slice(0, 10)
}
</script>

<style scoped lang="scss">
.license-list {
  display: flex; flex-direction: column; gap: 20px;
}

.license-card {
  padding: 28px 32px;
}

.lc-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 24px;
}
.lc-name {
  display: flex; align-items: center; gap: 10px;
  font-size: 18px; font-weight: 500; color: var(--text-secondary);
}
.dot {
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
}
.dot--green { background: var(--success); }
.dot--red { background: var(--danger); }
.dot--yellow { background: var(--warning); }
.dot--gray { background: var(--border); }

.lc-info {
  display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0;
  margin-bottom: 24px;
}
.lc-info__item {
  display: flex; flex-direction: column; gap: 4px;
}
.lc-label {
  font-size: 12px; color: var(--text-muted);
}
.lc-value {
  font-size: 14px; color: var(--text-secondary); font-weight: 500;
  &--danger { color: var(--danger); }
}

.lc-footer {
  display: flex; justify-content: space-between; align-items: center;
  margin-top: 8px;
}
.lc-hint {
  font-size: 13px; color: var(--text-muted); max-width: 400px; line-height: 1.6;
}
</style>
