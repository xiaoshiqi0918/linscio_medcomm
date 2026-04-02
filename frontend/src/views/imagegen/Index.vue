<template>
  <div class="imagegen">
    <h2>图像生成</h2>
    <el-alert
      v-if="isFallback"
      type="warning"
      title="当前使用 Pollinations 免费降级"
      description="首选生图 API 未配置或不可用，图像质量可能较低"
      show-icon
      class="fallback-banner"
    />
    <el-form label-position="top" class="form">
      <el-form-item label="场景 / 灵感（中文或英文均可）">
        <div class="row-with-btn">
          <el-input
            v-model="sceneIdea"
            type="textarea"
            :rows="2"
            placeholder="描述画面内容；留空时须填写下方正向提示词。可用「AI 生成提示词」根据本框内容覆盖正/负向。"
          />
          <el-button
            type="default"
            :loading="aiLoading"
            :disabled="!sceneIdea.trim()"
            @click="handleAiPrompts"
          >
            AI 生成提示词
          </el-button>
        </div>
      </el-form-item>
      <el-form-item label="正向提示词">
        <el-input
          v-model="positivePrompt"
          type="textarea"
          :rows="4"
          placeholder="留空则根据「场景」由系统自动构建医学英文提示词；填写则直接使用（不再套风格前缀）。"
        />
      </el-form-item>
      <el-form-item label="负向提示词">
        <el-input
          v-model="negativePrompt"
          type="textarea"
          :rows="2"
          placeholder="留空：使用默认医学安全负向（含水印、血腥等约束）。填写：完全替换默认负向，不与默认合并。"
        />
      </el-form-item>
      <div class="form-row-inline">
        <el-form-item label="风格">
          <el-select v-model="style" style="width: 160px">
            <el-option label="医学插画" value="medical_illustration" />
            <el-option label="漫画" value="comic" />
            <el-option label="扁平化" value="flat_design" />
            <el-option label="绘本" value="picture_book" />
          </el-select>
        </el-form-item>
        <el-form-item label="配图类型">
          <el-select v-model="imageType" style="width: 160px" filterable>
            <el-option
              v-for="t in imageTypeOptions"
              :key="t.id"
              :label="t.name"
              :value="t.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="画幅">
          <el-select v-model="aspectKey" style="width: 200px">
            <el-option
              v-for="a in aspectPresets"
              :key="a.key"
              :label="a.label"
              :value="a.key"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="张数">
          <el-input-number v-model="batchCount" :min="1" :max="8" />
        </el-form-item>
      </div>
      <div class="form-row-inline">
        <el-form-item label="种子">
          <el-checkbox v-model="seedFixed">固定种子（可复现）</el-checkbox>
          <el-input-number
            v-if="seedFixed"
            v-model="seedValue"
            :min="0"
            :max="2147483647"
            style="margin-left: 8px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="generating" @click="handleGenerate">
            生成
          </el-button>
        </el-form-item>
      </div>
      <el-collapse class="advanced-collapse">
        <el-collapse-item title="高级（主要影响 ComfyUI：步数 / CFG / 采样器）" name="adv">
          <div class="form-row-inline">
            <el-form-item label="Steps">
              <el-input-number v-model="advSteps" :min="0" :max="150" placeholder="默认" />
            </el-form-item>
            <el-form-item label="CFG">
              <el-input-number v-model="advCfg" :min="0" :max="30" :step="0.5" placeholder="默认" />
            </el-form-item>
            <el-form-item label="Sampler" class="sampler-field">
              <el-input v-model="advSampler" placeholder="如 euler / dpmpp_2m" clearable />
            </el-form-item>
          </div>
        </el-collapse-item>
      </el-collapse>
    </el-form>
    <el-alert
      v-if="error"
      type="error"
      :title="error"
      show-icon
      closable
      class="error-banner"
    />
    <p v-if="lastSeeds.length" class="seeds-line">
      本次种子：{{ lastSeeds.join(' · ') }}
    </p>
    <div v-if="images.length" class="results" v-viewer>
      <img
        v-for="(img, i) in displayUrls"
        :key="i"
        :src="img"
        class="thumb"
        alt="生成结果"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/api'
import { useImageGenerate, type ImageGenParams } from '@/composables/useImageGenerate'

const sceneIdea = ref('')
const positivePrompt = ref('')
const negativePrompt = ref('')
const style = ref('medical_illustration')
const imageType = ref('anatomy')
const imageTypeOptions = ref<Array<{ id: string; name: string }>>([{ id: 'anatomy', name: '解剖示意图' }])

const aspectPresets = [
  { key: '1_1', label: '1:1 · 1024²', w: 1024, h: 1024 },
  { key: '16_9', label: '16:9 · 1280×720', w: 1280, h: 720 },
  { key: '9_16', label: '9:16 · 720×1280', w: 720, h: 1280 },
  { key: '4_3', label: '4:3 · 1024×768', w: 1024, h: 768 },
] as const
const aspectKey = ref<(typeof aspectPresets)[number]['key']>('1_1')

const batchCount = ref(1)
const seedFixed = ref(false)
const seedValue = ref(42)
const advSteps = ref(0)
const advCfg = ref(0)
const advSampler = ref('')

const aiLoading = ref(false)

const { generating, images, error, isFallback, lastSeeds, generate, imageUrl } = useImageGenerate()

const dims = computed(() => aspectPresets.find((a) => a.key === aspectKey.value) || aspectPresets[0])

const displayUrls = computed(() => images.value.map((img) => imageUrl(img.path)))

onMounted(async () => {
  try {
    const res = await api.imagegen.getImageTypes()
    const list = res.data?.image_types || []
    if (list.length) {
      imageTypeOptions.value = list.map((t) => ({ id: t.id, name: t.name }))
      if (!list.some((t) => t.id === imageType.value)) {
        imageType.value = list[0].id
      }
    }
  } catch {
    /* 使用默认 anatomy */
  }
})

async function handleAiPrompts() {
  const idea = sceneIdea.value.trim()
  if (!idea) return
  aiLoading.value = true
  try {
    const res = await api.imagegen.aiPrompts({
      scene_idea: idea,
      style: style.value,
      image_type: imageType.value,
      target_audience: 'public',
      content_format: 'article',
    })
    const pos = res.data?.positive?.trim()
    const neg = res.data?.negative?.trim()
    if (!pos) {
      ElMessage.error('AI 未返回有效提示词，请重试')
      return
    }
    positivePrompt.value = pos
    negativePrompt.value = neg || ''
    if (res.data?.used_template_fallback) {
      ElMessage.info('大模型不可用或解析失败，已用内置模板生成提示词，可自行微调')
    }
    ElMessage.success('已写入正/负向提示词（覆盖原内容）')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || 'AI 提示词请求失败')
  } finally {
    aiLoading.value = false
  }
}

async function handleGenerate() {
  const params: ImageGenParams = {
    prompt: sceneIdea.value.trim(),
    style: style.value,
    width: dims.value.w,
    height: dims.value.h,
    content_format: 'article',
    image_type: imageType.value,
    batch_count: batchCount.value,
  }
  const up = positivePrompt.value.trim()
  const un = negativePrompt.value.trim()
  if (up) params.user_positive_prompt = up
  if (un) params.user_negative_prompt = un
  if (seedFixed.value) params.seed = seedValue.value
  if (advSteps.value && advSteps.value > 0) params.steps = advSteps.value
  if (advCfg.value && advCfg.value > 0) params.cfg_scale = advCfg.value
  const samp = advSampler.value.trim()
  if (samp) params.sampler_name = samp
  await generate(params)
}
</script>

<style scoped>
.imagegen {
  padding: 2rem;
  max-width: 920px;
}

.form {
  margin-bottom: 1rem;
}

.row-with-btn {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.row-with-btn :deep(.el-textarea) {
  flex: 1;
}

.form-row-inline {
  display: flex;
  flex-wrap: wrap;
  gap: 0 1.5rem;
  align-items: flex-end;
}

.form-row-inline :deep(.el-form-item) {
  margin-bottom: 12px;
}

.sampler-field {
  min-width: 200px;
}

.advanced-collapse {
  margin-top: 4px;
  border: none;
}

.advanced-collapse :deep(.el-collapse-item__header) {
  font-size: 0.9rem;
  color: #606266;
}

.fallback-banner,
.error-banner {
  margin-bottom: 1rem;
}

.seeds-line {
  font-size: 0.85rem;
  color: #6b7280;
  margin-bottom: 0.75rem;
}

.results {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
}

.thumb {
  width: 256px;
  height: 256px;
  object-fit: cover;
  cursor: pointer;
  border-radius: 8px;
  border: 1px solid #eee;
}
</style>
