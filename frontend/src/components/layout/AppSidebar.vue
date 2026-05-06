<template>
  <aside class="sidebar">
    <nav class="nav-groups">
      <div class="nav-group">
        <span class="nav-group-title">主要功能</span>
        <router-link to="/medcomm" class="nav-item">
          <span class="icon">✍️</span> 科普写作
        </router-link>
        <router-link to="/illustration" class="nav-item">
          <span class="icon">🎨</span> 配图工作台
        </router-link>
      </div>
      <div v-if="isElectron" class="nav-group">
        <span class="nav-group-title">绘图 <span class="dev-tag">开发中</span></span>
        <router-link to="/drawing/txt2img" class="nav-item">
          <span class="icon">🖼️</span> 文生图
        </router-link>
        <router-link to="/drawing/img2img" class="nav-item">
          <span class="icon">🔄</span> 图生图
        </router-link>
      </div>
      <div class="nav-group">
        <span class="nav-group-title">写作工具</span>
        <router-link to="/literature" class="nav-item">
          <span class="icon">📖</span> 文献支撑库
        </router-link>
        <router-link to="/templates" class="nav-item">
          <span class="icon">📄</span> 模板库
        </router-link>
      </div>
      <div class="nav-group">
        <span class="nav-group-title">资产管理</span>
        <router-link to="/creations" class="nav-item">
          <span class="icon">🗂</span> 创作库
        </router-link>
        <router-link to="/knowledge" class="nav-item">
          <span class="icon">🧠</span> 知识库
        </router-link>
        <router-link to="/personal-corpus" class="nav-item">
          <span class="icon">📌</span> 个人语料
        </router-link>
      </div>
      <div class="nav-group">
        <span class="nav-group-title">系统</span>
        <router-link to="/settings" class="nav-item">
          <span class="icon">⚙️</span> 设置
        </router-link>
        <router-link to="/help" class="nav-item">
          <span class="icon">❓</span> 帮助
        </router-link>
        <router-link to="/contact" class="nav-item">
          <span class="icon">📞</span> 联系我们
        </router-link>
      </div>
    </nav>
    <div class="sidebar-footer">
      <template v-if="isLoggedIn || isElectron">
        <div class="footer-row">
          <span class="avatar">👤</span>
          <span class="user-info">{{ sidebarDisplayName }}</span>
        </div>
        <span v-if="isElectron && licenseStore.expiresAt" class="expiry-info">
          授权到期 {{ formatExpiry(licenseStore.expiresAt) }}
        </span>
      </template>
      <template v-else>
        <div class="footer-row guest-row">
          <span class="avatar">👤</span>
          <span class="user-info">游客模式</span>
        </div>
        <router-link to="/login" class="guest-login-btn">登录 / 注册</router-link>
      </template>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useUserStore } from '@/stores/user'
import { useAuthStore, AUTH_USER_CHANGED_EVENT } from '@/stores/auth'
import { useMedcommLicenseStore } from '@/stores/medcommLicense'
import { http, getAuthToken } from '@/api'

const userStore = useUserStore()
const authStore = useAuthStore()
const licenseStore = useMedcommLicenseStore()
const isElectron = typeof window !== 'undefined' && !!(window as any).electronAPI?.isElectron

const isLoggedIn = computed(() => !!getAuthToken())
const saasDisplayName = ref('')

const sidebarDisplayName = computed(() => {
  if (isElectron) {
    return authStore.user?.display_name || userStore.displayName
  }
  return saasDisplayName.value || '用户'
})

function formatExpiry(iso: string) {
  try {
    return new Date(iso).toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
  } catch {
    return iso
  }
}

async function onAuthUserChanged() {
  await authStore.refreshMe()
}

onMounted(async () => {
  window.addEventListener(AUTH_USER_CHANGED_EVENT, onAuthUserChanged as EventListener)
  if (!isElectron && isLoggedIn.value) {
    try {
      const res = await http.get('/api/v1/auth/me')
      saasDisplayName.value = res.data?.display_name || ''
    } catch { /* ignore */ }
  }
})
onUnmounted(() => {
  window.removeEventListener(AUTH_USER_CHANGED_EVENT, onAuthUserChanged as EventListener)
})
</script>

<style scoped>
.sidebar {
  width: 240px;
  min-width: 240px;
  background: #1a1a2e;
  color: #e8e8e8;
  display: flex;
  flex-direction: column;
}

.nav-groups {
  flex: 1;
  overflow-y: auto;
  padding: 0.5rem 0;
}

.nav-group {
  margin-bottom: 0.5rem;
}

.nav-group-title {
  display: block;
  padding: 0.5rem 1.25rem;
  font-size: 0.7rem;
  text-transform: uppercase;
  color: rgba(255,255,255,0.5);
}

.nav-item {
  display: flex;
  align-items: center;
  padding: 0.5rem 1.25rem;
  color: rgba(255,255,255,0.85);
  text-decoration: none;
  font-size: 0.9rem;
  transition: background 0.15s;
}

.nav-item:hover {
  background: rgba(255,255,255,0.06);
  color: #fff;
}

.nav-item.router-link-active {
  background: rgba(59, 130, 246, 0.2);
  color: #60a5fa;
}

.icon {
  margin-right: 0.5rem;
}
.dev-tag {
  font-size: 0.6rem;
  background: rgba(251, 191, 36, 0.25);
  color: #fbbf24;
  padding: 1px 5px;
  border-radius: 3px;
  margin-left: 0.25rem;
  vertical-align: middle;
  line-height: 1;
}

.sidebar-footer {
  padding: 0.75rem 1.25rem;
  border-top: 1px solid rgba(255,255,255,0.08);
  font-size: 0.8rem;
  color: rgba(255,255,255,0.6);
}
.footer-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.avatar { font-size: 1.2rem; }
.expiry-info {
  display: block;
  margin-top: 0.25rem;
  font-size: 0.75rem;
  opacity: 0.8;
}
.guest-row .user-info {
  opacity: 0.6;
}
.guest-login-btn {
  display: block;
  margin-top: 0.5rem;
  padding: 6px 0;
  text-align: center;
  background: rgba(59, 130, 246, 0.2);
  color: #60a5fa;
  border-radius: 6px;
  text-decoration: none;
  font-size: 0.8rem;
  transition: background 0.15s;
}
.guest-login-btn:hover {
  background: rgba(59, 130, 246, 0.35);
  color: #93bbfd;
}
</style>
