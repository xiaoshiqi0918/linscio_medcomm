<template>
  <div class="stage-progress">
    <template v-for="(s, i) in stages" :key="s.key">
      <span
        class="dot"
        :class="dotClass(s.key)"
        :title="s.label"
      >
        {{ s.key === 'image' && status?.image_stage === 'skipped' ? '○' : dotChar(s.key) }}
      </span>
      <span v-if="i < stages.length - 1" class="line" />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const STAGES = [
  { key: 'topic', label: '选题策划' },
  { key: 'outline', label: '大纲' },
  { key: 'drafting', label: '正文写作' },
  { key: 'image', label: '配图生成' },
  { key: 'publish', label: '发布适配' },
]

const props = defineProps<{
  currentStage?: string
  imageStage?: 'pending' | 'active' | 'done' | 'skipped'
}>()

const status = computed(() => ({
  current_stage: props.currentStage || 'topic',
  image_stage: props.imageStage || 'pending',
}))

const stages = computed(() => STAGES)

function dotClass(key: string): string {
  const cur = status.value.current_stage
  const img = status.value.image_stage
  const idx = STAGES.findIndex((s) => s.key === cur)
  const myIdx = STAGES.findIndex((s) => s.key === key)

  if (key === 'image' && img === 'skipped') return 'skipped'
  if (myIdx < idx) return 'done'
  if (myIdx === idx) return 'active'
  return 'pending'
}

function dotChar(key: string): string {
  const c = dotClass(key)
  if (c === 'done') return '●'
  if (c === 'active') return '◉'
  return '○'
}
</script>

<style scoped>
.stage-progress {
  display: flex;
  align-items: center;
  font-size: 1rem;
  padding: 0.5rem 0;
}
.dot {
  width: 1.2em;
  text-align: center;
  color: #d1d5db;
  transition: color 0.2s;
}
.dot.done { color: #22c55e; }
.dot.active { color: #3b82f6; }
.dot.skipped { color: #9ca3af; opacity: 0.7; }
.line {
  width: 24px;
  height: 2px;
  background: #e5e7eb;
  margin: 0 2px;
}
</style>
