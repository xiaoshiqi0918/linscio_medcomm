<template>
  <div class="painting-intent-panel">
    <div class="panel-header">
      <h4>配图设置</h4>
      <el-tag v-if="slot?.image_status === 'uploaded'" type="success" size="small" effect="plain">已上传</el-tag>
      <el-tag v-else-if="slot?.image_status === 'prompt_ready'" type="warning" size="small" effect="plain">提示词就绪</el-tag>
      <el-tag v-else size="small" type="info" effect="plain">未配置</el-tag>
    </div>

    <!-- 画意输入 -->
    <div class="section-block">
      <div class="block-label">
        <span>画意</span>
        <el-button text type="primary" size="small" :loading="suggestLoading" @click="handleSuggestIntent">
          建议画意
        </el-button>
      </div>
      <el-input
        v-model="intentText"
        type="textarea"
        :rows="2"
        placeholder="描述这张配图要传达什么（如：医生向患者耐心讲解血压管理要点的温馨场景）"
        @change="onIntentChange"
      />
      <div v-if="suggestions.length" class="suggestions">
        <div
          v-for="(s, i) in suggestions"
          :key="i"
          class="suggestion-item"
          @click="applyIntentSuggestion(s)"
        >
          <span class="suggestion-text">{{ s.intent }}</span>
          <span class="suggestion-reason">{{ s.reason }}</span>
        </div>
      </div>
    </div>

    <!-- 画意范例浏览 -->
    <div class="section-block">
      <div class="block-label">
        <span>画意范例库</span>
        <el-select v-model="exampleTopic" size="small" placeholder="选题" clearable style="width: 140px;">
          <el-option v-for="t in topics" :key="t.id" :label="t.name" :value="t.id" />
        </el-select>
      </div>
      <div v-if="examples.length" class="example-list">
        <div
          v-for="ex in examples"
          :key="ex.id"
          class="example-item"
          @click="applyExample(ex)"
        >{{ ex.intent_text }}</div>
      </div>
      <div v-else class="example-empty">{{ exampleTopic ? '暂无该选题范例' : '选择选题浏览范例' }}</div>
    </div>

    <!-- 画幅选择 -->
    <div class="section-block">
      <div class="block-label">画幅</div>
      <el-radio-group v-model="aspectRatio" size="small" @change="onConfigChange">
        <el-radio-button value="16:9">横版 16:9</el-radio-button>
        <el-radio-button value="1:1">方形 1:1</el-radio-button>
        <el-radio-button value="3:4">竖版 3:4</el-radio-button>
      </el-radio-group>
    </div>

    <!-- 风格预设 -->
    <div class="section-block">
      <div class="block-label">风格预设</div>
      <div class="style-grid">
        <div
          v-for="preset in stylePresets"
          :key="preset.id"
          class="style-card"
          :class="{ selected: selectedPresetId === preset.id }"
          @click="selectPreset(preset)"
        >
          <div class="style-name">{{ preset.display_name }}</div>
          <div class="style-desc">{{ preset.description }}</div>
        </div>
      </div>
    </div>

    <!-- 微调（可选展开） -->
    <el-collapse v-model="showAdjustments" class="adjustments-collapse">
      <el-collapse-item name="adj" title="微调参数">
        <el-form size="small" label-width="60px">
          <el-form-item label="构图">
            <el-input v-model="adjustments.composition_zh" placeholder="如：特写、中景、全景" />
          </el-form-item>
          <el-form-item label="光线">
            <el-input v-model="adjustments.lighting_zh" placeholder="如：自然光、柔和照明" />
          </el-form-item>
          <el-form-item label="色调">
            <el-input v-model="adjustments.color_zh" placeholder="如：温暖色调、冷色调" />
          </el-form-item>
        </el-form>
      </el-collapse-item>
    </el-collapse>

    <!-- 生成按钮 -->
    <div class="generate-row">
      <el-button type="primary" :loading="generating" :disabled="!intentText" @click="handleGenerate">
        一键生成双语提示词
      </el-button>
    </div>

    <!-- 双语 Prompt 展示 -->
    <div v-if="promptZh || promptEn" class="prompt-display">
      <div class="prompt-columns">
        <div class="prompt-col">
          <div class="prompt-col-header">
            <span>中文提示词</span>
            <el-button text size="small" @click="copyText(promptZh)">复制</el-button>
          </div>
          <el-input
            v-model="promptZh"
            type="textarea"
            :rows="4"
            class="prompt-textarea"
          />
        </div>
        <div class="prompt-col">
          <div class="prompt-col-header">
            <span>英文提示词</span>
            <el-button text size="small" @click="copyText(promptEn)">复制</el-button>
          </div>
          <el-input
            v-model="promptEn"
            type="textarea"
            :rows="4"
            class="prompt-textarea"
          />
        </div>
      </div>

      <!-- 负向词 -->
      <div v-if="negativeWordsText" class="negative-words">
        <div class="prompt-col-header">
          <span>负向词（自动合并）</span>
          <el-button text size="small" @click="copyText(negativeWordsText)">复制</el-button>
        </div>
        <div class="negative-text">{{ negativeWordsText }}</div>
      </div>
    </div>

    <!-- AI 生成配图 -->
    <div v-if="(promptZh || promptEn) && hasImageProviders" class="ai-generate-block">
      <div class="ai-generate-row">
        <el-button
          type="success"
          :loading="generatingImage"
          :disabled="generatingImage"
          @click="handleGenerateImage"
        >
          {{ generatingImage ? 'AI 生成中，预计 10-30 秒...' : 'AI 生成配图' }}
        </el-button>
        <el-select
          v-model="preferredProvider"
          size="small"
          style="width: 218px;"
          placeholder="引擎"
        >
          <el-option label="自动选择" value="" />
          <el-option
            v-for="opt in imageEngineOptions"
            :key="opt.value"
            :label="imageEngineOptionLabel(opt)"
            :value="opt.value"
            :disabled="!imageEngineReady(opt.value)"
          />
        </el-select>
      </div>
      <div v-if="imageProvider" class="provider-tag">
        上次由 <el-tag size="small" type="info">{{ providerLabel(imageProvider) }}</el-tag> 生成
      </div>
    </div>

    <!-- 操作指引 -->
    <div v-if="(promptZh || promptEn) && !hasImageProviders" class="guide-block">
      <el-alert type="info" :closable="false" show-icon>
        <template #title>操作指引</template>
        复制中文或英文提示词 → 在所用文生图工具中选择相同比例（{{ aspectRatio }}） → 导出 JPG/PNG → 上传至下方
      </el-alert>
    </div>

    <!-- 图片上传 -->
    <div class="section-block">
      <div class="block-label">{{ hasImageProviders ? '手动上传配图（覆盖 AI 生成）' : '上传配图' }}</div>
      <el-upload
        :auto-upload="false"
        :show-file-list="false"
        accept=".jpg,.jpeg,.png"
        @change="onImageSelected"
      >
        <div v-if="slot?.image_path" class="uploaded-preview">
          <img :src="imagePreviewUrl" alt="配图预览" class="preview-img" />
          <el-button size="small" class="reupload-btn">重新上传</el-button>
        </div>
        <el-button v-else type="default" size="small">选择图片（JPG/PNG）</el-button>
      </el-upload>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/api'

const props = defineProps<{
  articleId: number
  sectionId: number | null
  sectionText?: string
  topic?: string
  sectionType?: string
  requiredImageFormat?: string
}>()

const emit = defineEmits<{
  slotUpdated: [slot: any]
}>()

// ── State ──
const slot = ref<any>(null)
const intentText = ref('')
const aspectRatio = ref('16:9')
const selectedPresetId = ref<number | null>(null)
const promptZh = ref('')
const promptEn = ref('')
const negativeWordsText = ref('')
const generating = ref(false)
const generatingImage = ref(false)
const suggestLoading = ref(false)
const imageProviders = ref<Record<string, boolean>>({})
const hasImageProviders = ref(false)
const preferredProvider = ref('')
const imageProvider = ref<string | null>(null)
const suggestions = ref<Array<{ intent: string; reason: string }>>([])
const showAdjustments = ref<string[]>([])
const adjustments = reactive({
  composition_zh: '',
  lighting_zh: '',
  color_zh: '',
})

// ── Data ──
const stylePresets = ref<any[]>([])
const topics = ref<any[]>([])
const exampleTopic = ref('')
const examples = ref<any[]>([])

const imagePreviewUrl = computed(() => {
  if (!slot.value?.image_path) return ''
  return `/api/v1/imagegen/serve?path=${encodeURIComponent(slot.value.image_path)}`
})

onMounted(async () => {
  await Promise.all([loadPresets(), loadTopics(), loadSlot(), loadImageProviders()])
})

async function refreshExamples() {
  if (!exampleTopic.value) { examples.value = []; return }
  try {
    const res = await api.imageIntent.getIntentExamples({ topic: exampleTopic.value, style_preset_id: selectedPresetId.value })
    examples.value = res.data?.items || []
  } catch {
    examples.value = []
  }
}

watch(() => exampleTopic.value, refreshExamples)
watch(() => selectedPresetId.value, () => { if (exampleTopic.value) refreshExamples() })

watch(() => props.sectionId, () => loadSlot())

async function loadPresets() {
  try {
    const res = await api.imageIntent.getStylePresets()
    stylePresets.value = res.data?.items || []
    if (stylePresets.value.length && !selectedPresetId.value) {
      selectedPresetId.value = stylePresets.value[0].id
      applyPresetDefaults(stylePresets.value[0])
    }
  } catch { /* ignore */ }
}

async function loadTopics() {
  try {
    const res = await api.imageIntent.getTopics()
    topics.value = res.data?.items || []
  } catch { /* ignore */ }
}

async function loadSlot() {
  if (!props.articleId) return
  try {
    const res = await api.imageIntent.getImageSlots(props.articleId)
    const slots = res.data?.items || []
    const match = slots.find((s: any) => s.section_id === props.sectionId)
    if (match) {
      slot.value = match
      intentText.value = match.intent_text || ''
      aspectRatio.value = match.aspect_ratio || '16:9'
      selectedPresetId.value = match.style_preset_id || selectedPresetId.value
      promptZh.value = match.prompt_zh || ''
      promptEn.value = match.prompt_en || ''
      negativeWordsText.value = match.negative_words || ''
      imageProvider.value = match.image_provider || null
    } else {
      slot.value = null
    }
  } catch { /* ignore */ }
}

async function ensureSlot(): Promise<any> {
  if (slot.value) return slot.value
  try {
    const res = await api.imageIntent.createImageSlot(props.articleId, {
      section_id: props.sectionId,
      intent_text: intentText.value,
      aspect_ratio: aspectRatio.value,
      style_preset_id: selectedPresetId.value,
    })
    slot.value = res.data
    return res.data
  } catch {
    return null
  }
}

function applyPresetDefaults(preset: any) {
  if (adjustments.composition_zh || adjustments.lighting_zh || adjustments.color_zh) return
  adjustments.composition_zh = preset.default_composition || '中景'
  adjustments.lighting_zh = preset.default_lighting || '柔和自然光'
  adjustments.color_zh = preset.default_color || '温暖色调'
}

function selectPreset(preset: any) {
  selectedPresetId.value = preset.id
  applyPresetDefaults(preset)
  onConfigChange()
}

async function onIntentChange() {
  const s = await ensureSlot()
  if (s) {
    await api.imageIntent.updateImageSlot(s.id, { intent_text: intentText.value })
  }
}

async function onConfigChange() {
  const s = await ensureSlot()
  if (s) {
    await api.imageIntent.updateImageSlot(s.id, {
      aspect_ratio: aspectRatio.value,
      style_preset_id: selectedPresetId.value,
    })
  }
}

async function handleSuggestIntent() {
  if (!props.sectionText) {
    ElMessage.warning('当前章节暂无正文内容')
    return
  }
  suggestLoading.value = true
  try {
    const res = await api.imageIntent.suggestIntent({
      section_text: props.sectionText,
      topic: props.topic,
      section_type: props.sectionType,
    })
    suggestions.value = res.data?.suggestions || []
    if (!suggestions.value.length) {
      ElMessage.info('暂无画意建议')
    }
  } catch {
    ElMessage.error('获取画意建议失败')
  } finally {
    suggestLoading.value = false
  }
}

function applyIntentSuggestion(s: { intent: string }) {
  intentText.value = s.intent
  suggestions.value = []
  onIntentChange()
}

function applyExample(ex: any) {
  intentText.value = ex.intent_text
  onIntentChange()
}

async function handleGenerate() {
  if (!intentText.value) return
  const s = await ensureSlot()
  if (!s) return

  generating.value = true
  try {
    await api.imageIntent.updateImageSlot(s.id, {
      intent_text: intentText.value,
      aspect_ratio: aspectRatio.value,
      style_preset_id: selectedPresetId.value,
      user_adjustments: Object.fromEntries(
        Object.entries(adjustments).filter(([, v]) => v)
      ) || undefined,
    })

    const res = await api.imageIntent.generateSlotPrompt(s.id)
    const result = res.data
    slot.value = result.slot || slot.value
    promptZh.value = result.slot?.prompt_zh || result.prompt_result?.prompt_zh || ''
    promptEn.value = result.slot?.prompt_en || result.prompt_result?.prompt_en || ''
    negativeWordsText.value = result.slot?.negative_words || result.prompt_result?.negative_words_text || ''
    emit('slotUpdated', slot.value)
    ElMessage.success('提示词生成完成')
  } catch {
    ElMessage.error('提示词生成失败')
  } finally {
    generating.value = false
  }
}

async function onImageSelected(uploadFile: any) {
  if (!uploadFile?.raw) return

  if (props.requiredImageFormat) {
    const ext = (uploadFile.raw.name || '').split('.').pop()?.toLowerCase()
    const required = props.requiredImageFormat.toLowerCase()
    if (required === 'jpg' && ext !== 'jpg' && ext !== 'jpeg') {
      ElMessage.warning(`赛制要求配图格式为 JPG，当前文件为 ${ext?.toUpperCase()}`)
    } else if (required === 'png' && ext !== 'png') {
      ElMessage.warning(`赛制要求配图格式为 PNG，当前文件为 ${ext?.toUpperCase()}`)
    }
  }

  const s = await ensureSlot()
  if (!s) return

  const formData = new FormData()
  formData.append('file', uploadFile.raw)
  try {
    const res = await api.imageIntent.uploadSlotImage(s.id, formData)
    slot.value = res.data
    emit('slotUpdated', slot.value)
    ElMessage.success('配图上传成功')
  } catch {
    ElMessage.error('配图上传失败')
  }
}

async function loadImageProviders() {
  try {
    const res = await api.imageIntent.getImageProviders()
    imageProviders.value = res.data?.providers || {}
    hasImageProviders.value = res.data?.any_available || false
  } catch {
    hasImageProviders.value = false
  }
}

async function handleGenerateImage() {
  const s = await ensureSlot()
  if (!s) return

  generatingImage.value = true
  try {
    const res = await api.imageIntent.generateSlotImage(
      s.id,
      preferredProvider.value ? { preferred_provider: preferredProvider.value } : undefined,
    )
    slot.value = res.data?.slot || slot.value
    imageProvider.value = res.data?.provider || null
    emit('slotUpdated', slot.value)
    ElMessage.success(`配图生成完成${res.data?.provider ? '（' + providerLabel(res.data.provider) + '）' : ''}`)
  } catch (err: any) {
    const msg = err?.response?.data?.detail || '图像生成失败，请稍后重试'
    ElMessage.error(msg)
  } finally {
    generatingImage.value = false
  }
}

const imageEngineOptions: Array<{ value: string; label: string }> = [
  { value: 'gpt_image', label: 'GPT Image' },
  { value: 'openai', label: 'DALL·E 3 / ChatGPT' },
  { value: 'gemini_image', label: 'Google Gemini 图像' },
  { value: 'moonshot_image', label: 'Kimi（Moonshot）图像' },
  { value: 'midjourney', label: 'Midjourney' },
  { value: 'comfyui_local', label: 'ComfyUI（本地）' },
  { value: 'comfyui_cloud', label: 'ComfyUI Cloud' },
  { value: 'wanx', label: '通义万相' },
  { value: 'siliconflow', label: '硅基流动' },
  { value: 'wenxin', label: '文心一格' },
]

function imageEngineOptionLabel(opt: { value: string; label: string }) {
  return imageEngineReady(opt.value) ? opt.label : `${opt.label}（未接入）`
}

const _PROVIDER_LABELS: Record<string, string> = {
  gpt_image: 'GPT Image',
  openai: 'DALL·E 3',
  gemini_image: 'Google Gemini 图像',
  moonshot_image: 'Kimi（Moonshot）图像',
  midjourney: 'Midjourney',
  comfyui_local: 'ComfyUI（本地）',
  comfyui_cloud: 'ComfyUI Cloud',
  comfyui: 'ComfyUI',
  wanx: '通义万相',
  siliconflow: '硅基流动',
  wenxin: '文心一格',
  pollinations: 'Pollinations',
}

function imageEngineReady(value: string): boolean {
  const p = imageProviders.value
  if (!value) return true
  if (value === 'comfyui_local') return !!(p.comfyui_local_running)
  return !!(p as Record<string, boolean>)[value]
}
function providerLabel(name: string): string {
  return _PROVIDER_LABELS[name] || name
}

function copyText(text: string) {
  navigator.clipboard.writeText(text).then(() => {
    ElMessage.success('已复制')
  }).catch(() => {
    ElMessage.error('复制失败')
  })
}
</script>

<style scoped>
.painting-intent-panel {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.panel-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.panel-header h4 {
  margin: 0;
  font-size: 0.95rem;
}

.section-block {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.block-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 0.85rem;
  font-weight: 600;
  color: #666;
}

.suggestions {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-top: 0.25rem;
}

.suggestion-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.4rem 0.6rem;
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
  transition: background 0.15s;
}

.suggestion-item:hover {
  background: #e0f2fe;
}

.suggestion-reason {
  color: #999;
  font-size: 0.75rem;
  flex-shrink: 0;
  margin-left: 0.5rem;
}

.example-list {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  max-height: 150px;
  overflow-y: auto;
}

.example-item {
  padding: 0.35rem 0.6rem;
  background: #fafafa;
  border: 1px solid #eee;
  border-radius: 4px;
  font-size: 0.8rem;
  cursor: pointer;
  transition: background 0.15s;
}

.example-item:hover {
  background: #ecf5ff;
  border-color: #b3d8ff;
}

.example-empty {
  font-size: 0.8rem;
  color: #999;
  padding: 0.5rem 0;
}

.style-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.5rem;
}

.style-card {
  padding: 0.5rem;
  border: 1px solid #eee;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s;
  text-align: center;
}

.style-card:hover {
  border-color: #409eff;
}

.style-card.selected {
  border-color: #409eff;
  background: #ecf5ff;
}

.style-name {
  font-size: 0.85rem;
  font-weight: 600;
  margin-bottom: 0.2rem;
}

.style-desc {
  font-size: 0.7rem;
  color: #999;
  line-height: 1.3;
}

.adjustments-collapse {
  border: none;
}

.adjustments-collapse :deep(.el-collapse-item__header) {
  font-size: 0.85rem;
  color: #666;
  height: 36px;
}

.generate-row {
  text-align: center;
}

.prompt-display {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.prompt-columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}

.prompt-col-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.8rem;
  font-weight: 600;
  color: #666;
  margin-bottom: 0.25rem;
}

.prompt-textarea :deep(textarea) {
  font-size: 0.8rem;
  line-height: 1.5;
}

.negative-words {
  padding: 0.5rem;
  background: #fef0f0;
  border-radius: 6px;
}

.negative-text {
  font-size: 0.75rem;
  color: #666;
  line-height: 1.5;
  white-space: pre-wrap;
}

.ai-generate-block {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin-top: 0.25rem;
}

.ai-generate-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.provider-tag {
  font-size: 0.78rem;
  color: #888;
}

.guide-block {
  margin-top: 0.25rem;
}

.guide-block :deep(.el-alert__content) {
  font-size: 0.8rem;
}

.uploaded-preview {
  position: relative;
  display: inline-block;
}

.preview-img {
  max-width: 200px;
  max-height: 150px;
  border-radius: 6px;
  border: 1px solid #eee;
}

.reupload-btn {
  position: absolute;
  bottom: 4px;
  right: 4px;
}
</style>
