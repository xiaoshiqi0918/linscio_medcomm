<template>
  <div v-if="!isElectron && providers.length > 0" class="provider-hint">
    <el-popover
      placement="bottom-start"
      :width="220"
      trigger="click"
    >
      <template #reference>
        <el-button text size="small" class="provider-hint-btn">
          <span class="provider-hint-label">{{ currentLabel }}</span>
          <el-icon style="margin-left: 2px;"><ArrowDown /></el-icon>
        </el-button>
      </template>
      <div class="provider-hint-menu">
        <div class="provider-hint-title">临时切换服务商</div>
        <div
          v-for="p in menuOptions"
          :key="p.id === '' ? 'default' : p.id"
          class="provider-hint-item"
          :class="{ active: p.id === currentProvider, muted: p.configured === false }"
          @click="selectProvider(p.id)"
        >
          <span>{{ p.label }}</span>
          <el-tag v-if="p.recommended" size="small" type="success" style="margin-left: auto;">推荐</el-tag>
          <el-icon v-if="p.id === currentProvider" style="margin-left: 4px; color: #3b82f6;"><Check /></el-icon>
        </div>
        <div class="provider-hint-note">仅本次操作生效，不影响设置页的默认配置</div>
      </div>
    </el-popover>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { ArrowDown, Check } from '@element-plus/icons-vue'
import { useSettingsStore } from '@/stores/settings'

const props = defineProps<{
  workflow?: string
}>()

const settingsStore = useSettingsStore()
const isElectron = typeof window !== 'undefined' && !!(window as any).electronAPI?.isElectron

const providers = computed(() => settingsStore.modelPrefsProviders)

const defaultForWorkflow = computed(() => {
  if (!props.workflow) return ''
  return settingsStore.modelPreferences[props.workflow] || ''
})

const currentProvider = computed(() => {
  return settingsStore.tempProviderOverride || defaultForWorkflow.value || ''
})

const currentLabel = computed(() => {
  if (!currentProvider.value) return '默认服务商'
  const p = providers.value.find(x => x.id === currentProvider.value)
  if (!p) return currentProvider.value
  return p.configured === false ? `${p.label}（未接入）` : p.label
})

const menuOptions = computed(() => {
  const wf = settingsStore.modelPrefsWorkflows.find(w => w.id === props.workflow)
  const rec = wf?.recommended || 'deepseek'
  return [
    { id: '', label: '使用默认', recommended: false, configured: true as boolean | undefined },
    ...providers.value.map(p => ({
      id: p.id,
      label: p.configured === false ? `${p.label}（未接入）` : p.label,
      recommended: p.id === rec,
      configured: p.configured,
    })),
  ]
})

function selectProvider(id: string) {
  settingsStore.setTempProviderOverride(id)
}

onMounted(() => {
  if (providers.value.length === 0) {
    settingsStore.loadModelPreferences()
  }
})
</script>

<style scoped>
.provider-hint {
  display: inline-flex;
  align-items: center;
}
.provider-hint-btn {
  font-size: 12px;
  color: #6b7280;
  padding: 2px 6px;
  height: auto;
}
.provider-hint-label {
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.provider-hint-menu {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.provider-hint-title {
  font-size: 12px;
  color: #9ca3af;
  padding: 2px 0 6px;
  border-bottom: 1px solid #f3f4f6;
  margin-bottom: 4px;
}
.provider-hint-item {
  display: flex;
  align-items: center;
  padding: 6px 8px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  color: #374151;
  transition: background 0.15s;
}
.provider-hint-item:hover {
  background: #f3f4f6;
}
.provider-hint-item.active {
  background: #eff6ff;
  color: #1e40af;
  font-weight: 500;
}
.provider-hint-item.muted {
  opacity: 0.75;
}
.provider-hint-note {
  font-size: 11px;
  color: #9ca3af;
  padding: 6px 0 2px;
  border-top: 1px solid #f3f4f6;
  margin-top: 4px;
}
</style>
