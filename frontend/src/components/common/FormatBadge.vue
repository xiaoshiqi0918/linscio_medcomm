<template>
  <el-tag :type="tagType" size="small">{{ label }}</el-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { formatLabel } from '@/composables/useFormats'

const props = defineProps<{
  formatId: string
  type?: 'default' | 'primary' | 'success' | 'info' | 'warning'
}>()

const label = computed(() => formatLabel(props.formatId))
const tagType = computed(() => props.type ?? 'info')
</script>
