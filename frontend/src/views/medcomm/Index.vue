<template>
  <div class="creation-lib">
    <div class="header">
      <h2>创作库</h2>
      <div class="header-actions">
        <el-button
          v-if="selectedIds.length"
          type="danger"
          plain
          @click="handleBatchDelete"
        >
          批量删除 ({{ selectedIds.length }})
        </el-button>
        <el-button type="primary" @click="handleNewArticle">+ 新建文章</el-button>
      </div>
    </div>

    <div class="filters-bar">
      <el-select v-model="filterFormat" placeholder="全部形式" clearable size="default" style="width: 160px">
        <el-option v-for="(name, id) in FORMAT_NAMES" :key="id" :label="name" :value="id" />
      </el-select>
      <el-select v-model="filterPlatform" placeholder="全部平台" clearable size="default" style="width: 160px">
        <el-option v-for="(name, id) in PLATFORM_NAMES" :key="id" :label="name" :value="id" />
      </el-select>
    </div>

    <el-empty v-if="!loading && !filteredArticles.length" description="暂无作品，点击新建开始创作" />

    <el-table
      v-else
      ref="tableRef"
      v-loading="loading"
      :data="filteredArticles"
      style="width: 100%"
      @selection-change="onSelectionChange"
    >
      <el-table-column type="selection" width="50" />
      <el-table-column label="标题" min-width="240">
        <template #default="{ row }">
          <span class="title-link" @click="previewArticle(row)">
            {{ row.title || row.topic || '未命名' }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="主题" prop="topic" min-width="200" show-overflow-tooltip />
      <el-table-column label="形式" width="120">
        <template #default="{ row }">
          <el-tag size="small">{{ formatLabel(row.content_format) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="平台" width="120">
        <template #default="{ row }">
          <el-tag size="small" type="info">{{ platformLabel(row.platform) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="字数" width="80" prop="word_count" />
      <el-table-column label="更新时间" width="170">
        <template #default="{ row }">
          {{ formatDate(row.updated_at || row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="previewArticle(row)">预览</el-button>
          <el-button link type="primary" size="small" @click="downloadWord(row)">下载</el-button>
          <el-button link type="primary" size="small" @click="editArticle(row.id)">编辑</el-button>
          <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 全文预览弹窗 -->
    <el-dialog
      v-model="previewVisible"
      :title="previewTitle"
      width="800px"
      top="5vh"
      destroy-on-close
      class="preview-dialog"
    >
      <div class="preview-toolbar">
        <el-button type="primary" size="small" @click="downloadWord(previewRow)" :loading="downloading">
          下载 Word
        </el-button>
        <el-button size="small" @click="editArticle(previewRow?.id)">前往编辑</el-button>
      </div>
      <div v-loading="previewLoading" class="preview-body">
        <div v-if="previewHtml" v-html="previewHtml" class="article-preview-content" />
        <el-empty v-else-if="!previewLoading" description="暂无内容，请先生成文章" />
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api'
import { formatLabel, platformLabel, FORMAT_NAMES, PLATFORM_NAMES } from '@/composables/useFormats'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()
const articles = ref<any[]>([])
const loading = ref(false)
const selectedIds = ref<number[]>([])
const tableRef = ref()

const filterFormat = ref('')
const filterPlatform = ref('')

const filteredArticles = computed(() => {
  let list = articles.value
  if (filterFormat.value) list = list.filter((a) => a.content_format === filterFormat.value)
  if (filterPlatform.value) list = list.filter((a) => a.platform === filterPlatform.value)
  return list
})

const previewVisible = ref(false)
const previewLoading = ref(false)
const previewHtml = ref('')
const previewTitle = ref('')
const previewRow = ref<any>(null)
const downloading = ref(false)

async function loadArticles() {
  loading.value = true
  try {
    const res = await api.medcomm.getArticles()
    articles.value = res.data?.items || []
  } catch {
    articles.value = []
  } finally {
    loading.value = false
  }
}

function onSelectionChange(rows: any[]) {
  selectedIds.value = rows.map((r: any) => r.id)
}

function handleNewArticle() {
  router.push('/medcomm/new')
}

function editArticle(id: number) {
  previewVisible.value = false
  router.push(`/medcomm/article/${id}`)
}

async function previewArticle(row: any) {
  previewRow.value = row
  previewTitle.value = row.title || row.topic || '未命名'
  previewHtml.value = ''
  previewVisible.value = true
  previewLoading.value = true
  try {
    const res = await api.medcomm.exportArticle(row.id, 'html')
    const blob = res.data as Blob
    previewHtml.value = await blob.text()
  } catch {
    previewHtml.value = ''
  } finally {
    previewLoading.value = false
  }
}

async function downloadWord(row: any) {
  if (!row) return
  downloading.value = true
  try {
    const res = await api.medcomm.exportArticle(row.id, 'docx')
    const blob = new Blob([res.data], {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${row.title || row.topic || '文章'}.docx`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    ElMessage.success('下载成功')
  } catch {
    ElMessage.error('下载失败')
  } finally {
    downloading.value = false
  }
}

async function handleDelete(row: any) {
  try {
    await ElMessageBox.confirm(
      `确定删除「${row.title || row.topic || '未命名'}」？删除后不可恢复。`,
      '删除确认',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    )
    await api.medcomm.deleteArticle(row.id)
    ElMessage.success('已删除')
    await loadArticles()
  } catch {
    // cancelled
  }
}

async function handleBatchDelete() {
  const count = selectedIds.value.length
  if (!count) return
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${count} 篇文章？删除后不可恢复。`,
      '批量删除确认',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    )
    const res = await api.medcomm.batchDeleteArticles(selectedIds.value)
    const deleted = res.data?.deleted || 0
    ElMessage.success(`已删除 ${deleted} 篇文章`)
    selectedIds.value = []
    await loadArticles()
  } catch {
    // cancelled
  }
}

function formatDate(iso: string | null): string {
  if (!iso) return '-'
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

onMounted(loadArticles)
</script>

<style scoped>
.creation-lib {
  padding: 1.5rem 2rem;
  max-width: 1400px;
  margin: 0 auto;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.header h2 {
  margin: 0;
  font-size: 1.25rem;
}

.header-actions {
  display: flex;
  gap: 0.5rem;
}

.filters-bar {
  display: flex;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.title-link {
  color: var(--el-color-primary);
  cursor: pointer;
  font-weight: 500;
}
.title-link:hover {
  text-decoration: underline;
}

.preview-dialog :deep(.el-dialog__body) {
  padding: 0 20px 20px;
  max-height: 75vh;
  overflow-y: auto;
}

.preview-toolbar {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
  padding-top: 0.5rem;
}

.preview-body {
  min-height: 200px;
}

.article-preview-content {
  line-height: 1.8;
  font-size: 15px;
  color: #333;
}

.article-preview-content :deep(h1) {
  font-size: 1.5rem;
  margin: 1rem 0 0.5rem;
  border-bottom: 1px solid #eee;
  padding-bottom: 0.5rem;
}

.article-preview-content :deep(h2) {
  font-size: 1.25rem;
  margin: 1rem 0 0.5rem;
}

.article-preview-content :deep(h3) {
  font-size: 1.1rem;
  margin: 0.75rem 0 0.25rem;
}

.article-preview-content :deep(p) {
  margin: 0.5rem 0;
}

.article-preview-content :deep(ul),
.article-preview-content :deep(ol) {
  padding-left: 1.5rem;
}

.article-preview-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 0.75rem 0;
}

.article-preview-content :deep(th),
.article-preview-content :deep(td) {
  border: 1px solid #ddd;
  padding: 0.5rem;
  text-align: left;
}

.article-preview-content :deep(th) {
  background: #f5f7fa;
  font-weight: 600;
}

.article-preview-content :deep(blockquote) {
  border-left: 4px solid var(--el-color-primary-light-5);
  padding: 0.5rem 1rem;
  margin: 0.75rem 0;
  background: #f9f9f9;
}
</style>
