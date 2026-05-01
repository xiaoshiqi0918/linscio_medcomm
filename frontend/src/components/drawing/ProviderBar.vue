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
        <!-- 双 Key 模式（如可灵 AI 的 AccessKey + SecretKey） -->
        <template v-if="editingProvider?.dualKey">
          <el-form-item :label="editingProvider.dualKey.firstLabel">
            <el-input
              v-model="editingKey"
              type="password"
              :placeholder="editingProvider.dualKey.firstPlaceholder"
              show-password
            />
          </el-form-item>
          <el-form-item :label="editingProvider.dualKey.secondLabel">
            <el-input
              v-model="editingKeySecondary"
              type="password"
              :placeholder="editingProvider.dualKey.secondPlaceholder"
              show-password
            />
          </el-form-item>
        </template>
        <!-- 单 Key 模式 -->
        <el-form-item v-else :label="`${editingProvider?.label} API Key`">
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

interface DualKeyDef {
  firstLabel: string
  firstAccount: string
  firstPlaceholder: string
  secondLabel: string
  secondAccount: string
  secondPlaceholder: string
}

interface ProviderDef {
  id: string
  label: string
  keychainAccount: string
  placeholder: string
  applyUrl: string
  configured: boolean
  dualKey?: DualKeyDef
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
  {
    id: 'kling',
    label: '可灵 AI',
    // keychainAccount 仅用作 configured 状态键，实际保存走 dualKey 字段
    keychainAccount: 'kling_ak',
    placeholder: '',
    applyUrl: 'https://app.klingai.com/cn/dev/',
    configured: false,
    dualKey: {
      firstLabel: 'AccessKey',
      firstAccount: 'kling_ak',
      firstPlaceholder: '可灵开放平台 AccessKey',
      secondLabel: 'SecretKey',
      secondAccount: 'kling_sk',
      secondPlaceholder: '可灵开放平台 SecretKey',
    },
  },
  {
    id: 'jimeng',
    label: '即梦 AI',
    keychainAccount: 'volcengine_ak',
    placeholder: '',
    applyUrl: 'https://www.volcengine.com/docs/85621/1616429',
    configured: false,
    dualKey: {
      firstLabel: 'AccessKey ID',
      firstAccount: 'volcengine_ak',
      firstPlaceholder: '火山引擎 AccessKey ID（VOLCENGINE_AK）',
      secondLabel: 'AccessKey Secret',
      secondAccount: 'volcengine_sk',
      secondPlaceholder: '火山引擎 AccessKey Secret（VOLCENGINE_SK）',
    },
  },
])

const dialogVisible = ref(false)
const editingProvider = ref<ProviderDef | null>(null)
const editingKey = ref('')
const editingKeySecondary = ref('')
const saving = ref(false)

const electron = typeof window !== 'undefined' ? (window as any).electronAPI : null

function handleClick(p: ProviderDef) {
  if (p.configured) {
    activeProvider.value = p.id
    emit('update:modelValue', p.id)
  } else {
    editingProvider.value = p
    editingKey.value = ''
    editingKeySecondary.value = ''
    dialogVisible.value = true
  }
}

async function _saveSingleKey(account: string, key: string) {
  if (electron?.saveApiKey) {
    await electron.saveApiKey(account, key)
  } else {
    localStorage.setItem(`drawing_key_${account}`, key)
  }
}

async function _readSingleKey(account: string): Promise<string> {
  if (electron?.getApiKey) {
    const v = await electron.getApiKey(account)
    return v || ''
  }
  return localStorage.getItem(`drawing_key_${account}`) || ''
}

async function handleSave() {
  if (!editingProvider.value) return
  const key = editingKey.value.trim()
  const dual = editingProvider.value.dualKey
  if (!key) {
    ElMessage.warning(dual ? `请输入 ${dual.firstLabel}` : '请输入 API Key')
    return
  }
  if (dual && !editingKeySecondary.value.trim()) {
    ElMessage.warning(`请输入 ${dual.secondLabel}`)
    return
  }
  saving.value = true
  try {
    if (dual) {
      await _saveSingleKey(dual.firstAccount, key)
      await _saveSingleKey(dual.secondAccount, editingKeySecondary.value.trim())
    } else {
      await _saveSingleKey(editingProvider.value.keychainAccount, key)
    }
    if (electron?.reloadApiKeys) {
      try {
        const reloadRes = await electron.reloadApiKeys()
        if (reloadRes && !reloadRes.ok) {
          console.warn('reloadApiKeys failed:', reloadRes.error)
        }
      } catch { /* ignore */ }
    }
    editingProvider.value.configured = true
    activeProvider.value = editingProvider.value.id
    emit('update:modelValue', editingProvider.value.id)
    ElMessage.success(`${editingProvider.value.label} 已保存`)
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
      if (p.dualKey) {
        const ak = await _readSingleKey(p.dualKey.firstAccount)
        const sk = await _readSingleKey(p.dualKey.secondAccount)
        p.configured = !!(ak && sk)
      } else {
        const v = await _readSingleKey(p.keychainAccount)
        p.configured = !!v
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
