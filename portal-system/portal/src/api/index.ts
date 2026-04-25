import axios from 'axios'

const AUTH_TOKEN_KEY = 'linscio_auth_token'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8765',
  timeout: 30000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(AUTH_TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem(AUTH_TOKEN_KEY)
      localStorage.removeItem('linscio_refresh_token')
      const currentPath = window.location.pathname
      if (currentPath !== '/login') {
        window.location.href = `/login?redirect=${encodeURIComponent(currentPath)}`
      }
    }
    return Promise.reject(err)
  },
)

export default api

export function setAuthToken(token: string | null) {
  if (token) localStorage.setItem(AUTH_TOKEN_KEY, token)
  else localStorage.removeItem(AUTH_TOKEN_KEY)
}

export function getAuthToken(): string | null {
  return localStorage.getItem(AUTH_TOKEN_KEY)
}

// Auth — 与 SaaS 后端 /api/v1/auth 接口一致
export const authRegister = (data: {
  phone: string
  password: string
  display_name?: string
  referral_code?: string
  agreed_terms: boolean
}) => api.post('/api/v1/auth/register', data)

export const authLogin = (data: { phone: string; password: string }) =>
  api.post('/api/v1/auth/login', data)

export const authRefresh = (data: { refresh_token: string }) =>
  api.post('/api/v1/auth/refresh', data)

export const authLogout = () => api.post('/api/v1/auth/logout')

export const authMe = () => api.get('/api/v1/auth/me')

// License
export const licenseActivate = (data: { code: string; device_fingerprint?: string; device_name?: string }) =>
  api.post('/api/license/activate', data)
export const licenseStatusAll = () =>
  api.get('/api/license/status/all')

// Products
export const getProducts = () => api.get('/api/products')

// User specialties
export const getUserSpecialties = () => api.get('/api/license/specialties')

// Download — SaaS 后端
export const getProductInfo = () => api.get('/api/v1/download/product-info')
export const downloadSoftware = (data: { product_id: string; platform: string }) =>
  api.post('/api/v1/download/software', data)

// Device
export const deviceVerify = (data: { product_id: string; code: string }) =>
  api.post('/api/device/change-code/verify', data)

// Account
export const changePassword = (data: { old_password: string; new_password: string }) =>
  api.post('/api/account/change-password', data)
export const changePhone = (data: { phone: string }) =>
  api.patch('/api/account/phone', data)
export const deleteAccount = (data: { password: string }) =>
  api.delete('/api/account', { data })
