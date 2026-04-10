<template>
  <div class="artgen">
    <div class="page-header">
      <h2>创意绘图</h2>
      <span class="powered-by">Midjourney 技术驱动</span>
    </div>
    <el-alert
      type="info"
      title="该模块正在开发中，部分功能尚未完善"
      show-icon
      :closable="false"
      class="dev-banner"
    />
    <p class="page-desc">
      擅长高品质视觉对比图、概念信息图、艺术风格插图。生成耗时约 30-90 秒，请耐心等待。
    </p>

    <el-alert
      v-if="providerUnavailable"
      type="warning"
      title="创意绘图服务未配置"
      description="请在 设置 → 图像生成 中配置 Midjourney Proxy 地址。当前将降级为通用 API 生成。"
      show-icon
      class="warn-banner"
    />

    <el-form label-position="top" class="form">
      <el-form-item label="画面描述（中文或英文）">
        <div class="row-with-btn">
          <el-input
            v-model="sceneIdea"
            type="textarea"
            :rows="3"
            placeholder="描述你想要的画面内容，例如：一张对比图，左侧展示血糖剧烈波动，右侧展示平稳曲线"
          />
          <el-button
            type="default"
            :loading="aiLoading"
            :disabled="!sceneIdea.trim()"
            @click="handleAiPrompts"
          >
            AI 优化描述
          </el-button>
        </div>
      </el-form-item>

      <el-form-item label="精调提示词（可选，留空则根据描述自动构建英文提示词）">
        <el-input
          v-model="positivePrompt"
          type="textarea"
          :rows="3"
          placeholder="填写则直接使用此提示词生成（英文效果更佳）"
        />
      </el-form-item>

      <div class="form-row-inline">
        <el-form-item label="画幅比例">
          <el-select v-model="aspectKey" style="width: 180px">
            <el-option
              v-for="a in aspectPresets"
              :key="a.key"
              :label="a.label"
              :value="a.key"
            />
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
        <el-form-item label="风格">
          <el-select v-model="style" style="width: 160px">
            <el-option label="医学插画" value="medical_illustration" />
            <el-option label="写实" value="realistic" />
            <el-option label="扁平化" value="flat_design" />
            <el-option label="漫画" value="comic" />
            <el-option label="卡通" value="cartoon" />
            <el-option label="数据可视化" value="data_viz" />
          </el-select>
        </el-form-item>
        <el-form-item label="张数">
          <el-input-number v-model="batchCount" :min="1" :max="4" />
        </el-form-item>
      </div>

      <el-button
        type="primary"
        size="large"
        :loading="generating"
        :disabled="!sceneIdea.trim() && !positivePrompt.trim()"
        @click="handleGenerate"
      >
        {{ generating ? '创作中，请稍候…' : '开始创作' }}
      </el-button>
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
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '@/api'
import { useImageGenerate, type ImageGenParams } from '@/composables/useImageGenerate'

const route = useRoute()
const sceneIdea = ref('')
const positivePrompt = ref('')
const style = ref('medical_illustration')
const imageType = ref('comparison')
const batchCount = ref(1)
const aiLoading = ref(false)
const providerUnavailable = ref(false)

const imageTypeOptions = ref<Array<{ id: string; name: string }>>([
  { id: 'comparison', name: '对比图' },
  { id: 'infographic', name: '信息图' },
  { id: 'flowchart', name: '流程图' },
  { id: 'data_viz', name: '数据可视化' },
  { id: 'anatomy', name: '解剖示意图' },
  { id: 'pathology', name: '病理过程图' },
  { id: 'symptom', name: '症状示意图' },
  { id: 'prevention', name: '预防指导图' },
  { id: 'illustration', name: '通用插图' },
])

const aspectPresets = [
  { key: '1_1', label: '1:1 · 正方形', w: 1024, h: 1024 },
  { key: '16_9', label: '16:9 · 横屏', w: 1280, h: 720 },
  { key: '9_16', label: '9:16 · 竖屏', w: 720, h: 1280 },
  { key: '4_3', label: '4:3 · 标准', w: 1024, h: 768 },
  { key: '3_4', label: '3:4 · 竖版', w: 768, h: 1024 },
  { key: '3_2', label: '3:2 · 宽幅', w: 1200, h: 800 },
] as const

const aspectKey = ref<string>('16_9')

const { generating, images, error, isFallback, lastSeeds, generate, imageUrl } = useImageGenerate()

const dims = computed(() => aspectPresets.find((a) => a.key === aspectKey.value) || aspectPresets[0])
const displayUrls = computed(() => images.value.map((img) => imageUrl(img.path)))

onMounted(async () => {
  try {
    const res = await api.imagegen.getProviders()
    const providers = res.data as Record<string, boolean>
    if (!providers?.midjourney) {
      providerUnavailable.value = true
    }
  } catch {
    /* ignore */
  }

  try {
    const res = await api.imagegen.getImageTypes()
    const list = res.data?.image_types || []
    if (list.length) {
      imageTypeOptions.value = list.map((t) => ({ id: t.id, name: t.name }))
    }
  } catch {
    /* use defaults */
  }

  const qPrompt = String(route.query.prompt || '').trim()
  const qStyle = String(route.query.style || '').trim()
  const qType = String(route.query.image_type || '').trim()
  if (qPrompt) sceneIdea.value = qPrompt
  if (qStyle) style.value = qStyle
  if (qType) imageType.value = qType
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
      provider: 'midjourney',
    })
    const pos = res.data?.positive?.trim()
    if (!pos) {
      ElMessage.error('AI 未返回有效提示词，请重试')
      return
    }
    positivePrompt.value = pos
    ElMessage.success('已生成优化提示词')
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
  if (up) params.user_positive_prompt = up

  await generate(params, undefined, { preferredProvider: 'midjourney' })

  if (isFallback.value) {
    ElMessage.info({
      message: '创意绘图服务暂不可用，已自动降级为其他 API 生成',
      duration: 5000,
    })
  }
}
</script>

<style scoped>
.artgen {
  padding: 2rem;
  max-width: 920px;
}

.page-header {
  display: flex;
  align-items: baseline;
  gap: 0.75rem;
  margin-bottom: 0.25rem;
}

.page-header h2 {
  margin: 0;
  font-size: 1.5rem;
}

.powered-by {
  font-size: 0.8rem;
  color: #8b5cf6;
  background: #f5f3ff;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 500;
}

.page-desc {
  color: #6b7280;
  font-size: 0.88rem;
  margin-bottom: 1.25rem;
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

.dev-banner {
  margin-bottom: 1rem;
}
.warn-banner,
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
  margin-top: 1rem;
}

.thumb {
  width: 320px;
  max-width: 100%;
  height: auto;
  object-fit: cover;
  cursor: pointer;
  border-radius: 8px;
  border: 1px solid #eee;
}
</style>
