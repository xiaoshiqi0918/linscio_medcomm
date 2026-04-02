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

  async function switchUser(username: string) {
    const name = String(username || '').trim()
    if (!name) throw new Error('username 为空')
    const res = await api.auth.login({ username: name })
    const token = String(res.data?.token || '')
    if (!token) throw new Error('token 为空')
    setAuthToken(token)
    try {
      window.localStorage.setItem(AUTH_PREFERRED_USERNAME_KEY, name)
    } catch {
      // ignore
    }
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

