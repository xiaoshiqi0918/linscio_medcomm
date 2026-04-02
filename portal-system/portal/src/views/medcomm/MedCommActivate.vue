<template>
  <div class="page container-shell">
    <h1>激活授权码</h1>
    <p class="sub">格式：LINSCIO-XXXX-XXXX-XXXX-XXXX（可粘贴，自动大写）</p>

    <!-- 步骤 1：输入授权码 -->
    <div v-if="step === 1" class="box">
      <input
        v-model="code"
        type="text"
        class="code-input"
        placeholder="LINSCIO-XXXX-XXXX-XXXX-XXXX"
        @input="onCodeInput"
      />
      <button class="btn" :disabled="loading || !code.trim()" @click="validateCode">
        {{ loading ? '验证中…' : '验证授权码' }}
      </button>
      <p v-if="validateError" class="err">{{ validateError }}</p>
    </div>

    <!-- 步骤 2：预览（基础版续费） -->
    <div v-else-if="step === 2 && preview?.license_type === 'basic'" class="box preview-box">
      <p class="success-icon">✅ 授权码有效</p>
      <p class="preview-line">
        类型：{{ preview.is_trial ? '试用版' : '正式版' }}基础版 · 周期：{{ preview.duration_months || 12 }} 个月
      </p>
      <p v-if="preview.current_days_remaining != null" class="preview-line">
        当前剩余：{{ preview.current_days_remaining }} 天
      </p>
      <p class="preview-line">
        激活后到期时间：{{ formatDate(preview.new_expires_at) }}
      </p>
      <label class="row">设备指纹（测试可填 test-fp）</label>
      <input v-model="fingerprint" type="text" class="wide" />
      <label class="row">设备名称</label>
      <input v-model="deviceName" type="text" class="wide" placeholder="例如 MacBook Pro" />
      <button class="btn" :disabled="loading" @click="doActivate">确认激活</button>
      <p v-if="activateError" class="err">{{ activateError }}</p>
      <button type="button" class="link" @click="reset">← 重新输入</button>
    </div>

    <!-- 步骤 2：预览（学科包） -->
    <div v-else-if="step === 2 && preview?.license_type === 'specialty'" class="box preview-box">
      <p class="success-icon">✅ 授权码有效</p>
      <p class="preview-line">类型：学科包 · {{ (preview.specialty_names || []).join('、') }}</p>
      <label class="row">设备指纹</label>
      <input v-model="fingerprint" type="text" class="wide" />
      <label class="row">设备名称</label>
      <input v-model="deviceName" type="text" class="wide" placeholder="例如 MacBook Pro" />
      <button class="btn" :disabled="loading" @click="doActivate">确认激活</button>
      <p v-if="activateError" class="err">{{ activateError }}</p>
      <button type="button" class="link" @click="reset">← 重新输入</button>
    </div>

    <!-- 激活完成：续费 -->
    <div v-else-if="step === 3 && activatedRenewal" class="box result-box">
      <p class="success-icon">✅ 续费成功！授权已延长至 {{ formatDate(activatedExpires) }}</p>
      <p class="hint">无需任何操作，软件将在下次检查授权时自动更新到期时间。（通常在软件启动 10 秒后自动更新）</p>
      <button type="button" class="link" @click="reset">激活其他授权码</button>
    </div>

    <!-- 激活完成：首次激活 -->
    <div v-else-if="step === 3 && !activatedRenewal" class="box result-box">
      <p class="success-icon">✅ 授权激活成功！有效至 {{ formatDate(activatedExpires) }}</p>
      <p class="deeplink-title">请唤起软件完成设备绑定：</p>
      <a
        :href="deepLink"
        class="btn btn-invoke"
        @click.prevent="invokeApp"
      >点击唤起软件</a>
      <div v-if="showFallbackHint" class="fallback-hint">
        <p class="warn-title">⚠️ 未检测到软件响应</p>
        <ul>
          <li>软件未运行：请先打开软件，再点击上方按钮</li>
          <li>软件未安装：<router-link to="/medcomm/download">前往下载软件</router-link>，安装后返回此页面点击唤起</li>
          <li>Token 将保留 30 天，可随时返回此页面重新唤起</li>
        </ul>
      </div>
      <button type="button" class="link" @click="reset">激活其他授权码</button>
    </div>

    <nav class="subnav">
      <router-link to="/medcomm/specialties">我的学科包</router-link>
      <router-link to="/medcomm/download">软件更新与下载</router-link>
      <router-link to="/medcomm/device">换机</router-link>
      <router-link v-if="rebindRemaining > 0" to="/medcomm/device/request">申请换机码</router-link>
      <span v-else class="muted">换机次数已用完，请联系客服</span>
      <router-link to="/medcomm/migration">账号迁移申请</router-link>
      <router-link to="/medcomm/help">帮助中心</router-link>
      <a href="#" class="logout" @click.prevent="doLogout">退出 MedComm</a>
    </nav>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { medcommLicense } from '../../api/medcomm'
import { useMedcommAuthStore } from '../../stores/medcommAuth'

const router = useRouter()
const medcommStore = useMedcommAuthStore()
const rebindRemaining = ref(2)

onMounted(async () => {
  const data = await medcommStore.fetchLicenseStatus()
  if (data?.base?.rebind_remaining != null) rebindRemaining.value = data.base.rebind_remaining
})

function doLogout() {
  medcommStore.logout()
  router.push('/medcomm/login')
}

function formatDate(s) {
  if (!s) return '—'
  try {
    return new Date(s).toLocaleDateString('zh-CN')
  } catch {
    return s
  }
}

const step = ref(1)
const code = ref('')
const fingerprint = ref('test-fingerprint')
const deviceName = ref('')
const loading = ref(false)
const validateError = ref('')
const activateError = ref('')
const preview = ref(null)
const deepLink = ref('')
const activatedRenewal = ref(false)
const activatedExpires = ref('')
const showFallbackHint = ref(false)

function onCodeInput() {
  let s = code.value.toUpperCase().replace(/[^A-Z0-9]/g, '')
  if (s.startsWith('LINSCIO') && s.length >= 7) {
    const rest = s.slice(7)
    if (rest.length <= 12) {
      const parts = [rest.slice(0, 4), rest.slice(4, 8), rest.slice(8, 12)].filter(Boolean)
      code.value = 'LINSCIO-' + parts.join('-').replace(/-+$/, '')
    } else if (rest.length <= 16) {
      const parts = [rest.slice(0, 4), rest.slice(4, 8), rest.slice(8, 12), rest.slice(12, 16)].filter(Boolean)
      code.value = 'LINSCIO-' + parts.join('-').replace(/-+$/, '')
    }
  } else if (s.length === 12 && !s.startsWith('LINSCIO')) {
    code.value = `LINSCIO-${s.slice(0, 4)}-${s.slice(4, 8)}-${s.slice(8, 12)}`
  } else if (s.length === 16 && !s.startsWith('LINSCIO')) {
    code.value = `LINSCIO-${s.slice(0, 4)}-${s.slice(4, 8)}-${s.slice(8, 12)}-${s.slice(12, 16)}`
  }
}

function reset() {
  step.value = 1
  code.value = ''
  preview.value = null
  validateError.value = ''
  activateError.value = ''
  deepLink.value = ''
  showFallbackHint.value = false
}

async function validateCode() {
  validateError.value = ''
  loading.value = true
  try {
    const { data } = await medcommLicense.validate({ code: code.value.trim() })
    if (data.valid) {
      preview.value = data
      step.value = 2
    } else {
      validateError.value = data.error || '授权码无效'
    }
  } catch (e) {
    validateError.value = e.response?.data?.detail || '验证失败'
  } finally {
    loading.value = false
  }
}

async function doActivate() {
  activateError.value = ''
  loading.value = true
  try {
    const { data } = await medcommLicense.activate({
      code: code.value.trim(),
      device_fingerprint: fingerprint.value.trim() || 'web',
      device_name: deviceName.value.trim() || 'Web',
    })
    if (data.success) {
      if (data.rebind_count_reset) rebindRemaining.value = 2
      activatedRenewal.value = !!data.token_unchanged
      activatedExpires.value = data.new_expires_at || ''
      deepLink.value = data.deep_link || ''
      step.value = 3
      if (!data.token_unchanged && data.deep_link) {
        showFallbackHint.value = false
        setTimeout(() => {
          showFallbackHint.value = true
        }, 3000)
      }
    } else {
      const errMap = {
        rate_limit_exceeded: '请求过于频繁，请稍后再试',
        account_locked: '激活失败次数过多，请联系管理员解锁',
        trial_no_specialty: '试用账号不可激活学科包，请先购买正式版授权',
        code_invalid_or_used: '授权码无效或已使用',
      }
      activateError.value = errMap[data.error] || data.message || data.error || '激活失败'
    }
  } catch (e) {
    activateError.value = e.response?.data?.detail || '激活失败'
  } finally {
    loading.value = false
  }
}

function invokeApp() {
  if (deepLink.value) {
    window.location.href = deepLink.value
  }
}
</script>

<style scoped>
.page { max-width: 640px; margin: 0 auto; padding: 100px 16px 48px; }
h1 { font-size: 1.75rem; margin-bottom: 8px; }
.sub { color: #64748b; margin-bottom: 24px; }
.box {
  background: #fff; border-radius: 12px; padding: 24px;
  border: 1px solid #e2e8f0; box-shadow: 0 4px 20px rgba(15,23,42,0.04);
}
.code-input {
  width: 100%; font-size: 1.1rem; letter-spacing: 0.05em;
  padding: 12px; border: 2px solid #cbd5e1; border-radius: 8px; box-sizing: border-box;
}
.row { display: block; margin-top: 16px; font-size: 13px; color: #475569; }
.wide { width: 100%; padding: 10px; margin-top: 6px; border-radius: 8px; border: 1px solid #cbd5e1; box-sizing: border-box; }
.btn {
  margin-top: 20px; padding: 12px 24px; background: #2563eb; color: #fff;
  border: none; border-radius: 8px; font-weight: 600; cursor: pointer; display: block;
}
.btn-invoke { display: inline-block; text-decoration: none; margin-top: 12px; }
.err { color: #dc2626; margin-top: 12px; }
.preview-box .success-icon { color: #059669; font-weight: 600; margin-bottom: 12px; }
.preview-line { margin: 6px 0; color: #334155; }
.result-box .success-icon { color: #059669; font-weight: 600; margin-bottom: 12px; }
.deeplink-title { margin-top: 12px; font-weight: 500; }
.fallback-hint { margin-top: 20px; padding: 16px; background: #fffbeb; border-radius: 8px; border: 1px solid #fde68a; }
.warn-title { font-weight: 600; color: #b45309; margin-bottom: 8px; }
.fallback-hint ul { margin: 8px 0 0; padding-left: 20px; color: #92400e; line-height: 1.8; }
.hint { font-size: 13px; color: #64748b; margin-top: 10px; }
.link { background: none; border: none; color: #2563eb; cursor: pointer; margin-top: 16px; font-size: 14px; }
.subnav { margin-top: 32px; display: flex; gap: 16px; flex-wrap: wrap; }
.subnav a { color: #2563eb; font-size: 14px; }
.subnav a.logout { color: #64748b; }
.subnav .muted { color: #94a3b8; font-size: 14px; }
</style>
