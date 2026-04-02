<template>
  <div class="auth-v7">
    <div class="bg-orb orb-a"></div>
    <div class="bg-orb orb-b"></div>

    <div class="auth-wrap">
      <section class="auth-left card-base">
        <div class="badge">LinScio AI · 聆思恪</div>
        <h1>科研账号中心</h1>
        <p>支持注册、登录与授权激活。建议先注册，再在用户中心完成授权码激活与下载。</p>
        <ul>
          <li>支持门户账号与管理员账号（同名同步）登录</li>
          <li>支持授权码激活与后续更新</li>
          <li>登录后可进入用户中心下载与管理设备</li>
        </ul>
        <router-link to="/" class="back">← 返回首页</router-link>
      </section>

      <section class="auth-card card-base">
        <div class="tabs">
          <button class="tab" :class="{ active: mode === 'login' }" @click="mode = 'login'">登录</button>
          <button class="tab" :class="{ active: mode === 'register' }" @click="mode = 'register'">注册</button>
          <button class="tab" :class="{ active: mode === 'activate' }" @click="mode = 'activate'">激活</button>
        </div>

        <form v-if="mode !== 'activate'" class="form" @submit.prevent="submit">
          <div class="field">
            <label>用户名</label>
            <input v-model="username" type="text" required placeholder="请输入用户名" />
          </div>
          <div class="field" v-if="mode === 'register'">
            <label>邮箱（选填）</label>
            <input v-model="email" type="email" placeholder="you@example.com" />
          </div>
          <div class="field">
            <label>密码</label>
            <input v-model="password" type="password" required placeholder="请输入密码" />
          </div>
          <p v-if="error" class="error">{{ error }}</p>
          <button class="btn btn-base btn-primary-ui" type="submit" :disabled="loading">
            {{ loading ? '提交中…' : (mode === 'login' ? '登录' : '创建账号') }}
          </button>
        </form>

        <div v-else class="activate-block">
          <p>激活需先登录后在用户中心完成。若你已有账号，请先登录。</p>
          <div class="activate-actions">
            <button class="btn btn-base btn-primary-ui" @click="mode = 'login'">去登录</button>
            <button class="btn btn-base btn-outline-ui" @click="mode = 'register'">新建账号</button>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const mode = ref('login')
const username = ref('')
const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  loading.value = true
  try {
    if (mode.value === 'login') {
      await authStore.login(username.value, password.value)
    } else {
      await authStore.register({ username: username.value, password: password.value, email: email.value || undefined })
    }
    router.push('/dashboard')
  } catch (e) {
    error.value = e.response?.data?.detail || (Array.isArray(e.response?.data?.detail) ? e.response.data.detail[0]?.msg : '请求失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-v7 {
  min-height: calc(100vh - 68px);
  position: relative;
  background: linear-gradient(160deg, #f0f7ff 0%, #e8f2ff 40%, #f5f9ff 70%, #ffffff 100%);
  color: var(--color-text-body);
  padding: var(--space-8) var(--space-6);
  overflow: hidden;
}
.bg-orb { position: absolute; border-radius: 50%; filter: blur(90px); pointer-events: none; }
.orb-a { width: 360px; height: 360px; top: -80px; right: -120px; background: rgba(59,130,246,.22); }
.orb-b { width: 320px; height: 320px; bottom: -100px; left: -100px; background: rgba(45,212,191,.15); }

.auth-wrap {
  position: relative; z-index: 2; max-width: 1100px; margin: 0 auto;
  display: grid; grid-template-columns: 1.1fr 1fr; gap: var(--space-6); align-items: stretch;
}
.auth-left, .auth-card { border-radius: 18px; box-shadow: 0 10px 26px rgba(15,23,42,0.06); }
.auth-left { padding: 34px; }
.auth-card { padding: 28px; }
.badge {
  display: inline-block; padding: 6px 12px; border-radius: 999px;
  background: var(--color-bg-brand-soft); border: 1px solid var(--color-border-brand);
  color: var(--color-brand-700); font-size: var(--fs-xs);
}
.auth-left h1 { font-size: clamp(28px, 4vw, 42px); margin: 16px 0 12px; color: var(--color-text-strong); }
.auth-left p { color: var(--color-text-muted); line-height: 1.7; }
.auth-left ul { margin: 18px 0 20px; padding-left: 18px; color: var(--color-text-body); display: grid; gap: 8px; }
.back { color: var(--color-brand-700); text-decoration: none; }

.tabs {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px;
  background: #f8fafc; border-radius: 10px; padding: 4px; border: 1px solid #e2e8f0;
}
.tab {
  border: 0; background: transparent; color: #64748b;
  border-radius: 8px; padding: 8px 10px; cursor: pointer; font-weight: 600;
}
.tab.active { color: #1d4ed8; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.06); }

.form { margin-top: 18px; display: grid; gap: 14px; }
.field label { display: block; font-size: 13px; color: #475569; margin-bottom: 6px; }
.field input {
  width: 100%; background: #fff; color: #0f172a; border: 1.5px solid #cbd5e1;
  border-radius: 10px; padding: 11px 12px; outline: none;
}
.field input:focus { border-color: #60a5fa; box-shadow: 0 0 0 3px rgba(59,130,246,.08); }
.error { color: #ef4444; font-size: 14px; }

.btn { padding: 10px 14px; cursor: pointer; font-weight: 600; }
.btn:disabled { opacity: .6; cursor: not-allowed; }

.activate-block { margin-top: 18px; color: #64748b; }
.activate-actions { margin-top: 14px; display: flex; gap: 10px; flex-wrap: wrap; }

@media (max-width: 900px) {
  .auth-wrap { grid-template-columns: 1fr; }
}
</style>
