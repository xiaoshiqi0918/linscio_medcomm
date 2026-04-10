<template>
  <div class="format-picker">
    <div class="platform-picker platform-first" v-if="platformFirst && showPlatform">
      <h4>目标平台（先选）</h4>
      <div class="platform-options">
        <el-button
          v-for="p in platforms"
          :key="p.id"
          :type="platform === p.id ? 'primary' : platformTypeForPlatform(p.id)"
          :plain="platform !== p.id && !platformHasFormats(p.id)"
          size="small"
          @click="onPlatformSelect(p.id)"
        >
          {{ p.name }}
          <span v-if="platformHasFormats(p.id)" class="badge">{{ formatCountForPlatform(p.id) }}</span>
        </el-button>
      </div>
    </div>
    <div class="format-groups">
      <div v-for="group in formatGroups" :key="group.name" class="format-group">
        <h4 class="group-title">{{ group.name }}</h4>
        <div class="format-options">
          <el-radio-group :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)">
            <el-radio-button
              v-for="f in filteredFormatsInGroup(group)"
              :key="f.id"
              :value="f.id"
            >{{ f.name }}</el-radio-button>
          </el-radio-group>
        </div>
      </div>
    </div>
    <div class="platform-picker" v-if="showPlatform && !platformFirst">
      <h4>目标平台</h4>
      <p class="hint">根据所选形式，推荐程度：深色 ★★★ 最适合 / 普通 ★★ 适合 / 灰色 不推荐</p>
      <div class="platform-options">
        <el-button
          v-for="p in platforms"
          :key="p.id"
          :type="platform === p.id ? 'primary' : platformType(p.id)"
          :plain="platform !== p.id && platformScore(p.id) === 0"
          size="small"
          @click="$emit('update:platform', p.id)"
        >
          {{ p.name }}
          <span v-if="platformScore(p.id) > 0" class="stars">
            {{ '★'.repeat(platformScore(p.id)) }}
          </span>
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    modelValue: string
    platform?: string
    showPlatform?: boolean
    platformFirst?: boolean
    formats?: Array<{ id: string; name: string; platform_matrix?: Record<string, number> }>
    matrix?: Record<string, Record<string, number>>
  }>(),
  { showPlatform: true, platformFirst: false, formats: () => [], matrix: () => ({}) }
)

const emit = defineEmits<{ 'update:modelValue': [v: string]; 'update:platform': [v: string] }>()

function formatScoreForPlatform(formatId: string, platformId: string): number {
  const row = props.matrix[formatId] || {}
  return row[platformId] ?? 0
}

function platformHasFormats(platformId: string): boolean {
  return formatCountForPlatform(platformId) > 0
}

function formatCountForPlatform(platformId: string): number {
  let n = 0
  for (const g of formatGroups) {
    for (const f of g.formats) {
      if (formatScoreForPlatform(f.id, platformId) > 0) n++
    }
  }
  return n
}

function filteredFormatsInGroup(group: { formats: Array<{ id: string; name: string }> }) {
  if (!props.platformFirst || !props.platform) return group.formats
  return group.formats.filter((f) => formatScoreForPlatform(f.id, props.platform!) > 0)
}

function platformTypeForPlatform(platformId: string): '' | 'primary' | 'success' {
  if (platformId === props.platform) return 'primary'
  return platformHasFormats(platformId) ? 'success' : ''
}

function onPlatformSelect(platformId: string) {
  emit('update:platform', platformId)
  if (props.platformFirst) {
    const valid = formatScoreForPlatform(props.modelValue, platformId) > 0
    if (!valid) {
      const first = formatGroups.flatMap((g) => g.formats).find((f) => formatScoreForPlatform(f.id, platformId) > 0)
      if (first) emit('update:modelValue', first.id)
    }
  }
}

const formatGroups = [
  {
    name: '叙事文章类',
    formats: [
      { id: 'article', name: '图文文章' },
      { id: 'story', name: '科普故事' },
      { id: 'debunk', name: '辟谣文' },
      { id: 'qa_article', name: '问答科普' },
      { id: 'research_read', name: '研究速读' },
    ],
  },
  {
    name: '脚本类',
    formats: [
      { id: 'oral_script', name: '口播脚本' },
      { id: 'drama_script', name: '情景剧本' },
      { id: 'storyboard', name: '动画分镜' },
    ],
  },
  {
    name: '图示/视觉类',
    formats: [
      { id: 'comic_strip', name: '条漫' },
      { id: 'card_series', name: '知识卡片' },
      { id: 'poster', name: '科普海报' },
      { id: 'picture_book', name: '科普绘本' },
      { id: 'long_image', name: '竖版长图' },
    ],
  },
  {
    name: '互动/结构类',
    formats: [
      { id: 'patient_handbook', name: '患者手册' },
    ],
  },
]

const platforms = [
  { id: 'wechat', name: '微信' },
  { id: 'douyin', name: '抖音' },
  { id: 'xiaohongshu', name: '小红书' },
  { id: 'bilibili', name: 'B站' },
  { id: 'journal', name: '期刊' },
  { id: 'offline', name: '线下' },
  { id: 'universal', name: '通用' },
]

function platformScore(platformId: string): number {
  const row = props.matrix[props.modelValue] || {}
  return row[platformId] ?? 0
}

function platformType(platformId: string): '' | 'primary' | 'success' | 'info' {
  const score = platformScore(platformId)
  if (score === 3) return 'primary'
  if (score === 2) return 'success'
  return ''
}
</script>

<style scoped>
.format-picker {
  margin-bottom: 1rem;
}

.format-groups {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.group-title {
  font-size: 0.875rem;
  color: #666;
  margin-bottom: 0.5rem;
}

.format-options :deep(.el-radio-group) {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.platform-picker {
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid #eee;
}

.platform-picker h4 {
  font-size: 0.875rem;
  margin-bottom: 0.25rem;
}

.hint {
  font-size: 0.75rem;
  color: #999;
  margin-bottom: 0.5rem;
}

.platform-options {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.stars {
  margin-left: 0.25rem;
  font-size: 0.75em;
}

.platform-first {
  margin-top: 0;
  padding-top: 0;
  border-top: none;
}

.badge {
  margin-left: 0.25rem;
  font-size: 0.7em;
  opacity: 0.9;
}
</style>
