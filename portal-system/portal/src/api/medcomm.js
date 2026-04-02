import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('medcomm_session_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (r) => r,
  (e) => {
    if (e.response?.status === 401) {
      localStorage.removeItem('medcomm_session_token')
      if (!window.location.pathname.startsWith('/medcomm/login')) {
        window.location.href = '/medcomm/login'
      }
    }
    return Promise.reject(e)
  }
)

export const medcommAuth = {
  register: (data) => api.post('/medcomm/auth/register', data),
  verify: (data) => api.post('/medcomm/auth/verify', data),
  login: (data) => api.post('/medcomm/auth/login', data),
  changePassword: (data) => api.post('/medcomm/auth/change-password', data),
  forgotPassword: (data) => api.post('/medcomm/auth/forgot-password', data),
  resetPassword: (data) => api.post('/medcomm/auth/reset-password', data),
}

export const medcommLicense = {
  validate: (data) => api.post('/medcomm/license/validate', data),
  activate: (data) => api.post('/medcomm/license/activate', data),
  status: (params) => api.get('/medcomm/license/status', { params }),
}

export const medcommDevice = {
  requestChangeCode: (data) => api.post('/medcomm/device/change-code/request', data),
  verifyChangeCode: (data) => api.post('/medcomm/device/change-code/verify', data),
}

export const medcommUpdate = {
  check: (data) => api.post('/medcomm/update/check', data),
}

export const medcommDownload = {
  software: (data) => api.post('/medcomm/download/software', data),
  complete: (data) => api.post('/medcomm/download/complete', data),
  specialty: (data) => api.post('/medcomm/specialty/download', data),
  specialtyDocuments: (specialtyId) => api.get(`/medcomm/specialty/${specialtyId}/documents`),
}

export const medcommAccount = {
  migrationRequest: (data) => api.post('/medcomm/account/migration-request', data),
}

export default api
