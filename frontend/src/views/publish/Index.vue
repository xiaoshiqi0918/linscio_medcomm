<template>
  <div class="publish-index">
    <h2>发布管理</h2>
    <el-table :data="records">
      <el-table-column prop="article_id" label="文章ID" width="100" />
      <el-table-column prop="platform" label="平台" width="120" />
      <el-table-column prop="publish_url" label="发布链接" />
      <el-table-column prop="read_count" label="阅读量（手动录入）" width="120">
        <template #default="{ row }">
          <el-input-number v-model="row.read_count" size="small" :min="0" @change="() => updateRecord(row)" />
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api'

const records = ref<any[]>([])

async function load() {
  try {
    const res = await api.publish.getRecords()
    records.value = res.data?.items || []
  } catch {
    records.value = []
  }
}

async function updateRecord(row: any) {
  try {
    await api.publish.updateRecord(row.id, row.read_count, undefined)
  } catch (e) {
    console.error(e)
  }
}

onMounted(load)
</script>

<style scoped>
.publish-index { padding: 1.5rem; }
h2 { margin-bottom: 1rem; }
</style>
