<template>
  <div class="illustration-workspace" v-loading="loading">
    <!-- 顶部信息栏 -->
    <div class="workspace-header">
      <div class="header-row">
        <el-button text size="small" @click="goBack">
          <el-icon><ArrowLeft /></el-icon>
          返回选择文章
        </el-button>
        <div class="title-area">
          <h2 class="article-title">{{ articleTitleDisplay }}</h2>
          <div class="title-tags">
            <FormatBadge v-if="article?.content_format" :format-id="article.content_format" />
            <PlatformBadge v-if="article?.platform" :platform-id="article.platform" />
            <span v-if="article?.word_count != null" class="word-meta">字数 {{ article.word_count }}</span>
            <el-tag v-if="contestImageSlotCount > 0" size="small" type="success">
              {{ contestImageUploadedCount }}/{{ paintableSectionCount || contestImageSlotCount }} 已上传
            </el-tag>
            <el-tag v-if="customPaintSlotCount > 0" size="small" type="info">
              自定义 {{ customPaintSlotCount }} 张
            </el-tag>
          </div>
        </div>
        <div class="header-actions">
          <el-button size="small" @click="goToWriting">前往写作页</el-button>
          <el-button v-if="hasImageSlotCapability" size="small" type="primary" @click="posterDialogVisible = true">
            海报导出
          </el-button>
        </div>
      </div>
    </div>

    <div v-if="!hasImageSlotCapability && article" class="not-supported">
      <el-empty description="当前文章形式不支持配图管理（仅赛制 / 长文 / 健康手册等支持）" />
    </div>

    <template v-else-if="article">
      <!-- 图示连贯性 -->
      <div v-if="showSeriesVisualPanel" class="block series-visual-block">
        <div class="block-head">
          <h3>图示连贯性（条漫 / 分镜 / 卡片系列）</h3>
        </div>
        <p class="block-hint">
          锁定文案会注入每一张生成图的正向提示词；系列种子基准在 ComfyUI 等支持种子的后端下可区分各格随机性。像素级一致需工作流内参考图 / LoRA。
        </p>
        <el-input
          v-model="visualContinuityDraft"
          type="textarea"
          :rows="4"
          placeholder="例如：同一角色形象与配色、线条风格、禁止写实照片…（中/英均可）"
        />
        <div class="series-seed-row">
          <span class="series-seed-label">系列种子基准（留空则各格随机）</span>
          <el-input-number
            v-model="imageSeriesSeedBaseDraft"
            :min="0"
            :max="2147483647"
            :step="1"
            controls-position="right"
            placeholder="可选"
          />
        </div>
        <div class="series-visual-actions">
          <el-button type="primary" size="small" :loading="savingVisualContinuity" @click="saveVisualContinuity">
            保存到文章
          </el-button>
          <el-button
            v-if="article?.content_format === 'comic_strip'"
            size="small"
            type="success"
            plain
            @click="goToWritingForComicBatch"
          >
            前往写作页运行「条漫一键批量出图」
          </el-button>
          <span v-if="article?.content_format === 'comic_strip'" class="block-hint--inline">
            （需要在编辑器内逐格写回图片，必须在写作页执行）
          </span>
        </div>
      </div>

      <!-- 全章配图概览 -->
      <div class="block">
        <ContestImageOverview
          v-if="paintableSections.length"
          :article-id="articleId"
          :sections="paintableSections"
          :slots="contestImageSlots"
          :active-section-id="null"
          :preferred-provider="slotBatchEngine"
          :topic="article?.topic"
          :visual-anchor="visualAnchor"
          :live-content-json="contentJson"
          :external-image-batch="{
            total: slotBatchTotal,
            done: slotBatchDone,
            fail: slotBatchFail,
            skip: slotBatchSkipped,
            running: slotBatchGenerating,
          }"
          @navigate="onOverviewNavigate"
          @slot-updated="onImageSlotUpdated"
          @slot-removed="onImageSlotRemoved"
          @engine-change="onSlotBatchEngineChange"
          @batch-image="onOverviewBatchImage"
          @visual-anchor-refresh="loadVisualAnchor"
          @visual-anchor-updated="onVisualAnchorUpdated"
        />
        <el-empty v-else description="当前文章尚无可配图的章节正文，请先在写作页生成至少一节正文" />
      </div>

      <!-- 自定义绘图 -->
      <div class="block">
        <div class="block-head">
          <h3>
            自定义绘图
            <el-tooltip
              content="不绑定章节，自由描述要画什么；自动套用文章视觉锚点保持人物/画风一致。"
              placement="top"
            >
              <el-icon style="margin-left: 0.35rem; color: #9ca3af;"><InfoFilled /></el-icon>
            </el-tooltip>
          </h3>
        </div>
        <CustomPaintPanel
          :article-id="articleId"
          :slots="customPaintSlots"
          :topic="article?.topic"
          :preferred-provider="slotBatchEngine"
          @slots-changed="loadContestImageSlots"
        />
      </div>
    </template>

    <PosterExportDialog
      v-model="posterDialogVisible"
      :article-id="articleId"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, InfoFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, ElNotification } from 'element-plus'
import { api, axiosErrorDetail, type VisualAnchor } from '@/api'
import { useSettingsStore } from '@/stores/settings'
import FormatBadge from '@/components/common/FormatBadge.vue'
import PlatformBadge from '@/components/common/PlatformBadge.vue'
import ContestImageOverview from '@/components/contest/ContestImageOverview.vue'
import CustomPaintPanel from '@/components/contest/CustomPaintPanel.vue'
import PosterExportDialog from '@/components/contest/PosterExportDialog.vue'

const FORMATS_WITH_IMAGE_SLOTS = new Set(['contest_article', 'article', 'patient_handbook'])
const META_SECTION_TYPES = new Set([
  'planner', 'series_plan', 'book_plan', 'image_plan', 'script_plan',
  'drama_plan', 'anim_plan', 'handbook_plan', 'poster_brief', 'design_spec',
  'prod_notes', 'filming_notes', 'cast_table', 'char_design',
])
const STORYBOARD_SUPPORTED_PROVIDERS = new Set(['kling', 'jimeng', 'midjourney'])

const route = useRoute()
const router = useRouter()
const settingsStore = useSettingsStore()

const articleId = computed<number | null>(() => {
  const raw = route.params.articleId
  const n = Number(Array.isArray(raw) ? raw[0] : raw)
  return Number.isFinite(n) && n > 0 ? n : null
})

const loading = ref(false)
const article = ref<any>(null)
const contentJson = ref<any>(null)
const articleTitleDisplay = computed(
  () => article.value?.title?.trim() || article.value?.topic || '未命名文章',
)

// ── 图示连贯性 ──
const visualContinuityDraft = ref('')
const imageSeriesSeedBaseDraft = ref<number | null>(null)
const savingVisualContinuity = ref(false)
const showSeriesVisualPanel = computed(() => {
  const cf = article.value?.content_format
  return cf === 'comic_strip' || cf === 'storyboard' || cf === 'card_series'
})

// ── 视觉锚点 ──
const visualAnchor = ref<VisualAnchor | null>(null)

async function loadVisualAnchor() {
  if (!articleId.value) return
  try {
    const res = await api.imageIntent.getVisualAnchor(articleId.value)
    visualAnchor.value = res.data
  } catch {
    visualAnchor.value = null
  }
}

function onVisualAnchorUpdated(a: VisualAnchor) {
  visualAnchor.value = a
}

// ── Slots ──
const contestImageSlots = ref<any[]>([])
const customPaintSlots = computed(() =>
  (contestImageSlots.value || []).filter((s: any) => s.section_id == null),
)
const customPaintSlotCount = computed(() => customPaintSlots.value.length)

const paintableSections = computed(() => {
  const list = article.value?.sections || []
  return [...list]
    .filter((s: any) => s?.has_content && !META_SECTION_TYPES.has(s.section_type || ''))
    .sort((a: any, b: any) => Number(a.order_num || 0) - Number(b.order_num || 0))
})
const paintableSectionCount = computed(() => paintableSections.value.length)

const hasImageSlotCapability = computed(() =>
  FORMATS_WITH_IMAGE_SLOTS.has(article.value?.content_format || ''),
)

const contestImageSlotCount = computed(() => contestImageSlots.value.length)
const contestImageUploadedCount = computed(() =>
  contestImageSlots.value.filter((s: any) => s.image_status === 'uploaded').length,
)

async function loadContestImageSlots() {
  if (!articleId.value || !hasImageSlotCapability.value) return
  try {
    const res = await api.imageIntent.getImageSlots(articleId.value)
    contestImageSlots.value = res.data?.items || []
  } catch { /* ignore */ }
}

function onImageSlotUpdated(slot: any) {
  const idx = contestImageSlots.value.findIndex((s: any) => s.id === slot.id)
  if (idx >= 0) contestImageSlots.value[idx] = slot
  else contestImageSlots.value.push(slot)
}

function onImageSlotRemoved(slotId: number) {
  contestImageSlots.value = contestImageSlots.value.filter((s: any) => s.id !== slotId)
}

function onOverviewNavigate(_sectionId: number) {
  // 配图工作台不切换章节（无编辑器），由子组件自行高亮处理
}

// ── 批量生图引擎 ──
const slotBatchEngine = ref<string>('')
const slotBatchUseEnrich = ref<boolean>(false)
const slotBatchStoryboard = ref<boolean>(false)
const slotBatchGenerating = ref(false)
const slotBatchTotal = ref(0)
const slotBatchDone = ref(0)
const slotBatchFail = ref(0)
const slotBatchSkipped = ref(0)
const slotBatchProviders = ref<Record<string, boolean>>({})
const slotBatchProvidersLoaded = ref(false)

function slotBatchEngineReady(value: string): boolean {
  if (!slotBatchProvidersLoaded.value) return true
  if (!value) return true
  if (value === 'comfyui_local') return !!slotBatchProviders.value.comfyui_local_running
  return !!slotBatchProviders.value[value]
}

function onSlotBatchEngineChange(val: string) {
  slotBatchEngine.value = val
  if (val) settingsStore.setPreferredImageProvider(val)
}

async function loadSlotBatchProviders() {
  try {
    const res = await api.imageIntent.getImageProviders()
    slotBatchProviders.value = res.data?.providers || {}
  } catch {
    slotBatchProviders.value = {}
  } finally {
    slotBatchProvidersLoaded.value = true
  }
}

async function onOverviewBatchImage(opts: { useEnrich: boolean; storyboard: boolean; engine: string }) {
  slotBatchUseEnrich.value = !!opts.useEnrich
  slotBatchStoryboard.value = !!opts.storyboard
  slotBatchEngine.value = opts.engine || ''
  await handleBatchSlotGenerate()
}

function _findSlotForSection(sectionId: number) {
  return contestImageSlots.value.find((s: any) => s.section_id === sectionId) || null
}

function _sectionPlainText(sec: any): string {
  if (!sec) return ''
  if (typeof sec.content_excerpt === 'string' && sec.content_excerpt.trim()) {
    return sec.content_excerpt.trim()
  }
  if (typeof sec.content_text === 'string' && sec.content_text.trim()) return sec.content_text.trim()
  if (sec.content_json) {
    try {
      const doc = typeof sec.content_json === 'string' ? JSON.parse(sec.content_json) : sec.content_json
      if (doc?.content) {
        return doc.content
          .filter((n: any) => n.type === 'paragraph' || n.type === 'heading')
          .map((n: any) => (n.content || []).map((c: any) => c.text || '').join(''))
          .join('\n')
      }
    } catch {
      /* ignore */
    }
  }
  return ''
}

async function _ensureSlotForSection(sectionId: number, intentText: string) {
  const existing = _findSlotForSection(sectionId)
  if (existing) return existing
  try {
    const res = await api.imageIntent.createImageSlot(articleId.value!, {
      section_id: sectionId,
      intent_text: intentText,
      aspect_ratio: '16:9',
    })
    const slot = res.data
    if (slot) contestImageSlots.value.push(slot)
    return slot
  } catch {
    return null
  }
}

async function _generateOneSection(sec: any): Promise<{ ok: boolean; skipped?: boolean; error?: string }> {
  try {
    let slot = _findSlotForSection(sec.id)
    let intentText = slot?.intent_text || ''

    if (!intentText) {
      const sectionText = _sectionPlainText(sec)
      const charLen = sectionText.length
      if (!sectionText) {
        return { ok: false, skipped: true, error: '正文未生成（请先生成本节内容）' }
      }
      if (charLen < 30) {
        return { ok: false, skipped: true, error: `正文过短（${charLen} 字 < 30 字），跳过` }
      }
      try {
        const priorIntents = (contestImageSlots.value || [])
          .filter((s: any) => s.section_id !== sec.id && s.intent_text)
          .map((s: any) => String(s.intent_text || '').trim())
          .filter(Boolean)
          .slice(-6)
        const sgRes = await api.imageIntent.suggestIntent({
          section_text: sectionText,
          topic: article.value?.topic,
          section_type: sec.section_type,
          section_title: sec.title || sec.section_type || '',
          prior_intents: priorIntents,
        })
        const first = sgRes.data?.suggestions?.[0]?.intent
        if (first) intentText = String(first).trim()
      } catch { /* ignore */ }
      if (!intentText) {
        const trimmed = sectionText.replace(/\s+/g, ' ').slice(0, 60)
        intentText = `围绕「${sec.title || sec.section_type || article.value?.topic || '健康科普'}」配一张专业、温和、贴合医学语境的插画：${trimmed}`
      }
    }

    if (!slot) {
      slot = await _ensureSlotForSection(sec.id, intentText)
    } else if (!slot.intent_text) {
      try {
        const upd = await api.imageIntent.updateImageSlot(slot.id, { intent_text: intentText })
        slot = upd.data || { ...slot, intent_text: intentText }
        const idx = contestImageSlots.value.findIndex((s: any) => s.id === slot.id)
        if (idx >= 0) contestImageSlots.value[idx] = slot
      } catch { /* ignore */ }
    }
    if (!slot) return { ok: false, error: '建画位失败' }

    if (slotBatchUseEnrich.value) {
      try {
        const enr = await api.imageIntent.enrichIntent({
          intent_text: slot.intent_text || intentText,
          aspect_ratio: slot.aspect_ratio || '16:9',
          section_text: _sectionPlainText(sec) || sec.content_excerpt || '',
          topic: article.value?.topic || '',
          section_type: sec.section_type || '',
        })
        const data = enr.data
        if (data && data.status === 'ok' && data.enriched_intent) {
          const upd = await api.imageIntent.updateImageSlot(slot.id, {
            intent_text: data.enriched_intent,
            prompt_zh: '',
            prompt_en: '',
          })
          slot = upd.data || { ...slot, intent_text: data.enriched_intent, prompt_zh: '', prompt_en: '' }
          const idx = contestImageSlots.value.findIndex((s: any) => s.id === slot.id)
          if (idx >= 0) contestImageSlots.value[idx] = slot
        }
      } catch { /* enrich 失败不阻断 */ }
    }

    if (!slot.prompt_zh && !slot.prompt_en) {
      const pr = await api.imageIntent.generateSlotPrompt(slot.id, {
        preferred_provider: slotBatchEngine.value || undefined,
      })
      slot = pr.data?.slot || slot
      const idx = contestImageSlots.value.findIndex((s: any) => s.id === slot.id)
      if (idx >= 0) contestImageSlots.value[idx] = slot
    }

    const _genPayload: { preferred_provider?: string; consistency_strength?: 'normal' | 'high' } = {}
    if (slotBatchEngine.value) _genPayload.preferred_provider = slotBatchEngine.value
    if (slotBatchStoryboard.value) _genPayload.consistency_strength = 'high'
    const gen = await api.imageIntent.generateSlotImage(
      slot.id,
      Object.keys(_genPayload).length ? _genPayload : undefined,
    )
    const newSlot = gen.data?.slot
    if (newSlot) {
      const idx = contestImageSlots.value.findIndex((s: any) => s.id === newSlot.id)
      if (idx >= 0) contestImageSlots.value[idx] = newSlot
      else contestImageSlots.value.push(newSlot)
    }
    return { ok: true }
  } catch (e: any) {
    const msg = e?.response?.data?.detail || e?.message || '生成失败'
    return { ok: false, error: String(msg) }
  }
}

async function handleBatchSlotGenerate() {
  if (!articleId.value) return
  const sections = paintableSections.value
  if (!sections.length) {
    ElMessage.warning('当前文章尚无可配图的章节正文，请先生成章节内容')
    return
  }

  await loadContestImageSlots()
  const alreadyPainted = sections.filter((sec: any) => {
    const slot = _findSlotForSection(sec.id)
    return slot?.image_path
  })
  const enrichExtra = slotBatchUseEnrich.value
    ? `\n（已启用 AI 扩写画意，每节额外 +0.6 积分，预计 +${(sections.length * 0.6).toFixed(1)} 积分）`
    : ''
  const storyboardExtra = slotBatchStoryboard.value
    ? '\n🎬 故事板模式：串行 + 强制锚点图，耗时增加 ≈ 30%，但角色一致性最强'
    : ''
  if (alreadyPainted.length > 0) {
    try {
      await ElMessageBox.confirm(
        `已有 ${alreadyPainted.length} 节配图，重新生成将覆盖。是否继续？（未配图的 ${sections.length - alreadyPainted.length} 节也会一起处理）${enrichExtra}${storyboardExtra}`,
        '一键全文配图',
        { confirmButtonText: '全部重新生成', cancelButtonText: '取消', type: 'warning' },
      )
    } catch {
      return
    }
  } else if (slotBatchUseEnrich.value || slotBatchStoryboard.value) {
    try {
      const lines: string[] = []
      if (slotBatchUseEnrich.value) {
        lines.push(`将为 ${sections.length} 节启用 AI 扩写画意，每节额外 +0.6 积分，预计 +${(sections.length * 0.6).toFixed(1)} 积分`)
      }
      if (slotBatchStoryboard.value) {
        lines.push('🎬 故事板模式开启：将串行生图，第一张完成后作为后续所有图的视觉锚点')
      }
      lines.push('是否继续？')
      await ElMessageBox.confirm(
        lines.join('\n'),
        slotBatchStoryboard.value ? '🎬 故事板模式 · 一键全文配图' : 'AI 扩写画意',
        { confirmButtonText: '继续', cancelButtonText: '取消', type: 'info' },
      )
    } catch {
      return
    }
  }

  if (slotBatchStoryboard.value && visualAnchor.value && visualAnchor.value.anchor_source === 'disabled') {
    try {
      const upd = await api.imageIntent.updateVisualAnchor(articleId.value, {
        anchor_source: 'auto_first',
      })
      visualAnchor.value = upd.data
      ElMessage.info('已自动启用「视觉锚点 · 首图自动锁定」以配合故事板模式')
    } catch { /* ignore */ }
  }

  if (!slotBatchProvidersLoaded.value) await loadSlotBatchProviders()
  if (slotBatchEngine.value && !slotBatchEngineReady(slotBatchEngine.value)) {
    ElMessage.warning('所选引擎当前未接入，已切换为自动选择')
    slotBatchEngine.value = ''
  }

  slotBatchGenerating.value = true
  slotBatchTotal.value = sections.length
  slotBatchDone.value = 0
  slotBatchFail.value = 0
  slotBatchSkipped.value = 0

  const CONCURRENCY = slotBatchStoryboard.value ? 1 : 2
  const queue = [...sections]
  const errors: string[] = []
  let _firstImageDone = false

  async function worker() {
    while (queue.length) {
      const sec = queue.shift()
      if (!sec) break
      const r = await _generateOneSection(sec)
      slotBatchDone.value++
      if (!r.ok) {
        if (r.skipped) slotBatchSkipped.value++
        else slotBatchFail.value++
        if (r.error) errors.push(`${sec.title || sec.section_type}：${r.error}`)
      } else if (slotBatchStoryboard.value && !_firstImageDone) {
        _firstImageDone = true
        try { await loadVisualAnchor() } catch { /* ignore */ }
      }
    }
  }

  try {
    await Promise.allSettled(Array.from({ length: CONCURRENCY }, () => worker()))
    await loadContestImageSlots()
    void loadVisualAnchor()
    const ok = slotBatchDone.value - slotBatchFail.value - slotBatchSkipped.value
    if (slotBatchFail.value === 0 && slotBatchSkipped.value === 0) {
      ElNotification({
        title: '全文配图完成',
        message: `成功 ${ok} / ${slotBatchTotal.value} 节，可在「全章配图概览」逐节查看 / 重生 / 替换。`,
        type: 'success',
        duration: 6000,
      })
    } else if (slotBatchFail.value === 0) {
      ElNotification({
        title: '部分章节已跳过',
        message: `完成 ${ok} 节，跳过 ${slotBatchSkipped.value} 节（正文过短或未生成）。`,
        type: 'warning',
        duration: 6000,
      })
      if (errors.length) console.warn('[batch-slot-generate] skipped:', errors)
    } else {
      ElNotification({
        title: '部分章节失败',
        message: `完成 ${ok} 节，失败 ${slotBatchFail.value} 节${slotBatchSkipped.value ? `，跳过 ${slotBatchSkipped.value} 节` : ''}。`,
        type: 'warning',
        duration: 6000,
      })
      if (errors.length) console.warn('[batch-slot-generate] errors:', errors)
    }
  } finally {
    slotBatchGenerating.value = false
  }
}

// ── 图示连贯性保存 ──
async function saveVisualContinuity() {
  if (!articleId.value) return
  savingVisualContinuity.value = true
  try {
    const res = await api.medcomm.patchArticleVisualContinuity(articleId.value, {
      visual_continuity_prompt: visualContinuityDraft.value.trim(),
      image_series_seed_base: imageSeriesSeedBaseDraft.value,
    })
    if (res.data) {
      article.value = { ...article.value, ...res.data }
    }
    ElMessage.success('已保存图示连贯性配置')
  } catch (e: any) {
    ElMessage.error((await axiosErrorDetail(e)) || '保存失败')
  } finally {
    savingVisualContinuity.value = false
  }
}

// ── 加载文章 ──
async function loadArticle() {
  if (!articleId.value) return
  loading.value = true
  try {
    const res = await api.medcomm.getArticle(articleId.value)
    article.value = res.data
    visualContinuityDraft.value = res.data?.visual_continuity_prompt || ''
    imageSeriesSeedBaseDraft.value =
      res.data?.image_series_seed_base != null ? Number(res.data.image_series_seed_base) : null
    const fullDoc = res.data?.full_content_json
    if (fullDoc && Array.isArray(fullDoc.content) && fullDoc.content.length > 0) {
      contentJson.value = fullDoc
    } else {
      contentJson.value = res.data?.content_json || { type: 'doc', content: [] }
    }
    await nextTick()
    void loadContestImageSlots()
    void loadVisualAnchor()
    void loadSlotBatchProviders()
  } catch (e: any) {
    article.value = null
    ElMessage.error((await axiosErrorDetail(e)) || '加载文章失败')
  } finally {
    loading.value = false
  }
}

// ── 海报弹窗 ──
const posterDialogVisible = ref(false)

// ── 跳转 ──
function goBack() {
  router.push('/illustration')
}
function goToWriting() {
  if (articleId.value) router.push(`/medcomm/article/${articleId.value}`)
}
function goToWritingForComicBatch() {
  if (articleId.value) {
    router.push({ path: `/medcomm/article/${articleId.value}`, query: { auto_comic_batch: '1' } })
  }
}

// ── 初始引擎从 settings 读取一次 ──
onMounted(() => {
  const preferred = settingsStore.preferredImageProvider
  if (preferred) slotBatchEngine.value = preferred
  void loadArticle()
})

watch(
  () => articleId.value,
  () => { void loadArticle() },
)
</script>

<style scoped>
.illustration-workspace {
  padding: 1.25rem 1.5rem 2rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  min-height: 100%;
  box-sizing: border-box;
  background: #f7f8fa;
}

.workspace-header {
  background: #fff;
  border-radius: 8px;
  padding: 0.75rem 1rem;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}
.header-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}
.title-area {
  flex: 1;
  min-width: 240px;
}
.article-title {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
  color: #1f2937;
}
.title-tags {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.35rem;
  flex-wrap: wrap;
}
.word-meta {
  font-size: 0.8rem;
  color: #6b7280;
}
.header-actions {
  display: flex;
  gap: 0.5rem;
}

.block {
  background: #fff;
  border-radius: 8px;
  padding: 1rem 1.25rem;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}
.block-head h3 {
  margin: 0 0 0.5rem;
  font-size: 1rem;
  font-weight: 600;
  color: #1f2937;
}
.block-hint {
  margin: 0 0 0.75rem;
  color: #6b7280;
  font-size: 0.85rem;
}
.block-hint--inline {
  color: #9ca3af;
  font-size: 0.8rem;
  margin-left: 0.5rem;
}

.series-visual-block .series-seed-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.75rem;
}
.series-seed-label {
  font-size: 0.85rem;
  color: #4b5563;
}
.series-visual-actions {
  margin-top: 0.75rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.not-supported {
  background: #fff;
  border-radius: 8px;
  padding: 2rem 1rem;
}
</style>
