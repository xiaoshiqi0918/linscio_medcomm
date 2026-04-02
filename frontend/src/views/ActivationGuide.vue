<template>
  <div class="activation-guide">
    <div class="activation-content">
      <h1 class="title">LinScio MedComm 需要激活授权</h1>

      <!-- 登录表单 -->
      <div v-if="showLoginForm" class="login-form">
        <p class="desc">使用门户账号登录以绑定本机授权</p>
        <input v-model="email" type="email" class="input" placeholder="门户注册邮箱" @keydown.enter="doLogin" />
        <input v-model="password" type="password" class="input" placeholder="密码" @keydown.enter="doLogin" />
        <p v-if="loginError" class="error">{{ loginError }}</p>
        <div class="actions">
          <button class="btn-primary" :disabled="loginLoading" @click="doLogin">
            {{ loginLoading ? '登录中…' : '登录' }}
          </button>
          <button class="btn-secondary" @click="showLoginForm = false">返回</button>
        </div>
        <p class="hint">
          还没有账号？
          <a href="#" @click.prevent="openActivatePage">前往门户注册</a>
        </p>
      </div>

      <!-- 引导页 -->
      <div v-else>
        <p class="desc">请先完成授权激活，再返回软件使用。</p>
        <ol class="steps">
          <li>在门户注册账号并激活授权码</li>
          <li>使用门户邮箱和密码直接登录（推荐）</li>
          <li>或前往门户通过 deep_link 唤起软件完成绑定</li>
        </ol>
        <div class="actions">
          <button class="btn-primary" @click="showLoginForm = true">使用门户账号登录</button>
          <button class="btn-secondary" :disabled="loading" @click="openActivatePage">
            {{ loading ? '正在打开…' : '前往官网激活' }}
          </button>
        </div>
        <p class="hint">
          还没有账号？前往
          <a href="#" @click.prevent="openActivatePage">门户网站</a>
          注册并获取授权码。
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const loading = ref(false)
const showLoginForm = ref(false)
const email = ref('')
const password = ref('')
const loginLoading = ref(false)
const loginError = ref('')

async function doLogin() {
  const e = email.value.trim()
  const p = password.value
  if (!e || !p) {
    loginError.value = '请输入邮箱和密码'
    return
  }
  loginLoading.value = true
  loginError.value = ''
  try {
    const eApi = window.electronAPI
    if (!eApi?.portalLogin) {
      loginError.value = '当前环境不支持门户登录'
      return
    }
    const res = await eApi.portalLogin(e, p)
    if (res.ok) {
      // 登录成功后 main.js 会发 license-activated → App.vue 隐藏激活引导
      password.value = ''
    } else {
      loginError.value = res.error || '登录失败'
    }
  } catch (err: any) {
    loginError.value = err?.message || '网络错误'
  } finally {
    loginLoading.value = false
  }
}

async function openActivatePage() {
  if (!window.electronAPI?.getPortalActivateUrl || !window.electronAPI?.openExternal) return
  loading.value = true
  try {
    const url = await window.electronAPI.getPortalActivateUrl()
    if (url) {
      await window.electronAPI.openExternal(url)
    } else {
      window.alert('未配置门户地址，请联系技术支持。')
    }
  } catch (e) {
    console.error('[ActivationGuide]', e)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.activation-guide {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  color: #e8e8e8;
}

.activation-content {
  max-width: 480px;
  padding: 2rem;
}

.title {
  font-size: 1.5rem;
  font-weight: 600;
  margin-bottom: 0.75rem;
}

.desc {
  color: #a0a0a8;
  margin-bottom: 1.5rem;
  line-height: 1.6;
}

.steps {
  margin: 0 0 1.5rem 1.25rem;
  padding: 0;
  color: #c0c0c8;
  line-height: 2;
}

.steps li {
  margin-bottom: 0.5rem;
}

.login-form {
  margin-top: 0.5rem;
}

.input {
  display: block;
  width: 100%;
  padding: 0.65rem 0.85rem;
  margin-bottom: 0.75rem;
  font-size: 0.95rem;
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.15);
  border-radius: 8px;
  color: #e8e8e8;
  outline: none;
  transition: border-color 0.2s;
}

.input:focus {
  border-color: #4a90d9;
}

.input::placeholder {
  color: rgba(255,255,255,0.35);
}

.error {
  color: #f87171;
  font-size: 0.875rem;
  margin-bottom: 0.75rem;
}

.actions {
  display: flex;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}

.btn-primary {
  padding: 0.65rem 1.5rem;
  font-size: 0.95rem;
  background: #4a90d9;
  color: #fff;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-primary:hover:not(:disabled) {
  background: #3a7bc8;
}

.btn-primary:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.btn-secondary {
  padding: 0.65rem 1.5rem;
  font-size: 0.95rem;
  background: transparent;
  color: #a0a0a8;
  border: 1px solid rgba(255,255,255,0.2);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-secondary:hover:not(:disabled) {
  border-color: rgba(255,255,255,0.4);
  color: #e8e8e8;
}

.btn-secondary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.hint {
  font-size: 0.875rem;
  color: #808088;
  line-height: 1.6;
}

.hint a {
  color: #6ba3e8;
  text-decoration: none;
}

.hint a:hover {
  text-decoration: underline;
}
</style>
