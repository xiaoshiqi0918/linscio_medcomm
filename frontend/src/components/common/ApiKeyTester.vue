<template>
  <div class="api-key-tester">
    <el-button :loading="testing" size="small" @click="test">测试连接</el-button>
    <span v-if="result" :class="['result', result.valid ? 'ok' : 'err']">
      {{ result.valid ? '✓ 有效' : '✗ ' + (result.error || '无效') }}
    </span>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { api } from '@/api'

const props = defineProps<{
  apiKey?: string
}>()

const testing = ref(false)
const result = ref<{ valid: boolean; error?: string } | null>(null)

async function test() {
  testing.value = true
  result.value = null
  try {
    const res = await api.system.testApiKey(props.apiKey)
    result.value = { valid: res.data?.valid ?? false, error: res.data?.error }
  } catch {
    result.value = { valid: false, error: '请求失败' }
  } finally {
    testing.value = false
  }
}
</script>

<style scoped>
.api-key-tester {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}
.result.ok { color: #22c55e; }
.result.err { color: #ef4444; }
</style>
