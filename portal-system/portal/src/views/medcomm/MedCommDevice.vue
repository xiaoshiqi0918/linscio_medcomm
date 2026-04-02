<template>
  <div class="page container-shell">
    <h1>我的设备</h1>

    <div v-if="base" class="device-card">
      <div class="device-icon">💻</div>
      <div class="device-info">
        <div class="device-name">{{ base.device_name || '暂未绑定设备' }}</div>
        <div v-if="base.token_created_at" class="device-meta">绑定时间：{{ formatDate(base.token_created_at) }}</div>
        <div class="device-meta">本周期剩余换机次数：{{ rebindRemaining }} 次</div>
      </div>
    </div>

    <div class="section">
      <h2 class="section-title">需要换机？</h2>
      <ol class="steps">
        <li>① 在新设备打开软件</li>
        <li>② 软件会要求输入账号密码，完成后显示 6 位换机码</li>
        <li>③ 在下方输入换机码完成换绑</li>
      </ol>
    </div>

    <div class="box">
      <label>6 位换机码</label>
      <input v-model="code" maxlength="6" class="code" placeholder="000000" />
      <button class="btn" :disabled="loading" @click="verify">确认换机</button>
      <p v-if="msg" :class="ok ? 'ok' : 'err'">{{ msg }}</p>
      <div v-if="deepLink" class="deeplink">
        <p>新设备 Deep Link：</p>
        <a :href="deepLink">{{ deepLink }}</a>
      </div>
    </div>

    <p class="footnote">换机码有效期 5 分钟，超时请在软件重新获取。本周期剩余自助换机次数：{{ rebindRemaining }} 次（超出请联系客服）。</p>

    <nav class="subnav">
      <router-link to="/medcomm/activate">← 返回激活页</router-link>
      <router-link to="/medcomm/help">帮助中心</router-link>
    </nav>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { medcommDevice } from '../../api/medcomm'
import { useMedcommAuthStore } from '../../stores/medcommAuth'

const medcommStore = useMedcommAuthStore()
const base = ref(null)
const rebindRemaining = ref(2)

function formatDate(s) {
  if (!s) return '—'
  try {
    const d = new Date(s)
    return d.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch {
    return s
  }
}

onMounted(async () => {
  const data = await medcommStore.fetchLicenseStatus()
  if (data?.base) {
    base.value = data.base
    if (data.base.rebind_remaining != null) rebindRemaining.value = data.base.rebind_remaining
  }
})

const code = ref('')
const loading = ref(false)
const msg = ref('')
const ok = ref(false)
const deepLink = ref('')

async function verify() {
  msg.value = ''
  deepLink.value = ''
  loading.value = true
  try {
    const { data } = await medcommDevice.verifyChangeCode({ code: code.value.trim() })
    if (data.success) {
      ok.value = true
      rebindRemaining.value = data.rebind_remaining ?? 0
      msg.value = `换机成功，剩余自助次数：${data.rebind_remaining ?? '—'}`
      deepLink.value = data.deep_link || ''
    } else {
      ok.value = false
      const map = {
        code_invalid: '换机码无效',
        code_expired: '换机码已过期',
        rate_limited: '尝试过多，请稍后再试',
      }
      msg.value = map[data.error] || data.error || '失败'
    }
  } catch (e) {
    ok.value = false
    msg.value = e.response?.data?.detail || '请求失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.page { max-width: 520px; margin: 0 auto; padding: 100px 16px; }
.device-card {
  display: flex; align-items: flex-start; gap: 14px; padding: 18px; margin-bottom: 20px;
  background: #fff; border: 1px solid #e2e8f0; border-radius: 12px;
}
.device-icon { font-size: 24px; }
.device-info { flex: 1; }
.device-name { font-weight: 600; font-size: 16px; color: #0f172a; margin-bottom: 6px; }
.device-meta { font-size: 13px; color: #64748b; margin-top: 4px; }
.section { margin-bottom: 20px; }
.section-title { font-size: 15px; font-weight: 600; margin-bottom: 10px; color: #334155; }
.steps { margin: 0; padding-left: 20px; color: #64748b; line-height: 1.9; font-size: 14px; }
.footnote { font-size: 12px; color: #94a3b8; margin-top: 16px; line-height: 1.6; }
.box { background: #fff; padding: 24px; border-radius: 12px; border: 1px solid #e2e8f0; }
label { display: block; font-size: 13px; margin-bottom: 8px; }
.code {
  width: 100%; font-size: 1.5rem; letter-spacing: 0.3em; text-align: center;
  padding: 12px; border-radius: 8px; border: 2px solid #cbd5e1; box-sizing: border-box;
}
.btn { margin-top: 16px; padding: 12px 24px; background: #2563eb; color: #fff; border: none; border-radius: 8px; cursor: pointer; }
.ok { color: #059669; margin-top: 12px; }
.err { color: #dc2626; margin-top: 12px; }
.deeplink { margin-top: 16px; word-break: break-all; font-size: 13px; }
.subnav { margin-top: 24px; display: flex; gap: 16px; }
.subnav a { color: #2563eb; }
</style>
