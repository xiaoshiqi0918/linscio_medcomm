<template>
  <div class="login-page">
    <el-card class="login-card">
      <template #header>
        <span>管理员登录</span>
      </template>
      <el-form @submit.prevent="submit" :model="form" label-width="0">
        <el-form-item>
          <el-input v-model="form.username" placeholder="用户名" size="large" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" placeholder="密码" size="large" show-password @keyup.enter="submit" />
        </el-form-item>
        <el-alert v-if="error" type="error" :title="error" show-icon class="mb" />
        <el-form-item>
          <el-button type="primary" size="large" style="width:100%" :loading="loading" @click="submit">登录</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { adminAuth } from '../api'

const form = reactive({ username: '', password: '' })
const error = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  if (!form.username || !form.password) {
    error.value = '请输入用户名和密码'
    return
  }
  loading.value = true
  try {
    const { data } = await adminAuth.login(form)
    if (!data || !data.access_token) {
      error.value = '登录返回数据异常，请重试'
      return
    }
    localStorage.setItem('admin_token', data.access_token)
    // 使用 location 强制刷新到首页，确保后续请求带上 token
    window.location.href = '/'
  } catch (e) {
    const status = e.response?.status
    const d = e.response?.data?.detail
    if (status === 502) {
      error.value = '无法连接后端 API（502 Bad Gateway）。请确认 portal-system 后端已启动：在 portal-system 目录执行 docker compose up -d linscio-db linscio-api，或本地运行 cd api && uvicorn main:app --reload --port 8001。'
    } else if (Array.isArray(d) && d.length) {
      error.value = d.map((x) => x.msg || JSON.stringify(x)).join('；')
    } else if (typeof d === 'string') {
      error.value = d
    } else {
      error.value = e.response?.data?.detail || e.message || '登录失败'
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page { min-height: 100vh; display: flex; align-items: center; justify-content: center; background: #f0f2f5; }
.login-card { width: 400px; }
.mb { margin-bottom: 16px; }
</style>
