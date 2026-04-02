import { createRouter, createWebHashHistory } from 'vue-router'
import AppLayout from '@/components/layout/AppLayout.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
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
          path: 'imagegen',
          name: 'imagegen',
          component: () => import('@/views/imagegen/Index.vue'),
          meta: { title: '图像生成' },
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
        {
          path: 'publish',
          name: 'publish',
          component: () => import('@/views/publish/Index.vue'),
          meta: { title: '发布管理' },
        },
      ],
    },
  ],
})

export default router
