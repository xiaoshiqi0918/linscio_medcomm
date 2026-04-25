<template>
  <div class="auth-page">
    <div class="auth-card card">
      <h1 class="auth-title">注册 LinScio</h1>
      <p class="auth-subtitle text-muted">创建您的账号</p>

      <div v-if="error" class="alert alert--error">{{ error }}</div>

      <form @submit.prevent="handleRegister">
        <div class="form-group">
          <label>手机号</label>
          <input v-model="form.phone" type="tel" class="form-input" placeholder="请输入手机号" required maxlength="11" />
        </div>
        <div class="form-group">
          <label>密码</label>
          <input v-model="form.password" type="password" class="form-input" placeholder="至少 6 位" required minlength="6" />
        </div>
        <div class="form-group">
          <label>确认密码</label>
          <input v-model="confirmPassword" type="password" class="form-input" placeholder="再次输入密码" required />
        </div>
        <div class="form-group">
          <label>昵称 <span class="optional">选填</span></label>
          <input v-model="form.displayName" type="text" class="form-input" placeholder="填写昵称" />
        </div>
        <div class="form-group">
          <label>邀请码 <span class="optional">选填</span></label>
          <input v-model="form.referralCode" type="text" class="form-input" placeholder="填写邀请码" maxlength="8" />
        </div>
        <div class="form-group">
          <label class="checkbox-label">
            <input type="checkbox" v-model="form.agreedTerms" />
            <span>我已阅读并同意《用户服务协议》《免责声明》《隐私政策》</span>
          </label>
        </div>
        <button type="submit" class="btn btn--primary btn--block" :disabled="loading">
          {{ loading ? '注册中...' : '注册' }}
        </button>
      </form>
      <div class="auth-links mt-2">
        <router-link to="/login">已有账号？登录</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { authRegister } from '@/api'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const error = ref('')
const confirmPassword = ref('')
const form = reactive({
  phone: '',
  password: '',
  displayName: '',
  referralCode: '',
  agreedTerms: false,
})

async function handleRegister() {
  error.value = ''
  if (form.password !== confirmPassword.value) {
    error.value = '两次输入的密码不一致'
    return
  }
  if (!form.agreedTerms) {
    error.value = '请先阅读并同意协议'
    return
  }
  loading.value = true
  try {
    const { data } = await authRegister({
      phone: form.phone,
      password: form.password,
      display_name: form.displayName || undefined,
      referral_code: form.referralCode || undefined,
      agreed_terms: form.agreedTerms,
    })
    auth.setSession(
      data.access_token,
      data.refresh_token || '',
      form.phone.trim(),
      data.display_name || '',
    )
    router.push('/')
  } catch (e: any) {
    error.value = e.response?.data?.detail || '注册失败'
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
.auth-links { font-size: 13px; }
.optional { font-size: 12px; color: var(--text-muted); margin-left: 4px; }
.checkbox-label {
  display: flex; align-items: flex-start; gap: 8px;
  font-size: 13px; color: var(--text-secondary); cursor: pointer;
  input { margin-top: 3px; }
}
</style>
