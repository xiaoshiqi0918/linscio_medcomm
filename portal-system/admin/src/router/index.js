import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'Stats', component: () => import('../views/Stats.vue'), meta: { title: '数据总览' } },
  { path: '/users', name: 'Users', component: () => import('../views/Users.vue'), meta: { title: '用户管理' } },
  { path: '/plans-periods', name: 'PlansAndPeriods', component: () => import('../views/PlansAndPeriods.vue'), meta: { title: '套餐与周期' } },
  { path: '/licenses', name: 'Licenses', component: () => import('../views/Licenses.vue'), meta: { title: '授权码管理' } },
  { path: '/modules', name: 'Modules', component: () => import('../views/Modules.vue'), meta: { title: '模块权限配置' } },
  { path: '/registry', name: 'Registry', component: () => import('../views/Registry.vue'), meta: { title: '镜像版本' } },
  { path: '/settings', name: 'Settings', component: () => import('../views/Settings.vue'), meta: { title: '系统设置' } },
  { path: '/login', name: 'Login', component: () => import('../views/Login.vue'), meta: { title: '登录' } },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('admin_token')
  if (to.path === '/login') {
    if (token) next('/')  // 已登录则跳转首页
    else next()
  } else if (!token) {
    next('/login')
  } else {
    next()
  }
})

export default router
