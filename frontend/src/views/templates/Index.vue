<template>
  <div class="templates-index">
    <h2>模板库</h2>
    <el-select v-model="filterFormat" placeholder="按形式筛选" clearable style="margin-bottom: 1rem;">
      <el-option label="图文文章" value="article" />
      <el-option label="辟谣文" value="debunk" />
      <el-option label="口播脚本" value="oral_script" />
      <el-option label="条漫" value="comic_strip" />
      <el-option label="患者手册" value="patient_handbook" />
    </el-select>
    <el-table :data="filteredTemplates">
      <el-table-column prop="name" label="模板名" />
      <el-table-column prop="content_format" label="形式" width="120" />
      <el-table-column prop="platform" label="平台" width="100" />
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { api } from '@/api'

const templates = ref<any[]>([])
const filterFormat = ref('')

const filteredTemplates = computed(() => {
  if (!filterFormat.value) return templates.value
  return templates.value.filter((t: any) => t.content_format === filterFormat.value)
})

async function load() {
  try {
    const res = await api.templates.getTemplates(filterFormat.value || undefined)
    templates.value = res.data?.items || []
  } catch {
    templates.value = []
  }
}

watch(filterFormat, load)

onMounted(load)
</script>

<style scoped>
.templates-index { padding: 1.5rem; }
h2 { margin-bottom: 1rem; }
</style>
