<template>
  <el-tag :type="tagType" size="small">{{ label }}</el-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { platformLabel } from '@/composables/useFormats'

const props = defineProps<{
  platformId: string
  type?: 'default' | 'primary' | 'success' | 'info' | 'warning'
}>()

const label = computed(() => platformLabel(props.platformId || ''))
const tagType = computed(() => props.type ?? 'info')
</script>
