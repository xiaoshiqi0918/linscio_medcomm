<template>
  <div class="medcomm-layout">
    <MedCommTopbar :article="currentArticle" />
    <div class="medcomm-body">
      <ArticleListPanel
        ref="listRef"
        :selected-id="selectedArticleId"
        @select="onSelectArticle"
        @deleted="onArticleDeleted"
      />
      <div class="editor-slot">
        <router-view />
      </div>
      <div
        v-if="rightPanelVisible"
        class="resize-handle"
        @mousedown="onResizeStart"
      />
      <transition name="slide-right">
        <RightPanel
          v-if="rightPanelVisible"
          :article="currentArticle"
          :verification-report="articleStore.verificationReport"
          :ollama-warning="articleStore.ollamaWarning"
          :image-suggestions="articleStore.imageSuggestions"
          :refreshing-suggestions="refreshingSuggestions"
          :style="{ width: rightPanelWidth + 'px', minWidth: rightPanelWidth + 'px' }"
          @locate-suggestion="onLocateSuggestion"
          @generate-from-suggestion="onGenerateFromSuggestion"
          @refresh-suggestions="onRefreshSuggestions"
          @ai-replace="onAiReplace"
          @ai-insert="onAiInsert"
        />
      </transition>
      <button
        class="right-panel-toggle"
        :class="{ collapsed: !rightPanelVisible }"
        :style="{ right: rightPanelVisible ? (rightPanelWidth + 5) + 'px' : '0' }"
        :title="rightPanelVisible ? '隐藏右侧面板' : '展开右侧面板'"
        @click="toggleRightPanel"
      >
        <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor">
          <path v-if="rightPanelVisible" d="M9.5 3L14 8l-4.5 5" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
          <path v-else d="M6.5 3L2 8l4.5 5" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, provide, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import MedCommTopbar from '@/components/layout/MedCommTopbar.vue'
import ArticleListPanel from '@/components/layout/ArticleListPanel.vue'
import RightPanel from '@/components/layout/RightPanel.vue'
import { useArticleStore } from '@/stores/article'

const route = useRoute()
const router = useRouter()
const articleStore = useArticleStore()
const listRef = ref<{ load?: () => void } | null>(null)

const RIGHT_PANEL_MIN = 280
const RIGHT_PANEL_MAX = 640
const RIGHT_PANEL_DEFAULT = 380
const STORAGE_KEY_RIGHT_VISIBLE = 'medcomm_right_panel_visible'
const rightPanelWidth = ref(RIGHT_PANEL_DEFAULT)
const rightPanelVisible = ref(
  localStorage.getItem(STORAGE_KEY_RIGHT_VISIBLE) !== 'false'
)
let resizing = false
let startX = 0
let startWidth = 0

function toggleRightPanel() {
  rightPanelVisible.value = !rightPanelVisible.value
  localStorage.setItem(STORAGE_KEY_RIGHT_VISIBLE, String(rightPanelVisible.value))
}

function onResizeStart(e: MouseEvent) {
  e.preventDefault()
  resizing = true
  startX = e.clientX
  startWidth = rightPanelWidth.value
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
  document.addEventListener('mousemove', onResizeMove)
  document.addEventListener('mouseup', onResizeEnd)
}

function onResizeMove(e: MouseEvent) {
  if (!resizing) return
  const delta = startX - e.clientX
  const newWidth = Math.min(RIGHT_PANEL_MAX, Math.max(RIGHT_PANEL_MIN, startWidth + delta))
  rightPanelWidth.value = newWidth
}

function onResizeEnd() {
  resizing = false
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
  document.removeEventListener('mousemove', onResizeMove)
  document.removeEventListener('mouseup', onResizeEnd)
}

onUnmounted(() => {
  document.removeEventListener('mousemove', onResizeMove)
  document.removeEventListener('mouseup', onResizeEnd)
})

const selectedArticleId = computed(() => {
  const id = route.params.id
  return id ? Number(id) : null
})

const currentArticle = computed(() => articleStore.current)

function onSelectArticle(id: number) {
  router.push(`/medcomm/article/${id}`)
}

function onArticleDeleted(id: number) {
  if (selectedArticleId.value === id) {
    router.push('/medcomm')
  }
}

provide('medcommRefreshList', () => listRef.value?.load?.())

function onLocateSuggestion(anchor: string) {
  articleStore.requestEditorLocate(anchor)
}

function onGenerateFromSuggestion(suggestion: Record<string, unknown>) {
  const desc = String(suggestion.en_description || suggestion.description || '')
  const sStyle = String(suggestion.style || '')
  const tool = String(suggestion.recommended_tool || '')
  const imgType = String(suggestion.image_type || '')

  const query: Record<string, string> = {}
  if (desc) query.prompt = desc
  if (sStyle) query.style = sStyle
  if (imgType) query.image_type = imgType

  const routes: Record<string, string> = {
    artgen: '/artgen',
    api: '/imagegen',
    medpic: '/medpic',
  }
  router.push({ path: routes[tool] || '/medpic', query })
}

function onAiReplace(payload: { from: number; to: number; text: string }) {
  articleStore.requestEditorReplace(payload.from, payload.to, payload.text)
}

function onAiInsert(text: string) {
  articleStore.requestEditorInsert(text)
}

const refreshingSuggestions = ref(false)

async function onRefreshSuggestions() {
  const sectionId = articleStore.currentSectionId
  if (!sectionId) {
    ElMessage.warning('请先选中一个章节')
    return
  }
  refreshingSuggestions.value = true
  try {
    const { api } = await import('@/api')
    const res = await api.imagegen.getSuggestions(sectionId, true)
    const suggestions = res.data?.suggestions || []
    articleStore.setImageSuggestions(suggestions)
    if (!suggestions.length) {
      ElMessage.info('当前章节暂无配图建议')
    }
  } catch {
    ElMessage.error('获取配图建议失败')
  } finally {
    refreshingSuggestions.value = false
  }
}

watch(() => route.name, (name, prev) => {
  if (prev === 'medcomm-new') listRef.value?.load?.()
})
</script>

<style scoped>
.medcomm-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.medcomm-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.editor-slot {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  overflow-x: hidden;
  min-width: 0;
  min-height: 0;
}

.resize-handle {
  width: 5px;
  cursor: col-resize;
  background: transparent;
  flex-shrink: 0;
  position: relative;
  z-index: 10;
  transition: background 0.15s;
}
.resize-handle::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 3px;
  height: 32px;
  border-radius: 2px;
  background: #d1d5db;
  opacity: 0;
  transition: opacity 0.15s;
}
.resize-handle:hover {
  background: #e5e7eb;
}
.resize-handle:hover::after {
  opacity: 1;
}

.right-panel-toggle {
  position: absolute;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  z-index: 20;
  width: 20px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #e5e7eb;
  border-right: none;
  border-radius: 6px 0 0 6px;
  background: #fff;
  color: #9ca3af;
  cursor: pointer;
  padding: 0;
  transition: all 0.2s;
}
.right-panel-toggle:hover {
  background: #f3f4f6;
  color: #374151;
}
.right-panel-toggle.collapsed {
  right: 0;
}

.medcomm-body {
  position: relative;
}

.slide-right-enter-active,
.slide-right-leave-active {
  transition: all 0.25s ease;
}
.slide-right-enter-from,
.slide-right-leave-to {
  opacity: 0;
  transform: translateX(30px);
  width: 0 !important;
  min-width: 0 !important;
  overflow: hidden;
}
</style>
