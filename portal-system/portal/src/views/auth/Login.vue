<template>
  <div class="auth-page">
    <div class="auth-card card">
      <h1 class="auth-title">登录 LinScio</h1>
      <p class="auth-subtitle text-muted">使用您的手机号和密码登录</p>

      <div v-if="error" class="alert alert--error">{{ error }}</div>

      <form @submit.prevent="handleLogin">
        <div class="form-group">
          <label>手机号</label>
          <input v-model="form.phone" type="tel" class="form-input" placeholder="请输入手机号" required maxlength="11" />
        </div>
        <div class="form-group">
          <label>密码</label>
          <input v-model="form.password" type="password" class="form-input" placeholder="请输入密码" required />
        </div>
        <button type="submit" class="btn btn--primary btn--block" :disabled="loading">
          {{ loading ? '登录中...' : '登录' }}
        </button>
      </form>

      <div class="auth-links mt-2">
        <router-link to="/register">注册新账号</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { authLogin } from '@/api'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const loading = ref(false)
const error = ref('')
const form = reactive({ phone: '', password: '' })

async function handleLogin() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await authLogin(form)
    auth.setSession(
      data.access_token,
      data.refresh_token || '',
      form.phone.trim(),
      data.display_name || '',
    )
    const redirect = (route.query.redirect as string) || '/'
    router.push(redirect)
  } catch (e: any) {
    error.value = e.response?.data?.detail || '登录失败，请检查手机号和密码'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="scss">
.auth-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}
.auth-card { width: 100%; max-width: 420px; }
.auth-title { font-size: 24px; font-weight: 600; margin-bottom: 4px; }
.auth-subtitle { margin-bottom: 24px; }
.auth-links { display: flex; justify-content: space-between; font-size: 13px; }
</style>
