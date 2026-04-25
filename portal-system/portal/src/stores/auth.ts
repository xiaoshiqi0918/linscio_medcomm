import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const AUTH_TOKEN_KEY = 'linscio_auth_token'
const REFRESH_TOKEN_KEY = 'linscio_refresh_token'

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref(localStorage.getItem(AUTH_TOKEN_KEY) || '')
  const userPhone = ref(localStorage.getItem('user_phone') || '')
  const displayName = ref(localStorage.getItem('user_display_name') || '')

  const isLoggedIn = computed(() => !!accessToken.value)

  function setSession(access: string, refresh: string, phone: string, name: string) {
    accessToken.value = access
    userPhone.value = phone
    displayName.value = name
    localStorage.setItem(AUTH_TOKEN_KEY, access)
    localStorage.setItem(REFRESH_TOKEN_KEY, refresh)
    localStorage.setItem('user_phone', phone)
    localStorage.setItem('user_display_name', name)
  }

  function clearSession() {
    accessToken.value = ''
    userPhone.value = ''
    displayName.value = ''
    localStorage.removeItem(AUTH_TOKEN_KEY)
    localStorage.removeItem(REFRESH_TOKEN_KEY)
    localStorage.removeItem('user_phone')
    localStorage.removeItem('user_display_name')
  }

  return { accessToken, userPhone, displayName, isLoggedIn, setSession, clearSession }
})
