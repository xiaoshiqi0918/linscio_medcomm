<template>
  <div class="dashboard-page page-shell" :class="{ compact: isCompact }">
    <header class="dash-header">
      <div class="container">
        <div class="user-info">
          <span class="avatar">{{ profile?.username?.charAt(0)?.toUpperCase() || '?' }}</span>
          <div>
            <div class="name">{{ profile?.username }}</div>
            <div class="meta">注册于 {{ profile?.created_at ? formatDate(profile.created_at) : '—' }}</div>
          </div>
        </div>
        <div class="badge" :class="license?.is_activated ? 'active' : 'inactive'">
          {{ license?.is_activated ? `已激活 · 维护期至 ${formatDate(license.expires_at)}` : '未激活' }}
        </div>
      </div>
    </header>

    <div class="container main">
      <section class="card card-base">
        <h2>我的授权</h2>
        <template v-if="!license?.is_activated">
          <p class="hint">请输入授权码以激活软件使用权，激活后可在「下载」页获取安装包</p>
          <div class="activate-row">
            <input v-model="activateCode" type="text" placeholder="LINSCIO-XXXX-XXXX-XXXX-XXXX" class="code-input" />
            <button class="btn btn-base btn-primary-ui" :disabled="activating || !activateCode.trim()" @click="doActivate">
              {{ activating ? '激活中…' : '立即激活' }}
            </button>
          </div>
          <p v-if="activateError" class="error">{{ activateError }}</p>
          <p class="note">暂无授权码？请联系管理员获取</p>
        </template>
        <template v-else>
          <p class="success-msg">✅ 授权已激活</p>
          <p>套餐：{{ license.plan_name || 'LinScio AI' }} · {{ license.period_name || '标准版' }}</p>
          <p>激活时间：{{ formatDate(license.activated_at) }}</p>
          <p><strong>维护期至：{{ formatDate(license.expires_at) }}</strong>（剩余 {{ license.days_remaining ?? 0 }} 天）</p>
          <p class="muted-note">维护期内可正常使用软件；到期后续交年维护费可延长使用。</p>

          <div class="update-license-section">
            <p class="update-label">更换授权码</p>
            <p class="update-hint">若使用新的授权码，输入后点击「更新」即可用新授权码激活本账户；原授权码将解除绑定。</p>
            <div class="activate-row">
              <input v-model="updateCode" type="text" placeholder="LINSCIO-XXXX-XXXX-XXXX-XXXX" class="code-input" />
              <button class="btn btn-base btn-secondary" :disabled="updating || !updateCode.trim()" @click="doUpdateLicense">
                {{ updating ? '更新中…' : '更新' }}
              </button>
            </div>
            <p v-if="updateError" class="error">{{ updateError }}</p>
          </div>

          <p class="sub-link"><router-link to="/dashboard/machines">管理已绑定机器 →</router-link></p>
          <p class="sub-link"><router-link to="/dashboard/quota">查看生成次数 →</router-link></p>
        </template>
      </section>

      <section class="card card-base" :class="{ locked: !license?.is_activated }">
        <h2>下载 <span v-if="!license?.is_activated" class="lock-badge">🔒</span></h2>
        <template v-if="!license?.is_activated">
          <p class="locked-hint">请先完成上方授权激活</p>
        </template>
        <template v-else>
          <p class="section-desc">激活后请前往「下载」页获取 LinScio AI 安装包。</p>
          <div class="download-cta">
            <router-link to="/download" class="btn btn-base btn-primary-ui">前往下载页</router-link>
          </div>
          <router-link to="/docs" class="doc-link">查看完整安装文档 →</router-link>
        </template>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { user as userApi } from '../api'

const authStore = useAuthStore()
const profile = computed(() => authStore.profile)

const license = ref(null)
const activateCode = ref('')
const activating = ref(false)
const activateError = ref('')
const updateCode = ref('')
const updating = ref(false)
const updateError = ref('')
const isCompact = ref(false)

function formatDate(d) {
  if (!d) return '—'
  const x = typeof d === 'string' ? new Date(d) : d
  return x.toLocaleDateString('zh-CN')
}

async function loadLicense() {
  try {
    const { data } = await userApi.license()
    license.value = data
  } catch {
    license.value = null
  }
}

async function doActivate() {
  activateError.value = ''
  activating.value = true
  try {
    await userApi.activate(activateCode.value.trim())
    await loadLicense()
    activateCode.value = ''
  } catch (e) {
    const d = e.response?.data?.detail
    if (typeof d === 'string') activateError.value = d
    else if (Array.isArray(d) && d[0]?.msg) activateError.value = d[0].msg
    else activateError.value = '激活失败，请检查授权码是否正确或已使用'
  } finally {
    activating.value = false
  }
}

async function doUpdateLicense() {
  updateError.value = ''
  updating.value = true
  try {
    await userApi.updateLicense(updateCode.value.trim())
    await loadLicense()
    updateCode.value = ''
  } catch (e) {
    const d = e.response?.data?.detail
    if (typeof d === 'string') updateError.value = d
    else if (Array.isArray(d) && d[0]?.msg) updateError.value = d[0].msg
    else updateError.value = '更新授权码失败，请检查新授权码是否正确或未被使用'
  } finally {
    updating.value = false
  }
}


function setupCompactMode() {
  const forced = localStorage.getItem('portal_compact')
  if (forced === '1') {
    isCompact.value = true
    return
  }
  if (forced === '0') {
    isCompact.value = false
    return
  }
  isCompact.value = window.innerWidth <= 1366
}

onMounted(async () => {
  setupCompactMode()
  if (!authStore.isLoggedIn) {
    const ok = await authStore.fetchProfile()
    if (!ok) return
  }
  await loadLicense()
})
</script>

<style scoped>
.dashboard-page { padding-top: 68px; color: var(--color-text-body); }
.dash-header { background: var(--color-bg-base); border-bottom: 1px solid var(--color-border-soft); padding: 18px 24px; }
.container { max-width: 860px; margin: 0 auto; }
.user-info { display: flex; align-items: center; gap: 12px; }
.avatar { width: 40px; height: 40px; border-radius: 50%; background: linear-gradient(135deg, #2563eb, #1d4ed8); color: #fff; display: flex; align-items: center; justify-content: center; font-weight: 700; }
.name { font-weight: 700; color: var(--color-text-strong); }
.meta { font-size: var(--fs-sm); color: var(--color-text-muted); }
.badge { display: inline-block; margin-top: 8px; padding: 4px 10px; border-radius: var(--radius-pill); font-size: var(--fs-xs); }
.badge.active { background: rgba(0,229,160,.15); color: #00e5a0; }
.badge.inactive { background: #e5e7eb; color: #64748b; }

.main { padding: 18px 24px 28px; }
.card { padding: 20px; border-radius: 14px; margin-bottom: 12px; }
.card h2 { font-size: 16px; margin-bottom: 10px; display: flex; align-items: center; gap: 6px; }
.card-icon { font-size: 1em; }
.lock-badge { opacity: .85; font-size: 15px; }
.card.locked { opacity: .88; }
.locked-hint { color: var(--color-text-muted); }
.hint { color: var(--color-text-muted); margin-bottom: 10px; font-size: var(--fs-md); }
.activate-row { display: flex; gap: 8px; margin-bottom: 6px; }
.code-input { flex: 1; padding: 9px 10px; border: 1.5px solid #cbd5e1; border-radius: 9px; font-family: 'JetBrains Mono', monospace; font-size: var(--fs-xs); background: #fff; color: var(--color-text-strong); }
.code-input:focus { outline: none; border-color: #60a5fa; box-shadow: 0 0 0 3px rgba(59,130,246,.08); }
.note, .success-msg { font-size: var(--fs-sm); color: var(--color-text-muted); margin-top: 10px; }
.success-msg { color: #00e5a0; }
.download-cta { margin-bottom: 14px; }
.doc-link { font-size: var(--fs-md); color: var(--color-brand-700); }
.error { color: #ef4444; font-size: var(--fs-sm); margin-top: 8px; }
.muted-note { font-size: var(--fs-sm); color: var(--color-text-muted); margin-top: 8px; }
.section-desc { font-size: var(--fs-md); color: var(--color-text-muted); margin-bottom: 12px; }
.sub-link { margin-top: 10px; font-size: 14px; }
.sub-link a { color: var(--color-brand-700); }
.update-license-section { margin-top: 16px; padding-top: 14px; border-top: 1px solid var(--color-border-soft); }
.update-label { font-weight: 700; margin-bottom: 6px; }
.update-hint { font-size: var(--fs-sm); color: var(--color-text-muted); margin-bottom: 10px; }

.btn { padding: 7px 11px; border-radius: 9px; font-weight: 600; font-size: 12px; cursor: pointer; border: 1px solid transparent; }
.btn-secondary { background: transparent; color: var(--color-text-body); border-color: #cbd5e1; }

@media (max-width: 640px) { .activate-row { flex-direction: column; } }


/* compact 开关：可通过 localStorage.portal_compact = "1" 强制启用；"0" 强制关闭 */
.compact .main { padding-top: 14px; padding-bottom: 20px; }
.compact .card { padding: 18px; border-radius: 12px; }
.compact .btn { padding: 5px 9px; font-size: 11px; }
.compact .table-wrap { margin-top: 12px; }
.compact .machine-table,
.compact .quota-table { font-size: 11px; }
.compact .machine-table th,
.compact .machine-table td,
.compact .quota-table th,
.compact .quota-table td { padding: 6px 8px; }
.compact .machine-table th,
.compact .quota-table th { font-size: 11px; }

</style>
