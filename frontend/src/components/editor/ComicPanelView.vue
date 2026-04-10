<template>
  <node-view-wrapper class="comic-panel-view">
    <div class="panel-root" :class="{ 'has-image': imagePath }">
      <div class="panel-meta">第 {{ node.attrs.panelIndex ?? 1 }} 格</div>
      <node-view-content class="panel-content" />
      <div v-if="imagePath" class="panel-image">
        <img :src="displayUrl" alt="格图" />
      </div>
      <div class="panel-actions">
        <el-button
          size="small"
          :type="imagePath ? 'default' : 'primary'"
          :loading="generating"
          :disabled="!promptText"
          @click="handleGenerate"
        >
          {{ generating ? '生成中…' : (imagePath ? '重新生成' : '生成配图') }}
        </el-button>
        <el-button
          v-if="imagePath && !generating"
          size="small"
          type="danger"
          plain
          @click="handleRemoveImage"
        >
          移除配图
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

const panelIndexZeroBased = computed(() => {
  const raw = Number(props.node.attrs?.panelIndex ?? 1)
  const oneBased = Number.isFinite(raw) && raw > 0 ? raw : 1
  return oneBased - 1
})

const imagePath = computed(() => props.node.attrs?.imagePath as string | null)
const promptText = computed(() => {
  const desc = props.node.attrs?.sceneDesc as string | undefined
  if (desc?.trim()) return desc.trim()
  const d = props.node.attrs?.dialogue as string | undefined
  const n = props.node.attrs?.narration as string | undefined
  const fromAttrs = [d, n].filter(Boolean).join(' ').trim()
  if (fromAttrs) return fromAttrs
  const text = (props.node as { textContent?: string })?.textContent?.trim()
  return text || ''
})

const generating = ref(false)
const error = ref<string | null>(null)

const displayUrl = computed(() => {
  const p = imagePath.value
  if (!p) return ''
  return p.startsWith('medcomm-image://')
    ? api.imagegen.imageUrl(p)
    : p
})

function handleRemoveImage() {
  props.updateAttributes({ imagePath: null })
}

async function handleGenerate() {
  if (!promptText.value) return
  generating.value = true
  error.value = null
  try {
    const res = await api.imagegen.createTask({
      prompt: promptText.value,
      style: 'comic',
      content_format: 'comic_strip',
      image_type: 'comic_panel',
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
.comic-panel-view {
  margin: 1em 0;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 0.75rem;
  background: #fafafa;
}

.panel-meta {
  font-size: 0.75rem;
  color: #6b7280;
  margin-bottom: 0.5rem;
}

.panel-content {
  min-height: 2em;
}

.panel-image {
  margin-top: 0.75rem;
}

.panel-image img {
  max-width: 100%;
  height: auto;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
}

.panel-actions {
  margin-top: 0.5rem;
}

.panel-actions .err {
  margin-left: 0.5rem;
  color: #ef4444;
  font-size: 0.75rem;
}
</style>
