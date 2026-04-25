<template>
  <div class="auth-page">
    <p class="muted">正在退出…</p>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { authLogout } from '@/api'

const router = useRouter()
const auth = useAuthStore()

onMounted(async () => {
  try { await authLogout() } catch {}
  auth.clearSession()
  router.push('/login')
})
</script>

<style scoped lang="scss">
.auth-page {
  min-height: 40vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}
.muted { color: var(--text-muted, #888); font-size: 14px; }
</style>
