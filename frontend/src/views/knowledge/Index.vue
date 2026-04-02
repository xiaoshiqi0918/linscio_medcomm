<template>
  <div class="knowledge-index">
    <div class="knowledge-header">
      <h2>知识库</h2>
      <el-upload
        :auto-upload="false"
        accept=".pdf,.txt,.md"
        :limit="1"
        :on-change="handleFileChange"
      >
        <el-button type="primary">+ 上传文档</el-button>
      </el-upload>
    </div>

    <!-- 基础版：空态 + 升级提示 -->
    <template v-if="settingsStore.isBasic">
      <div v-if="docs.length === 0" class="empty-state">
        <p class="empty-title">📂 你还没有上传任何文档</p>
        <p class="empty-desc">
          上传医学文献或科室资料，AI 写作时会自动参考这些内容，
          提升输出的专业性和准确性。
        </p>
        <p class="empty-formats">支持格式：PDF / TXT / Markdown</p>
        <div class="upgrade-hint">
          💡 升级定制版后，我们会为你的学科预置权威指南和教材，无需自行上传。
        </div>
      </div>
      <el-table v-else :data="docs" style="margin-top: 1rem;">
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'done' ? 'success' : 'info'" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button type="danger" text size="small" @click="handleDelete(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </template>

    <!-- 定制版：预置文档 + 我的文档 -->
    <template v-else>
      <!-- 预置文档区 -->
      <div v-if="presetDocs.length > 0" class="preset-section">
        <h3 class="section-title">✦ {{ presetSectionTitle }} 预置文档（由 LinScio 维护）</h3>
        <div class="doc-list">
          <div v-for="(d, i) in presetDocs" :key="'preset-' + i" class="doc-item preset">
            <span class="doc-icon">📄</span>
            <div class="doc-info">
              <span class="doc-name">{{ d.name }}</span>
              <span class="doc-meta">已索引 · {{ d.chunk_count ?? '-' }} 块 · 更新于 {{ d.updated_at ?? '-' }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 我的文档区 -->
      <div class="my-section">
        <h3 class="section-title">📁 我的文档（科室自行上传）</h3>
        <div v-if="docs.length === 0" class="empty-my">
          <p>暂无自行上传的文档</p>
        </div>
        <el-table v-else :data="docs" style="margin-top: 0.5rem;">
          <el-table-column prop="name" label="名称" />
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="row.status === 'done' ? 'success' : 'info'" size="small">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100">
            <template #default="{ row }">
              <el-button type="danger" text size="small" @click="handleDelete(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { api } from '@/api'
import { useSettingsStore } from '@/stores/settings'

const settingsStore = useSettingsStore()
const docs = ref<any[]>([])

const presetDocs = computed(() => settingsStore.license.presetDocs)
const presetSectionTitle = computed(() =>
  settingsStore.license.customSpecialties[0] || '学科'
)

async function load() {
  try {
    const res = await api.knowledge.getDocs()
    docs.value = res.data?.items || []
  } catch {
    docs.value = []
  }
}

async function handleFileChange(file: any) {
  const form = new FormData()
  form.append('file', file.raw)
  try {
    await api.knowledge.uploadDoc(form)
    await load()
  } catch (e) {
    console.error(e)
  }
}

async function handleDelete(id: number) {
  try {
    await api.knowledge.deleteDoc(id)
    await load()
  } catch (e) {
    console.error(e)
  }
}

onMounted(load)
</script>

<style scoped>
.knowledge-index { padding: 1.5rem; }
.knowledge-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}
h2 { margin-bottom: 0; }
.empty-state {
  padding: 2rem;
  background: #fff;
  border-radius: 8px;
  text-align: center;
}
.empty-title { font-size: 1rem; margin-bottom: 0.5rem; }
.empty-desc { color: #6b7280; font-size: 0.9rem; margin-bottom: 0.5rem; }
.empty-formats { color: #9ca3af; font-size: 0.85rem; margin-bottom: 1rem; }
.upgrade-hint {
  padding: 0.75rem 1rem;
  background: #f0f9ff;
  color: #0369a1;
  border-radius: 6px;
  font-size: 0.85rem;
  text-align: left;
}
.preset-section { margin-bottom: 1.5rem; }
.section-title { font-size: 0.95rem; margin-bottom: 0.75rem; color: #374151; }
.doc-list { background: #fff; border-radius: 8px; padding: 0.75rem; }
.doc-item { display: flex; align-items: flex-start; gap: 0.5rem; padding: 0.5rem 0; }
.doc-item.preset { border-bottom: 1px solid #f3f4f6; }
.doc-item:last-child { border-bottom: none; }
.doc-icon { font-size: 1.2rem; }
.doc-info { display: flex; flex-direction: column; }
.doc-name { font-weight: 500; }
.doc-meta { font-size: 0.8rem; color: #6b7280; margin-top: 0.25rem; }
.my-section { background: #fff; border-radius: 8px; padding: 1rem; }
.empty-my { color: #9ca3af; font-size: 0.9rem; padding: 1rem; }
</style>
