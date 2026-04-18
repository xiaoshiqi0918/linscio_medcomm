<template>
  <div class="templates-index">
    <div class="page-header">
      <h2>模板库</h2>
      <el-button type="primary" @click="openCreate">新建模板</el-button>
    </div>

    <div class="filter-bar">
      <el-select v-model="filterFormat" placeholder="按形式筛选" clearable style="width: 180px;">
        <el-option
          v-for="f in FORMAT_OPTIONS"
          :key="f.value"
          :label="f.label"
          :value="f.value"
        />
      </el-select>
      <el-input
        v-model="searchText"
        placeholder="搜索模板名称"
        clearable
        style="width: 220px;"
      />
    </div>

    <el-table :data="displayList" v-loading="loading" empty-text="暂无模板" stripe>
      <el-table-column prop="name" label="模板名称" min-width="200">
        <template #default="{ row }">
          <span class="tmpl-name">{{ row.name }}</span>
          <el-tag v-if="row.is_system" size="small" type="info" effect="plain" style="margin-left: 6px;">系统</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="形式" width="120">
        <template #default="{ row }">{{ FORMAT_LABEL[row.content_format] || row.content_format }}</template>
      </el-table-column>
      <el-table-column prop="platform" label="平台" width="100">
        <template #default="{ row }">{{ PLATFORM_LABEL[row.platform] || row.platform || '-' }}</template>
      </el-table-column>
      <el-table-column prop="specialty" label="专科" width="100">
        <template #default="{ row }">{{ row.specialty || '-' }}</template>
      </el-table-column>
      <el-table-column label="字数" width="80">
        <template #default="{ row }">{{ row.target_word_count || '-' }}</template>
      </el-table-column>
      <el-table-column label="章节数" width="80" align="center">
        <template #default="{ row }">{{ row.section_count }}</template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="!row.is_system"
            text
            type="primary"
            size="small"
            @click="openEdit(row)"
          >编辑</el-button>
          <el-button
            text
            type="primary"
            size="small"
            @click="handleDuplicate(row)"
          >复制</el-button>
          <el-button
            v-if="!row.is_system"
            text
            type="danger"
            size="small"
            @click="handleDelete(row)"
          >删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <TemplateEditor
      v-model:visible="editorVisible"
      :template-data="editingTemplate"
      @saved="loadTemplates"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'
import TemplateEditor from '@/components/templates/TemplateEditor.vue'

const FORMAT_OPTIONS = [
  { value: 'article', label: '图文文章' },
  { value: 'story', label: '科普故事' },
  { value: 'debunk', label: '辟谣文' },
  { value: 'qa_article', label: '问答科普' },
  { value: 'research_read', label: '研究速读' },
  { value: 'oral_script', label: '口播脚本' },
  { value: 'drama_script', label: '情景剧本' },
  { value: 'storyboard', label: '动画分镜' },
  { value: 'audio_script', label: '播客脚本' },
  { value: 'comic_strip', label: '条漫' },
  { value: 'card_series', label: '知识卡片系列' },
  { value: 'poster', label: '科普海报' },
  { value: 'picture_book', label: '科普绘本' },
  { value: 'long_image', label: '竖版长图' },
  { value: 'patient_handbook', label: '患者教育手册' },
  { value: 'quiz_article', label: '自测科普' },
  { value: 'h5_outline', label: 'H5 互动大纲' },
]

const FORMAT_LABEL: Record<string, string> = Object.fromEntries(FORMAT_OPTIONS.map(f => [f.value, f.label]))

const PLATFORM_LABEL: Record<string, string> = {
  wechat: '微信公众号',
  xiaohongshu: '小红书',
  douyin: '抖音',
  bilibili: 'B站',
  journal: '期刊',
  offline: '线下',
  universal: '通用',
}

const loading = ref(false)
const templates = ref<any[]>([])
const filterFormat = ref('')
const searchText = ref('')

const displayList = computed(() => {
  let list = templates.value
  if (filterFormat.value) {
    list = list.filter(t => t.content_format === filterFormat.value)
  }
  if (searchText.value.trim()) {
    const q = searchText.value.trim().toLowerCase()
    list = list.filter(t => (t.name || '').toLowerCase().includes(q))
  }
  return list
})

async function loadTemplates() {
  loading.value = true
  try {
    const res = await api.templates.getTemplates()
    templates.value = res.data?.items || []
  } catch {
    templates.value = []
  } finally {
    loading.value = false
  }
}

watch(filterFormat, loadTemplates)
onMounted(loadTemplates)

const editorVisible = ref(false)
const editingTemplate = ref<any>(null)

function openCreate() {
  editingTemplate.value = null
  editorVisible.value = true
}

function openEdit(row: any) {
  editingTemplate.value = { ...row }
  editorVisible.value = true
}

async function handleDuplicate(row: any) {
  try {
    await api.templates.duplicateTemplate(row.id)
    ElMessage.success('已复制模板')
    loadTemplates()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '复制失败')
  }
}

async function handleDelete(row: any) {
  try {
    await ElMessageBox.confirm(`确定删除模板「${row.name}」？`, '确认删除', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await api.templates.deleteTemplate(row.id)
    ElMessage.success('已删除')
    loadTemplates()
  } catch (e: any) {
    if (e === 'cancel') return
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}
</script>

<style scoped>
.templates-index {
  padding: 1.5rem 2rem;
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
}

.page-header h2 {
  margin: 0;
}

.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 1rem;
}

.tmpl-name {
  font-weight: 500;
}
</style>
