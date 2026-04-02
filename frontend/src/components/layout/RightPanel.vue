<template>
  <aside class="right-panel">
    <el-tabs v-model="activeTab" class="panel-tabs">
      <el-tab-pane label="AI 写作" name="ai" />
      <el-tab-pane label="配图建议" name="image" />
      <el-tab-pane label="核实状态" name="verify" />
      <el-tab-pane label="文章信息" name="info" />
    </el-tabs>
    <div class="panel-content">
      <div v-if="activeTab === 'ai'" class="tab-body">
        <p class="hint">选中内容后可调用 AI 续写、润色</p>
      </div>
      <div v-else-if="activeTab === 'image'" class="tab-body">
        <p class="hint">根据当前章节推荐配图方案</p>
      </div>
      <div v-else-if="activeTab === 'verify'" class="tab-body">
        <div v-if="ollamaWarning" class="ollama-warning">
          ⚠ {{ ollamaWarning }}
        </div>
        <VerificationPanel :report="verificationReport" />
        <div v-if="verificationReport" class="verify-summary">
          <div class="row"><span>✓ 声明</span> {{ claimSummary }}</div>
          <div class="row"><span>⚠ 可疑</span> {{ suspiciousCount }}处</div>
          <div class="row"><span>✓ 层级</span> {{ levelSummary }}</div>
        </div>
        <div v-if="settingsStore.showUpgradeHint" class="upgrade-hint">
          💡 当前使用通用内容库核实。升级定制版后，核实准确率将基于学科专属文献显著提升。
        </div>
      </div>
      <div v-else class="tab-body">
        <div v-if="article" class="info-list">
          <div class="row"><span>形式</span>{{ formatLabel(article.content_format) }}</div>
          <div class="row"><span>平台</span>{{ platformLabel(article.platform) }}</div>
          <div class="row"><span>主题</span>{{ article.topic }}</div>
          <div class="row"><span>受众</span>{{ article.target_audience || '-' }}</div>
        </div>
        <p v-else class="hint">选择文章查看信息</p>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import VerificationPanel from '@/components/verification/VerificationPanel.vue'
import { formatLabel, platformLabel } from '@/composables/useFormats'
import { useSettingsStore } from '@/stores/settings'

const settingsStore = useSettingsStore()
const props = defineProps<{
  article?: any
  verificationReport?: { claims?: any; reading_level?: any }
  ollamaWarning?: string | null
}>()

const activeTab = ref('verify')

const claimSummary = computed(() => {
  const r = props.verificationReport?.claims
  if (r?.skipped) return r.reason || '-'
  return r ? '已核实' : '8/10'
})

const suspiciousCount = computed(() => {
  const c = props.verificationReport?.claims
  if (!c || c.skipped) return 0
  return Number(c.pending_count ?? (Array.isArray(c.pending) ? c.pending.length : 0)) || 0
})

const levelSummary = computed(() => {
  const r = props.verificationReport?.reading_level
  if (r?.skipped) return r.reason || '-'
  return r ? '适合' : '-'
})
</script>

<style scoped>
.right-panel {
  width: 320px;
  min-width: 320px;
  background: #fff;
  border-left: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.panel-tabs { flex-shrink: 0; }
.panel-tabs :deep(.el-tabs__header) { margin: 0; padding: 0 0.5rem; }
.panel-tabs :deep(.el-tabs__content) { display: none; }
.panel-content { flex: 1; overflow-y: auto; padding: 0.75rem; }
.tab-body { font-size: 0.875rem; }
.hint { color: #9ca3af; font-size: 0.85rem; }
.verify-summary { margin-top: 0.75rem; }
.verify-summary .row { margin: 0.25rem 0; }
.verify-summary .row span { margin-right: 0.5rem; }
.ollama-warning {
  padding: 0.5rem 0.75rem;
  background: #fef3c7;
  color: #92400e;
  border-radius: 6px;
  font-size: 0.8rem;
  margin-bottom: 0.75rem;
}
.upgrade-hint {
  margin-top: 0.75rem;
  padding: 0.5rem 0.75rem;
  background: #f0f9ff;
  color: #0369a1;
  border-radius: 6px;
  font-size: 0.8rem;
}
.info-list .row { margin: 0.5rem 0; }
.info-list .row span { display: inline-block; width: 4em; color: #6b7280; }
</style>
