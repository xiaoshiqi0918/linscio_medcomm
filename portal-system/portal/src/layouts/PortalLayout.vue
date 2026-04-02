<template>
  <div class="portal-layout">
    <header class="nav" :class="{ scrolled: navScrolled }">
      <div class="nav-inner container-shell">
        <router-link to="/" class="brand">
          <span class="brand-mark">L</span>
          <span class="brand-text-wrap">
            <span class="brand-text">LinScio AI</span>
            <span class="brand-sub">聆思恪</span>
          </span>
        </router-link>

        <nav class="nav-links">
          <router-link to="/">产品概览</router-link>
          <router-link to="/features">功能详情</router-link>
          <router-link to="/download">下载</router-link>
          <router-link to="/medcomm/activate" class="medcomm-entry">MedComm</router-link>
          <a href="/docs/" target="_blank" rel="noopener noreferrer">帮助文档</a>
          <router-link to="/about">关于我们</router-link>
        </nav>

        <div class="actions">
          <template v-if="authStore.isLoggedIn">
            <span class="nav-avatar">{{ profile?.username?.charAt(0)?.toUpperCase() || '?' }}</span>
            <router-link to="/dashboard" class="link">用户中心</router-link>
            <a href="#" class="link" @click.prevent="logout">退出</a>
          </template>
          <template v-else>
            <router-link to="/auth" class="link">登录</router-link>
            <router-link to="/auth" class="btn btn-base btn-primary-ui">免费注册</router-link>
          </template>
        </div>
      </div>
    </header>

    <main class="main-wrap">
      <router-view />
    </main>

    <footer class="footer">
      <div class="container container-shell footer-top">
        <div>
          <div class="footer-brand">
            <span class="brand-mark">L</span>
            <span class="brand-text-wrap">
              <span class="brand-text">LinScio AI</span>
              <span class="brand-sub">聆思恪</span>
            </span>
          </div>
          <p class="footer-desc">面向高校科研人员的 AI 学术助手，覆盖从选题到发表的关键流程。</p>
        </div>

        <div>
          <h4>产品</h4>
          <div class="footer-links">
            <router-link to="/">产品概览</router-link>
            <router-link to="/features">功能详情</router-link>
            <router-link to="/download">下载客户端</router-link>
            <router-link to="/medcomm/activate">MedComm 账号与激活</router-link>
          </div>
        </div>

        <div>
          <h4>支持</h4>
          <div class="footer-links">
            <a href="/docs/" target="_blank" rel="noopener noreferrer">帮助文档</a>
            <router-link to="/about">联系我们</router-link>
          </div>
        </div>

        <div>
          <h4>服务端</h4>
          <div class="footer-links">
            <router-link to="/download">Docker 部署包</router-link>
            <router-link to="/download">版本下载</router-link>
          </div>
        </div>
      </div>
      <div class="container container-shell footer-bottom">
        <span>© 2026 LinScio AI · 聆思恪</span>
        <span>ICP备XXXXXXXX号</span>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const profile = computed(() => authStore.profile)
const navScrolled = ref(false)

function onScroll() {
  navScrolled.value = window.scrollY > 16
}

function logout() {
  authStore.logout()
  router.push('/')
}

onMounted(() => {
  authStore.fetchProfile()
  window.addEventListener('scroll', onScroll, { passive: true })
})

onBeforeUnmount(() => {
  window.removeEventListener('scroll', onScroll)
})
</script>

<style scoped>
.portal-layout { min-height: 100vh; display: flex; flex-direction: column; background: var(--color-bg-base); }
.main-wrap { flex: 1; padding-top: 68px; }

.nav {
  position: fixed; top: 0; left: 0; right: 0; z-index: 120;
  height: 68px; border-bottom: 1px solid var(--color-border-soft);
  background: rgba(255,255,255,0.92); backdrop-filter: blur(20px);
  transition: background .2s ease, border-color .2s ease;
}
.nav.scrolled { background: rgba(255,255,255,0.98); border-color: #cbd5e1; box-shadow: var(--shadow-header); }

.nav-inner {
  max-width: var(--container-max); margin: 0 auto; padding: 0 var(--space-6); height: 100%;
  display: flex; align-items: center; justify-content: space-between;
}

.brand, .footer-brand { display: inline-flex; align-items: center; gap: var(--space-2); text-decoration: none; }
.brand-mark {
  width: 34px; height: 34px; border-radius: var(--radius-md);
  display: inline-flex; align-items: center; justify-content: center;
  font-weight: 800; color: #fff;
  background: linear-gradient(140deg, #2563eb, #1e40af);
  box-shadow: 0 4px 12px rgba(37,99,235,0.3);
}
.brand-text-wrap { display: inline-flex; flex-direction: column; line-height: 1.1; }
.brand-text { color: var(--color-text-strong); font-weight: 700; letter-spacing: -.2px; }
.brand-sub { color: #94a3b8; font-size: 11px; font-family: 'Noto Serif SC', serif; }

.nav-links { display: flex; align-items: center; gap: 10px; }
.nav-links a {
  color: var(--color-text-muted); text-decoration: none; font-size: var(--fs-md); font-weight: 500;
  padding: 6px var(--space-3); border-radius: var(--radius-sm); transition: all .2s ease;
}
.nav-links a:hover, .nav-links a.router-link-active { color: var(--color-brand-700); background: var(--color-bg-brand-soft); }

.actions { display: flex; align-items: center; gap: 12px; }
.link { color: var(--color-text-muted); text-decoration: none; font-size: var(--fs-md); }
.link:hover { color: var(--color-brand-700); }
.nav-avatar {
  width: 32px; height: 32px; border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #2563eb, #1d4ed8); color: #fff; font-weight: 700;
}
.btn { padding: var(--space-2) var(--space-4); text-decoration: none; font-weight: 600; font-size: var(--fs-md); }

.footer { border-top: 1px solid rgba(255,255,255,0.06); background: #0f172a; padding: 56px 0 32px; }
.container { max-width: var(--container-max); margin: 0 auto; padding: 0 var(--space-6); }
.footer-top { display: grid; grid-template-columns: 1.6fr 1fr 1fr 1fr; gap: 48px; }
.footer .brand-text { color: #ffffff; }
.footer .brand-sub { color: #94a3b8; }
.footer-desc { margin-top: 12px; color: #94a3b8; font-size: 13.5px; line-height: 1.75; max-width: 420px; }
.footer h4 { color: #cbd5e1; margin-bottom: 12px; font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; }
.footer-links { display: grid; gap: 8px; }
.footer-links a { color: rgba(255,255,255,0.55); text-decoration: none; font-size: 14px; }
.footer-links a:hover { color: rgba(255,255,255,0.85); }
.footer-bottom {
  margin-top: 28px; padding-top: 22px; border-top: 1px solid rgba(255,255,255,0.08);
  display: flex; justify-content: space-between; flex-wrap: wrap; gap: 10px;
  color: rgba(255,255,255,0.3); font-size: 13px;
}

@media (max-width: 900px) {
  .nav-links { display: none; }
  .footer-top { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 620px) {
  .footer-top { grid-template-columns: 1fr; }
  .footer-bottom { flex-direction: column; }
}
</style>
