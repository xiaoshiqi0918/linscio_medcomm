<template>
  <div class="page">
    <h1 class="page__title">我的设备</h1>
    <p class="page__subtitle">每个账号同时只能绑定一台设备，换机需通过换机码完成验证。</p>

    <div v-if="loading" class="text-muted mt-3">加载中...</div>

    <div v-else>
      <!-- Current device -->
      <p class="section-label">当前绑定设备</p>

      <div v-if="currentDevice" class="device-card card">
        <div class="dc-header">
          <div class="dc-info">
            <div class="dc-icon">🖥</div>
            <div>
              <h3 class="dc-name">{{ currentDevice.device_name || '未知设备' }}</h3>
              <p class="dc-meta">{{ currentDevice.device_os || 'macOS' }} · {{ currentDevice.device_arch || 'Apple Silicon' }}</p>
            </div>
          </div>
          <span class="badge badge--valid">当前设备</span>
        </div>
        <div class="dc-stats">
          <div class="dc-stat">
            <span class="dc-stat__label">绑定时间</span>
            <span class="dc-stat__value">{{ formatDate(currentDevice.bound_at) }}</span>
          </div>
          <div class="dc-stat">
            <span class="dc-stat__label">最后活跃</span>
            <span class="dc-stat__value">{{ lastActive(currentDevice.last_active_at) }}</span>
          </div>
          <div class="dc-stat">
            <span class="dc-stat__label">本周期剩余换机次数</span>
            <span class="dc-stat__value">{{ currentDevice.rebind_remaining ?? '-' }} 次</span>
          </div>
        </div>
      </div>

      <div v-else class="device-card card">
        <p class="text-muted">尚未绑定设备。请在软件中登录以完成设备绑定。</p>
      </div>

      <!-- Rebind section -->
      <p class="section-label" style="margin-top:36px;">换机</p>

      <div class="rebind-card">
        <h3 class="rebind-title">需要换到新设备？</h3>
        <p class="rebind-desc">换机需要在新设备上获取换机码，再在此处输入完成验证。整个过程约 1 分钟。</p>

        <div class="rebind-steps">
          <div class="rebind-step">
            <span class="step-num">1</span>
            <p>在<strong>新设备</strong>上打开软件，选择「我已有账号，需要换机」</p>
          </div>
          <div class="rebind-step">
            <span class="step-num">2</span>
            <p>输入账号手机号和密码，软件将显示一个 <strong>6 位换机码</strong></p>
          </div>
          <div class="rebind-step">
            <span class="step-num">3</span>
            <p>在下方输入换机码，确认后新设备自动完成绑定</p>
          </div>
        </div>

        <div v-if="verifyError" class="alert alert--error" style="margin-top:16px;">{{ verifyError }}</div>
        <div v-if="verifyResult" class="alert alert--success" style="margin-top:16px;">
          <p>换绑成功！新设备：{{ verifyResult.new_device_name }}</p>
          <a v-if="verifyResult.deep_link" :href="verifyResult.deep_link" class="btn btn--outline mt-1">打开软件完成激活</a>
        </div>

        <template v-if="!verifyResult">
          <p class="code-label">输入换机码</p>
          <div class="code-boxes">
            <input
              v-for="(_, i) in 6"
              :key="i"
              :ref="el => { if (el) codeRefs[i] = el as HTMLInputElement }"
              v-model="digits[i]"
              type="text"
              maxlength="1"
              class="code-box"
              inputmode="numeric"
              @input="onDigitInput(i)"
              @keydown.delete="onDigitBackspace(i, $event)"
              @paste.prevent="onPaste"
            />
          </div>
          <p class="code-hint">换机码有效期 5 分钟，超时请在软件重新获取</p>

          <button class="btn btn--ghost rebind-btn" :disabled="verifyLoading || joinedCode.length < 6" @click="handleVerify">
            {{ verifyLoading ? '验证中...' : '确认换机' }}
          </button>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { licenseStatusAll, deviceVerify } from '@/api'

const loading = ref(true)
const currentDevice = ref<any>(null)
const verifyLoading = ref(false)
const verifyError = ref('')
const verifyResult = ref<any>(null)

const digits = reactive(['', '', '', '', '', ''])
const codeRefs = ref<HTMLInputElement[]>([])

const joinedCode = computed(() => digits.join(''))

onMounted(async () => {
  try {
    const { data } = await licenseStatusAll()
    const active = data.licenses.find((l: any) => l.status !== 'not_activated' && l.device_name)
    if (active) {
      currentDevice.value = {
        device_name: active.device_name || 'Unknown',
        device_os: active.device_os || 'macOS',
        device_arch: active.device_arch || 'Apple Silicon',
        bound_at: active.bound_at || active.expires_at,
        last_active_at: active.last_active_at,
        rebind_remaining: active.rebind_remaining,
        product_id: active.product_id,
      }
    }
  } catch {}
  loading.value = false
})

function onDigitInput(i: number) {
  const val = digits[i]
  if (val && /[0-9]/.test(val)) {
    if (i < 5) codeRefs.value[i + 1]?.focus()
  } else {
    digits[i] = ''
  }
}

function onDigitBackspace(i: number, e: KeyboardEvent) {
  if (!digits[i] && i > 0) {
    codeRefs.value[i - 1]?.focus()
  }
}

function onPaste(e: ClipboardEvent) {
  const text = (e.clipboardData?.getData('text') || '').replace(/\D/g, '').slice(0, 6)
  for (let i = 0; i < 6; i++) {
    digits[i] = text[i] || ''
  }
  const focusIdx = Math.min(text.length, 5)
  codeRefs.value[focusIdx]?.focus()
}

async function handleVerify() {
  verifyLoading.value = true
  verifyError.value = ''
  try {
    const productId = currentDevice.value?.product_id || ''
    const { data } = await deviceVerify({ product_id: productId, code: joinedCode.value })
    verifyResult.value = data
  } catch (e: any) {
    verifyError.value = e.response?.data?.detail || '验证失败'
  } finally {
    verifyLoading.value = false
  }
}

function formatDate(iso: string | null) {
  if (!iso) return '--'
  return iso.slice(0, 10)
}

function lastActive(iso: string | null) {
  if (!iso) return '--'
  const d = new Date(iso)
  const now = new Date()
  const diff = Math.floor((now.getTime() - d.getTime()) / 86400000)
  if (diff === 0) return '今天'
  if (diff === 1) return '昨天'
  return `${diff} 天前`
}
</script>

<style scoped lang="scss">
.section-label {
  font-size: 13px; color: var(--text-muted); margin-bottom: 14px;
}

/* ── Device card ── */
.device-card { padding: 24px 28px; }

.dc-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 20px;
}
.dc-info { display: flex; align-items: center; gap: 14px; }
.dc-icon {
  width: 44px; height: 44px; border-radius: 10px;
  background: var(--bg-surface); border: 1px solid var(--border);
  display: flex; align-items: center; justify-content: center;
  font-size: 20px;
}
.dc-name { font-size: 16px; font-weight: 500; color: var(--text-secondary); margin-bottom: 2px; }
.dc-meta { font-size: 13px; color: var(--text-muted); }

.dc-stats {
  display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0;
}
.dc-stat { display: flex; flex-direction: column; gap: 4px; }
.dc-stat__label { font-size: 12px; color: var(--text-muted); }
.dc-stat__value { font-size: 14px; color: var(--text-secondary); font-weight: 500; }

/* ── Rebind card ── */
.rebind-card {
  background: var(--bg-card); border: 1px solid var(--border-card); border-radius: 16px; padding: 32px;
  color: var(--text-primary);
}
.rebind-title { font-size: 17px; font-weight: 600; color: var(--text-primary); margin-bottom: 10px; }
.rebind-desc { font-size: 14px; color: var(--text-secondary); line-height: 1.7; margin-bottom: 24px; }

.rebind-steps {
  display: flex; flex-direction: column; gap: 12px; margin-bottom: 28px;
}
.rebind-step {
  display: flex; align-items: flex-start; gap: 12px;
  padding-bottom: 12px; border-bottom: 1px solid var(--border);
  p { font-size: 14px; color: var(--text-secondary); line-height: 1.6; }
  strong { color: var(--text-primary); }
  &:last-child { border-bottom: none; }
}
.step-num {
  width: 26px; height: 26px; border-radius: 50%;
  background: var(--bg-surface); color: var(--text-muted); flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 600;
}

.code-label { font-size: 13px; color: var(--text-muted); margin-bottom: 10px; }
.code-boxes {
  display: flex; gap: 10px; margin-bottom: 10px;
}
.code-box {
  width: 52px; height: 52px; border: 1px solid var(--border); border-radius: 8px;
  text-align: center; font-size: 22px; font-weight: 600;
  font-family: 'SF Mono', 'Fira Code', monospace;
  background: var(--bg-card); color: var(--text-primary); outline: none;
  transition: border-color 0.15s;
  &:focus { border-color: var(--primary); }
}
.code-hint { font-size: 12px; color: var(--text-muted); margin-bottom: 20px; }

.rebind-btn {
  border-color: var(--border); color: var(--text-secondary);
  &:hover { border-color: var(--primary); color: var(--primary); }
}

@media (max-width: 640px) {
  .dc-stats { grid-template-columns: 1fr; gap: 12px; }
  .code-boxes { gap: 6px; }
  .code-box { width: 44px; height: 44px; font-size: 18px; }
}
</style>
