<template>
  <div class="custom-paint">
    <!-- 顶部工具栏 -->
    <div class="custom-paint__head">
      <div class="custom-paint__head-left">
        <span class="custom-paint__hint">
          自定义绘图：你来描述画意，系统帮你出图。和章节配图分开，可加多张。
          <el-tooltip
            content="自定义绘图与章节配图不绑定章节，但仍会自动套用文章的视觉锚点（角色卡 + 风格锁），保证人物 / 画风一致。"
            placement="top"
          >
            <el-icon style="vertical-align: -2px; margin-left: 0.25em; color: #9ca3af;">
              <InfoFilled />
            </el-icon>
          </el-tooltip>
        </span>
      </div>
      <div class="custom-paint__head-right">
        <el-select
          v-model="defaultStylePresetId"
          size="small"
          placeholder="默认风格"
          clearable
          style="width: 180px;"
          @change="onDefaultStyleChange"
        >
          <el-option
            v-for="p in stylePresets"
            :key="p.id"
            :label="p.display_name || p.name"
            :value="p.id"
          />
        </el-select>
        <el-button size="small" type="primary" :icon="Plus" @click="addSlot" :loading="adding">
          新增绘图
        </el-button>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-if="!slots.length" class="custom-paint__empty">
      还没有自定义绘图。点击「新增绘图」开始。
    </div>

    <!-- 卡片列表 -->
    <div v-else class="custom-paint__list">
      <div
        v-for="(slot, idx) in slots"
        :key="slot.id"
        class="paint-card"
        :class="{ 'paint-card--has-image': !!slot.image_path }"
      >
        <!-- 卡片标题栏 -->
        <div class="paint-card__head">
          <span class="paint-card__title">
            自定义图 #{{ idx + 1 }}
            <el-tag
              v-if="slot.image_status === 'ai_generated'"
              size="small"
              type="success"
              effect="plain"
            >已出图</el-tag>
            <el-tag
              v-else-if="slot.prompt_zh || slot.prompt_en"
              size="small"
              type="warning"
              effect="plain"
            >提示词就绪</el-tag>
          </span>
          <div class="paint-card__head-right">
            <el-popconfirm
              title="确定删除这张自定义绘图？"
              @confirm="deleteSlot(slot)"
            >
              <template #reference>
                <el-button text size="small" type="danger" :icon="Delete">删除</el-button>
              </template>
            </el-popconfirm>
          </div>
        </div>

        <div class="paint-card__body">
          <!-- 左：参数 + 提示词 -->
          <div class="paint-card__main">
            <!-- 画意 -->
            <div class="block">
              <div class="block-head">
                <span class="block-label">画意（自由描述想画什么）</span>
                <div class="block-actions">
                  <el-tooltip
                    content="把简短画意扩写为更具体的画面描述（含构图、光线、人物动作等）"
                    placement="top"
                    :show-after="300"
                  >
                    <el-button
                      text
                      size="small"
                      :icon="MagicStick"
                      :disabled="!intentEdits[slot.id] || (intentEdits[slot.id] || '').trim().length < 4"
                      :loading="!!enrichingMap[slot.id]"
                      @click="openEnrichDialog(slot)"
                    >AI 扩写画意</el-button>
                  </el-tooltip>
                </div>
              </div>
              <el-input
                v-model="intentEdits[slot.id]"
                type="textarea"
                :rows="3"
                placeholder="例：画一个穿白大褂的医生，在诊室中向患者解释心电图，自然光，温暖色调"
                @blur="saveIntent(slot)"
              />
            </div>

            <!-- 风格预设 + 画幅 + 微调 -->
            <div class="paint-card__params">
              <div class="param-row">
                <span class="param-label">风格</span>
                <el-select
                  :model-value="slot.style_preset_id || null"
                  size="small"
                  placeholder="选择风格预设"
                  clearable
                  style="width: 200px;"
                  @change="onStyleChange(slot, $event)"
                >
                  <el-option
                    v-for="p in stylePresets"
                    :key="p.id"
                    :label="p.display_name || p.name"
                    :value="p.id"
                  />
                </el-select>
              </div>
              <div class="param-row param-row--aspect">
                <span class="param-label">画幅</span>
                <el-radio-group
                  :model-value="getAspectValue(slot)"
                  size="small"
                  @update:model-value="(v: any) => onAspectChange(slot, v)"
                >
                  <el-radio-button label="16:9" value="16:9">横版 16:9</el-radio-button>
                  <el-radio-button label="1:1" value="1:1">方形 1:1</el-radio-button>
                  <el-radio-button label="3:4" value="3:4">竖版 3:4</el-radio-button>
                  <el-radio-button label="small" value="small">小图 1:1</el-radio-button>
                </el-radio-group>
                <div class="aspect-preview" :title="aspectPixelText(getAspectValue(slot))">
                  <div
                    class="aspect-preview__box"
                    :class="`aspect-preview__box--${aspectClass(getAspectValue(slot))}`"
                  >
                    <span class="aspect-preview__label">{{ aspectShortLabel(getAspectValue(slot)) }}</span>
                  </div>
                  <span class="aspect-preview__pixels">{{ aspectPixelText(getAspectValue(slot)) }}</span>
                </div>
              </div>

              <!-- 形状构图（可选）-->
              <div class="param-row">
                <span class="param-label">形状</span>
                <el-select
                  :model-value="adjustEdits[slot.id].shape || ''"
                  size="small"
                  style="width: 200px;"
                  @change="(v: any) => onShapeChange(slot, v)"
                >
                  <el-option label="不限定（矩形）" value="" />
                  <el-option label="圆形" value="circle" />
                  <el-option label="椭圆" value="ellipse" />
                  <el-option label="直角三角 · 左上" value="triangle_top_left" />
                  <el-option label="直角三角 · 右上" value="triangle_top_right" />
                  <el-option label="直角三角 · 左下" value="triangle_bottom_left" />
                  <el-option label="直角三角 · 右下" value="triangle_bottom_right" />
                </el-select>
                <div
                  v-if="adjustEdits[slot.id].shape"
                  class="shape-preview"
                  :title="`形状构图：${shapeLabel(adjustEdits[slot.id].shape)}`"
                >
                  <div
                    class="shape-preview__box"
                    :class="`shape-preview__box--${adjustEdits[slot.id].shape}`"
                  ></div>
                  <span class="shape-preview__hint">画面会按此形状构图，矩形画幅不变</span>
                </div>
              </div>

              <div class="param-row param-row--wrap">
                <span class="param-label">微调</span>
                <div class="param-input-wrap">
                  <el-input
                    v-model="adjustEdits[slot.id].composition_zh"
                    size="small"
                    placeholder="构图（如：特写 / 中景 / 全景）"
                    class="param-input"
                    clearable
                    @blur="saveAdjust(slot)"
                    @clear="saveAdjust(slot)"
                  />
                  <div class="param-quick">
                    <el-tag
                      v-for="tag in COMPOSITION_QUICK_TAGS"
                      :key="tag"
                      size="small"
                      effect="plain"
                      class="param-quick__tag"
                      @click="applyQuickCompositionTag(slot, tag)"
                    >{{ tag }}</el-tag>
                  </div>
                </div>
                <el-input
                  v-model="adjustEdits[slot.id].lighting_zh"
                  size="small"
                  placeholder="光线（如：自然光 / 暖光）"
                  class="param-input"
                  clearable
                  @blur="saveAdjust(slot)"
                  @clear="saveAdjust(slot)"
                />
                <el-input
                  v-model="adjustEdits[slot.id].color_zh"
                  size="small"
                  placeholder="色调（如：暖色 / 冷色 / 高饱和）"
                  class="param-input"
                  clearable
                  @blur="saveAdjust(slot)"
                  @clear="saveAdjust(slot)"
                />
              </div>
            </div>

            <!-- 提示词 -->
            <div class="block">
              <div class="block-head">
                <span class="block-label">
                  提示词
                  <span class="prompt-lang-tag">
                    {{ promptLangLabel }}
                  </span>
                </span>
                <div class="block-actions">
                  <el-button
                    text
                    size="small"
                    :icon="Document"
                    :loading="!!promptingMap[slot.id]"
                    :disabled="!intentEdits[slot.id] || (intentEdits[slot.id] || '').trim().length < 4"
                    @click="generatePrompt(slot)"
                  >{{ promptButtonLabel }}</el-button>
                </div>
              </div>
              <div
                v-if="hasVisiblePrompt(slot)"
                :class="showBothPromptCols(slot) ? 'prompt-cols' : 'prompt-single'"
              >
                <div v-if="showZhCol(slot)" class="prompt-col">
                  <div class="prompt-col__head">
                    <span>中文</span>
                    <el-button text size="small" @click="copyText(promptZhEdits[slot.id])">复制</el-button>
                  </div>
                  <el-input
                    v-model="promptZhEdits[slot.id]"
                    type="textarea"
                    :rows="3"
                    :placeholder="providerLang === 'zh' ? '点上方按钮生成中文提示词' : ''"
                    @blur="savePromptZh(slot)"
                  />
                </div>
                <div v-if="showEnCol(slot)" class="prompt-col">
                  <div class="prompt-col__head">
                    <span>英文</span>
                    <el-button text size="small" @click="copyText(promptEnEdits[slot.id])">复制</el-button>
                  </div>
                  <el-input
                    v-model="promptEnEdits[slot.id]"
                    type="textarea"
                    :rows="3"
                    :placeholder="providerLang === 'en' ? '点上方按钮生成英文提示词' : ''"
                    @blur="savePromptEn(slot)"
                  />
                </div>
              </div>
              <div v-else class="prompt-empty">
                {{ promptEmptyHint }}
              </div>
            </div>

            <!-- 反向提示词（折叠） -->
            <div v-if="slot.negative_words && providerNeedsNegative" class="block negative-block">
              <div class="block-head block-head--toggle" @click="toggleNegative(slot.id)">
                <span class="block-label">
                  反向提示词
                  <el-tag size="small" type="info" effect="plain" style="margin-left: 0.4rem;">
                    {{ negativeWordCount(slot.negative_words) }} 词
                  </el-tag>
                </span>
                <div class="block-actions" @click.stop>
                  <el-button text size="small" @click="copyText(slot.negative_words)">复制</el-button>
                  <el-button text size="small" @click="toggleNegative(slot.id)">
                    {{ negativeOpen[slot.id] ? '收起' : '展开' }}
                  </el-button>
                </div>
              </div>
              <div v-if="negativeOpen[slot.id]" class="negative-text">
                {{ slot.negative_words }}
              </div>
            </div>

            <!-- 生成图按钮行 -->
            <div class="paint-card__actions">
              <el-button
                type="primary"
                size="small"
                :icon="Picture"
                :loading="!!generatingMap[slot.id]"
                :disabled="!(promptZhEdits[slot.id] || promptEnEdits[slot.id])"
                @click="generateImage(slot)"
              >生成图片</el-button>
              <el-tooltip
                content="勾选后，会用文章的锚点图作为参考（人物/画风更一致）"
                placement="top"
              >
                <el-checkbox v-model="useStoryboardMap[slot.id]" size="small">
                  与锚点保持高一致
                </el-checkbox>
              </el-tooltip>
            </div>
          </div>

          <!-- 右：图片预览 -->
          <div class="paint-card__preview">
            <div v-if="slot.image_path" class="preview-img-wrap">
              <img
                :src="resolveImageUrl(slot)"
                alt="生成图"
                class="preview-img"
                @click="openPreview(slot)"
              />
              <div class="preview-actions">
                <el-button text size="small" :icon="ZoomIn" @click="openPreview(slot)">放大</el-button>
                <el-button
                  text
                  size="small"
                  type="primary"
                  :loading="!!generatingMap[slot.id]"
                  @click="generateImage(slot)"
                >🔄 重新生成</el-button>
              </div>
            </div>
            <div v-else class="preview-empty">
              <el-icon size="32" color="#d1d5db"><Picture /></el-icon>
              <span>尚未生成</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- AI 扩写弹窗 -->
    <IntentEnrichDialog
      v-model="enrichDialogVisible"
      :initial-intent="enrichDialogIntent"
      :style-name="enrichDialogStyle"
      :section-text="''"
      :topic="topic || ''"
      :section-type="''"
      :aspect-ratio="enrichDialogAspect"
      :auto-enrich="true"
      @apply="onEnrichApplied"
    />

    <!-- 图片预览 -->
    <el-dialog v-model="previewVisible" :title="`自定义图预览`" width="720px" destroy-on-close>
      <img v-if="previewUrl" :src="previewUrl" alt="预览" style="width: 100%; border-radius: 6px;" />
      <div v-if="previewIntent" class="preview-intent">{{ previewIntent }}</div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  InfoFilled, MagicStick, Document, Picture, ZoomIn, Plus, Delete,
} from '@element-plus/icons-vue'
import { api } from '@/api'
import IntentEnrichDialog from './IntentEnrichDialog.vue'

const props = defineProps<{
  articleId: number
  slots: any[]              // 仅 section_id=null 的 slot
  topic?: string | null
  preferredProvider?: string
}>()

const emit = defineEmits<{
  (e: 'slots-changed'): void
}>()

// ── 风格预设 ──────────────────────────────────────────────────
const stylePresets = ref<any[]>([])
const defaultStylePresetId = ref<number | null>(null)

;(async () => {
  try {
    const res = await api.imageIntent.getStylePresets()
    stylePresets.value = (res.data?.items || res.data || []) as any[]
  } catch { /* ignore */ }
})()

function onDefaultStyleChange(_id: number | null) {
  // 仅作为下次"新增绘图"的默认；不影响现有 slot
}

// ── Provider → 语言 / 是否需要负向词（与后端 prompt_engine 保持一致） ──
const PROVIDER_LANG_MAP: Record<string, 'zh' | 'en'> = {
  kling: 'zh', jimeng: 'zh', wenxin: 'zh', wanx: 'zh', tongyi: 'zh',
  moonshot_image: 'zh', gpt_image: 'zh',
  openai: 'en', dalle3: 'en', midjourney: 'en', siliconflow: 'en',
  comfyui_local: 'en', comfyui_cloud: 'en', gemini_image: 'en', pollinations: 'en',
}
const PROVIDER_NEG_MAP: Record<string, boolean> = {
  kling: false, jimeng: false, wenxin: false, wanx: false, tongyi: false,
  moonshot_image: false, gpt_image: false, openai: false, dalle3: false,
  gemini_image: false, pollinations: false,
  midjourney: true, siliconflow: true, comfyui_local: true, comfyui_cloud: true,
}

const providerLang = computed<'zh' | 'en' | 'both'>(() => {
  const p = (props.preferredProvider || '').trim().toLowerCase()
  if (!p) return 'both'
  return PROVIDER_LANG_MAP[p] || 'both'
})

const providerNeedsNegative = computed<boolean>(() => {
  const p = (props.preferredProvider || '').trim().toLowerCase()
  if (!p) return true
  return PROVIDER_NEG_MAP[p] !== false
})

const promptLangLabel = computed(() => {
  if (providerLang.value === 'zh') return '中文（适配国内绘图引擎）'
  if (providerLang.value === 'en') return '英文（适配 SD / FLUX / MJ / DALL-E）'
  return '中 / 英双语'
})
const promptButtonLabel = computed(() => {
  if (providerLang.value === 'zh') return '生成中文'
  if (providerLang.value === 'en') return '生成英文'
  return '生成中英'
})
const promptEmptyHint = computed(() => {
  if (providerLang.value === 'zh') return '填好画意后点「生成中文」生成中文提示词；也可直接点下方「生成图片」一气呵成。'
  if (providerLang.value === 'en') return '填好画意后点「生成英文」生成英文提示词；也可直接点下方「生成图片」一气呵成。'
  return '填好画意后点「生成中英」可单独生成提示词；也可直接点下方「生成图片」一气呵成。'
})

function showZhCol(slot: any): boolean {
  if (providerLang.value === 'en') return false
  if (providerLang.value === 'zh') return true
  return !!promptZhEdits[slot.id]
}
function showEnCol(slot: any): boolean {
  if (providerLang.value === 'zh') return false
  if (providerLang.value === 'en') return true
  return !!promptEnEdits[slot.id]
}
function showBothPromptCols(slot: any): boolean {
  return showZhCol(slot) && showEnCol(slot)
}
function hasVisiblePrompt(slot: any): boolean {
  if (providerLang.value === 'zh') return !!promptZhEdits[slot.id]
  if (providerLang.value === 'en') return !!promptEnEdits[slot.id]
  return !!(promptZhEdits[slot.id] || promptEnEdits[slot.id])
}

// ── 本地编辑 state（按 slot.id） ──
const intentEdits = reactive<Record<number, string>>({})
const promptZhEdits = reactive<Record<number, string>>({})
const promptEnEdits = reactive<Record<number, string>>({})
const adjustEdits = reactive<Record<number, {
  composition_zh: string
  lighting_zh: string
  color_zh: string
  shape: string
}>>({})
const aspectRatioEdits = reactive<Record<number, string>>({})
const promptingMap = reactive<Record<number, boolean>>({})
const generatingMap = reactive<Record<number, boolean>>({})
const enrichingMap = reactive<Record<number, boolean>>({})
const negativeOpen = reactive<Record<number, boolean>>({})
const useStoryboardMap = reactive<Record<number, boolean>>({})
const adding = ref(false)

watch(
  () => props.slots,
  (newSlots) => {
    for (const slot of newSlots || []) {
      const id = slot.id
      if (!(id in intentEdits)) intentEdits[id] = slot.intent_text || ''
      else if ((slot.intent_text || '') !== intentEdits[id] && document.activeElement?.tagName !== 'TEXTAREA') {
        intentEdits[id] = slot.intent_text || ''
      }
      if (!(id in promptZhEdits)) promptZhEdits[id] = slot.prompt_zh || ''
      else if ((slot.prompt_zh || '') !== promptZhEdits[id] && document.activeElement?.tagName !== 'TEXTAREA') {
        promptZhEdits[id] = slot.prompt_zh || ''
      }
      if (!(id in promptEnEdits)) promptEnEdits[id] = slot.prompt_en || ''
      else if ((slot.prompt_en || '') !== promptEnEdits[id] && document.activeElement?.tagName !== 'TEXTAREA') {
        promptEnEdits[id] = slot.prompt_en || ''
      }
      if (!(id in adjustEdits)) {
        const ua = slot.user_adjustments || {}
        adjustEdits[id] = {
          composition_zh: ua.composition_zh || '',
          lighting_zh: ua.lighting_zh || '',
          color_zh: ua.color_zh || '',
          shape: ua.shape || '',
        }
      } else {
        // 后端可能由其他途径更新了 user_adjustments；在用户没在输入时同步过来
        const ua = slot.user_adjustments || {}
        const cur = adjustEdits[id]
        if (!document.activeElement?.matches?.('input,textarea')) {
          if ((ua.shape || '') !== cur.shape) cur.shape = ua.shape || ''
        }
      }
      // 画幅：本地 reactive 状态，避免 :model-value 单向绑定 + 异步保存导致"点了不显示"
      if (!(id in aspectRatioEdits)) {
        aspectRatioEdits[id] = slot.aspect_ratio || '16:9'
      } else if (
        (slot.aspect_ratio || '16:9') !== aspectRatioEdits[id]
        && !document.activeElement?.matches?.('input,textarea')
      ) {
        aspectRatioEdits[id] = slot.aspect_ratio || '16:9'
      }
    }
  },
  { immediate: true, deep: true },
)

function negativeWordCount(text: string | null | undefined): number {
  if (!text) return 0
  return text.split(/[,，;；\s]+/).filter(Boolean).length
}
function toggleNegative(slotId: number) {
  negativeOpen[slotId] = !negativeOpen[slotId]
}

async function copyText(text: string | undefined) {
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制')
  } catch {
    ElMessage.warning('复制失败，请手动复制')
  }
}

function resolveImageUrl(slot: any): string {
  if (!slot.image_path) return ''
  let p = String(slot.image_path)
  if (p.startsWith('/')) {
    const m = p.match(/(?:^|\/)(images\/.+)$/)
    p = m ? m[1] : ''
  }
  if (!p) return ''
  return `/api/v1/imagegen/serve?path=${encodeURIComponent(p)}&t=${slot.updated_at || ''}`
}

// ── CRUD ──────────────────────────────────────────────────────
async function addSlot() {
  if (adding.value) return
  adding.value = true
  try {
    await api.imageIntent.createImageSlot(props.articleId, {
      section_id: null,
      order_num: (props.slots?.length || 0) + 1,
      intent_text: '',
      aspect_ratio: '16:9',
      style_preset_id: defaultStylePresetId.value,
    })
    emit('slots-changed')
    ElMessage.success('已新增一张自定义绘图')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '新增失败')
  } finally {
    adding.value = false
  }
}

async function deleteSlot(slot: any) {
  try {
    await api.imageIntent.deleteImageSlot(slot.id)
    emit('slots-changed')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

async function saveIntent(slot: any) {
  const v = (intentEdits[slot.id] || '').trim()
  if ((slot.intent_text || '') === v) return
  try {
    await api.imageIntent.updateImageSlot(slot.id, { intent_text: v })
    emit('slots-changed')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存画意失败')
  }
}

async function savePromptZh(slot: any) {
  const v = (promptZhEdits[slot.id] || '').trim()
  if ((slot.prompt_zh || '') === v) return
  try {
    await api.imageIntent.updateImageSlot(slot.id, { prompt_zh: v })
    emit('slots-changed')
  } catch { /* ignore */ }
}
async function savePromptEn(slot: any) {
  const v = (promptEnEdits[slot.id] || '').trim()
  if ((slot.prompt_en || '') === v) return
  try {
    await api.imageIntent.updateImageSlot(slot.id, { prompt_en: v })
    emit('slots-changed')
  } catch { /* ignore */ }
}

async function onStyleChange(slot: any, presetId: number | null) {
  // 切换风格时连带清空已生成的中英 prompt，下一次"生成提示词/生图"会按新风格重算
  // 否则会出现"风格已改但生成的图还是旧风格"的体验
  const hadPrompt = !!(slot.prompt_zh || slot.prompt_en)
  try {
    const upd = await api.imageIntent.updateImageSlot(slot.id, {
      style_preset_id: presetId,
      prompt_zh: '',
      prompt_en: '',
    })
    if (upd.data) {
      promptZhEdits[slot.id] = ''
      promptEnEdits[slot.id] = ''
    }
    emit('slots-changed')
    if (hadPrompt) {
      ElMessage.success('已切换风格并清空旧提示词，下次生图会按新风格重算')
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存风格失败')
  }
}

// 直接读最稳定的画幅值（兜底 props.slot 自带的值，避免 reactive Record 注入时机问题）
function getAspectValue(slot: any): string {
  if (slot?.id != null && aspectRatioEdits[slot.id]) return aspectRatioEdits[slot.id]
  return slot?.aspect_ratio || '16:9'
}

// 与后端 contest.py 的 _ASPECT_TO_PIXELS 一一对应
const ASPECT_PIXELS: Record<string, [number, number]> = {
  '16:9':  [1792, 1024],
  '1:1':   [1024, 1024],
  '3:4':   [1024, 1792],
  'small': [512, 512],
}
function aspectClass(v: string): string {
  if (v === '16:9') return 'wide'
  if (v === '3:4')  return 'tall'
  if (v === 'small') return 'small'
  return 'square'
}
function aspectShortLabel(v: string): string {
  return v === 'small' ? '小 1:1' : v
}
function aspectPixelText(v: string): string {
  const px = ASPECT_PIXELS[v]
  return px ? `${px[0]} × ${px[1]} px` : v
}

// ── 形状构图（与后端 SHAPE_COMPOSITION_HINTS 一一对应）──
const SHAPE_LABELS: Record<string, string> = {
  '': '不限定（矩形）',
  circle: '圆形',
  ellipse: '椭圆',
  triangle_top_left: '直角三角 · 左上',
  triangle_top_right: '直角三角 · 右上',
  triangle_bottom_left: '直角三角 · 左下',
  triangle_bottom_right: '直角三角 · 右下',
}
function shapeLabel(s: string | undefined): string {
  return SHAPE_LABELS[s || ''] || (s || '')
}

// ── 构图快捷标签（点一下即填进微调·构图字段）──
const COMPOSITION_QUICK_TAGS = ['特写', '中景', '全景', '俯视', '仰视'] as const

async function onAspectChange(slot: any, aspect: any) {
  const v = String(aspect || '16:9')
  aspectRatioEdits[slot.id] = v
  try {
    await api.imageIntent.updateImageSlot(slot.id, { aspect_ratio: v })
    emit('slots-changed')
  } catch (e: any) {
    aspectRatioEdits[slot.id] = slot.aspect_ratio || '16:9'
    ElMessage.error(e?.response?.data?.detail || '保存画幅失败')
  }
}

async function saveAdjust(slot: any) {
  const a = adjustEdits[slot.id]
  // 合并 / 覆盖现有 user_adjustments，保留服务端可能写入的其他字段
  const old = slot.user_adjustments || {}
  const payload: Record<string, any> = {
    ...old,
    composition_zh: (a.composition_zh || '').trim() || null,
    lighting_zh: (a.lighting_zh || '').trim() || null,
    color_zh: (a.color_zh || '').trim() || null,
    shape: (a.shape || '').trim() || null,
  }
  try {
    await api.imageIntent.updateImageSlot(slot.id, { user_adjustments: payload })
    emit('slots-changed')
  } catch { /* ignore */ }
}

// 形状变化：保存到 user_adjustments，并清空旧 prompt（让下次生成按新形状重算）
async function onShapeChange(slot: any, shape: string) {
  adjustEdits[slot.id].shape = shape || ''
  const old = slot.user_adjustments || {}
  const payload: Record<string, any> = {
    ...old,
    shape: shape || null,
  }
  try {
    const upd = await api.imageIntent.updateImageSlot(slot.id, {
      user_adjustments: payload,
      prompt_zh: '',
      prompt_en: '',
    })
    if (upd.data) {
      promptZhEdits[slot.id] = ''
      promptEnEdits[slot.id] = ''
    }
    emit('slots-changed')
    if (shape) ElMessage.success(`已切换为${shapeLabel(shape)}构图，下次生图按新形状重算`)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存形状失败')
  }
}

function applyQuickCompositionTag(slot: any, tag: string) {
  const cur = (adjustEdits[slot.id]?.composition_zh || '').trim()
  // 已经填了同名标签：再点一下取消（toggle）；否则直接覆盖（这是单选语义而非追加）
  adjustEdits[slot.id].composition_zh = cur === tag ? '' : tag
  void saveAdjust(slot)
}

// ── 提示词 / 生图 ─────────────────────────────────────────────
async function generatePrompt(slot: any) {
  if (promptingMap[slot.id]) return
  // 先把当前画意保存
  await saveIntent(slot)
  promptingMap[slot.id] = true
  try {
    const res = await api.imageIntent.generateSlotPrompt(slot.id, {
      preferred_provider: props.preferredProvider || undefined,
    })
    const newSlot = res.data?.slot || res.data
    if (newSlot) {
      promptZhEdits[slot.id] = newSlot.prompt_zh || ''
      promptEnEdits[slot.id] = newSlot.prompt_en || ''
      emit('slots-changed')
      ElMessage.success('提示词生成完成')
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '生成提示词失败')
  } finally {
    promptingMap[slot.id] = false
  }
}

async function generateImage(slot: any) {
  if (generatingMap[slot.id]) return
  // 若还没提示词，自动先生成
  if (!slot.prompt_zh && !slot.prompt_en && !promptZhEdits[slot.id] && !promptEnEdits[slot.id]) {
    if (!(intentEdits[slot.id] || '').trim()) {
      ElMessage.warning('请先填写画意')
      return
    }
    await generatePrompt(slot)
  }
  generatingMap[slot.id] = true
  try {
    await api.imageIntent.generateSlotImage(slot.id, {
      preferred_provider: props.preferredProvider,
      consistency_strength: useStoryboardMap[slot.id] ? 'high' : 'normal',
    })
    emit('slots-changed')
    ElMessage.success('生成完成')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '生成图失败')
  } finally {
    generatingMap[slot.id] = false
  }
}

// ── AI 扩写画意 ───────────────────────────────────────────────
const enrichDialogVisible = ref(false)
const enrichDialogIntent = ref('')
const enrichDialogStyle = ref('')
const enrichDialogAspect = ref('16:9')
const enrichingSlotId = ref<number | null>(null)

function openEnrichDialog(slot: any) {
  enrichingSlotId.value = slot.id
  enrichDialogIntent.value = intentEdits[slot.id] || ''
  enrichDialogAspect.value = slot.aspect_ratio || '16:9'
  const preset = stylePresets.value.find(p => p.id === slot.style_preset_id)
  enrichDialogStyle.value = preset?.display_name || preset?.name || ''
  enrichDialogVisible.value = true
}

async function onEnrichApplied(text: string, _source: 'original' | 'enriched') {
  const id = enrichingSlotId.value
  if (id == null) return
  intentEdits[id] = text
  const slot = props.slots.find(s => s.id === id)
  if (slot) await saveIntent(slot)
}

// ── 预览 ──────────────────────────────────────────────────────
const previewVisible = ref(false)
const previewUrl = ref('')
const previewIntent = ref('')

function openPreview(slot: any) {
  previewUrl.value = resolveImageUrl(slot)
  previewIntent.value = slot.intent_text || ''
  previewVisible.value = true
}
</script>

<style scoped>
.custom-paint {
  padding: 0.6rem 0.75rem 0.75rem;
}
.custom-paint__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}
.custom-paint__hint {
  font-size: 0.82em;
  color: #6b7280;
  line-height: 1.55;
  display: inline-flex;
  align-items: center;
  gap: 0.25em;
}
.custom-paint__head-right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.custom-paint__empty {
  padding: 1.5em;
  color: #9ca3af;
  text-align: center;
  background: #f9fafb;
  border-radius: 6px;
  font-size: 0.85em;
}

.custom-paint__list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.paint-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}
.paint-card--has-image { border-color: #bbf7d0; }
.paint-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5em 0.75em;
  background: #fafafa;
  border-bottom: 1px solid #e5e7eb;
  font-size: 0.88em;
}
.paint-card__title {
  display: inline-flex;
  align-items: center;
  gap: 0.5em;
  font-weight: 500;
  color: #374151;
}
.paint-card__body {
  display: grid;
  grid-template-columns: 1fr 240px;
  gap: 0.75rem;
  padding: 0.75rem;
}
@media (max-width: 720px) {
  .paint-card__body { grid-template-columns: 1fr; }
}
.paint-card__main {
  display: flex;
  flex-direction: column;
  gap: 0.55em;
  min-width: 0;
}

.paint-card__params {
  display: flex;
  flex-direction: column;
  gap: 0.4em;
  padding: 0.55em 0.7em;
  background: #f9fafb;
  border-radius: 4px;
}
.param-row {
  display: flex;
  align-items: center;
  gap: 0.6em;
  flex-wrap: wrap;
}
.param-row--wrap { gap: 0.4em; }
.param-row--aspect { gap: 0.75em; }

/* ── 画幅预览 ── */
.aspect-preview {
  display: inline-flex;
  align-items: center;
  gap: 0.5em;
  margin-left: 0.25em;
}
.aspect-preview__box {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1.5px solid #2563eb;
  border-radius: 3px;
  background: rgba(37, 99, 235, 0.08);
  color: #1e40af;
  font-size: 0.7em;
  font-weight: 600;
  height: 32px;
  flex-shrink: 0;
  transition: width 0.2s ease, height 0.2s ease;
}
.aspect-preview__box--wide {
  width: 56px;
  height: 32px;
}
.aspect-preview__box--square {
  width: 32px;
  height: 32px;
}
.aspect-preview__box--tall {
  width: 24px;
  height: 32px;
  font-size: 0.62em;
}
.aspect-preview__box--small {
  width: 18px;
  height: 18px;
  font-size: 0.55em;
}
.aspect-preview__label {
  line-height: 1;
  white-space: nowrap;
}
.aspect-preview__pixels {
  font-size: 0.72em;
  color: #6b7280;
  white-space: nowrap;
}

/* ── 形状构图预览 ── */
.shape-preview {
  display: inline-flex;
  align-items: center;
  gap: 0.5em;
  margin-left: 0.25em;
}
.shape-preview__box {
  width: 28px;
  height: 28px;
  background: rgba(37, 99, 235, 0.18);
  border: 1.2px solid #2563eb;
  flex-shrink: 0;
}
.shape-preview__box--circle {
  border-radius: 50%;
}
.shape-preview__box--ellipse {
  width: 36px;
  height: 22px;
  border-radius: 50%;
}
.shape-preview__box--triangle_top_left {
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.25) 50%, transparent 50%);
  border: none;
  outline: 1.2px solid #2563eb;
  outline-offset: -1.2px;
  clip-path: polygon(0 0, 100% 0, 0 100%);
}
.shape-preview__box--triangle_top_right {
  background: rgba(37, 99, 235, 0.25);
  border: none;
  clip-path: polygon(0 0, 100% 0, 100% 100%);
  outline: 1.2px solid #2563eb;
  outline-offset: -1.2px;
}
.shape-preview__box--triangle_bottom_left {
  background: rgba(37, 99, 235, 0.25);
  border: none;
  clip-path: polygon(0 0, 0 100%, 100% 100%);
  outline: 1.2px solid #2563eb;
  outline-offset: -1.2px;
}
.shape-preview__box--triangle_bottom_right {
  background: rgba(37, 99, 235, 0.25);
  border: none;
  clip-path: polygon(100% 0, 100% 100%, 0 100%);
  outline: 1.2px solid #2563eb;
  outline-offset: -1.2px;
}
.shape-preview__hint {
  font-size: 0.7em;
  color: #6b7280;
  white-space: nowrap;
}

/* ── 构图快捷标签（特写/中景/全景/俯视/仰视）── */
.param-input-wrap {
  display: flex;
  flex-direction: column;
  gap: 0.25em;
  flex: 1 1 140px;
  min-width: 120px;
  max-width: 220px;
}
.param-input-wrap .param-input { max-width: none; }
.param-quick {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25em;
}
.param-quick__tag {
  cursor: pointer;
  user-select: none;
}
.param-quick__tag:hover {
  background: #eef2ff !important;
  color: #4338ca !important;
}
.param-label {
  flex-shrink: 0;
  font-size: 0.82em;
  color: #6b7280;
  width: 3em;
}
.param-input {
  flex: 1 1 140px;
  min-width: 120px;
  max-width: 220px;
}

.block {
  display: flex;
  flex-direction: column;
  gap: 0.35em;
}
.block-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5em;
}
.block-label {
  font-size: 0.85em;
  color: #374151;
  font-weight: 500;
  display: inline-flex;
  align-items: center;
}
.block-actions { display: inline-flex; align-items: center; gap: 0.25em; }

.prompt-cols {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5em;
}
@media (max-width: 720px) {
  .prompt-cols { grid-template-columns: 1fr; }
}
.prompt-single {
  display: flex;
  flex-direction: column;
  gap: 0.5em;
}
.prompt-lang-tag {
  margin-left: 0.5em;
  padding: 0.05em 0.5em;
  border-radius: 999px;
  background: #eef2ff;
  color: #4338ca;
  font-size: 0.7em;
  font-weight: 500;
}
.prompt-col {
  display: flex;
  flex-direction: column;
  gap: 0.25em;
}
.prompt-col__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 0.78em;
  color: #6b7280;
}
.prompt-empty {
  padding: 0.6em;
  background: #f9fafb;
  border-radius: 4px;
  font-size: 0.82em;
  color: #6b7280;
  line-height: 1.5;
}

.negative-block { margin-top: 0.4em; }
.block-head--toggle { cursor: pointer; user-select: none; }
.block-head--toggle:hover .block-label { color: #2563eb; }
.negative-text {
  margin-top: 0.4em;
  padding: 0.55em 0.7em;
  background: #fff7ed;
  border: 1px dashed #fed7aa;
  border-radius: 4px;
  color: #9a3412;
  font-size: 0.78em;
  line-height: 1.55;
  word-break: break-word;
  white-space: pre-wrap;
}

.paint-card__actions {
  display: flex;
  align-items: center;
  gap: 0.6em;
  padding-top: 0.35em;
  border-top: 1px dashed #e5e7eb;
  margin-top: 0.25em;
}

.paint-card__preview {
  display: flex;
  align-items: stretch;
  justify-content: center;
}
.preview-img-wrap {
  display: flex;
  flex-direction: column;
  gap: 0.3em;
  width: 100%;
}
.preview-img {
  width: 100%;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
  cursor: zoom-in;
  object-fit: cover;
  max-height: 240px;
}
.preview-actions {
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.25em;
}
.preview-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.4em;
  width: 100%;
  height: 100%;
  min-height: 160px;
  background: #f9fafb;
  border: 1px dashed #d1d5db;
  border-radius: 6px;
  color: #9ca3af;
  font-size: 0.8em;
}

.preview-intent {
  margin-top: 0.7em;
  padding: 0.5em 0.7em;
  background: #f3f4f6;
  border-radius: 4px;
  font-size: 0.82em;
  color: #4b5563;
  line-height: 1.5;
}
</style>
