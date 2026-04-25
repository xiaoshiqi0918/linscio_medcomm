<template>
  <div class="app-layout">
    <header class="app-header">
      <div class="header-inner">
        <div class="header-left">
          <router-link to="/" class="logo">
            <span class="logo-brand">LinScio</span>
            <span class="logo-label">用户中心</span>
          </router-link>
        </div>
        <div class="header-right">
          <span v-if="auth.userPhone" class="header-email">{{ auth.userPhone }}</span>
          <button class="header-logout" @click="handleLogout">退出登录</button>
        </div>
      </div>
    </header>

    <div class="app-body">
      <aside class="sidebar">
        <nav class="sidebar-nav">
          <router-link to="/license" class="sidebar-link" exact-active-class="active">
            <span class="dot dot--green"></span>我的授权
          </router-link>
          <router-link to="/license/activate" class="sidebar-link" exact-active-class="active">
            <span class="dot"></span>激活授权码
          </router-link>
          <router-link to="/license/specialties" class="sidebar-link" exact-active-class="active">
            <span class="dot"></span>我的学科包
          </router-link>
          <router-link to="/device" class="sidebar-link" exact-active-class="active">
            <span class="dot"></span>我的设备
          </router-link>
          <div class="sidebar-spacer"></div>
          <router-link to="/account" class="sidebar-link" exact-active-class="active">
            <span class="dot"></span>账号设置
          </router-link>
        </nav>
      </aside>

      <main class="app-main">
        <router-view />
      </main>
    </div>

    <footer class="app-footer">
      <div class="footer-inner">
        <span>&copy; {{ year }} LinScio · 用户中心</span>
        <span class="footer-links">
          <a :href="`${wwwUrl}/legal/privacy`" target="_blank">隐私政策</a>
          <a :href="`${wwwUrl}/legal/terms`" target="_blank">服务条款</a>
          <a :href="`${medcommUrl}/help`" target="_blank">帮助中心</a>
        </span>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { authLogout } from '@/api'
const router = useRouter()
const auth = useAuthStore()
const year = new Date().getFullYear()
const wwwUrl = import.meta.env.VITE_URL_WWW
const medcommUrl = import.meta.env.VITE_URL_MEDCOMM

async function handleLogout() {
  try { await authLogout() } catch {}
  auth.clearSession()
  router.push('/login')
}
</script>

<style scoped lang="scss">
.app-layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* ── Header ── */
.app-header {
  background: var(--bg-dark);
  position: sticky; top: 0; z-index: 100;
}
.header-inner {
  display: flex; align-items: center; justify-content: space-between;
  height: 52px; padding: 0 32px;
}
.logo {
  display: flex; align-items: baseline; gap: 10px; text-decoration: none;
}
.logo-brand {
  font-size: 17px; font-weight: 700; color: #fff;
  letter-spacing: -0.5px;
}
.logo-label {
  font-size: 14px; color: var(--text-on-dark-muted); font-weight: 400;
}
.header-right {
  display: flex; align-items: center; gap: 20px;
}
.header-email { font-size: 13px; color: var(--text-on-dark-muted); }
.header-logout {
  font-size: 13px; color: var(--text-on-dark-muted); background: none; border: none;
  font-family: inherit; transition: color 0.15s;
  &:hover { color: #fff; }
}

/* ── Body ── */
.app-body {
  flex: 1; display: flex;
}

/* ── Sidebar ── */
.sidebar {
  width: 200px; flex-shrink: 0; padding: 24px 16px;
  background: var(--bg-card);
  border-right: 1px solid var(--border);
}
.sidebar-nav {
  display: flex; flex-direction: column; gap: 4px;
}
.sidebar-link {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 14px; border-radius: var(--radius);
  font-size: 14px; color: var(--text-muted); text-decoration: none;
  transition: all 0.15s;

  &:hover { color: var(--text-secondary); }
  &.active {
    color: var(--text-primary); font-weight: 500;
    background: var(--bg-surface);
  }
}
.dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--border); flex-shrink: 0;
}
.dot--green { background: var(--success); }
.sidebar-spacer { height: 16px; }

/* ── Main ── */
.app-main {
  flex: 1; padding: 32px 40px 48px;
  min-width: 0;
  background: var(--bg-alt);
}

/* ── Footer ── */
.app-footer {
  background: var(--bg-dark);
  padding: 20px 0;
}
.footer-inner {
  display: flex; justify-content: space-between; align-items: center;
  padding: 0 32px; font-size: 12px; color: var(--text-on-dark-muted);
}
.footer-links {
  display: flex; gap: 20px;
  a { color: var(--text-on-dark-muted); text-decoration: none; &:hover { color: #fff; } }
}

@media (max-width: 768px) {
  .app-body { flex-direction: column; }
  .sidebar { width: 100%; padding: 16px; }
  .sidebar-nav { flex-direction: row; flex-wrap: wrap; }
  .sidebar-spacer { display: none; }
  .app-main { padding: 24px 16px; }
}
</style>
