<template>
  <div class="page container-shell">
    <h1>申请换机码</h1>
    <p class="sub">
      在新设备上打开此页面，输入 MedComm 账号密码后可获取 6 位换机码。
      然后在<strong>旧设备</strong>的浏览器中登录门户，前往「换机」页输入该换机码完成换绑。
    </p>

    <div class="box">
      <label>邮箱或手机号</label>
      <input v-model="credential" type="text" class="wide" placeholder="user@email.com 或 13800138000" />
      <label>密码</label>
      <input v-model="password" type="password" class="wide" />
      <label>新设备指纹（软件端会显示，测试可填 test-fp）</label>
      <input v-model="newFingerprint" type="text" class="wide" placeholder="test-fingerprint" />
      <label>新设备名称</label>
      <input v-model="deviceName" type="text" class="wide" placeholder="例如 MacBook Pro 新" />
      <button class="btn" :disabled="loading" @click="request">获取换机码</button>
      <p v-if="err" class="err">{{ err }}</p>

      <div v-if="code" class="result">
        <p class="label">6 位换机码（5 分钟内有效）</p>
        <p class="code-display">{{ code }}</p>
        <p class="hint">请到旧设备登录门户后，在「换机」页输入此码完成换绑。</p>
        <router-link to="/medcomm/device" class="link">已登录？前往验证换机码 →</router-link>
      </div>
    </div>

    <router-link to="/medcomm/login" class="back">← 返回 MedComm 登录</router-link>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { medcommDevice } from '../../api/medcomm'

const credential = ref('')
const password = ref('')
const newFingerprint = ref('test-fingerprint')
const deviceName = ref('')
const loading = ref(false)
const err = ref('')
const code = ref('')

async function request() {
  err.value = ''
  code.value = ''
  loading.value = true
  try {
    const { data } = await medcommDevice.requestChangeCode({
      credential: credential.value.trim(),
      password: password.value,
      new_fingerprint: newFingerprint.value.trim() || 'web',
      new_device_name: deviceName.value.trim() || 'Web',
    })
    if (data.success) {
      code.value = data.code || ''
    } else {
      const map = {
        invalid_credential: '账号或密码错误',
        account_disabled: '账号已被封禁',
        no_license: '未找到有效授权，请先激活授权码',
        rebind_limit_exceeded: '本周期换机次数已用完，请联系客服',
        rate_limited: '请求过于频繁，请稍后再试',
      }
      err.value = data.message || map[data.error] || data.error || '申请失败'
    }
  } catch (e) {
    err.value = e.response?.data?.detail || '请求失败'
    if (e.response?.status === 429) err.value = '请求过于频繁，请稍后再试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.page { max-width: 520px; margin: 0 auto; padding: 100px 16px; }
.sub { color: #64748b; margin-bottom: 24px; line-height: 1.7; }
.sub strong { color: #334155; }
.box { background: #fff; padding: 24px; border-radius: 12px; border: 1px solid #e2e8f0; }
label { display: block; font-size: 13px; margin: 14px 0 6px; color: #475569; }
.wide { width: 100%; padding: 10px; border-radius: 8px; border: 1px solid #cbd5e1; box-sizing: border-box; }
.btn { margin-top: 20px; padding: 12px 24px; background: #2563eb; color: #fff; border: none; border-radius: 8px; font-weight: 600; cursor: pointer; }
.err { color: #dc2626; margin-top: 12px; }
.result { margin-top: 24px; padding: 20px; background: #f0fdf4; border-radius: 8px; }
.label { font-size: 13px; color: #475569; margin-bottom: 8px; }
.code-display { font-size: 2rem; font-weight: 700; letter-spacing: 0.3em; color: #059669; font-family: ui-monospace, monospace; }
.hint { font-size: 13px; color: #64748b; margin-top: 12px; }
.link { display: inline-block; margin-top: 12px; color: #2563eb; font-size: 14px; }
.back { display: inline-block; margin-top: 24px; color: #2563eb; font-size: 14px; }
</style>
