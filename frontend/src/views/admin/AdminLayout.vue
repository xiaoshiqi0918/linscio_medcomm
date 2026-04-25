<template>
  <div class="admin-layout">
    <aside class="admin-sidebar">
      <div class="admin-brand">
        <span class="brand-icon">⚙</span>
        <span class="brand-text">管理后台</span>
      </div>
      <nav class="admin-nav">
        <router-link to="/admin" exact-active-class="active" class="nav-item">
          <span class="nav-icon">📊</span> 仪表盘
        </router-link>
        <router-link to="/admin/users" active-class="active" class="nav-item">
          <span class="nav-icon">👥</span> 用户管理
        </router-link>
        <router-link to="/admin/orders" active-class="active" class="nav-item">
          <span class="nav-icon">📋</span> 订单管理
        </router-link>
        <router-link to="/admin/reconciliation" active-class="active" class="nav-item">
          <span class="nav-icon">🔍</span> 对账记录
        </router-link>
        <router-link to="/admin/licenses" active-class="active" class="nav-item">
          <span class="nav-icon">🔑</span> 授权码管理
        </router-link>
        <router-link to="/admin/config" active-class="active" class="nav-item">
          <span class="nav-icon">⚡</span> 系统配置
        </router-link>
      </nav>
      <div class="admin-footer">
        <router-link to="/" class="nav-item back-link">← 返回前台</router-link>
      </div>
    </aside>
    <main class="admin-main">
      <header class="admin-header">
        <span class="header-title">{{ $route.meta.title || '管理后台' }}</span>
        <span class="header-user">{{ adminUser?.display_name || adminUser?.phone || '管理员' }}</span>
      </header>
      <div class="admin-content">
        <router-view />
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { http } from '@/api'
import { ElMessage } from 'element-plus'

const router = useRouter()
const adminUser = ref<any>(null)

onMounted(async () => {
  try {
    const res = await http.get('/api/v1/admin/auth/me')
    adminUser.value = res.data
  } catch {
    ElMessage.error('无管理员权限')
    router.replace('/')
  }
})
</script>

<style scoped>
.admin-layout {
  display: flex;
  min-height: 100vh;
  background: #f5f7fa;
}
.admin-sidebar {
  width: 220px;
  background: #1e293b;
  color: #e2e8f0;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}
.admin-brand {
  padding: 20px 16px;
  font-size: 1.1rem;
  font-weight: 700;
  border-bottom: 1px solid #334155;
  display: flex;
  align-items: center;
  gap: 8px;
}
.brand-icon { font-size: 1.3rem; }
.admin-nav {
  flex: 1;
  padding: 12px 0;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 20px;
  color: #94a3b8;
  text-decoration: none;
  font-size: 0.9rem;
  transition: all 0.15s;
}
.nav-item:hover { color: #e2e8f0; background: #334155; }
.nav-item.active { color: #fff; background: #3b82f6; }
.nav-icon { font-size: 1rem; width: 20px; text-align: center; }
.admin-footer {
  padding: 12px 0;
  border-top: 1px solid #334155;
}
.back-link { color: #64748b !important; font-size: 0.85rem; }
.admin-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.admin-header {
  height: 56px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
}
.header-title { font-size: 1rem; font-weight: 600; color: #1e293b; }
.header-user { font-size: 0.85rem; color: #64748b; }
.admin-content {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
}
</style>
