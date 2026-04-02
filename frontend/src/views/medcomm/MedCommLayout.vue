<template>
  <div class="medcomm-layout">
    <MedCommTopbar :article="currentArticle" />
    <div class="medcomm-body">
      <ArticleListPanel
        ref="listRef"
        :selected-id="selectedArticleId"
        @select="onSelectArticle"
      />
      <div class="editor-slot">
        <router-view />
      </div>
      <RightPanel
        :article="currentArticle"
        :verification-report="articleStore.verificationReport"
        :ollama-warning="articleStore.ollamaWarning"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, provide } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import MedCommTopbar from '@/components/layout/MedCommTopbar.vue'
import ArticleListPanel from '@/components/layout/ArticleListPanel.vue'
import RightPanel from '@/components/layout/RightPanel.vue'
import { useArticleStore } from '@/stores/article'

const route = useRoute()
const router = useRouter()
const articleStore = useArticleStore()
const listRef = ref<{ load?: () => void } | null>(null)

const selectedArticleId = computed(() => {
  const id = route.params.id
  return id ? Number(id) : null
})

const currentArticle = computed(() => articleStore.current)

function onSelectArticle(id: number) {
  router.push(`/medcomm/article/${id}`)
}

provide('medcommRefreshList', () => listRef.value?.load?.())

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
</style>
