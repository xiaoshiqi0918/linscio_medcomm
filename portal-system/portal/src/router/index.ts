import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/auth/Login.vue'),
      meta: { guest: true },
    },
    {
      path: '/register',
      name: 'Register',
      component: () => import('@/views/auth/Register.vue'),
      meta: { guest: true },
    },
    {
      path: '/forgot-password',
      name: 'ForgotPassword',
      component: () => import('@/views/auth/ForgotPassword.vue'),
      meta: { guest: true },
    },
    {
      path: '/reset-password',
      name: 'ResetPassword',
      component: () => import('@/views/auth/ResetPassword.vue'),
      meta: { guest: true },
    },
    {
      path: '/logout',
      name: 'Logout',
      component: () => import('@/views/auth/Logout.vue'),
    },
    {
      path: '/',
      component: () => import('@/components/layout/AppLayout.vue'),
      meta: { auth: true },
      children: [
        { path: '', redirect: '/license' },
        {
          path: 'license',
          name: 'License',
          component: () => import('@/views/license/Index.vue'),
        },
        {
          path: 'license/activate',
          name: 'Activate',
          component: () => import('@/views/license/Activate.vue'),
        },
        {
          path: 'license/specialties',
          name: 'Specialties',
          component: () => import('@/views/license/Specialties.vue'),
        },
        {
          path: 'device',
          name: 'Device',
          component: () => import('@/views/device/Index.vue'),
        },
        {
          path: 'account',
          name: 'Account',
          component: () => import('@/views/account/Index.vue'),
        },
        {
          path: 'download',
          name: 'Download',
          component: () => import('@/views/download/Index.vue'),
        },
      ],
    },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.auth && !auth.isLoggedIn) {
    return { name: 'Login', query: { redirect: to.fullPath } }
  }
  if (to.meta.guest && auth.isLoggedIn) {
    return '/'
  }
})

export default router
