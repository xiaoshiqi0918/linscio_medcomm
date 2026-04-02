import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/auth',
    name: 'Auth',
    component: () => import('../views/Auth.vue'),
    meta: { title: '登录/注册' },
  },
  {
    path: '/medcomm/login',
    name: 'MedCommLogin',
    component: () => import('../views/medcomm/MedCommLogin.vue'),
    meta: { title: 'MedComm 登录' },
  },
  {
    path: '/medcomm',
    component: () => import('../layouts/PortalLayout.vue'),
    meta: { medcommAuth: true },
    redirect: '/medcomm/activate',
    children: [
      { path: 'activate', name: 'MedCommActivate', component: () => import('../views/medcomm/MedCommActivate.vue'), meta: { title: '激活授权码' } },
      { path: 'specialties', name: 'MedCommSpecialties', component: () => import('../views/medcomm/MedCommSpecialties.vue'), meta: { title: '我的学科包' } },
      { path: 'device', name: 'MedCommDevice', component: () => import('../views/medcomm/MedCommDevice.vue'), meta: { title: '换机' } },
      { path: 'device/request', name: 'MedCommDeviceRequest', component: () => import('../views/medcomm/MedCommDeviceRequest.vue'), meta: { title: '申请换机码', medcommAuth: false } },
      { path: 'migration', name: 'MedCommMigration', component: () => import('../views/medcomm/MedCommMigration.vue'), meta: { title: '账号迁移' } },
      { path: 'download', name: 'MedCommDownload', component: () => import('../views/medcomm/MedCommDownload.vue'), meta: { title: '软件更新与下载' } },
      { path: 'help', name: 'MedCommHelp', component: () => import('../views/medcomm/MedCommHelp.vue'), meta: { title: '帮助中心', medcommAuth: false } },
    ],
  },
  {
    path: '/',
    component: () => import('../layouts/PortalLayout.vue'),
    children: [
      { path: '', name: 'Home', component: () => import('../views/Home.vue'), meta: { title: '首页' } },
      { path: 'features', name: 'Features', component: () => import('../views/Features.vue'), meta: { title: '功能详情' } },
      { path: 'docs', name: 'Docs', component: () => import('../views/Docs.vue'), meta: { title: '文档' } },
      { path: 'download', name: 'Download', component: () => import('../views/Download.vue'), meta: { title: '下载' } },
      { path: 'about', name: 'About', component: () => import('../views/About.vue'), meta: { title: '关于我们' } },
      { path: 'dashboard', name: 'Dashboard', component: () => import('../views/Dashboard.vue'), meta: { title: '用户中心', requiresAuth: true } },
      { path: 'dashboard/machines', name: 'Machines', component: () => import('../views/Machines.vue'), meta: { title: '机器管理', requiresAuth: true } },
      { path: 'dashboard/quota', name: 'Quota', component: () => import('../views/Quota.vue'), meta: { title: '生成次数', requiresAuth: true } },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('portal_token')
  const requiresAuth = to.matched.some((r) => r.meta.requiresAuth)
  if (requiresAuth && !token) {
    next('/auth')
    return
  }
  const needsMedcomm = to.matched.some((r) => r.meta.medcommAuth)
  const skipMedcommAuth = to.matched.some((r) => r.meta.medcommAuth === false)
  if (needsMedcomm && !skipMedcommAuth && !localStorage.getItem('medcomm_session_token')) {
    next({ path: '/medcomm/login', query: { redirect: to.fullPath } })
    return
  }
  next()
})

export default router
