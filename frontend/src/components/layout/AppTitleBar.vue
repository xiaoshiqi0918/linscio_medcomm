<template>
  <header class="title-bar">
    <div class="left">
      <span class="app-name">LinScio MedComm</span>
      <span class="divider">·</span>
      <span class="brand">聆思恪</span>
    </div>
    <div class="right no-drag">
      <!-- SaaS 模式 -->
      <template v-if="!isElectron">
        <template v-if="isLoggedIn">
          <el-dropdown trigger="click" @command="onCommand">
            <span class="user-chip">
              {{ saasDisplayName || '用户' }}
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item disabled class="key-status-item">
                  <span class="key-label">积分余额</span>
                  <span class="key-badge configured">{{ saasCredits }}</span>
                </el-dropdown-item>
                <el-dropdown-item command="settings" divided>设置</el-dropdown-item>
                <el-dropdown-item command="saasLogout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
        <template v-else>
          <router-link to="/login" class="auth-link">登录</router-link>
          <span class="auth-divider">/</span>
          <router-link to="/register" class="auth-link">注册</router-link>
        </template>
      </template>
      <!-- 桌面模式 -->
      <template v-else>
        <el-dropdown trigger="click" @command="onCommand">
          <span class="user-chip">
            {{ authStore.user?.display_name || '未登录' }}
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item disabled class="key-status-item">
                <span class="key-label">PubMed (NCBI)</span>
                <span :class="['key-badge', ncbiMask ? 'configured' : 'empty']">
                  {{ ncbiMask || '未配置' }}
                </span>
              </el-dropdown-item>
              <el-dropdown-item command="configNcbi">配置 NCBI Key</el-dropdown-item>
              <el-dropdown-item command="applyNcbi" class="apply-link-item">申请 NCBI API Key ↗</el-dropdown-item>

              <el-dropdown-item disabled class="key-status-item" divided>
                <span class="key-label">Semantic Scholar</span>
                <span :class="['key-badge', s2Mask ? 'configured' : 'empty']">
                  {{ s2Mask || '未配置' }}
                </span>
              </el-dropdown-item>
              <el-dropdown-item command="configS2">配置 S2 Key</el-dropdown-item>
              <el-dropdown-item command="applyS2" class="apply-link-item">申请 S2 API Key ↗</el-dropdown-item>

              <el-dropdown-item command="switch" divided>切换用户</el-dropdown-item>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </template>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { AUTH_USER_CHANGED_EVENT, useAuthStore } from '@/stores/auth'
import { api, http, setAuthToken, getAuthToken } from '@/api'

const router = useRouter()
const authStore = useAuthStore()
const isElectron = typeof window !== 'undefined' && !!(window as any).electronAPI?.isElectron
const ncbiMask = ref('')
const s2Mask = ref('')
let lastUserChangedToastAt = 0

const saasDisplayName = ref('')
const saasCredits = ref(0)
const _authTokenSnapshot = ref(getAuthToken())
const isLoggedIn = computed(() => !!_authTokenSnapshot.value)

async function loadSaasInfo() {
  if (isElectron) return
  try {
    const res = await http.get('/api/v1/auth/me')
    saasDisplayName.value = res.data?.display_name || '用户'
  } catch { /* ignore */ }
  try {
    const res = await http.get('/api/v1/credits/balance')
    saasCredits.value = res.data?.total_available ?? 0
  } catch { /* ignore */ }
}

async function refreshSummary() {
  try {
    const res = await api.system.getUserSettingsSummary()
    ncbiMask.value = res.data?.ncbi_key?.masked || ''
    s2Mask.value   = res.data?.s2_key?.masked   || ''
  } catch {
    ncbiMask.value = ''
    s2Mask.value   = ''
  }
}

onMounted(async () => {
  if (isElectron) {
    await authStore.refreshMe()
    await refreshSummary()
  } else if (isLoggedIn.value) {
    await loadSaasInfo()
  }
  window.addEventListener(AUTH_USER_CHANGED_EVENT, onAuthUserChanged as EventListener)
})

onUnmounted(() => {
  window.removeEventListener(AUTH_USER_CHANGED_EVENT, onAuthUserChanged as EventListener)
})

async function onAuthUserChanged(e: Event) {
  await refreshSummary()
  const now = Date.now()
  if (now - lastUserChangedToastAt < 1200) return
  lastUserChangedToastAt = now
  const detail = (e as CustomEvent<{ userId: number | null; displayName?: string | null; action?: string }>).detail
  if (detail?.action === 'logout') {
    ElMessage.info('已退出并刷新为匿名视图')
    return
  }
  const name = detail?.displayName || authStore.user?.display_name || '当前用户'
  ElMessage.info(`已刷新为 ${name} 视图`)
}

async function onCommand(cmd: string) {
  if (cmd === 'settings') {
    router.push('/settings').catch(() => {})
    return
  }
  if (cmd === 'saasLogout') {
    try {
      await ElMessageBox.confirm('确认退出当前账号？', '退出登录', {
        confirmButtonText: '退出', cancelButtonText: '取消', type: 'warning',
      })
      try { await http.post('/api/v1/auth/logout') } catch { /* ignore */ }
      setAuthToken(null)
      _authTokenSnapshot.value = null
      router.push('/login').catch(() => {})
      ElMessage.success('已退出')
    } catch { /* user cancel */ }
    return
  }
  if (cmd === 'configNcbi') {
    try {
      const { value } = await ElMessageBox.prompt(
        `请输入 NCBI API Key（当前：${ncbiMask.value || '未配置'}）\n申请地址：https://www.ncbi.nlm.nih.gov/account/`,
        '配置 NCBI Key',
        {
          confirmButtonText: '保存',
          cancelButtonText: '取消',
          inputType: 'password',
          inputPlaceholder: '例如：xxxxxxxxxxxxxxxx（16位字母数字）',
        }
      )
      await api.system.setNcbiKey(String(value || '').trim())
      await refreshSummary()
      ElMessage.success('已保存 NCBI Key')
    } catch (e: any) {
      if (e === 'cancel' || e === 'close') return
      ElMessage.error('保存失败')
    }
  }
  if (cmd === 'applyNcbi') {
    window.open('https://www.ncbi.nlm.nih.gov/account/', '_blank')
  }
  if (cmd === 'configS2') {
    try {
      const { value } = await ElMessageBox.prompt(
        `请输入 Semantic Scholar API Key（当前：${s2Mask.value || '未配置'}）\n申请地址：https://www.semanticscholar.org/product/api`,
        '配置 Semantic Scholar Key',
        {
          confirmButtonText: '保存',
          cancelButtonText: '取消',
          inputType: 'password',
          inputPlaceholder: '例如：xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx（40位）',
        }
      )
      await api.system.setS2Key(String(value || '').trim())
      await refreshSummary()
      ElMessage.success('已保存 Semantic Scholar Key')
    } catch (e: any) {
      if (e === 'cancel' || e === 'close') return
      ElMessage.error('保存失败')
    }
  }
  if (cmd === 'applyS2') {
    window.open('https://www.semanticscholar.org/product/api', '_blank')
  }
  if (cmd === 'switch') {
    try {
      const { value } = await ElMessageBox.prompt('输入用户名（用于区分不同用户配置）', '切换用户', {
        confirmButtonText: '登录/切换',
        cancelButtonText: '取消',
        inputPlaceholder: '例如：张三',
      })
      const name = String(value || '').trim()
      if (!name) return
      await authStore.switchUser(name)
    } catch (e: any) {
      if (e === 'cancel' || e === 'close') return
      ElMessage.error('切换失败')
    }
  }
  if (cmd === 'logout') {
    try {
      await ElMessageBox.confirm('将清空本地会话 token，下次请求会重新登录。', '退出登录', {
        confirmButtonText: '退出',
        cancelButtonText: '取消',
        type: 'warning',
      })
      authStore.logout()
      ncbiMask.value = ''
      s2Mask.value   = ''
    } catch {
      // ignore
    }
  }
}
</script>

<style scoped>
.title-bar {
  height: 48px;
  min-height: 48px;
  background: #1a1a2e;
  color: rgba(255,255,255,0.9);
  display: flex;
  align-items: center;
  padding: 0 1.25rem;
  font-size: 1.05rem;
  -webkit-app-region: drag;
  justify-content: space-between;
}
.left { display: flex; align-items: center; }
.app-name { font-weight: 600; font-size: 1.1rem; }
.divider { margin: 0 0.5rem; opacity: 0.6; }
.brand { font-size: 0.85em; opacity: 0.8; }
.right { display: flex; align-items: center; }
.no-drag { -webkit-app-region: no-drag; }
.user-chip {
  cursor: pointer;
  padding: 4px 10px;
  border: 1px solid rgba(255,255,255,0.18);
  border-radius: 999px;
  color: rgba(255,255,255,0.9);
  font-size: 12px;
  line-height: 1;
}
.auth-link {
  color: rgba(255,255,255,0.9);
  text-decoration: none;
  font-size: 13px;
  padding: 4px 8px;
  border-radius: 4px;
  transition: background 0.15s;
}
.auth-link:hover {
  background: rgba(255,255,255,0.12);
  color: #fff;
}
.auth-divider {
  color: rgba(255,255,255,0.4);
  font-size: 13px;
  margin: 0 2px;
}
</style>

<style>
/* 全局覆盖，避免 scoped 无法命中 el-dropdown-menu 内容 */
.key-status-item.el-dropdown-menu__item {
  display: flex !important;
  justify-content: space-between !important;
  align-items: center !important;
  gap: 12px;
  cursor: default !important;
  color: #606266 !important;
  font-size: 12px;
  min-width: 220px;
}
.key-label {
  font-weight: 500;
  color: #303133;
}
.key-badge {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  white-space: nowrap;
}
.key-badge.configured {
  background: #f0f9eb;
  color: #67c23a;
  border: 1px solid #b3e19d;
}
.key-badge.empty {
  background: #fdf6ec;
  color: #e6a23c;
  border: 1px solid #f5dab1;
}
.apply-link-item.el-dropdown-menu__item {
  color: #409eff !important;
  font-size: 12px;
}
</style>
