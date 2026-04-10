<template>
  <aside class="article-list-panel">
    <div class="filters">
      <el-select v-model="filterFormat" placeholder="形式" clearable size="small" style="width:100%;margin-bottom:0.5rem">
        <el-option v-for="(name, id) in FORMAT_NAMES" :key="id" :label="name" :value="id" />
      </el-select>
      <el-select v-model="filterPlatform" placeholder="平台" clearable size="small" style="width:100%">
        <el-option v-for="(name, id) in PLATFORM_NAMES" :key="id" :label="name" :value="id" />
      </el-select>
    </div>
    <div class="list">
      <div
        v-for="a in filteredArticles"
        :key="a.id"
        class="article-card"
        :class="{ active: selectedId === a.id }"
        @click="$emit('select', a.id)"
      >
        <div class="card-header">
          <div class="meta">
            <FormatBadge :format-id="a.content_format" />
            <PlatformBadge :platform-id="a.platform" />
          </div>
          <el-icon
            class="delete-btn"
            @click.stop="handleDelete(a)"
          ><Delete /></el-icon>
        </div>
        <h4>{{ a.title || a.topic || '未命名' }}</h4>
      </div>
      <el-empty v-if="!filteredArticles.length" description="暂无作品" :image-size="60" />
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { api } from '@/api'
import { Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import FormatBadge from '@/components/common/FormatBadge.vue'
import PlatformBadge from '@/components/common/PlatformBadge.vue'
import { FORMAT_NAMES, PLATFORM_NAMES } from '@/composables/useFormats'

const props = defineProps<{ selectedId?: number | null }>()
const emit = defineEmits<{ select: [id: number]; deleted: [id: number] }>()

const articles = ref<any[]>([])
const filterFormat = ref('')
const filterPlatform = ref('')

const filteredArticles = computed(() => {
  let list = articles.value
  if (filterFormat.value) list = list.filter((a) => a.content_format === filterFormat.value)
  if (filterPlatform.value) list = list.filter((a) => a.platform === filterPlatform.value)
  return list
})

async function load() {
  try {
    const res = await api.medcomm.getArticles()
    articles.value = res.data?.items || []
  } catch {
    articles.value = []
  }
}

async function handleDelete(a: any) {
  try {
    await ElMessageBox.confirm(
      `确定删除「${a.title || a.topic || '未命名'}」？删除后不可恢复。`,
      '删除创作',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
    await api.medcomm.deleteArticle(a.id)
    ElMessage.success('已删除')
    await load()
    emit('deleted', a.id)
  } catch {
    // 用户取消
  }
}

load()
defineExpose({ load })
</script>

<style scoped>
.article-list-panel {
  width: 300px;
  min-width: 300px;
  background: #fff;
  border-right: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.filters { padding: 0.75rem; border-bottom: 1px solid #eee; }
.list { flex: 1; overflow-y: auto; padding: 0.5rem; }
.article-card {
  padding: 0.75rem;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 0.25rem;
  position: relative;
}
.article-card:hover { background: #f3f4f6; }
.article-card.active { background: #dbeafe; border: 1px solid #93c5fd; }
.card-header { display: flex; justify-content: space-between; align-items: flex-start; }
.meta { display: flex; gap: 0.25rem; margin-bottom: 0.25rem; }
.article-card h4 { font-size: 0.9rem; margin: 0; font-weight: 500; }
.delete-btn {
  opacity: 0;
  color: #9ca3af;
  font-size: 14px;
  cursor: pointer;
  padding: 2px;
  border-radius: 4px;
  transition: opacity 0.15s, color 0.15s;
  flex-shrink: 0;
}
.article-card:hover .delete-btn { opacity: 1; }
.delete-btn:hover { color: #ef4444; background: rgba(239, 68, 68, 0.08); }
</style>
