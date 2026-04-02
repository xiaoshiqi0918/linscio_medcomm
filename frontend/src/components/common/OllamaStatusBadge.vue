<template>
  <el-tag :type="status ? 'success' : 'info'" size="small">
    {{ status ? 'Ollama 已连接' : 'Ollama 未检测' }}
  </el-tag>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

const status = ref(false)

onMounted(async () => {
  try {
    const res = await fetch('http://127.0.0.1:11434/api/tags', { signal: AbortSignal.timeout(2000) })
    status.value = res.ok
  } catch {
    status.value = false
  }
})
</script>
