<template>
  <div class="new-article">
    <h2>新建科普文章</h2>
    <el-form :model="form" label-width="100px" style="max-width: 720px;">
      <el-form-item label="科普形式" required>
        <div class="format-mode">
          <el-switch v-model="platformFirst" active-text="平台优先" inactive-text="形式优先" />
        </div>
        <FormatPicker
          v-model="form.content_format"
          :platform="form.platform"
          :matrix="formatMatrix"
          :platform-first="platformFirst"
          @update:platform="form.platform = $event"
        />
      </el-form-item>
      <el-form-item label="主题" required>
        <el-input v-model="form.topic" placeholder="如：糖尿病日常管理" />
      </el-form-item>
      <el-form-item v-if="showTargetAudience" label="目标受众">
        <el-select v-model="form.target_audience" placeholder="选择受众">
          <el-option label="公众" value="public" />
          <el-option label="患者" value="patient" />
          <el-option label="学生" value="student" />
          <el-option label="专业人士" value="professional" />
          <el-option label="儿童" value="children" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="showReadingLevel" label="阅读难度">
        <el-select v-model="form.reading_level" placeholder="选择难度" clearable>
          <el-option label="通俗" value="layman" />
          <el-option label="专业" value="professional" />
        </el-select>
      </el-form-item>
      <el-form-item label="选择专科">
        <div class="specialty-picker">
          <el-radio-group v-model="form.specialty" class="specialty-options">
            <el-radio
              v-for="opt in SPECIALTY_OPTIONS"
              :key="opt.value"
              :value="opt.value"
              border
            >
              <span v-if="settingsStore.hasCustomSpecialty(opt.value)" class="custom-badge">
                {{ opt.label }} ✦定制
              </span>
              <span v-else>{{ opt.label }}</span>
            </el-radio>
          </el-radio-group>
        </div>
        <div v-if="settingsStore.isBasic" class="upgrade-hint">
          💡 当前使用通用预置内容，如需{{ form.specialty || '学科' }}专属词典和高质量示例，可升级为定制版
        </div>
        <div v-else-if="form.specialty && settingsStore.hasCustomSpecialty(form.specialty)" class="specialty-pack-info">
          ✦ {{ form.specialty }}：专属词典 {{ specialtyStats.terms }} 条 · 示例 {{ specialtyStats.examples }} 个
          <span v-if="specialtyStats.docs">· 知识库 {{ specialtyStats.docs }} 份文献</span>
          <span v-if="specialtyStats.updated_at"> · 最后更新 {{ specialtyStats.updated_at }}</span>
        </div>
      </el-form-item>
      <el-form-item label="模板">
        <el-select v-model="form.template_id" placeholder="选择模板（可选）" clearable>
          <el-option
            v-for="t in filteredTemplates"
            :key="t.id"
            :label="t.name"
            :value="t.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleCreate" :loading="creating">创建</el-button>
        <el-button @click="$router.back()">取消</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import FormatPicker from '@/components/common/FormatPicker.vue'
import { api } from '@/api'
import { useSettingsStore } from '@/stores/settings'
import { SPECIALTY_OPTIONS } from '@/constants/specialties'

const router = useRouter()
const settingsStore = useSettingsStore()
const creating = ref(false)
const platformFirst = ref(false) // 切换：形式优先 / 平台优先
const formatMatrix = ref<Record<string, Record<string, number>>>({})
const fieldVisibility = ref<Record<string, Record<string, boolean>>>({})

onMounted(async () => {
  try {
    const res = await api.formats.getFormats()
    formatMatrix.value = res.data?.matrix || {}
    const fmts = res.data?.formats || []
    const vis: Record<string, Record<string, boolean>> = {}
    for (const f of fmts) {
      vis[f.id] = f.field_visibility || {}
    }
    fieldVisibility.value = vis
  } catch {
    formatMatrix.value = {}
  }
})

const showTargetAudience = computed(() => {
  if (form.content_format === 'picture_book') return false
  const vis = fieldVisibility.value[form.content_format]
  return vis?.target_audience !== false
})

const showReadingLevel = computed(() => {
  const vis = fieldVisibility.value[form.content_format]
  return vis?.reading_level !== false
})

const form = reactive({
  content_format: 'article',
  topic: '',
  platform: 'wechat',
  target_audience: 'public',
  reading_level: null as string | null,
  specialty: '内分泌科',
  template_id: null as number | null,
})

const specialtyStats = computed(() => {
  if (!form.specialty) return { terms: 0, examples: 0, docs: 0, updated_at: undefined }
  return settingsStore.license.specialtyStats[form.specialty] ?? { terms: 0, examples: 0, docs: 0, updated_at: undefined }
})

const templates = ref<any[]>([])
const filteredTemplates = computed(() =>
  templates.value.filter((t: any) => t.content_format === form.content_format)
)

watch(() => form.content_format, async (fmt) => {
  if (fmt === 'picture_book') form.target_audience = 'children'
  const res = await api.templates.getTemplates(form.content_format)
  templates.value = res.data?.items || []
}, { immediate: true })

async function handleCreate() {
  if (!form.topic?.trim()) return
  creating.value = true
  try {
    const res = await api.medcomm.createArticle({
      ...form,
      default_model: settingsStore.defaultModel,
    })
    const id = res.data?.id
    if (id) {
      router.push(`/medcomm/article/${id}`)
    }
  } finally {
    creating.value = false
  }
}
</script>

<style scoped>
.new-article {
  padding: 2rem;
}

.format-mode {
  margin-bottom: 0.5rem;
}

h2 {
  margin-bottom: 1.5rem;
}

.specialty-picker {
  width: 100%;
}

.specialty-options {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.specialty-options :deep(.el-radio) {
  margin-right: 0;
}

.custom-badge {
  color: var(--el-color-primary);
  font-weight: 500;
}

.upgrade-hint {
  margin-top: 0.5rem;
  padding: 0.5rem 0.75rem;
  background: #f0f9ff;
  color: #0369a1;
  border-radius: 6px;
  font-size: 0.85rem;
}

.specialty-pack-info {
  margin-top: 0.5rem;
  font-size: 0.9rem;
  color: #059669;
}
</style>
