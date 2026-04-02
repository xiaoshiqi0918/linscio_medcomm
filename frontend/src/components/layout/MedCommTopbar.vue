<template>
  <header class="medcomm-topbar">
    <div class="breadcrumb">
      <span>MedComm</span>
      <span v-if="article" class="sep">›</span>
      <span v-if="article">{{ article.title || article.topic || '编辑中' }}</span>
    </div>
    <div class="tags">
      <FormatBadge v-if="article?.content_format" :format-id="article.content_format" />
      <PlatformBadge v-if="article?.platform" :platform-id="article.platform" />
    </div>
    <el-button class="new-btn" type="primary" size="small" @click="goNew">+ 新建</el-button>
  </header>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import FormatBadge from '@/components/common/FormatBadge.vue'
import PlatformBadge from '@/components/common/PlatformBadge.vue'

defineProps<{
  article?: { title?: string; topic?: string; content_format?: string; platform?: string } | null
}>()

const router = useRouter()
const route = useRoute()

async function goNew() {
  // 若已在新建页，附加时间戳强制触发一次路由更新，避免“点击无反应”感知
  if (route.name === 'medcomm-new') {
    await router.replace({ path: '/medcomm/new', query: { t: String(Date.now()) } })
    return
  }
  await router.push('/medcomm/new')
}
</script>

<style scoped>
.medcomm-topbar {
  height: 56px;
  min-height: 56px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 1rem;
}
.breadcrumb { font-size: 0.95rem; color: #374151; }
.sep { margin: 0 0.5rem; color: #9ca3af; }
.tags { display: flex; gap: 0.5rem; }
.new-btn { -webkit-app-region: no-drag; }
</style>
