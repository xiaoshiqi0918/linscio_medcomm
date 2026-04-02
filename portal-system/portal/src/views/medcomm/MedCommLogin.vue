<template>
  <div class="page">
    <div class="card">
      <h1>MedComm 账号</h1>
      <p class="hint">医学科普写作软件（LinScio MedComm）门户登录，与 LinScio AI 主账号独立。</p>

      <div class="tabs">
        <button :class="{ active: tab === 'login' }" @click="switchTab('login')">登录</button>
        <button :class="{ active: tab === 'register' }" @click="switchTab('register')">注册</button>
        <button :class="{ active: tab === 'forgot' }" @click="switchTab('forgot')">忘记密码</button>
      </div>

      <!-- 登录 -->
      <form v-if="tab === 'login'" @submit.prevent="onLogin">
        <label>邮箱 / 手机号 / 用户名</label>
        <input v-model="credential" type="text" required placeholder="user@email.com 或 13800138000 或 myuser" />
        <label>密码</label>
        <input v-model="password" type="password" required minlength="8" />
        <p v-if="err" class="err">{{ err }}</p>
        <button type="submit" class="btn" :disabled="loading">登录</button>
      </form>

      <!-- 注册：步骤1 获取验证码 -->
      <form v-else-if="tab === 'register' && !registerStep2" @submit.prevent="onRegisterSendCode">
        <label>类型</label>
        <select v-model="credType">
          <option value="email">邮箱</option>
          <option value="phone">手机号</option>
          <option value="username">用户名</option>
        </select>
        <label>{{ credType === 'email' ? '邮箱' : credType === 'phone' ? '手机号' : '用户名（3-32 位字母数字下划线）' }}</label>
        <input v-model="credential" type="text" required />
        <label>密码（≥8 位，含字母与数字）</label>
        <input v-model="password" type="password" required minlength="8" />
        <p v-if="err" class="err">{{ err }}</p>
        <button type="submit" class="btn" :disabled="loading">获取验证码</button>
      </form>

      <!-- 注册：步骤2 输入验证码完成 -->
      <form v-else-if="tab === 'register' && registerStep2" @submit.prevent="onRegisterVerify">
        <p class="hint">已向 {{ credential }} 发送验证码（开发环境可用 123456）</p>
        <label>验证码</label>
        <input v-model="verifyCode" type="text" maxlength="6" placeholder="6 位数字" />
        <p v-if="err" class="err">{{ err }}</p>
        <button type="submit" class="btn" :disabled="loading">完成注册</button>
        <button type="button" class="btn-link" @click="registerStep2 = false">← 返回修改</button>
      </form>

      <!-- 忘记密码：步骤1 获取验证码 -->
      <form v-else-if="tab === 'forgot' && !forgotStep2" @submit.prevent="onForgotSendCode">
        <label>邮箱 / 手机号 / 用户名</label>
        <input v-model="credential" type="text" required placeholder="用于找回密码的账号" />
        <p v-if="err" class="err">{{ err }}</p>
        <button type="submit" class="btn" :disabled="loading">发送重置验证码</button>
      </form>

      <!-- 忘记密码：步骤2 输入验证码与新密码 -->
      <form v-else-if="tab === 'forgot' && forgotStep2" @submit.prevent="onForgotReset">
        <p class="hint">已向 {{ credential }} 发送重置验证码（开发环境可用 123456）</p>
        <label>验证码</label>
        <input v-model="verifyCode" type="text" maxlength="6" placeholder="6 位数字" />
        <label>新密码（≥8 位）</label>
        <input v-model="newPassword" type="password" required minlength="8" />
        <p v-if="err" class="err">{{ err }}</p>
        <button type="submit" class="btn" :disabled="loading">重置密码</button>
        <button type="button" class="btn-link" @click="forgotStep2 = false">← 返回</button>
      </form>

      <router-link to="/" class="back">← 返回首页</router-link>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useMedcommAuthStore } from '../../stores/medcommAuth'
import { medcommAuth } from '../../api/medcomm'

const router = useRouter()
const store = useMedcommAuthStore()
const tab = ref('login')
const credential = ref('')
const password = ref('')
const newPassword = ref('')
const credType = ref('email')
const verifyCode = ref('')
const registerStep2 = ref(false)
const forgotStep2 = ref(false)
const err = ref('')
const loading = ref(false)

function switchTab(t) {
  tab.value = t
  err.value = ''
  registerStep2.value = false
  forgotStep2.value = false
}

async function onLogin() {
  err.value = ''
  loading.value = true
  try {
    await store.login(credential.value.trim(), password.value)
    const redir = router.currentRoute.value.query.redirect
    router.push(typeof redir === 'string' && redir.startsWith('/medcomm') ? redir : '/medcomm/activate')
  } catch (e) {
    err.value = e.response?.data?.detail || '登录失败'
  } finally {
    loading.value = false
  }
}

async function onRegisterSendCode() {
  err.value = ''
  loading.value = true
  try {
    await medcommAuth.register({
      credential: credential.value.trim(),
      password: password.value,
      credential_type: credType.value,
    })
    registerStep2.value = true
    verifyCode.value = ''
  } catch (e) {
    err.value = e.response?.data?.detail || '获取验证码失败'
  } finally {
    loading.value = false
  }
}

async function onRegisterVerify() {
  err.value = ''
  loading.value = true
  try {
    await medcommAuth.verify({
      credential: credential.value.trim(),
      code: verifyCode.value.trim(),
    })
    tab.value = 'login'
    registerStep2.value = false
    err.value = ''
    alert('注册成功，请登录')
  } catch (e) {
    err.value = e.response?.data?.detail || '验证失败'
  } finally {
    loading.value = false
  }
}

async function onForgotSendCode() {
  err.value = ''
  loading.value = true
  try {
    await medcommAuth.forgotPassword({ credential: credential.value.trim() })
    forgotStep2.value = true
    verifyCode.value = ''
    newPassword.value = ''
  } catch (e) {
    err.value = e.response?.data?.detail || '发送失败'
  } finally {
    loading.value = false
  }
}

async function onForgotReset() {
  err.value = ''
  loading.value = true
  try {
    await medcommAuth.resetPassword({
      credential: credential.value.trim(),
      code: verifyCode.value.trim(),
      new_password: newPassword.value,
    })
    tab.value = 'login'
    forgotStep2.value = false
    err.value = ''
    alert('密码已重置，请登录')
  } catch (e) {
    err.value = e.response?.data?.detail || '重置失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.page { min-height: 100vh; padding: 100px 16px; background: linear-gradient(160deg, #f0f9ff, #e0e7ff); }
.card {
  max-width: 420px; margin: 0 auto; background: #fff; border-radius: 16px;
  padding: 32px; box-shadow: 0 12px 40px rgba(15,23,42,0.08);
}
h1 { font-size: 1.5rem; margin-bottom: 8px; }
.hint { color: #64748b; font-size: 13px; margin-bottom: 20px; line-height: 1.5; }
.tabs { display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; }
.tabs button {
  padding: 8px 14px; border: 1px solid #e2e8f0; background: #f8fafc;
  border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 13px;
}
.tabs button.active { background: #2563eb; color: #fff; border-color: #2563eb; }
label { display: block; font-size: 13px; color: #475569; margin: 12px 0 6px; }
input, select {
  width: 100%; padding: 10px 12px; border: 1px solid #cbd5e1; border-radius: 8px;
  box-sizing: border-box;
}
.btn {
  width: 100%; margin-top: 20px; padding: 12px; background: #2563eb; color: #fff;
  border: none; border-radius: 8px; font-weight: 600; cursor: pointer;
}
.btn:disabled { opacity: 0.6; }
.btn-link { background: none; border: none; color: #64748b; cursor: pointer; margin-top: 8px; font-size: 13px; }
.err { color: #dc2626; font-size: 13px; margin-top: 8px; }
.back { display: inline-block; margin-top: 20px; color: #64748b; font-size: 14px; }
</style>
