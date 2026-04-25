<template>
  <div class="auth-page">
    <div class="auth-card">
      <h2>注册</h2>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="0" @submit.prevent="handleRegister">
        <el-form-item prop="phone">
          <el-input v-model="form.phone" placeholder="手机号" prefix-icon="Phone" maxlength="11" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input v-model="form.password" type="password" placeholder="密码（至少6位）" prefix-icon="Lock" show-password />
        </el-form-item>
        <el-form-item prop="confirmPassword">
          <el-input v-model="form.confirmPassword" type="password" placeholder="确认密码" prefix-icon="Lock" show-password />
        </el-form-item>
        <el-form-item prop="displayName">
          <el-input v-model="form.displayName" placeholder="昵称（可选）" prefix-icon="User" />
        </el-form-item>
        <el-form-item prop="referralCode">
          <el-input v-model="form.referralCode" placeholder="邀请码（可选）" maxlength="8" />
        </el-form-item>
        <el-form-item prop="agreedTerms">
          <el-checkbox v-model="form.agreedTerms">
            我已阅读并同意《用户服务协议》《免责声明》《隐私政策》
          </el-checkbox>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" style="width: 100%;" @click="handleRegister">注册</el-button>
        </el-form-item>
      </el-form>
      <div class="auth-footer">
        已有账号？<router-link to="/login">去登录</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { http, setAuthToken } from '@/api'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

const router = useRouter()
const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  phone: '',
  password: '',
  confirmPassword: '',
  displayName: '',
  referralCode: '',
  agreedTerms: false,
})

const rules: FormRules = {
  phone: [{ required: true, message: '请输入手机号', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_: any, value: string, callback: Function) => {
        if (value !== form.password) callback(new Error('两次密码不一致'))
        else callback()
      },
      trigger: 'blur',
    },
  ],
  agreedTerms: [
    {
      validator: (_: any, value: boolean, callback: Function) => {
        if (!value) callback(new Error('请先同意协议'))
        else callback()
      },
      trigger: 'change',
    },
  ],
}

async function handleRegister() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    const res = await http.post('/api/v1/auth/register', {
      phone: form.phone,
      password: form.password,
      display_name: form.displayName || undefined,
      referral_code: form.referralCode || undefined,
      agreed_terms: form.agreedTerms,
    })
    const { access_token, refresh_token } = res.data
    setAuthToken(access_token)
    if (refresh_token) {
      try { localStorage.setItem('linscio_refresh_token', refresh_token) } catch {}
    }
    ElMessage.success('注册成功，已自动登录')
    router.push('/').catch(() => {})
  } catch (e: any) {
    const detail = e?.response?.data?.detail || '注册失败'
    ElMessage.error(detail)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
}
.auth-card {
  width: 400px;
  padding: 40px 32px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
}
.auth-card h2 {
  text-align: center;
  margin-bottom: 28px;
  font-size: 1.4rem;
  color: #1f2937;
}
.auth-footer {
  text-align: center;
  margin-top: 12px;
  color: #6b7280;
  font-size: 0.9rem;
}
.auth-footer a {
  color: #409eff;
  text-decoration: none;
}
.auth-footer a:hover {
  text-decoration: underline;
}
</style>
