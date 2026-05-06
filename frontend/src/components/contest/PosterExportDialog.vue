<template>
  <el-dialog
    v-model="visibleProxy"
    title="海报模式 · 选模板 / 预览 / 下载"
    width="92%"
    :style="{ maxWidth: '1280px' }"
    align-center
    destroy-on-close
    @opened="onOpen"
  >
    <div class="poster-dialog">
      <!-- 左侧模板列表 -->
      <aside class="poster-templates" :class="{ loading }">
        <div v-if="loading && !templates.length" class="poster-loading">加载模板…</div>
        <div
          v-for="t in templates"
          :key="t.id"
          class="poster-template-card"
          :class="{ active: t.id === selectedId }"
          :style="{ borderColor: t.id === selectedId ? t.accent_color : undefined }"
          @click="onSelectTemplate(t.id)"
        >
          <div class="poster-template-card__color" :style="{ background: t.accent_color }"></div>
          <div class="poster-template-card__body">
            <div class="poster-template-card__title">{{ t.name }}</div>
            <div class="poster-template-card__desc">{{ t.description }}</div>
            <div class="poster-template-card__hint">
              <el-tag size="small" effect="plain">{{ aspectHintLabel(t.aspect_hint) }}</el-tag>
              <el-tag size="small" effect="plain">{{ coverStyleLabel(t.cover_style) }}</el-tag>
            </div>
          </div>
        </div>
      </aside>

      <!-- 右侧预览 -->
      <main class="poster-preview">
        <div class="poster-preview-toolbar">
          <span class="poster-preview-toolbar__title">{{ editMode ? '内联编辑' : '实时预览' }}</span>
          <span v-if="previewLoading" class="poster-preview-toolbar__hint">加载中…</span>
          <span v-else-if="previewError" class="poster-preview-toolbar__error">{{ previewError }}</span>
          <span v-else-if="editMode && hasOverrides" class="poster-preview-toolbar__hint">
            已修改 {{ overridesSummary }}（仅本次导出生效）
          </span>
          <span class="poster-preview-toolbar__spacer"></span>
          <el-tooltip
            content="进入编辑后可点击标题 / 作者 / 单位 / 各节标题与正文 / 参考文献条目直接修改；图片悬浮可上下移 / 隐藏"
            placement="top" :show-after="200"
          >
            <el-switch
              v-model="editMode"
              size="small"
              active-text="编辑"
              inactive-text="预览"
              :disabled="previewLoading"
              @change="onToggleEditMode"
            />
          </el-tooltip>
          <el-button
            v-if="hasOverrides"
            size="small"
            type="warning"
            text
            @click="resetOverrides"
          >
            重置改动
          </el-button>
          <el-button size="small" :loading="previewLoading" @click="loadPreview">刷新</el-button>
          <el-button size="small" type="success" :loading="downloadingHtml" @click="downloadHtml">下载 HTML</el-button>
          <el-button size="small" type="info" :loading="downloadingDocx" @click="downloadDocx">下载 Word</el-button>
          <el-button size="small" type="primary" :loading="downloadingPdf" @click="downloadPdf">下载 PDF</el-button>
        </div>

        <!-- 作者 / 单位 / 参考文献 选项 -->
        <div class="poster-options">
          <div class="poster-options__row">
            <el-input
              v-model="opts.first_author"
              size="small"
              class="poster-options__input"
              placeholder="第一作者（留空则不显示）"
              clearable
              @change="onOptsChanged"
            />
            <el-input
              v-model="opts.second_author"
              size="small"
              class="poster-options__input"
              placeholder="第二作者"
              clearable
              @change="onOptsChanged"
            />
            <el-input
              v-model="opts.corresponding_author"
              size="small"
              class="poster-options__input"
              placeholder="通讯作者"
              clearable
              @change="onOptsChanged"
            />
            <el-input
              v-model="opts.affiliation"
              size="small"
              class="poster-options__input poster-options__input--wide"
              placeholder="单位 / 机构（如：XX 医院 心血管内科）"
              clearable
              @change="onOptsChanged"
            />
          </div>
          <div class="poster-options__row poster-options__row--toggle">
            <el-checkbox v-model="opts.include_references" @change="onOptsChanged">
              文末附参考文献
            </el-checkbox>
            <span class="poster-options__hint">
              改动作者 / 参考文献后会自动刷新预览；下载 HTML / PDF 时同步带上
            </span>
          </div>
        </div>
        <div class="poster-preview-frame">
          <iframe
            v-if="previewSrc"
            :src="previewSrc"
            sandbox="allow-same-origin allow-scripts"
            class="poster-iframe"
            @load="onIframeLoad"
          />
          <div v-else-if="previewError" class="poster-preview-error">
            <p>{{ previewError }}</p>
            <p v-if="needsChromiumInstall" class="poster-preview-error__hint">
              首次使用需安装 Chromium：在 backend 运行 <code>python -m playwright install chromium</code>
            </p>
          </div>
        </div>
        <div class="poster-preview-tips">
          <div>提示：</div>
          <ul>
            <li>切换到「编辑」模式：标题 / 副标题 / 作者 / 单位 / 章节标题 / 正文 / 参考文献条目可<strong>点击直接修改</strong>；图片悬浮可<strong>上下移 / 隐藏</strong>，下方可<strong>加图说</strong>。</li>
            <li>所有改动<strong>仅本次导出生效</strong>，不会修改原文章 / 原配图。「重置改动」可一键清空。</li>
            <li>HTML 适合保留链接、双击放大；PDF 适合打印 / 投稿（PDF 下载扣 3 积分）。</li>
            <li>题图自动取最早一节的已生成配图；可在「全章配图概览」更换该章配图调整。</li>
          </ul>
        </div>
      </main>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'

const props = defineProps<{
  modelValue: boolean
  articleId: number | null
}>()
const emit = defineEmits<{
  'update:modelValue': [v: boolean]
}>()

const visibleProxy = computed({
  get: () => props.modelValue,
  set: v => emit('update:modelValue', v),
})

const templates = ref<Array<any>>([])
const selectedId = ref<string>('contest_pro')
const loading = ref(false)
const previewLoading = ref(false)
const previewError = ref<string>('')
const needsChromiumInstall = ref(false)
const previewSrc = ref<string>('')
const previewBlobUrl = ref<string>('')
const downloadingPdf = ref(false)
const downloadingHtml = ref(false)
const downloadingDocx = ref(false)

// ── 编辑模式 ──
const editMode = ref(false)

// ── 用户在预览页直接改动的 overrides（仅本次导出生效）──
interface PosterOverrides {
  title?: string
  subtitle?: string
  affiliation?: string
  authors?: Array<{ label: string; name: string }>
  references?: string[]
  section_title_overrides?: Record<string, string>
  section_body_overrides?: Record<string, string>
  section_hidden?: string[]
  slot_overrides?: Record<string, { hidden?: boolean; caption?: string; order?: number }>
  hero_hidden?: boolean
}
const overrides = ref<PosterOverrides>({})

const hasOverrides = computed(() => {
  const o = overrides.value
  return !!(
    o.title || o.subtitle || o.affiliation
    || (o.authors && o.authors.length)
    || (o.references && o.references.length)
    || (o.section_title_overrides && Object.keys(o.section_title_overrides).length)
    || (o.section_body_overrides && Object.keys(o.section_body_overrides).length)
    || (o.section_hidden && o.section_hidden.length)
    || (o.slot_overrides && Object.keys(o.slot_overrides).length)
    || o.hero_hidden
  )
})

const overridesSummary = computed(() => {
  const o = overrides.value
  const parts: string[] = []
  let metaCnt = 0
  if (o.title) metaCnt++
  if (o.subtitle != null) metaCnt++
  if (o.affiliation != null) metaCnt++
  if (o.authors && o.authors.length) metaCnt++
  if (metaCnt) parts.push(`${metaCnt} 项元信息`)
  if (o.section_title_overrides && Object.keys(o.section_title_overrides).length) {
    parts.push(`${Object.keys(o.section_title_overrides).length} 个标题`)
  }
  if (o.section_body_overrides && Object.keys(o.section_body_overrides).length) {
    parts.push(`${Object.keys(o.section_body_overrides).length} 段正文`)
  }
  if (o.references && o.references.length) parts.push('参考文献')
  if (o.slot_overrides && Object.keys(o.slot_overrides).length) {
    parts.push(`${Object.keys(o.slot_overrides).length} 张图`)
  }
  return parts.join(' · ')
})

interface PosterOpts {
  first_author: string
  second_author: string
  corresponding_author: string
  affiliation: string
  include_references: boolean
}
const opts = ref<PosterOpts>({
  first_author: '',
  second_author: '',
  corresponding_author: '',
  affiliation: '',
  include_references: true,
})

/** 将 opts 转成 query / API options，过滤空字符串。 */
function buildOptionsForApi() {
  return {
    first_author: opts.value.first_author?.trim() || undefined,
    second_author: opts.value.second_author?.trim() || undefined,
    corresponding_author: opts.value.corresponding_author?.trim() || undefined,
    affiliation: opts.value.affiliation?.trim() || undefined,
    include_references: opts.value.include_references,
  }
}

function buildPreviewQuery() {
  const o = buildOptionsForApi()
  const parts: string[] = []
  parts.push(`template=${encodeURIComponent(selectedId.value)}`)
  parts.push('format=html')
  if (o.first_author) parts.push(`first_author=${encodeURIComponent(o.first_author)}`)
  if (o.second_author) parts.push(`second_author=${encodeURIComponent(o.second_author)}`)
  if (o.corresponding_author) parts.push(`corresponding_author=${encodeURIComponent(o.corresponding_author)}`)
  if (o.affiliation) parts.push(`affiliation=${encodeURIComponent(o.affiliation)}`)
  parts.push(`include_references=${o.include_references ? 'true' : 'false'}`)
  parts.push(`t=${Date.now()}`)
  return parts.join('&')
}

let optsDebounce: ReturnType<typeof setTimeout> | null = null
function onOptsChanged() {
  // 输入框 change 触发即可（el-input 的 change 是失焦/回车）；这里加个轻微防抖避免连续输入抖动
  if (optsDebounce) clearTimeout(optsDebounce)
  optsDebounce = setTimeout(() => loadPreview(), 120)
}

// ─── 编辑模式：postMessage 接收来自 iframe 的改动 ───
function handlePosterMessage(ev: MessageEvent) {
  const msg = ev.data
  if (!msg || msg.source !== 'poster-editor') return
  switch (msg.kind) {
    case 'ready':
      break
    case 'meta': {
      const f = msg.field as 'title' | 'subtitle' | 'affiliation'
      const v = (msg.value || '').toString().trim()
      ;(overrides.value as any)[f] = v
      break
    }
    case 'authors_bulk': {
      const names: string[] = Array.isArray(msg.names) ? msg.names : []
      // 简化：按位置塞 label = "作者 1 / 2 / 3..."；用户后续可再点 author-name 单独改
      overrides.value.authors = names.map((name, i) => ({
        label: i === 0 ? '第一作者' : (i === 1 ? '第二作者' : `作者 ${i + 1}`),
        name,
      }))
      break
    }
    case 'author_name': {
      const idx = msg.index | 0
      const list = (overrides.value.authors || []).slice()
      while (list.length <= idx) list.push({ label: '作者', name: '' })
      list[idx] = { label: msg.label || list[idx].label || '作者', name: (msg.value || '').toString().trim() }
      overrides.value.authors = list.filter(a => a.name)
      break
    }
    case 'section_title': {
      const st = msg.section_type || ''
      if (!st) break
      const m = { ...(overrides.value.section_title_overrides || {}) }
      m[st] = (msg.value || '').toString()
      overrides.value.section_title_overrides = m
      break
    }
    case 'section_body': {
      const st = msg.section_type || ''
      if (!st) break
      const m = { ...(overrides.value.section_body_overrides || {}) }
      m[st] = (msg.value || '').toString()
      overrides.value.section_body_overrides = m
      break
    }
    case 'slot_caption': {
      const sid = String(msg.slot_id || '')
      if (!sid) break
      const cur = { ...(overrides.value.slot_overrides || {}) }
      cur[sid] = { ...(cur[sid] || {}), caption: (msg.value || '').toString() }
      overrides.value.slot_overrides = cur
      break
    }
    case 'slot_overrides_bulk': {
      const incoming: Record<string, any> = msg.value || {}
      const cur = { ...(overrides.value.slot_overrides || {}) }
      // 合并 hidden / order，但保留已有的 caption
      Object.keys(incoming).forEach(sid => {
        cur[sid] = { ...(cur[sid] || {}), ...incoming[sid] }
      })
      // 把没出现在 incoming 里的 hidden / order 清掉
      Object.keys(cur).forEach(sid => {
        if (!incoming[sid]) {
          if ('hidden' in cur[sid]) delete cur[sid].hidden
          if ('order' in cur[sid]) delete cur[sid].order
          if (Object.keys(cur[sid]).length === 0) delete cur[sid]
        }
      })
      overrides.value.slot_overrides = cur
      break
    }
    case 'reference_item': {
      const idx = msg.index | 0
      const list = (overrides.value.references || []).slice()
      while (list.length <= idx) list.push('')
      list[idx] = (msg.value || '').toString()
      overrides.value.references = list
      break
    }
  }
}

window.addEventListener('message', handlePosterMessage)
onBeforeUnmount(() => {
  window.removeEventListener('message', handlePosterMessage)
  if (previewBlobUrl.value) URL.revokeObjectURL(previewBlobUrl.value)
})

function onToggleEditMode() {
  loadPreview()
}

async function resetOverrides() {
  if (!hasOverrides.value) return
  try {
    await ElMessageBox.confirm(
      '将清空预览页内的所有改动（标题 / 作者 / 单位 / 章节 / 配图调整 / 参考文献），不可撤销。',
      '重置改动',
      { confirmButtonText: '重置', cancelButtonText: '取消', type: 'warning' },
    )
  } catch { return }
  overrides.value = {}
  await loadPreview()
  ElMessage.success('已重置')
}

function aspectHintLabel(h: string) {
  return ({ magazine: '杂志风', card: '卡片风', long: '长图文' } as Record<string, string>)[h] || h
}
function coverStyleLabel(s: string) {
  return ({ hero_image: '题图封面', color_block: '色块封面', minimal: '极简封面' } as Record<string, string>)[s] || s
}

async function loadTemplates() {
  loading.value = true
  try {
    const res = await api.medcomm.listPosterTemplates()
    templates.value = res.data?.items || []
    if (templates.value.length && !templates.value.find(t => t.id === selectedId.value)) {
      selectedId.value = templates.value[0].id
    }
  } catch (e: any) {
    ElMessage.error('加载海报模板失败：' + (e?.message || ''))
  } finally {
    loading.value = false
  }
}

function onSelectTemplate(id: string) {
  if (id === selectedId.value) return
  selectedId.value = id
  loadPreview()
}

function buildPostPayload(format: 'html' | 'pdf') {
  return {
    template: selectedId.value,
    format,
    ...buildOptionsForApi(),
    editable: false,
    overrides: hasOverrides.value ? sanitizeOverrides() : undefined,
  }
}

function sanitizeOverrides() {
  // 把 ref 转普通对象，过滤掉空值
  const o: PosterOverrides = JSON.parse(JSON.stringify(overrides.value))
  if (o.title === '') delete o.title
  if (o.subtitle === '') o.subtitle = ''  // 空字符串表示清空，要保留
  return o
}

async function loadPreview() {
  if (!props.articleId) return
  previewLoading.value = true
  previewError.value = ''
  needsChromiumInstall.value = false
  try {
    // 编辑模式或有 overrides → POST → blob URL（避免 GET URL 太长）
    if (editMode.value || hasOverrides.value) {
      const res = await api.medcomm.renderPosterWithOverrides(props.articleId, {
        template: selectedId.value,
        format: 'html',
        ...buildOptionsForApi(),
        editable: editMode.value,
        overrides: hasOverrides.value ? sanitizeOverrides() : undefined,
      })
      const blob = new Blob([res.data as any], { type: 'text/html;charset=utf-8' })
      if (previewBlobUrl.value) URL.revokeObjectURL(previewBlobUrl.value)
      previewBlobUrl.value = URL.createObjectURL(blob)
      previewSrc.value = previewBlobUrl.value
    } else {
      // 普通预览：GET URL 直接给 iframe（浏览器加载更快）
      previewSrc.value = `/api/v1/medcomm/articles/${props.articleId}/poster?${buildPreviewQuery()}`
    }
  } catch (e: any) {
    previewError.value = e?.response?.data?.detail || e?.message || '预览失败'
    previewLoading.value = false
  }
}

function onIframeLoad() {
  previewLoading.value = false
}

// axios 在 responseType=blob/arraybuffer 时，错误响应里的 data 也是 Blob/ArrayBuffer，
// 直接读 .detail 拿不到任何文本——必须先把它解码成字符串再尝试 JSON.parse。
async function _extractErrorDetail(e: any): Promise<string> {
  const data = e?.response?.data
  if (!data) return e?.message || ''
  // string / object 直接读
  if (typeof data === 'string') {
    try {
      const j = JSON.parse(data)
      return j?.detail || data
    } catch {
      return data
    }
  }
  if (typeof data === 'object' && !(data instanceof Blob) && !(data instanceof ArrayBuffer)) {
    return data?.detail || JSON.stringify(data)
  }
  // Blob / ArrayBuffer：解码成 text 再尝试 JSON
  try {
    let text = ''
    if (data instanceof Blob) {
      text = await data.text()
    } else if (data instanceof ArrayBuffer) {
      text = new TextDecoder('utf-8').decode(data)
    }
    if (!text) return e?.message || ''
    try {
      const j = JSON.parse(text)
      return j?.detail || text
    } catch {
      return text
    }
  } catch {
    return e?.message || ''
  }
}

async function downloadHtml() {
  if (!props.articleId) return
  downloadingHtml.value = true
  try {
    let res
    if (hasOverrides.value) {
      res = await api.medcomm.renderPosterWithOverrides(props.articleId, buildPostPayload('html'))
    } else {
      res = await api.medcomm.renderPoster(props.articleId, selectedId.value, 'html', buildOptionsForApi())
    }
    const blob = new Blob([res.data as any], { type: 'text/html;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `poster_${selectedId.value}${hasOverrides.value ? '_edited' : ''}.html`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('HTML 已下载')
  } catch (e: any) {
    const detail = await _extractErrorDetail(e)
    ElMessage.error('下载失败：' + (detail || '未知错误'))
  } finally {
    downloadingHtml.value = false
  }
}

async function downloadPdf() {
  if (!props.articleId) return
  downloadingPdf.value = true
  try {
    let res
    if (hasOverrides.value) {
      res = await api.medcomm.renderPosterWithOverrides(props.articleId, buildPostPayload('pdf'))
    } else {
      res = await api.medcomm.renderPoster(props.articleId, selectedId.value, 'pdf', buildOptionsForApi())
    }
    const blob = new Blob([res.data as any], { type: 'application/pdf' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `poster_${selectedId.value}${hasOverrides.value ? '_edited' : ''}.pdf`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('PDF 已下载')
  } catch (e: any) {
    const detail = (await _extractErrorDetail(e)) || '下载失败'
    if (/Chromium|playwright|install/i.test(detail)) {
      needsChromiumInstall.value = true
      previewError.value = detail
    }
    ElMessage.error('下载失败：' + detail)
  } finally {
    downloadingPdf.value = false
  }
}

async function downloadDocx() {
  if (!props.articleId) return
  downloadingDocx.value = true
  try {
    let res
    if (hasOverrides.value) {
      res = await api.medcomm.renderPosterWithOverrides(props.articleId, buildPostPayload('docx'))
    } else {
      res = await api.medcomm.renderPoster(props.articleId, selectedId.value, 'docx', buildOptionsForApi())
    }
    const blob = new Blob([res.data as any], {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `poster_${selectedId.value}${hasOverrides.value ? '_edited' : ''}.docx`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('Word 已下载')
  } catch (e: any) {
    const detail = (await _extractErrorDetail(e)) || '下载失败'
    ElMessage.error('下载失败：' + detail)
  } finally {
    downloadingDocx.value = false
  }
}

// 注：编辑模式下不自动重新加载 iframe（会打断用户的输入光标）。
// overrides 累积在内存里，用户切回"预览"模式或点"刷新"或"下载"时才重新渲染。

async function onOpen() {
  if (!templates.value.length) await loadTemplates()
  if (props.articleId) loadPreview()
}

watch(() => props.modelValue, v => {
  if (v) onOpen()
})
</script>

<style scoped>
.poster-dialog {
  display: flex;
  gap: 16px;
  height: 70vh;
  min-height: 500px;
}
.poster-templates {
  flex: 0 0 240px;
  overflow-y: auto;
  padding-right: 4px;
}
.poster-loading {
  padding: 1rem;
  text-align: center;
  color: #9ca3af;
}
.poster-template-card {
  display: flex;
  border: 2px solid #e5e7eb;
  border-radius: 8px;
  margin-bottom: 10px;
  cursor: pointer;
  transition: all 0.18s ease;
  background: #fff;
  overflow: hidden;
}
.poster-template-card:hover {
  border-color: #93c5fd;
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}
.poster-template-card.active {
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.15);
}
.poster-template-card__color {
  flex: 0 0 6px;
}
.poster-template-card__body {
  padding: 10px 12px;
  flex: 1;
  min-width: 0;
}
.poster-template-card__title {
  font-size: 14px;
  font-weight: 600;
  color: #111827;
  margin-bottom: 4px;
}
.poster-template-card__desc {
  font-size: 12px;
  color: #6b7280;
  line-height: 1.45;
  margin-bottom: 8px;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.poster-template-card__hint {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
.poster-preview {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: #f9fafb;
  border-radius: 8px;
  overflow: hidden;
}
.poster-preview-toolbar {
  padding: 10px 14px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.poster-preview-toolbar__title { font-weight: 600; color: #111827; }
.poster-preview-toolbar__hint { color: #6b7280; }
.poster-preview-toolbar__error { color: #dc2626; font-size: 12px; }
.poster-preview-toolbar__spacer { flex: 1; }

.poster-options {
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
  padding: 8px 14px 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.poster-options__row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}
.poster-options__row--toggle {
  font-size: 12px;
  color: #6b7280;
  gap: 12px;
}
.poster-options__input {
  flex: 1 1 160px;
  min-width: 140px;
}
.poster-options__input--wide { flex: 2 1 240px; min-width: 200px; }
.poster-options__hint { font-size: 12px; color: #9ca3af; }
.poster-preview-frame {
  flex: 1;
  background: #fff;
  position: relative;
  overflow: hidden;
}
.poster-iframe {
  width: 100%;
  height: 100%;
  border: none;
  background: #fff;
}
.poster-preview-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #dc2626;
  padding: 2rem;
  text-align: center;
}
.poster-preview-error__hint {
  margin-top: 1em;
  color: #6b7280;
  font-size: 0.9em;
}
.poster-preview-error__hint code {
  background: #f3f4f6;
  padding: 0.15em 0.45em;
  border-radius: 3px;
  font-family: ui-monospace, monospace;
  color: #1f2937;
}
.poster-preview-tips {
  padding: 8px 14px 12px;
  font-size: 12px;
  color: #6b7280;
  background: #fff;
  border-top: 1px solid #e5e7eb;
}
.poster-preview-tips ul {
  margin: 4px 0 0;
  padding-left: 1.4em;
}
.poster-preview-tips li {
  margin: 2px 0;
}
</style>
