<template>
  <div class="medcomm-index">
    <div class="header">
      <h2>MedComm 科普写作</h2>
      <el-button type="primary" @click="handleNewArticle">+ 新建文章</el-button>
    </div>
    <el-empty v-if="!articles.length" description="暂无作品，点击新建开始创作" />
    <div v-else class="article-list">
      <el-card v-for="a in articles" :key="a.id" class="article-card" @click="openArticle(a.id)">
        <div class="article-meta">
          <el-tag size="small">{{ formatLabel(a.content_format) }}</el-tag>
          <el-tag size="small" type="info">{{ platformLabel(a.platform) }}</el-tag>
        </div>
        <h3>{{ a.title || a.topic || '未命名' }}</h3>
        <p class="topic">{{ a.topic }}</p>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api'
import { formatLabel, platformLabel } from '@/composables/useFormats'

const router = useRouter()
const articles = ref<any[]>([])

async function loadArticles() {
  try {
    const res = await api.medcomm.getArticles()
    articles.value = res.data?.items || []
  } catch {
    articles.value = []
  }
}

function handleNewArticle() {
  if (router.currentRoute.value.name === 'medcomm-new') {
    router.replace({ path: '/medcomm/new', query: { t: String(Date.now()) } })
    return
  }
  router.push('/medcomm/new')
}

function openArticle(id: number) {
  router.push(`/medcomm/article/${id}`)
}

onMounted(loadArticles)
</script>

<style scoped>
.medcomm-index {
  padding: 1.5rem;
  max-width: 1200px;
  margin: 0 auto;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.article-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
}

.article-card {
  cursor: pointer;
}

.article-card:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.article-meta {
  margin-bottom: 0.5rem;
}

.article-meta .el-tag {
  margin-right: 0.25rem;
}

.article-card h3 {
  font-size: 1rem;
  margin: 0.5rem 0;
}

.topic {
  font-size: 0.875rem;
  color: #666;
}
</style>
