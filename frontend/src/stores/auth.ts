import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, setAuthToken } from '@/api'

export const AUTH_USER_CHANGED_EVENT = 'linscio:auth-user-changed'
export const AUTH_PREFERRED_USERNAME_KEY = 'linscio_preferred_username'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<any>(null)
  const loading = ref(false)

  async function refreshMe() {
    loading.value = true
    try {
      const me = await api.auth.me()
      user.value = me.data
    } catch {
      user.value = null
    } finally {
      loading.value = false
    }
  }

  async function switchUser(_username?: string) {
    await refreshMe()
    window.dispatchEvent(new CustomEvent(AUTH_USER_CHANGED_EVENT, {
      detail: {
        userId: user.value?.id ?? null,
        displayName: user.value?.display_name ?? null,
        action: 'switch',
      },
    }))
  }

  function logout() {
    setAuthToken(null)
    user.value = null
    try {
      window.localStorage.removeItem(AUTH_PREFERRED_USERNAME_KEY)
    } catch {
      // ignore
    }
    window.dispatchEvent(new CustomEvent(AUTH_USER_CHANGED_EVENT, {
      detail: {
        userId: null,
        displayName: null,
        action: 'logout',
      },
    }))
  }

  return { user, loading, refreshMe, switchUser, logout }
})

