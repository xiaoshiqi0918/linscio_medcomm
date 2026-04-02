import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { auth as authApi, user as userApi } from '../api'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('portal_token') || '')
  const profile = ref(null)

  const isLoggedIn = computed(() => !!token.value)

  function setToken(t) {
    token.value = t
    if (t) localStorage.setItem('portal_token', t)
    else localStorage.removeItem('portal_token')
  }

  async function login(username, password) {
    const { data } = await authApi.login({ username, password })
    setToken(data.access_token)
    await fetchProfile()
    return data
  }

  async function register(payload) {
    const { data } = await authApi.register(payload)
    setToken(data.access_token)
    await fetchProfile()
    return data
  }

  function logout() {
    setToken('')
    profile.value = null
  }

  async function fetchProfile() {
    if (!token.value) return
    try {
      const { data } = await userApi.profile()
      profile.value = data
      return data
    } catch {
      logout()
    }
  }

  return { token, profile, isLoggedIn, setToken, login, register, logout, fetchProfile }
})
