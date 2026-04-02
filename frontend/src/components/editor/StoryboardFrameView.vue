<template>
  <node-view-wrapper class="storyboard-frame-view">
    <div class="frame-root" :class="{ 'has-image': imagePath }">
      <div class="frame-meta">
        分镜 {{ node.attrs.frameIndex ?? 1 }}
        <span v-if="node.attrs.duration" class="dur">· {{ node.attrs.duration }}s</span>
      </div>
      <node-view-content class="frame-content" />
      <div v-if="imagePath" class="frame-image">
        <img :src="displayUrl" alt="分镜配图" />
      </div>
      <div class="frame-actions">
        <el-button
          size="small"
          :loading="generating"
          :disabled="!promptText"
          @click="handleGenerate"
        >
          生成配图
        </el-button>
        <span v-if="error" class="err">{{ error }}</span>
      </div>
    </div>
  </node-view-wrapper>
</template>

<script setup lang="ts">
import { NodeViewWrapper, NodeViewContent } from '@tiptap/vue-3'
import type { Editor } from '@tiptap/core'
import { computed, ref } from 'vue'
import { api } from '@/api'
import { usePollingGuard } from '@/composables/usePollingGuard'
import { buildImageGenBackendOptions } from '@/composables/useImageGenerate'
import { useSettingsStore } from '@/stores/settings'

const settingsStore = useSettingsStore()

const props = defineProps<{
  editor?: Editor
  node: { attrs: Record<string, unknown> }
  updateAttributes: (attrs: Record<string, unknown>) => void
}>()

const articleIdForImage = computed(() => {
  const id = (props.editor?.storage as { medCommImageContext?: { articleId: number | null } })
    ?.medCommImageContext?.articleId
  return id != null && id > 0 ? id : undefined
})

/** 与后端 seed_base + panel_index 对齐：0-based */
const panelIndexZeroBased = computed(() => {
  const raw = Number(props.node.attrs?.frameIndex ?? 1)
  const oneBased = Number.isFinite(raw) && raw > 0 ? raw : 1
  return oneBased - 1
})

const imagePath = computed(() => props.node.attrs?.imagePath as string | null | undefined)
const promptText = computed(() => {
  const parts = [
    props.node.attrs?.sceneDesc as string | undefined,
    props.node.attrs?.voiceover as string | undefined,
    props.node.attrs?.cameraNote as string | undefined,
  ].filter((s) => s && String(s).trim())
  if (parts.length) return parts.map((s) => String(s).trim()).join('\n')
  const text = (props.node as { textContent?: string })?.textContent?.trim()
  return text || ''
})

const generating = ref(false)
const error = ref<string | null>(null)

const displayUrl = computed(() => {
  const p = imagePath.value
  if (!p) return ''
  return p.startsWith('medcomm-image://') ? api.imagegen.imageUrl(p) : p
})

async function handleGenerate() {
  if (!promptText.value) return
  generating.value = true
  error.value = null
  try {
    const res = await api.imagegen.createTask({
      prompt: promptText.value,
      content_format: 'storyboard',
      image_type: 'storyboard_frame',
      style: 'medical_illustration',
      width: 1024,
      height: 1024,
      ...(articleIdForImage.value != null
        ? { article_id: articleIdForImage.value, panel_index: panelIndexZeroBased.value }
        : {}),
      ...buildImageGenBackendOptions(settingsStore),
    })
    const taskId = res.data?.task_id
    if (!taskId) {
      error.value = '创建任务失败'
      return
    }
    await usePollingGuard({
      pollFn: async () => {
        const r = await api.imagegen.getTaskStatus(taskId)
        return r.data as { status: string; images?: { path: string }[]; error?: string }
      },
      interval: 2000,
      timeout: 300000,
      isDone: (s) => s.status === 'done',
      isFailed: (s) => s.status === 'failed',
      onDone: (s) => {
        const path = s.images?.[0]?.path
        if (path) {
          const full = path.startsWith('medcomm-image://') ? path : `medcomm-image://${path}`
          props.updateAttributes({ imagePath: full })
        }
      },
      onFailed: (s) => {
        error.value = s.error || '生成失败'
      },
      onTimeout: () => {
        error.value = '生成超时'
      },
    })
  } finally {
    generating.value = false
  }
}
</script>

<style scoped>
.storyboard-frame-view {
  margin: 1em 0;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 0.75rem;
  background: #fafafa;
}

.frame-meta {
  font-size: 0.75rem;
  color: #6b7280;
  margin-bottom: 0.5rem;
}

.frame-meta .dur {
  margin-left: 0.25rem;
}

.frame-content {
  min-height: 2em;
}

.frame-image {
  margin-top: 0.75rem;
}

.frame-image img {
  max-width: 100%;
  height: auto;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
}

.frame-actions {
  margin-top: 0.5rem;
}

.frame-actions .err {
  margin-left: 0.5rem;
  color: #ef4444;
  font-size: 0.75rem;
}
</style>
