<template>
  <div id="app" class="app-container">
    <div v-if="activationError" class="activation-toast">{{ activationError }}</div>
    <ActivationGuide v-if="showActivationGuide" />
    <router-view v-else />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import ActivationGuide from '@/views/ActivationGuide.vue'

const showActivationGuide = ref(false)
const router = useRouter()

const activationError = ref('')

onMounted(() => {
  const api = (window as unknown as { electronAPI?: {
    onShowActivationGuide?: (cb: () => void) => void
    onLicenseActivated?: (cb: (p: unknown) => void) => void
    onActivationError?: (cb: (p: { message: string }) => void) => void
  } }).electronAPI
  if (!api) return
  api.onShowActivationGuide?.(() => {
    showActivationGuide.value = true
    router.replace('/').catch(() => {})
  })
  api.onLicenseActivated?.(() => {
    showActivationGuide.value = false
    activationError.value = ''
    router.replace('/').catch(() => {})
  })
  api.onActivationError?.((payload) => {
    activationError.value = payload?.message || '激活失败，请重试'
    setTimeout(() => { activationError.value = '' }, 8000)
  })
})
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #app {
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

.activation-toast {
  position: fixed;
  top: 16px;
  left: 50%;
  transform: translateX(-50%);
  background: #dc3545;
  color: #fff;
  padding: 10px 24px;
  border-radius: 8px;
  font-size: 14px;
  z-index: 10000;
  box-shadow: 0 4px 12px rgba(0,0,0,0.3);
  animation: toast-in 0.3s ease;
}
@keyframes toast-in {
  from { opacity: 0; transform: translateX(-50%) translateY(-10px); }
  to   { opacity: 1; transform: translateX(-50%) translateY(0); }
}
</style>
