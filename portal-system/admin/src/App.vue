<template>
  <el-config-provider locale="zhCn">
    <router-view v-if="$route.path === '/login'" />
    <el-container v-else class="layout">
      <el-aside width="240px" class="aside">
        <div class="logo">LinScio AI · 聆思恪 管理后台</div>
        <el-menu
          :default-active="$route.path"
          router
          background-color="#001529"
          text-color="#fff"
          active-text-color="#00c4aa"
        >
          <el-menu-item index="/">数据总览</el-menu-item>
          <el-menu-item index="/users">用户管理</el-menu-item>
          <el-menu-item index="/plans-periods">套餐与周期</el-menu-item>
          <el-menu-item index="/licenses">授权码管理</el-menu-item>
          <el-menu-item index="/modules">模块权限配置</el-menu-item>
          <el-menu-item index="/registry">镜像版本</el-menu-item>
          <el-menu-item index="/settings">系统设置</el-menu-item>
        </el-menu>
        <div class="aside-footer">
          <el-button type="primary" link class="logout-btn" @click="logout">
            登出
          </el-button>
        </div>
      </el-aside>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-config-provider>
</template>

<script setup>
import { useRouter } from 'vue-router'
import zhCn from 'element-plus/es/locale/lang/zh-cn'

const router = useRouter()

function logout() {
  localStorage.removeItem('admin_token')
  router.push('/login')
}
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: system-ui, sans-serif; }
#app { min-height: 100vh; }
.layout { min-height: 100vh; }
.aside { background: #001529; display: flex; flex-direction: column; }
.logo { padding: 16px; color: #fff; font-weight: 600; }
.aside-footer { padding: 16px; margin-top: auto; border-top: 1px solid rgba(255,255,255,0.1); }
.logout-btn { color: #00c4aa !important; width: 100%; justify-content: flex-start; }
.main { background: #f0f2f5; padding: 24px; }
</style>
