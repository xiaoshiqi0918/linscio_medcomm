import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('portal_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (r) => r,
  (e) => {
    if (e.response?.status === 401) {
      localStorage.removeItem('portal_token')
      if (window.location.pathname !== '/auth') window.location.href = '/auth'
    }
    return Promise.reject(e)
  }
)

export default api

export const auth = {
  register: (data) => api.post('/auth/register', data),
  login: (data) => api.post('/auth/login', data),
}
export const user = {
  profile: () => api.get('/user/profile'),
  activate: (code) => api.post('/user/activate', { code }),
  updateLicense: (code) => api.post('/user/update-license', { code }),
  license: () => api.get('/user/license'),
  registryCredential: () => api.get('/user/registry-credential'), // 已废弃，请用 registryCredentialFromRegistry（GET /registry/credential）
  registryCredentialFromRegistry: () => api.get('/registry/credential'),
  machines: () => api.get('/user/machines'),
  deleteMachine: (bindingId) => api.delete(`/user/machines/${bindingId}`),
  quotaSummary: () => api.get('/user/quota-summary'),
}

export const download = {
  getCurrentVersion: () => api.get('/public/download/current-version'),
  getPresignUrl: (licenseCode) => api.post('/public/download/presign-url', { license_code: licenseCode }),
}
