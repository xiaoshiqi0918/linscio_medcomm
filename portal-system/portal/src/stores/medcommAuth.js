import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { medcommAuth, medcommLicense } from '../api/medcomm'

export const useMedcommAuthStore = defineStore('medcommAuth', () => {
  const token = ref(localStorage.getItem('medcomm_session_token') || '')
  const licenseStatus = ref(null)

  const isLoggedIn = computed(() => !!token.value)

  function setToken(t) {
    token.value = t
    if (t) localStorage.setItem('medcomm_session_token', t)
    else localStorage.removeItem('medcomm_session_token')
  }

  async function login(credential, password) {
    const { data } = await medcommAuth.login({ credential, password })
    setToken(data.session_token)
    return data
  }

  async function register(payload) {
    await medcommAuth.register(payload)
  }

  function logout() {
    setToken('')
    licenseStatus.value = null
  }

  async function fetchLicenseStatus() {
    if (!token.value) return null
    try {
      const { data } = await medcommLicense.status()
      licenseStatus.value = data
      return data
    } catch {
      return null
    }
  }

  return {
    token,
    licenseStatus,
    isLoggedIn,
    setToken,
    login,
    register,
    logout,
    fetchLicenseStatus,
  }
})
