import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('admin_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (r) => r,
  (e) => {
    if (e.response?.status === 401 && window.location.pathname !== '/login') {
      localStorage.removeItem('admin_token')
      window.location.href = '/login'
    }
    return Promise.reject(e)
  }
)

export default api

export const adminAuth = {
  login: (data) => api.post('/admin/auth/login', data),
}
export const admin = {
  stats: () => api.get('/admin/stats'),
  plans: () => api.get('/admin/plans'),
  plansManage: () => api.get('/admin/plans/manage'),
  planCreate: (data) => api.post('/admin/plans', data),
  planUpdate: (id, data) => api.patch(`/admin/plans/${id}`, data),
  billingPeriods: () => api.get('/admin/billing-periods'),
  billingPeriodsManage: () => api.get('/admin/billing-periods/manage'),
  billingPeriodCreate: (data) => api.post('/admin/billing-periods', data),
  billingPeriodUpdate: (id, data) => api.patch(`/admin/billing-periods/${id}`, data),
  plansPeriodsSeedDefaults: () => api.post('/admin/plans-periods/seed-defaults'),
  users: (params) => api.get('/admin/users', { params }),
  userUpdate: (id, data) => api.patch(`/admin/users/${id}`, data),
  refreshUserCredential: (userId) => api.post(`/admin/users/${userId}/refresh-credential`),
  licenses: (params) => api.get('/admin/licenses', { params }),
  licenseDetail: (id) => api.get(`/admin/licenses/${id}`),
  licensesBatch: (data) => api.post('/admin/licenses/batch', data),
  licensePreview: (params) => api.get('/admin/licenses/preview', { params }),
  licenseRevoke: (id) => api.patch(`/admin/licenses/${id}`),
  licenseExtend: (id, data) => api.patch(`/admin/licenses/${id}/extend`, data),
  licensesExport: () => api.get('/admin/licenses/export', { responseType: 'blob' }),
  modules: (params) => api.get('/admin/modules', { params }),
  moduleUpdate: (id, data) => api.patch(`/admin/modules/${id}`, data),
  moduleCreate: (data) => api.post('/admin/modules', data),
  seedControlledModules: () => api.post('/admin/modules/seed-controlled'),
  syncModules: () => api.post('/admin/registry-credentials/sync-modules'),
}
