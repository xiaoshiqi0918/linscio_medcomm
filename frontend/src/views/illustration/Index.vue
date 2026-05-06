<template>
  <div class="illustration-index">
    <div class="page-header">
      <h2>配图工作台</h2>
      <p class="page-hint">先选择一篇文章，然后进入它的配图工作台进行画意撰写、批量生图、视觉锚点配置与海报导出。</p>
    </div>

    <div class="filters-bar">
      <el-input
        v-model="search"
        placeholder="按标题 / 主题搜索"
        clearable
        size="default"
        style="width: 280px"
        :prefix-icon="Search"
      />
      <el-select v-model="filterFormat" placeholder="全部形式" clearable size="default" style="width: 200px">
        <el-option v-for="(name, id) in FORMAT_NAMES" :key="id" :label="name" :value="id" />
      </el-select>
      <el-tooltip content="仅显示赛制 / 长文 / 健康手册等支持配图的文章" placement="top">
        <el-checkbox v-model="onlyImageCapable">仅显示支持配图的形式</el-checkbox>
      </el-tooltip>
    </div>

    <el-empty v-if="!loading && !filteredArticles.length" description="暂无可用文章" />

    <div v-else v-loading="loading" class="article-grid">
      <div
        v-for="art in filteredArticles"
        :key="art.id"
        class="article-card"
        :class="{ 'is-disabled': !isImageCapable(art.content_format) }"
        @click="onSelect(art)"
      >
        <div class="card-title">
          {{ art.title || art.topic || '未命名' }}
        </div>
        <div class="card-meta">
          <FormatBadge :format-id="art.content_format || 'article'" />
          <PlatformBadge v-if="art.platform" :platform-id="art.platform" />
          <span v-if="art.word_count != null" class="meta-word">{{ art.word_count }} 字</span>
        </div>
        <div class="card-footer">
          <span class="card-time">{{ formatDate(art.updated_at || art.created_at) }}</span>
          <el-tag v-if="!isImageCapable(art.content_format)" size="small" type="info" effect="plain">
            该形式暂不支持配图
          </el-tag>
          <el-button v-else size="small" type="primary" plain>进入配图 →</el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { api } from '@/api'
import { FORMAT_NAMES } from '@/composables/useFormats'
import FormatBadge from '@/components/common/FormatBadge.vue'
import PlatformBadge from '@/components/common/PlatformBadge.vue'

const FORMATS_WITH_IMAGE_SLOTS = new Set(['contest_article', 'article', 'patient_handbook'])

const router = useRouter()
const articles = ref<any[]>([])
const loading = ref(false)
const search = ref('')
const filterFormat = ref('')
const onlyImageCapable = ref(true)

function isImageCapable(fmt: string | undefined | null): boolean {
  return !!fmt && FORMATS_WITH_IMAGE_SLOTS.has(fmt)
}

const filteredArticles = computed(() => {
  let list = articles.value
  if (filterFormat.value) list = list.filter(a => a.content_format === filterFormat.value)
  if (onlyImageCapable.value) list = list.filter(a => isImageCapable(a.content_format))
  const q = search.value.trim().toLowerCase()
  if (q) {
    list = list.filter(a => {
      const t = (a.title || '').toLowerCase()
      const topic = (a.topic || '').toLowerCase()
      return t.includes(q) || topic.includes(q)
    })
  }
  return list
})

function formatDate(s: string | undefined | null): string {
  if (!s) return '—'
  try {
    const d = new Date(s)
    return d.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
  } catch {
    return String(s)
  }
}

function onSelect(art: any) {
  if (!isImageCapable(art.content_format)) {
    ElMessage.info('该文章形式暂不支持配图工作台（仅赛制 / 长文 / 健康手册等支持）')
    return
  }
  router.push(`/illustration/${art.id}`)
}

async function loadArticles() {
  loading.value = true
  try {
    const res = await api.medcomm.getArticles()
    const items = (res.data?.items || []) as any[]
    items.sort((a, b) => {
      const ta = new Date(a.updated_at || a.created_at || 0).getTime()
      const tb = new Date(b.updated_at || b.created_at || 0).getTime()
      return tb - ta
    })
    articles.value = items
  } catch {
    articles.value = []
  } finally {
    loading.value = false
  }
}

onMounted(loadArticles)
</script>

<style scoped>
.illustration-index {
  padding: 1.5rem 2rem 3rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  min-height: 100%;
  box-sizing: border-box;
}

.page-header h2 {
  margin: 0;
  font-size: 1.4rem;
  color: #1f2937;
}
.page-hint {
  margin: 0.4rem 0 0;
  color: #6b7280;
  font-size: 0.9rem;
}

.filters-bar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.article-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
}

.article-card {
  background: #fff;
  border-radius: 10px;
  padding: 1rem;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
  border: 1px solid transparent;
  cursor: pointer;
  transition: box-shadow 0.15s, border-color 0.15s, transform 0.1s;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  min-height: 140px;
}
.article-card:hover {
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
  border-color: #93c5fd;
  transform: translateY(-1px);
}
.article-card.is-disabled {
  cursor: not-allowed;
  opacity: 0.7;
}
.article-card.is-disabled:hover {
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
  border-color: transparent;
  transform: none;
}

.card-title {
  font-size: 1rem;
  font-weight: 600;
  color: #111827;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.card-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  font-size: 0.8rem;
  color: #6b7280;
}
.meta-word {
  background: #f3f4f6;
  border-radius: 999px;
  padding: 1px 8px;
  font-size: 0.75rem;
}
.card-footer {
  margin-top: auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 0.8rem;
}
.card-time {
  color: #9ca3af;
}
</style>
