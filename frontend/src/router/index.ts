import { createRouter, createWebHashHistory, createWebHistory } from 'vue-router'
import AppLayout from '@/components/layout/AppLayout.vue'
import { getAuthToken, setAuthToken } from '@/api'

const isElectron = typeof window !== 'undefined' && !!(window as any).electronAPI?.isElectron

const router = createRouter({
  history: isElectron ? createWebHashHistory() : createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/auth/LoginView.vue'),
      meta: { title: '登录', guest: true },
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('@/views/auth/RegisterView.vue'),
      meta: { title: '注册', guest: true },
    },
    {
      path: '/',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'home',
          redirect: '/medcomm',
        },
        {
          path: 'medcomm',
          component: () => import('@/views/medcomm/MedCommLayout.vue'),
          children: [
            { path: '', name: 'medcomm', component: () => import('@/views/medcomm/MedCommEmpty.vue'), meta: { title: '科普写作' } },
            { path: 'new', name: 'medcomm-new', component: () => import('@/views/medcomm/NewArticle.vue'), meta: { title: '新建文章' } },
            { path: 'article/:id', name: 'article', component: () => import('@/views/medcomm/Article.vue'), meta: { title: '编辑文章' } },
          ],
        },
        {
          path: 'settings',
          name: 'settings',
          component: () => import('@/views/Settings.vue'),
          meta: { title: '设置' },
        },
        {
          path: 'help',
          name: 'help',
          component: () => import('@/views/HelpView.vue'),
          meta: { title: '帮助中心' },
        },
        {
          path: 'contact',
          name: 'contact',
          component: () => import('@/views/ContactView.vue'),
          meta: { title: '联系我们' },
        },
        {
          path: 'drawing',
          redirect: '/drawing/txt2img',
        },
        {
          path: 'drawing/txt2img',
          name: 'txt2img',
          component: () => import('@/views/drawing/Txt2Img.vue'),
          meta: { title: '文生图' },
        },
        {
          path: 'drawing/img2img',
          name: 'img2img',
          component: () => import('@/views/drawing/Img2Img.vue'),
          meta: { title: '图生图' },
        },
        {
          path: 'literature',
          name: 'literature',
          component: () => import('@/views/literature/Index.vue'),
          meta: { title: '文献支撑库' },
        },
        {
          path: 'literature/paper/:paperId',
          name: 'literature-paper',
          component: () => import('@/views/literature/Detail.vue'),
          meta: { title: '文献详情' },
        },
        {
          path: 'templates',
          name: 'templates',
          component: () => import('@/views/templates/Index.vue'),
          meta: { title: '模板库' },
        },
        {
          path: 'creations',
          name: 'creations',
          component: () => import('@/views/medcomm/Index.vue'),
          meta: { title: '创作库' },
        },
        {
          path: 'knowledge',
          name: 'knowledge',
          component: () => import('@/views/knowledge/Index.vue'),
          meta: { title: '知识库' },
        },
        {
          path: 'personal-corpus',
          name: 'personal-corpus',
          component: () => import('@/views/personal/PersonalCorpus.vue'),
          meta: { title: '个人语料' },
      },
    ],
  },
  {
    path: '/admin',
    component: () => import('@/views/admin/AdminLayout.vue'),
    meta: { title: '管理后台', admin: true },
    children: [
      { path: '', name: 'admin-dashboard', component: () => import('@/views/admin/DashboardView.vue'), meta: { title: '仪表盘' } },
      { path: 'users', name: 'admin-users', component: () => import('@/views/admin/UsersView.vue'), meta: { title: '用户管理' } },
      { path: 'orders', name: 'admin-orders', component: () => import('@/views/admin/OrdersView.vue'), meta: { title: '订单管理' } },
      { path: 'reconciliation', name: 'admin-recon', component: () => import('@/views/admin/ReconciliationView.vue'), meta: { title: '对账记录' } },
      { path: 'licenses', name: 'admin-licenses', component: () => import('@/views/admin/LicensesView.vue'), meta: { title: '授权码管理' } },
      { path: 'redeem-codes', name: 'admin-redeem-codes', component: () => import('@/views/admin/RedeemCodesView.vue'), meta: { title: '兑换码管理' } },
      { path: 'withdrawals', name: 'admin-withdrawals', component: () => import('@/views/admin/WithdrawalsView.vue'), meta: { title: '兑现审批' } },
      { path: 'config', name: 'admin-config', component: () => import('@/views/admin/ConfigView.vue'), meta: { title: '系统配置' } },
    ],
  },
],
})

const _isElectronEnv = typeof window !== 'undefined' && !!(window as any).electronAPI?.isElectron

router.beforeEach((to, _from, next) => {
  const token = getAuthToken()

  if (_isElectronEnv) {
    // 桌面端：未登录强制跳转登录页
    if (!token && !to.meta.guest) {
      next({ name: 'login', query: { redirect: to.fullPath } })
    } else if (token && to.meta.guest) {
      next('/')
    } else {
      next()
    }
    return
  }

  // SaaS：未登录可浏览，但 admin 页面仍需登录
  if (!token && to.meta.admin) {
    next({ name: 'login', query: { redirect: to.fullPath } })
  } else if (token && to.meta.guest) {
    if (to.name === 'register' && to.query.ref) {
      setAuthToken(null)
      try { localStorage.removeItem('linscio_refresh_token') } catch {}
      next()
    } else {
      next('/')
    }
  } else {
    next()
  }
})

export default router
