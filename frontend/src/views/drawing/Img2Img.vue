<template>
  <div class="img2img">
    <h2>图生图</h2>
    <ProviderBar v-model="activeProvider" />

    <div class="main-layout">
      <!-- 左侧：上传源图 -->
      <div class="source-panel">
        <div class="panel-title">源图</div>
        <el-upload
          ref="uploadRef"
          class="source-upload"
          :class="{ 'has-image': sourceImageUrl }"
          drag
          :auto-upload="false"
          :show-file-list="false"
          accept="image/*"
          @change="handleFileChange"
        >
          <div v-if="sourceImageUrl" class="source-preview">
            <img :src="sourceImageUrl" alt="源图" />
            <div class="overlay">
              <span>点击更换</span>
            </div>
          </div>
          <div v-else class="upload-placeholder">
            <el-icon :size="48" color="#909399"><UploadFilled /></el-icon>
            <div class="upload-text">拖拽图片到此处<br />或点击上传</div>
            <div class="upload-hint">支持 JPG / PNG / WebP</div>
          </div>
        </el-upload>
        <div v-if="sourceImageUrl" class="source-actions">
          <el-button size="small" @click="clearSource">清除</el-button>
        </div>
      </div>

      <!-- 右侧：控制面板 -->
      <div class="control-panel">
        <el-form label-position="top" class="form">
          <el-form-item label="变换描述">
            <el-input
              v-model="transformPrompt"
              type="textarea"
              :rows="3"
              placeholder="描述你希望对图片进行的变换，如：「转为扁平化医学插画风格」「添加标注文字」「去除背景，改为纯白」"
            />
          </el-form-item>

          <div class="form-row-inline">
            <el-form-item label="变换模式">
              <el-select v-model="transformMode" style="width: 180px">
                <el-option label="风格迁移" value="style_transfer" />
                <el-option label="局部重绘" value="inpaint" />
                <el-option label="图片扩展" value="outpaint" />
                <el-option label="超分辨率" value="upscale" />
                <el-option label="自由变换" value="free" />
              </el-select>
            </el-form-item>

            <el-form-item label="目标风格">
              <el-select v-model="targetStyle" style="width: 160px">
                <el-option label="医学插画" value="medical_illustration" />
                <el-option label="漫画" value="comic" />
                <el-option label="扁平化" value="flat_design" />
                <el-option label="绘本" value="picture_book" />
                <el-option label="写实" value="realistic" />
              </el-select>
            </el-form-item>
          </div>

          <el-form-item label="变换强度">
            <div class="strength-row">
              <el-slider
                v-model="strength"
                :min="0"
                :max="100"
                :step="5"
                :format-tooltip="(val: number) => `${val}%`"
                style="flex: 1"
              />
              <span class="strength-label">{{ strength }}%</span>
            </div>
            <div class="strength-hint">
              <span>保留原图 ←</span>
              <span>→ 大幅改变</span>
            </div>
          </el-form-item>

          <div class="form-row-inline">
            <el-form-item label="输出画幅">
              <el-select v-model="aspectKey" style="width: 200px">
                <el-option label="与源图相同" value="same" />
                <el-option
                  v-for="a in aspectPresets"
                  :key="a.key"
                  :label="a.label"
                  :value="a.key"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="张数">
              <el-input-number v-model="batchCount" :min="1" :max="4" />
            </el-form-item>
          </div>

          <el-form-item>
            <el-button
              type="primary"
              :loading="generating"
              :disabled="!sourceImageUrl"
              @click="handleGenerate"
            >
              开始变换
            </el-button>
          </el-form-item>
        </el-form>
      </div>
    </div>

    <el-alert
      v-if="error"
      type="error"
      :title="error"
      show-icon
      closable
      class="error-banner"
    />

    <div v-if="resultImages.length" class="results-section">
      <div class="results-title">变换结果</div>
      <div class="results" v-viewer>
        <img
          v-for="(img, i) in resultImages"
          :key="i"
          :src="img"
          class="thumb"
          alt="变换结果"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { api } from '@/api'
import { useImageGenerate, type ImageGenParams } from '@/composables/useImageGenerate'
import ProviderBar from '@/components/drawing/ProviderBar.vue'
import type { UploadFile } from 'element-plus'

const activeProvider = ref('dalle')

const sourceFile = ref<File | null>(null)
const sourceImageUrl = ref('')
const uploadRef = ref()
const uploadedRefPath = ref('')

const transformPrompt = ref('')
const transformMode = ref('style_transfer')
const targetStyle = ref('medical_illustration')
const strength = ref(60)
const batchCount = ref(1)
const aspectKey = ref('same')

const aspectPresets = [
  { key: '1_1', label: '1:1 · 1024²', w: 1024, h: 1024 },
  { key: '16_9', label: '16:9 · 1280×720', w: 1280, h: 720 },
  { key: '9_16', label: '9:16 · 720×1280', w: 720, h: 1280 },
  { key: '4_3', label: '4:3 · 1024×768', w: 1024, h: 768 },
]

const { generating, images, error, generate, imageUrl } = useImageGenerate()

const resultImages = ref<string[]>([])

const providerToApiProvider: Record<string, string> = {
  dalle: 'openai',
  comfyui: 'comfyui',
  midjourney: 'midjourney',
}

function handleFileChange(uploadFile: UploadFile) {
  const file = uploadFile.raw
  if (!file) return
  if (!file.type.startsWith('image/')) {
    ElMessage.warning('请上传图片文件')
    return
  }
  if (file.size > 20 * 1024 * 1024) {
    ElMessage.warning('图片不超过 20MB')
    return
  }
  sourceFile.value = file
  sourceImageUrl.value = URL.createObjectURL(file)
  uploadedRefPath.value = ''
}

function clearSource() {
  sourceFile.value = null
  if (sourceImageUrl.value) {
    URL.revokeObjectURL(sourceImageUrl.value)
  }
  sourceImageUrl.value = ''
  uploadedRefPath.value = ''
}

async function uploadSource(): Promise<string> {
  if (uploadedRefPath.value) return uploadedRefPath.value
  if (!sourceFile.value) throw new Error('未选择图片')
  const res = await api.medpic.uploadReferenceImage(sourceFile.value)
  uploadedRefPath.value = res.data?.path || ''
  return uploadedRefPath.value
}

async function handleGenerate() {
  if (!sourceFile.value) {
    ElMessage.warning('请先上传源图')
    return
  }
  resultImages.value = []

  try {
    const refPath = await uploadSource()

    const modePromptMap: Record<string, string> = {
      style_transfer: `Transform this image to ${targetStyle.value} style.`,
      inpaint: 'Inpaint and modify the selected area.',
      outpaint: 'Extend the image canvas with coherent content.',
      upscale: 'Upscale and enhance image quality and details.',
      free: '',
    }
    const basePrompt = modePromptMap[transformMode.value] || ''
    const userDesc = transformPrompt.value.trim()
    const fullPrompt = [basePrompt, userDesc].filter(Boolean).join(' ')

    const dims = aspectKey.value === 'same'
      ? {}
      : (() => {
          const preset = aspectPresets.find((a) => a.key === aspectKey.value)
          return preset ? { width: preset.w, height: preset.h } : {}
        })()

    const params: ImageGenParams = {
      prompt: fullPrompt || `Image transformation with ${targetStyle.value} style`,
      style: targetStyle.value,
      content_format: 'article',
      image_type: 'illustration',
      batch_count: batchCount.value,
      ...dims,
    }
    params.user_positive_prompt = fullPrompt
    ;(params as any).reference_image = refPath
    ;(params as any).ipadapter_weight = strength.value / 100.0

    const preferred = providerToApiProvider[activeProvider.value]
    await generate(params, undefined, preferred ? { preferredProvider: preferred } : undefined)

    resultImages.value = images.value.map((img) => imageUrl(img.path))
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '变换失败')
  }
}
</script>

<style scoped>
.img2img {
  padding: 2rem;
  max-width: 1100px;
}

.main-layout {
  display: flex;
  gap: 2rem;
  margin-bottom: 1.5rem;
}

.source-panel {
  flex: 0 0 340px;
}

.panel-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: #303133;
  margin-bottom: 0.5rem;
}

.source-upload {
  width: 340px;
  height: 340px;
}

.source-upload :deep(.el-upload) {
  width: 100%;
  height: 100%;
}

.source-upload :deep(.el-upload-dragger) {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  border: 2px dashed #dcdfe6;
  transition: border-color 0.2s;
}

.source-upload :deep(.el-upload-dragger:hover) {
  border-color: var(--el-color-primary);
}

.source-upload.has-image :deep(.el-upload-dragger) {
  border: none;
  padding: 0;
}

.source-preview {
  position: relative;
  width: 100%;
  height: 100%;
}

.source-preview img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  border-radius: 12px;
}

.source-preview .overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.4);
  opacity: 0;
  transition: opacity 0.2s;
  border-radius: 12px;
  color: #fff;
  font-size: 0.9rem;
}

.source-preview:hover .overlay {
  opacity: 1;
}

.upload-placeholder {
  text-align: center;
  color: #909399;
}

.upload-text {
  margin-top: 0.75rem;
  font-size: 0.95rem;
  line-height: 1.6;
}

.upload-hint {
  margin-top: 0.25rem;
  font-size: 0.8rem;
  color: #c0c4cc;
}

.source-actions {
  margin-top: 0.5rem;
  text-align: center;
}

.control-panel {
  flex: 1;
  min-width: 0;
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

.strength-row {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.strength-label {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--el-color-primary);
  min-width: 40px;
  text-align: right;
}

.strength-hint {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: #909399;
  margin-top: 2px;
}

.error-banner {
  margin-bottom: 1rem;
}

.results-section {
  margin-top: 1.5rem;
}

.results-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: #303133;
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
