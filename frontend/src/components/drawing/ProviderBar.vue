<template>
  <div class="provider-bar">
    <button
      v-for="p in providers"
      :key="p.id"
      class="provider-btn"
      :class="{ active: activeProvider === p.id, configured: p.configured }"
      @click="handleClick(p)"
    >
      {{ p.label }}
      <span v-if="p.configured" class="status-dot configured" />
      <span v-else class="status-dot unconfigured" />
    </button>

    <el-dialog
      v-model="dialogVisible"
      :title="`配置 ${editingProvider?.label} API Key`"
      width="480px"
      destroy-on-close
    >
      <el-form label-position="top">
        <el-form-item :label="`${editingProvider?.label} API Key`">
          <el-input
            v-model="editingKey"
            type="password"
            :placeholder="editingProvider?.placeholder"
            show-password
          />
        </el-form-item>
        <div v-if="editingProvider?.applyUrl" class="apply-hint">
          <a :href="editingProvider.applyUrl" target="_blank" rel="noopener">前往申请 API Key ↗</a>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

interface ProviderDef {
  id: string
  label: string
  keychainAccount: string
  placeholder: string
  applyUrl: string
  configured: boolean
}

const props = defineProps<{
  modelValue?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const activeProvider = ref(props.modelValue || 'dalle')

const providers = ref<ProviderDef[]>([
  {
    id: 'midjourney',
    label: 'Midjourney',
    keychainAccount: 'midjourney_proxy',
    placeholder: 'Midjourney Proxy URL 或 API Key',
    applyUrl: 'https://www.midjourney.com/',
    configured: false,
  },
  {
    id: 'comfyui',
    label: 'ComfyUI',
    keychainAccount: 'comfy_cloud',
    placeholder: 'Comfy Cloud API Key',
    applyUrl: 'https://platform.comfy.org',
    configured: false,
  },
  {
    id: 'dalle',
    label: 'DALL·E',
    keychainAccount: 'openai',
    placeholder: 'OpenAI API Key (sk-xxx)',
    applyUrl: 'https://platform.openai.com/api-keys',
    configured: false,
  },
])

const dialogVisible = ref(false)
const editingProvider = ref<ProviderDef | null>(null)
const editingKey = ref('')
const saving = ref(false)

const electron = typeof window !== 'undefined' ? (window as any).electronAPI : null

function handleClick(p: ProviderDef) {
  if (p.configured) {
    activeProvider.value = p.id
    emit('update:modelValue', p.id)
  } else {
    editingProvider.value = p
    editingKey.value = ''
    dialogVisible.value = true
  }
}

async function handleSave() {
  if (!editingProvider.value) return
  const key = editingKey.value.trim()
  if (!key) {
    ElMessage.warning('请输入 API Key')
    return
  }
  saving.value = true
  try {
    if (electron?.saveApiKey) {
      await electron.saveApiKey(editingProvider.value.keychainAccount, key)
      try {
        const reloadRes = await electron.reloadApiKeys?.()
        if (reloadRes && !reloadRes.ok) {
          console.warn('reloadApiKeys failed:', reloadRes.error)
        }
      } catch { /* ignore */ }
    } else {
      localStorage.setItem(`drawing_key_${editingProvider.value.keychainAccount}`, key)
    }
    editingProvider.value.configured = true
    activeProvider.value = editingProvider.value.id
    emit('update:modelValue', editingProvider.value.id)
    ElMessage.success(`${editingProvider.value.label} API Key 已保存`)
    dialogVisible.value = false
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function checkConfigured() {
  for (const p of providers.value) {
    try {
      if (electron?.getApiKey) {
        const val = await electron.getApiKey(p.keychainAccount)
        p.configured = !!val
      } else {
        p.configured = !!localStorage.getItem(`drawing_key_${p.keychainAccount}`)
      }
    } catch {
      p.configured = false
    }
  }
  const configured = providers.value.find((p) => p.id === activeProvider.value)
  if (!configured?.configured) {
    const first = providers.value.find((p) => p.configured)
    if (first) {
      activeProvider.value = first.id
      emit('update:modelValue', first.id)
    }
  }
}

onMounted(checkConfigured)
</script>

<style scoped>
.provider-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 1.5rem;
}

.provider-btn {
  position: relative;
  padding: 10px 28px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: #2a2a3e;
  color: rgba(255, 255, 255, 0.6);
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  letter-spacing: 0.3px;
}

.provider-btn:hover {
  background: #33334d;
  color: rgba(255, 255, 255, 0.85);
}

.provider-btn.active {
  background: #6366f1;
  color: #fff;
  border-color: #6366f1;
  box-shadow: 0 2px 12px rgba(99, 102, 241, 0.4);
}

.provider-btn.configured {
  border-color: rgba(99, 102, 241, 0.3);
}

.status-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  margin-left: 8px;
  vertical-align: middle;
}

.status-dot.configured {
  background: #22c55e;
}

.status-dot.unconfigured {
  background: #6b7280;
}

.apply-hint {
  margin-top: 0.5rem;
}

.apply-hint a {
  color: var(--el-color-primary);
  font-size: 0.85rem;
}
</style>
