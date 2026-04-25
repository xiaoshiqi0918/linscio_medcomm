<template>
  <div class="page">
    <h1 class="page__title">我的学科包</h1>
    <p class="page__subtitle">学科包一次购买永久有效，软件启动时自动检测并下载更新。</p>

    <div v-if="loading" class="text-muted mt-3">加载中...</div>

    <div v-else>
      <div v-if="specialties.length" class="spec-list">
        <div v-for="s in specialties" :key="s.id + s.product_id" class="card spec-card">
          <!-- Header -->
          <div class="sc-header">
            <div class="sc-name">
              <span class="sc-title">{{ s.name || s.id }}</span>
              <span class="sc-product">{{ s.product_id }}</span>
            </div>
            <span class="sc-badge" :class="badgeClass(s)">{{ statusText(s) }}</span>
          </div>

          <!-- Info -->
          <div class="sc-info">
            <div class="sc-info__item">
              <span class="sc-label">最新版本</span>
              <span class="sc-value">{{ s.remote_version || '--' }}</span>
            </div>
            <div class="sc-info__item">
              <span class="sc-label">已安装版本</span>
              <span class="sc-value" :class="{ 'sc-value--warn': hasUpdate(s) }">
                {{ s.local_version || '--' }}
              </span>
            </div>
            <div class="sc-info__item">
              <span class="sc-label">购买日期</span>
              <span class="sc-value">{{ s.purchased_at ? formatDate(s.purchased_at) : '--' }}</span>
            </div>
          </div>

          <!-- Footer -->
          <div class="sc-footer">
            <p class="sc-hint">{{ hintText(s) }}</p>
            <div class="sc-footer__actions">
              <a
                v-if="!s.local_version || hasUpdate(s)"
                :href="buildDeepLink(s)"
                class="btn btn--primary btn--sm"
              >打开 MedComm 安装</a>
              <button class="btn btn--ghost">更新日志</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Bottom CTA -->
      <div class="spec-cta">
        <p class="spec-cta__title">想要更多学科包？</p>
        <p class="spec-cta__desc">
          学科包目前处于即将上线阶段，<br/>
          如需了解请<router-link to="/contact" class="spec-cta__link">联系我们</router-link>。
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { licenseStatusAll } from '@/api'

interface SpecialtyItem {
  id: string
  name: string
  product_id: string
  remote_version: string | null
  local_version: string | null
  purchased_at: string | null
}

const loading = ref(true)
const specialties = ref<SpecialtyItem[]>([])

onMounted(async () => {
  try {
    const { data } = await licenseStatusAll()
    const allSpecs: SpecialtyItem[] = []
    for (const lic of data.licenses || []) {
      if (lic.specialties) {
        for (const s of lic.specialties) {
          allSpecs.push({ ...s, product_id: lic.product_name || lic.product_id })
        }
      }
    }
    if (!allSpecs.length) {
      const specResp = await import('@/api').then(m => m.getUserSpecialties())
      for (const s of specResp.data.specialties || []) {
        allSpecs.push({
          id: s.id,
          name: s.id,
          product_id: s.product_id,
          remote_version: null,
          local_version: null,
          purchased_at: s.purchased_at,
        })
      }
    }
    specialties.value = allSpecs
  } catch { /* interceptor */ }
  loading.value = false
})

function hasUpdate(s: SpecialtyItem) {
  return s.local_version && s.remote_version && s.local_version !== s.remote_version
}

function badgeClass(s: SpecialtyItem) {
  if (!s.local_version) return 'sc-badge--gray'
  if (!s.remote_version) return 'sc-badge--gray'
  return s.local_version === s.remote_version ? 'sc-badge--green' : 'sc-badge--orange'
}

function statusText(s: SpecialtyItem) {
  if (!s.local_version) return '未安装'
  if (!s.remote_version) return '未知'
  return s.local_version === s.remote_version ? '已是最新' : '有更新'
}

function hintText(s: SpecialtyItem) {
  if (!s.local_version) return '请先打开软件，软件会自动检测并下载可用学科包。'
  if (hasUpdate(s)) return '软件启动时将自动检测并下载更新，也可在软件内手动触发。'
  return '当前已是最新版本。'
}

function formatDate(iso: string) {
  return iso.slice(0, 10)
}

function buildDeepLink(s: SpecialtyItem) {
  return `linscio://specialty/new?ids=${encodeURIComponent(s.id)}`
}
</script>

<style scoped lang="scss">
.spec-list {
  display: flex; flex-direction: column; gap: 20px;
}

.spec-card {
  padding: 28px 32px;
}

/* ── Header ── */
.sc-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 24px;
}
.sc-name {
  display: flex; align-items: center; gap: 12px;
}
.sc-title {
  font-size: 17px; font-weight: 500; color: var(--text-secondary);
}
.sc-product {
  padding: 2px 10px; border: 1px solid var(--border); border-radius: 4px;
  font-size: 12px; color: var(--text-muted); background: transparent;
}

.sc-badge {
  padding: 3px 12px; border-radius: 4px; font-size: 12px; font-weight: 500;

  &--green { border: 1px solid var(--success); color: var(--success); }
  &--orange { border: 1px solid #e67e22; color: #e67e22; }
  &--gray { border: 1px solid var(--border); color: var(--text-muted); }
}

/* ── Info ── */
.sc-info {
  display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0;
  margin-bottom: 24px;
}
.sc-info__item {
  display: flex; flex-direction: column; gap: 4px;
}
.sc-label { font-size: 12px; color: var(--text-muted); }
.sc-value {
  font-size: 14px; color: var(--text-secondary); font-weight: 500;
  &--warn { color: #e67e22; }
}

/* ── Footer ── */
.sc-footer {
  display: flex; justify-content: space-between; align-items: center;
}
.sc-footer__actions {
  display: flex; align-items: center; gap: 10px;
}
.sc-hint {
  font-size: 13px; color: var(--text-muted); max-width: 420px; line-height: 1.6;
}
.btn--primary {
  padding: 6px 18px; border-radius: 6px; font-size: 13px; font-weight: 500;
  color: #fff; background: var(--text-secondary, #333); text-decoration: none;
  transition: opacity 0.15s;
  &:hover { opacity: 0.85; }
}
.btn--sm { padding: 5px 14px; font-size: 12px; }

/* ── Bottom CTA ── */
.spec-cta {
  text-align: center; padding: 48px 0 24px;
}
.spec-cta__title {
  font-size: 15px; color: var(--text-secondary); margin-bottom: 8px;
}
.spec-cta__desc {
  font-size: 13px; color: var(--text-muted); line-height: 1.8;
}
.spec-cta__link {
  color: var(--text-secondary); text-decoration: underline;
  text-underline-offset: 3px;
  &:hover { color: var(--text-primary); }
}
</style>
