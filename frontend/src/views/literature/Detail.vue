<template>
  <div class="literature-detail" v-loading="loading">
    <div class="top-row">
      <el-button link @click="goBack">← 返回文献库</el-button>
    </div>

    <template v-if="paper">
      <h2>{{ paper.title }}</h2>
      <div class="meta-line">
        <span>{{ (paper.authors || []).map((a: any) => a.name).join('; ') || '-' }}</span>
        <span>{{ paper.journal || '-' }}</span>
        <span>{{ paper.year || '-' }}</span>
      </div>
      <div class="meta-line">
        <span v-if="paper.doi">DOI: {{ paper.doi }}</span>
        <span v-if="paper.pmid">PMID: {{ paper.pmid }}</span>
      </div>

      <div class="fulltext-row">
        <el-tag :type="fulltextTagType(paper.fulltext_status)" size="small">
          {{ fulltextLabel(paper.fulltext_status) }}
        </el-tag>
        <el-button
          v-if="paper.fulltext_status !== 'full'"
          type="primary"
          size="small"
          :loading="resolveFulltextLoading"
          style="margin-left: 10px;"
          @click="onResolveFulltext"
        >
          一键补全文
        </el-button>
        <span v-if="paper.fulltext_status === 'pending'" class="muted hint">
          后台解析中，可稍后刷新本页或稍候再试
        </span>
        <span v-if="paper.fulltext_status === 'no_fulltext'" class="muted hint">
          无开放获取全文时请上传 PDF
        </span>
      </div>

      <div class="control-row">
        <el-radio-group v-model="readStatus" @change="saveMeta">
          <el-radio-button value="unread">未读</el-radio-button>
          <el-radio-button value="reading">在读</el-radio-button>
          <el-radio-button value="read">已读</el-radio-button>
        </el-radio-group>
        <span>评分：</span>
        <el-rate v-model="rating" @change="saveMeta" />
        <el-select v-model="collectionId" clearable placeholder="集合" style="width: 180px;" @change="saveMeta">
          <el-option v-for="c in flatCollections" :key="c.id" :label="c.name" :value="c.id" />
        </el-select>
        <el-select v-model="tagIds" multiple clearable placeholder="标签" style="width: 260px;" @change="saveMeta">
          <el-option v-for="t in tags" :key="t.id" :label="t.name" :value="t.id" />
        </el-select>
      </div>

      <el-tabs v-model="tab">
        <el-tab-pane label="摘要" name="abstract">
          <div class="panel-text">{{ paper.abstract || '暂无摘要' }}</div>
        </el-tab-pane>
        <el-tab-pane label="全文" name="fulltext">
          <div v-if="paper.fulltext_status !== 'full'" class="muted" style="padding: 16px 0;">
            全文尚未就绪，请先获取全文后查看。
          </div>
          <div v-else-if="fulltextLoading" v-loading="true" style="min-height: 120px;"></div>
          <div v-else-if="!fulltextChunks.length" class="muted" style="padding: 16px 0;">
            暂无全文分块数据
          </div>
          <div v-else class="paper-viewer">
            <!-- 悬浮目录 -->
            <div class="paper-toc" v-if="fulltextSections.length > 1">
              <div class="toc-title">目录</div>
              <div
                v-for="sec in fulltextSections"
                :key="sec"
                class="toc-item"
                :class="{ active: fulltextActiveSection === sec }"
                @click="scrollToSection(sec)"
              >
                {{ sec || '正文' }}
              </div>
            </div>

            <!-- 论文主体 -->
            <div class="paper-body" ref="paperBodyRef">
              <!-- 标题 -->
              <h1 class="paper-title">{{ paper.title }}</h1>

              <!-- 作者 & 期刊信息 -->
              <div class="paper-authors" v-if="paperAuthorsText">{{ paperAuthorsText }}</div>
              <div class="paper-journal">
                <span v-if="paper.journal">{{ paper.journal }}</span>
                <span v-if="paper.year"> ({{ paper.year }})</span>
                <span v-if="paper.volume"> {{ paper.volume }}<template v-if="paper.issue">({{ paper.issue }})</template></span>
                <span v-if="paper.pages">: {{ paper.pages }}</span>
              </div>
              <div class="paper-ids">
                <span v-if="paper.doi">DOI: {{ paper.doi }}</span>
                <span v-if="paper.pmid">PMID: {{ paper.pmid }}</span>
              </div>

              <hr class="paper-hr" />

              <!-- 摘要 -->
              <template v-if="abstractChunk || paper.abstract">
                <h2 class="section-heading" :ref="(el) => setChunkRef('Abstract', el)">Abstract</h2>
                <p class="paper-abstract">{{ abstractChunk?.chunk_text || paper.abstract }}</p>
              </template>

              <!-- 关键词 -->
              <div class="paper-keywords" v-if="parsedKeywords.length">
                <strong>Keywords: </strong>
                <span>{{ parsedKeywords.join('; ') }}</span>
              </div>

              <hr class="paper-hr" v-if="bodySections.length" />

              <!-- 正文各章节 -->
              <template v-for="group in bodySections" :key="group.section">
                <h2
                  class="section-heading"
                  :ref="(el) => setChunkRef(group.section, el)"
                >
                  {{ group.section || '正文' }}
                </h2>
                <template v-for="chunk in group.chunks" :key="chunk.id">
                  <p class="section-paragraph">{{ chunk.chunk_text }}</p>
                </template>
              </template>

              <!-- 参考文献 -->
              <template v-if="referencesChunk">
                <hr class="paper-hr" />
                <h2 class="section-heading" :ref="(el) => setChunkRef('References', el)">References</h2>
                <div class="paper-references">
                  <div
                    v-for="(ref, idx) in referenceLines"
                    :key="idx"
                    class="ref-item"
                  >
                    <span class="ref-num">{{ idx + 1 }}.</span>
                    <span>{{ ref }}</span>
                  </div>
                </div>
              </template>
            </div>

            <!-- 选中翻译浮动按钮 -->
            <Teleport to="body">
              <div
                v-if="translateBtnVisible"
                class="translate-float-btn"
                :style="{ top: translateBtnPos.y + 'px', left: translateBtnPos.x + 'px' }"
                @mousedown.prevent
                @click="doTranslateSelection"
              >
                翻译
              </div>
            </Teleport>

            <!-- 翻译结果弹层（可拖拽） -->
            <Teleport to="body">
              <div
                v-if="translateResultVisible"
                class="translate-result-popover"
                :style="{ top: translateResultPos.y + 'px', left: translateResultPos.x + 'px' }"
              >
                <div class="translate-result-header" @mousedown="startDragPopover">
                  <span class="translate-result-provider">{{ translateProvider }}</span>
                  <span class="translate-drag-hint">拖拽移动</span>
                  <el-button link size="small" @click="copyTranslation">复制</el-button>
                  <el-button link size="small" type="info" @click="translateResultVisible = false">关闭</el-button>
                </div>
                <div v-if="translateLoading" v-loading="true" style="min-height: 48px;"></div>
                <div v-else class="translate-result-text">{{ translateResultText }}</div>
                <div v-if="translateOriginalText" class="translate-original-text">{{ translateOriginalText }}</div>
              </div>
            </Teleport>
          </div>
        </el-tab-pane>
        <el-tab-pane label="我的笔记" name="notes">
          <el-input v-model="userNotes" type="textarea" :rows="6" placeholder="记录阅读笔记..." @blur="saveNotes" />
        </el-tab-pane>
        <el-tab-pane :label="`标注(${paper.annotation_count ?? 0})`" name="annotations">
          <el-button size="small" @click="openAddAnnotation">添加标注</el-button>
          <el-table :data="annotations" size="small" style="margin-top: 8px;" row-key="id">
            <el-table-column prop="page_number" label="页码" width="80">
              <template #default="{ row }">
                <span :ref="(el) => setAnnRowRef(row.id, el)" class="ann-row-anchor"></span>
                {{ row.page_number }}
              </template>
            </el-table-column>
            <el-table-column prop="annotation_type" label="类型" width="100" />
            <el-table-column prop="content" label="内容" min-width="140" />
            <el-table-column prop="selected_text" label="选中文本" min-width="140" />
            <el-table-column label="" width="180">
              <template #default="{ row }">
                <el-button link type="success" size="small" @click="jumpToAnnotation(row)">跳转</el-button>
                <el-button link type="primary" size="small" @click="onEditFromList(row)">编辑</el-button>
                <el-button link type="danger" size="small" @click="deleteAnnotation(row.id)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="相似文献" name="similar">
          <div class="tag-wrap">
            <el-tag v-for="it in similarPapers" :key="it.id" class="clickable" @click="openOther(it.id)">
              {{ it.title }}{{ it.year ? ` (${it.year})` : '' }}
            </el-tag>
            <span v-if="!similarPapers.length" class="muted">暂无相似文献推荐</span>
          </div>
        </el-tab-pane>
      </el-tabs>

      <el-divider content-position="left">被科普写作引用</el-divider>
      <el-table :data="articleBindings" size="small" empty-text="暂未被文章绑定引用">
        <el-table-column prop="article_title" label="文章" min-width="220" show-overflow-tooltip />
        <el-table-column label="章节" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.section_title || '整篇文章' }}
          </template>
        </el-table-column>
        <el-table-column label="" width="110">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openBindingArticle(row)">定位</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-divider content-position="left">标签建议</el-divider>
      <div class="tag-wrap">
        <el-tag
          v-for="t in tagSuggestions.existing_tags"
          :key="`ex-${t.id}`"
          class="clickable"
          @click="applyExistingTag(t)"
        >
          {{ t.name }}
        </el-tag>
        <el-tag
          v-for="name in tagSuggestions.new_tag_suggestions"
          :key="`new-${name}`"
          type="success"
          class="clickable"
          @click="createAndApplyTag(name)"
        >
          + {{ name }}
        </el-tag>
      </div>

      <el-divider content-position="left">PDF 阅读器</el-divider>
      <div v-if="paper.pdf_path" class="pdf-panel">
        <div class="pdf-toolbar">
          <el-button size="small" @click="prevPage" :disabled="pdfPage <= 1">←页</el-button>
          <span>第 {{ pdfPage }}/{{ pdfPageCount || 1 }} 页</span>
          <el-button size="small" @click="nextPage" :disabled="pdfPage >= pdfPageCount">页→</el-button>
          <el-button size="small" @click="zoomOut">缩放-</el-button>
          <span>{{ Math.round(pdfScale * 100) }}%</span>
          <el-button size="small" @click="zoomIn">缩放+</el-button>
        </div>
        <div class="pdf-canvas-wrap">
          <div ref="pdfPageShellRef" class="pdf-page-shell">
            <canvas ref="pdfCanvasRef"></canvas>
            <div class="pdf-ann-layer">
              <div
                v-for="ann in currentPageAnnotations"
                :key="ann.id"
                :ref="activeAnnId === ann.id ? setActiveAnnBoxRef : undefined"
                class="pdf-ann-box"
                :class="{ active: activeAnnId === ann.id }"
                :style="annotationStyle(ann)"
                @click.stop="focusAnnotation(ann)"
              ></div>
            </div>
            <div ref="pdfTextLayerRef" class="pdf-text-layer" @mouseup="handleTextSelection"></div>
          </div>
        </div>
      </div>
      <div v-else class="muted">暂无 PDF 文件</div>

      <el-divider content-position="left">引用格式</el-divider>
      <div class="cite-row">
        <el-select v-model="citationFormat" style="width: 140px;" @change="loadCitation">
          <el-option label="APA" value="apa" />
          <el-option label="BibTeX" value="bibtex" />
          <el-option label="NLM" value="nlm" />
          <el-option label="GB/T 7714" value="gbt7714" />
        </el-select>
        <el-button @click="copyCitation">复制</el-button>
        <el-button v-if="paper.pdf_path" @click="openPdf">在 PDF 阅读器中打开</el-button>
      </div>
      <div class="panel-text">{{ citationText || '-' }}</div>

      <el-divider content-position="left">附件</el-divider>
      <el-upload
        :show-file-list="false"
        accept=".pdf,.doc,.docx,.xls,.xlsx,.zip,.txt,.md,.csv"
        :before-upload="(file: File) => { uploadAttachment(file); return false }"
      >
        <el-button size="small">上传附件</el-button>
      </el-upload>
      <el-table v-if="paper.attachments?.length" :data="paper.attachments" size="small" style="margin-top: 8px;">
        <el-table-column prop="filename" label="文件名" show-overflow-tooltip />
        <el-table-column prop="file_type" label="类型" width="80" />
        <el-table-column prop="file_size" label="大小" width="90">
          <template #default="{ row }">{{ formatSize(row.file_size) }}</template>
        </el-table-column>
        <el-table-column label="" width="80">
          <template #default="{ row }">
            <el-button type="danger" link size="small" @click="deleteAttachment(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="danger-row">
        <el-button type="danger" plain @click="moveToTrash">删除（→回收站）</el-button>
      </div>

      <el-dialog v-model="showAddAnnotation" :title="editingAnn ? '编辑标注' : '添加标注'" width="420px" append-to-body>
        <el-form label-width="90px">
          <el-form-item label="类型">
            <el-select v-model="annForm.annotation_type" placeholder="选择">
              <el-option label="高亮" value="highlight" />
              <el-option label="批注" value="note" />
              <el-option label="下划线" value="underline" />
              <el-option label="删除线" value="strikethrough" />
            </el-select>
          </el-form-item>
          <el-form-item label="页码">
            <el-input-number v-model="annForm.page_number" :min="1" />
          </el-form-item>
          <el-form-item label="颜色">
            <el-color-picker v-model="annForm.color" />
          </el-form-item>
          <el-form-item label="批注内容">
            <el-input v-model="annForm.content" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item label="选中文本">
            <el-input v-model="annForm.selected_text" />
          </el-form-item>
          <el-form-item label="坐标(rect)">
            <el-input v-model="annForm.rect" placeholder='{"x1":0.1,"y1":0.1,"x2":0.4,"y2":0.16}' />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="showAddAnnotation = false">取消</el-button>
          <el-button type="primary" @click="saveAnnotation">保存</el-button>
        </template>
      </el-dialog>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'
import * as pdfjsLib from 'pdfjs-dist'
import pdfWorkerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorkerUrl

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const paper = ref<any>(null)
const annotations = ref<any[]>([])
const similarPapers = ref<any[]>([])
const articleBindings = ref<any[]>([])
const tagSuggestions = ref<{ existing_tags: any[]; new_tag_suggestions: string[] }>({
  existing_tags: [],
  new_tag_suggestions: [],
})
const tags = ref<any[]>([])
const collections = ref<any[]>([])
const tab = ref('abstract')
const readStatus = ref<'unread' | 'reading' | 'read'>('unread')
const rating = ref(0)
const collectionId = ref<number | null>(null)
const tagIds = ref<number[]>([])
const userNotes = ref('')
const citationFormat = ref<'apa' | 'bibtex' | 'nlm' | 'gbt7714'>('apa')
const citationText = ref('')
const pdfCanvasRef = ref<HTMLCanvasElement | null>(null)
const pdfPageShellRef = ref<HTMLDivElement | null>(null)
const pdfTextLayerRef = ref<HTMLDivElement | null>(null)
const pdfDoc = ref<any>(null)
const pdfPage = ref(1)
const pdfPageCount = ref(0)
const pdfScale = ref(1)
const showAddAnnotation = ref(false)
const editingAnn = ref<any>(null)
const activeAnnId = ref<number | null>(null)
const activeAnnBoxRef = ref<HTMLElement | null>(null)
const annRowRefs = ref<Record<number, HTMLElement>>({})
const annForm = ref({
  annotation_type: 'highlight',
  page_number: 1,
  rect: '{"x1":0.1,"y1":0.1,"x2":0.4,"y2":0.16}',
  color: '#FFD700',
  content: '',
  selected_text: '',
})
const resolveFulltextLoading = ref(false)
const fulltextChunks = ref<any[]>([])
const fulltextLoading = ref(false)
const fulltextActiveSection = ref('')
const chunkSectionRefs = ref<Record<string, HTMLElement>>({})
const paperBodyRef = ref<HTMLElement | null>(null)

const fulltextSections = computed(() => {
  const seen = new Set<string>()
  const result: string[] = []
  for (const c of fulltextChunks.value) {
    const sec = c.section || ''
    if (!seen.has(sec)) {
      seen.add(sec)
      result.push(sec)
    }
  }
  return result
})

const abstractChunk = computed(() =>
  fulltextChunks.value.find((c: any) => c.chunk_type === 'abstract')
)

const referencesChunk = computed(() =>
  fulltextChunks.value.find((c: any) => c.chunk_type === 'references')
)

const referenceLines = computed(() => {
  const text = referencesChunk.value?.chunk_text || ''
  return text.split('\n').map((l: string) => l.trim()).filter((l: string) => l.length > 5)
})

const bodySections = computed(() => {
  const groups: Array<{ section: string; chunks: any[] }> = []
  const excluded = new Set(['abstract', 'references'])
  let current: { section: string; chunks: any[] } | null = null
  for (const c of fulltextChunks.value) {
    if (excluded.has(c.chunk_type)) continue
    const sec = c.section || ''
    if (!current || current.section !== sec) {
      current = { section: sec, chunks: [] }
      groups.push(current)
    }
    current.chunks.push(c)
  }
  return groups
})

function parseAuthorsForDisplay(v: any): string {
  let arr: any[] = []
  if (Array.isArray(v)) arr = v
  else if (typeof v === 'string') {
    try { const p = JSON.parse(v); if (Array.isArray(p)) arr = p } catch { /* ignore */ }
  }
  return arr.map((a: any) => a.name || a).join(', ')
}

const paperAuthorsText = computed(() => parseAuthorsForDisplay(paper.value?.authors))

const parsedKeywords = computed(() => {
  const raw = paper.value?.keywords
  if (!raw) return []
  if (Array.isArray(raw)) return raw
  try {
    const p = JSON.parse(raw)
    if (Array.isArray(p)) return p
  } catch { /* ignore */ }
  return []
})

function setChunkRef(section: string, el: any) {
  if (el) chunkSectionRefs.value[section] = el as HTMLElement
}

function scrollToSection(sec: string) {
  fulltextActiveSection.value = sec
  const el = chunkSectionRefs.value[sec]
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

async function loadChunks() {
  if (!paperId.value || paper.value?.fulltext_status !== 'full') {
    fulltextChunks.value = []
    return
  }
  fulltextLoading.value = true
  try {
    const res = await api.literature.getChunks(paperId.value)
    fulltextChunks.value = (res.data as any)?.items || []
  } catch {
    fulltextChunks.value = []
  } finally {
    fulltextLoading.value = false
  }
}

// ── 选中翻译 ──────────────────────────────────────────────────────────────
const translateBtnVisible = ref(false)
const translateBtnPos = ref({ x: 0, y: 0 })
const translateResultVisible = ref(false)
const translateResultPos = ref({ x: 0, y: 0 })
const translateResultText = ref('')
const translateOriginalText = ref('')
const translateProvider = ref('')
const translateLoading = ref(false)
let _selectedText = ''

function onPaperBodyMouseUp() {
  const sel = window.getSelection()
  const text = sel?.toString().trim() || ''
  if (text.length < 2 || text.length > 15000) {
    translateBtnVisible.value = false
    return
  }
  _selectedText = text
  const range = sel!.getRangeAt(0)
  const rect = range.getBoundingClientRect()
  translateBtnPos.value = {
    x: Math.max(4, rect.left + rect.width / 2 - 24),
    y: Math.max(4, rect.top - 36),
  }
  translateBtnVisible.value = true
}

function onDocumentMouseDown(e: MouseEvent) {
  const target = e.target as HTMLElement
  if (target.closest('.translate-float-btn') || target.closest('.translate-result-popover')) return
  translateBtnVisible.value = false
}

async function doTranslateSelection() {
  if (!_selectedText) return
  translateBtnVisible.value = false
  translateOriginalText.value = _selectedText
  translateResultText.value = ''
  translateProvider.value = ''
  translateLoading.value = true
  translateResultVisible.value = true

  const sel = window.getSelection()
  if (sel && sel.rangeCount) {
    const rect = sel.getRangeAt(0).getBoundingClientRect()
    const popoverWidth = 400
    const popoverHeight = 300
    translateResultPos.value = {
      x: Math.max(8, Math.min(rect.left, window.innerWidth - popoverWidth - 16)),
      y: Math.min(rect.bottom + 8, window.innerHeight - popoverHeight - 16),
    }
  }

  try {
    const res = await api.translate.translate(_selectedText, 'zh', 'en')
    translateResultText.value = res.data?.text || '翻译结果为空'
    translateProvider.value = _providerLabel(res.data?.provider)
  } catch (e: any) {
    translateResultText.value = '翻译失败: ' + (e?.response?.data?.detail || e?.message || '未知错误')
    translateProvider.value = ''
  } finally {
    translateLoading.value = false
  }
}

function _providerLabel(p?: string): string {
  const map: Record<string, string> = {
    deepl: 'DeepL', google: 'Google', azure: 'Azure', llm: '大模型',
  }
  return map[p || ''] || p || ''
}

function copyTranslation() {
  if (!translateResultText.value) return
  navigator.clipboard.writeText(translateResultText.value).then(() => {
    ElMessage.success('已复制译文')
  })
}

let _dragOffset = { x: 0, y: 0 }
function startDragPopover(e: MouseEvent) {
  if ((e.target as HTMLElement).closest('.el-button')) return
  _dragOffset = {
    x: e.clientX - translateResultPos.value.x,
    y: e.clientY - translateResultPos.value.y,
  }
  const onMove = (ev: MouseEvent) => {
    translateResultPos.value = {
      x: Math.max(0, Math.min(ev.clientX - _dragOffset.x, window.innerWidth - 100)),
      y: Math.max(0, Math.min(ev.clientY - _dragOffset.y, window.innerHeight - 60)),
    }
  }
  const onUp = () => {
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
  }
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
}

watch(paperBodyRef, (el) => {
  if (el) {
    el.addEventListener('mouseup', onPaperBodyMouseUp)
    document.addEventListener('mousedown', onDocumentMouseDown)
  }
}, { immediate: true })

const paperId = computed(() => Number(route.params.paperId || 0))
const flatCollections = computed(() => {
  const out: Array<{ id: number; name: string }> = []
  const walk = (nodes: any[]) => {
    for (const n of nodes || []) {
      out.push({ id: n.id, name: n.name })
      if (Array.isArray(n.children)) walk(n.children)
    }
  }
  walk(collections.value)
  return out
})

async function loadBaseData() {
  const [tagRes, collRes] = await Promise.all([
    api.literature.getTags(),
    api.literature.getCollections(),
  ])
  tags.value = Array.isArray(tagRes.data) ? tagRes.data : []
  collections.value = Array.isArray(collRes.data) ? collRes.data : []
}

function fulltextLabel(s: string | undefined) {
  if (s === 'full') return '全文就绪'
  if (s === 'pending') return '全文获取中'
  if (s === 'no_fulltext') return '缺全文'
  return '全文获取中'
}

function fulltextTagType(s: string | undefined) {
  if (s === 'full') return 'success'
  if (s === 'no_fulltext') return 'danger'
  return 'warning'
}

async function onResolveFulltext() {
  if (!paperId.value) return
  resolveFulltextLoading.value = true
  try {
    await api.literature.resolveFulltext(paperId.value)
    ElMessage.success('已排队获取全文，正在轮询状态…')
    for (let i = 0; i < 24; i++) {
      await new Promise((r) => setTimeout(r, 2500))
      const res = await api.literature.getPaper(paperId.value)
      const p = res.data as any
      if (paper.value) {
        paper.value.fulltext_status = p?.fulltext_status
        paper.value.pdf_indexed = p?.pdf_indexed
      }
      const st = p?.fulltext_status
      if (st === 'full') {
        ElMessage.success('全文已就绪')
        await loadDetail()
        return
      }
      if (st === 'no_fulltext' && i >= 3) {
        ElMessage.warning('仍无法自动获取全文，请上传 PDF 或检查 DOI/PMID')
        return
      }
    }
    ElMessage.info('仍在处理或网络较慢，请稍后刷新页面')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '请求失败')
  } finally {
    resolveFulltextLoading.value = false
  }
}

async function loadDetail() {
  if (!paperId.value) return
  loading.value = true
  try {
    const [paperRes, annRes, simRes, tagRes, bindRes] = await Promise.all([
      api.literature.getPaper(paperId.value),
      api.literature.getAnnotations(paperId.value),
      api.literature.recommendSimilar(paperId.value, 5),
      api.literature.suggestTags(paperId.value),
      api.literature.getPaperBindings(paperId.value),
    ])
    paper.value = paperRes.data
    annotations.value = (annRes.data as any)?.items || []
    similarPapers.value = (simRes.data as any)?.items || []
    tagSuggestions.value = {
      existing_tags: (tagRes.data as any)?.existing_tags || [],
      new_tag_suggestions: (tagRes.data as any)?.new_tag_suggestions || [],
    }
    articleBindings.value = (bindRes.data as any)?.items || []
    readStatus.value = paper.value?.read_status || 'unread'
    rating.value = Number(paper.value?.rating || 0)
    collectionId.value = paper.value?.collection_id || null
    tagIds.value = (paper.value?.tags || []).map((t: any) => t.id)
    userNotes.value = String(paper.value?.user_notes || '')
    await loadPdfForCurrentPaper()
    await loadCitation()
    if (tab.value === 'fulltext' || paper.value?.fulltext_status === 'full') {
      await loadChunks()
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载详情失败')
  } finally {
    loading.value = false
  }
}

const currentPageAnnotations = computed(() => {
  return (annotations.value || []).filter((a) => Number(a.page_number) === pdfPage.value)
})

async function saveMeta() {
  if (!paperId.value) return
  try {
    await api.literature.updatePaper(paperId.value, {
      read_status: readStatus.value,
      rating: rating.value,
      collection_id: collectionId.value,
      tag_ids: tagIds.value,
    })
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  }
}

async function applyExistingTag(tag: any) {
  if (!paperId.value) return
  try {
    const merged = Array.from(new Set([...(tagIds.value || []), tag.id])) as number[]
    tagIds.value = merged
    await saveMeta()
    ElMessage.success(`已添加标签：${tag.name}`)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '添加标签失败')
  }
}

async function createAndApplyTag(name: string) {
  if (!paperId.value || !name) return
  try {
    const createRes = await api.literature.createTag({ name, color: '#1D9E75' })
    const createdTag = createRes.data as any
    tagIds.value = Array.from(new Set([...(tagIds.value || []), createdTag.id])) as number[]
    await saveMeta()
    ElMessage.success(`已创建并添加标签：${name}`)
    const tagRes = await api.literature.suggestTags(paperId.value)
    tagSuggestions.value = {
      existing_tags: (tagRes.data as any)?.existing_tags || [],
      new_tag_suggestions: (tagRes.data as any)?.new_tag_suggestions || [],
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '创建标签失败')
  }
}

async function saveNotes() {
  if (!paperId.value) return
  try {
    await api.literature.updatePaper(paperId.value, { user_notes: userNotes.value || '' })
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存笔记失败')
  }
}

async function loadCitation() {
  if (!paperId.value) return
  try {
    const res = await api.literature.exportCitation(paperId.value, citationFormat.value)
    citationText.value = String((res.data as any)?.citation || '')
  } catch {
    citationText.value = ''
  }
}

async function copyCitation() {
  if (!citationText.value) return
  try {
    await navigator.clipboard.writeText(citationText.value)
    ElMessage.success('引用已复制')
  } catch {
    ElMessage.error('复制失败')
  }
}

function openPdf() {
  if (!paper.value?.id) return
  window.open(api.literature.getPdfUrl(paper.value.id), '_blank')
}

async function loadPdfForCurrentPaper() {
  if (!paper.value?.id || !paper.value?.pdf_path) {
    pdfDoc.value = null
    pdfPage.value = 1
    pdfPageCount.value = 0
    return
  }
  try {
    await nextTick()
    const url = api.literature.getPdfUrl(paper.value.id)
    const loadingTask = pdfjsLib.getDocument(url)
    pdfDoc.value = await loadingTask.promise
    pdfPageCount.value = pdfDoc.value.numPages || 0
    pdfPage.value = 1
    await renderPdfPage()
  } catch {
    ElMessage.error('PDF 加载失败')
  }
}

async function renderPdfPage() {
  if (!pdfDoc.value || !pdfCanvasRef.value || !pdfTextLayerRef.value || !pdfPageShellRef.value || pdfPage.value < 1) return
  const page = await pdfDoc.value.getPage(pdfPage.value)
  const viewport = page.getViewport({ scale: pdfScale.value })
  const canvas = pdfCanvasRef.value
  const context = canvas.getContext('2d')
  if (!context) return
  canvas.width = Math.floor(viewport.width)
  canvas.height = Math.floor(viewport.height)
  pdfPageShellRef.value.style.width = `${Math.floor(viewport.width)}px`
  pdfPageShellRef.value.style.height = `${Math.floor(viewport.height)}px`
  await page.render({ canvasContext: context, viewport }).promise
  await renderTextLayer(page, viewport)
}

async function renderTextLayer(page: any, viewport: any) {
  if (!pdfTextLayerRef.value) return
  const layer = pdfTextLayerRef.value
  layer.innerHTML = ''
  const content = await page.getTextContent()
  for (const item of content.items || []) {
    const text = String(item.str ?? '')
    if (!text.trim()) continue
    const tx = (pdfjsLib as any).Util.transform(viewport.transform, item.transform)
    const span = document.createElement('span')
    span.textContent = text
    span.style.left = `${tx[4]}px`
    span.style.top = `${tx[5] - item.height}px`
    span.style.fontSize = `${item.height}px`
    span.style.fontFamily = item.fontName || 'sans-serif'
    layer.appendChild(span)
  }
}

function handleTextSelection() {
  const layer = pdfTextLayerRef.value
  if (!layer) return
  const sel = window.getSelection()
  if (!sel || sel.rangeCount === 0 || sel.isCollapsed) return
  const text = sel.toString().trim()
  if (!text) return
  const range = sel.getRangeAt(0)
  const rect = range.getBoundingClientRect()
  const layerRect = layer.getBoundingClientRect()
  if (rect.width <= 0 || rect.height <= 0 || layerRect.width <= 0 || layerRect.height <= 0) return

  const norm = {
    x1: Number(((rect.left - layerRect.left) / layerRect.width).toFixed(4)),
    y1: Number(((rect.top - layerRect.top) / layerRect.height).toFixed(4)),
    x2: Number(((rect.right - layerRect.left) / layerRect.width).toFixed(4)),
    y2: Number(((rect.bottom - layerRect.top) / layerRect.height).toFixed(4)),
  }

  annForm.value.selected_text = text
  annForm.value.page_number = pdfPage.value
  annForm.value.rect = JSON.stringify(norm)
  showAddAnnotation.value = true
  sel.removeAllRanges()
}

async function prevPage() {
  if (pdfPage.value <= 1) return
  pdfPage.value -= 1
  await renderPdfPage()
}

async function nextPage() {
  if (pdfPage.value >= pdfPageCount.value) return
  pdfPage.value += 1
  await renderPdfPage()
}

async function zoomIn() {
  pdfScale.value = Math.min(2, Number((pdfScale.value + 0.1).toFixed(2)))
  await renderPdfPage()
}

async function zoomOut() {
  pdfScale.value = Math.max(0.5, Number((pdfScale.value - 0.1).toFixed(2)))
  await renderPdfPage()
}

function annotationStyle(ann: any) {
  const rect = normalizeRect(ann?.rect)
  const width = Math.max(0, rect.x2 - rect.x1)
  const height = Math.max(0, rect.y2 - rect.y1)
  const color = ann?.color || '#FFD700'
  return {
    left: `${Math.max(0, rect.x1) * 100}%`,
    top: `${Math.max(0, rect.y1) * 100}%`,
    width: `${Math.min(1, width) * 100}%`,
    height: `${Math.min(1, height) * 100}%`,
    borderColor: color,
    backgroundColor: hexToRgba(color, 0.18),
  }
}

function normalizeRect(raw: any) {
  let r = raw
  if (typeof raw === 'string') {
    try { r = JSON.parse(raw) } catch { r = null }
  }
  const x1 = Number(r?.x1); const y1 = Number(r?.y1); const x2 = Number(r?.x2); const y2 = Number(r?.y2)
  if ([x1, y1, x2, y2].some((v) => Number.isNaN(v))) return { x1: 0, y1: 0, x2: 0, y2: 0 }
  return { x1: Math.min(Math.max(x1, 0), 1), y1: Math.min(Math.max(y1, 0), 1), x2: Math.min(Math.max(x2, 0), 1), y2: Math.min(Math.max(y2, 0), 1) }
}

function hexToRgba(hex: string, alpha: number) {
  const v = (hex || '').replace('#', '').trim()
  if (![3, 6].includes(v.length)) return `rgba(255, 215, 0, ${alpha})`
  const full = v.length === 3 ? v.split('').map((c) => c + c).join('') : v
  const n = Number.parseInt(full, 16)
  if (Number.isNaN(n)) return `rgba(255, 215, 0, ${alpha})`
  const r = (n >> 16) & 255
  const g = (n >> 8) & 255
  const b = n & 255
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

async function uploadAttachment(file: File) {
  if (!paper.value?.id) return
  const form = new FormData()
  form.append('file', file)
  try {
    await api.literature.uploadAttachment(paper.value.id, form)
    ElMessage.success('上传成功')
    await loadDetail()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '上传失败')
  }
}

async function deleteAttachment(attId: number) {
  if (!paper.value?.id) return
  try {
    await ElMessageBox.confirm('确定删除该附件？')
  } catch {
    return
  }
  try {
    await api.literature.deleteAttachment(paper.value.id, attId)
    ElMessage.success('已删除')
    await loadDetail()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

function openAddAnnotation() {
  editingAnn.value = null
  annForm.value = {
    annotation_type: 'highlight',
    page_number: pdfPage.value || 1,
    rect: '{"x1":0.1,"y1":0.1,"x2":0.4,"y2":0.16}',
    color: '#FFD700',
    content: '',
    selected_text: '',
  }
  showAddAnnotation.value = true
}

function editAnnotation(row: any) {
  editingAnn.value = row
  annForm.value = {
    annotation_type: row.annotation_type,
    page_number: row.page_number,
    rect: typeof row.rect === 'string' ? row.rect : JSON.stringify(row.rect || { x1: 0.1, y1: 0.1, x2: 0.4, y2: 0.16 }),
    color: row.color || '#FFD700',
    content: row.content || '',
    selected_text: row.selected_text || '',
  }
  showAddAnnotation.value = true
}

function parseRectInput(rectRaw: string) {
  try {
    const parsed = JSON.parse(rectRaw || '{}')
    const keys = ['x1', 'y1', 'x2', 'y2']
    const ok = keys.every((k) => typeof parsed[k] === 'number')
    if (!ok) throw new Error('invalid rect')
    return parsed
  } catch {
    throw new Error('坐标格式应为 JSON，例如 {"x1":0.1,"y1":0.1,"x2":0.4,"y2":0.16}')
  }
}

async function saveAnnotation() {
  if (!paperId.value) return
  try {
    const rectPayload = parseRectInput(annForm.value.rect)
    if (editingAnn.value) {
      await api.literature.updateAnnotation(paperId.value, editingAnn.value.id, {
        annotation_type: annForm.value.annotation_type,
        page_number: annForm.value.page_number,
        rect: rectPayload,
        color: annForm.value.color,
        content: annForm.value.content,
        selected_text: annForm.value.selected_text,
      })
      ElMessage.success('已更新')
    } else {
      await api.literature.createAnnotation(paperId.value, {
        annotation_type: annForm.value.annotation_type,
        page_number: annForm.value.page_number,
        rect: rectPayload,
        color: annForm.value.color,
        content: annForm.value.content,
        selected_text: annForm.value.selected_text,
      })
      ElMessage.success('已添加')
    }
    showAddAnnotation.value = false
    editingAnn.value = null
    await loadDetail()
  } catch (e: any) {
    ElMessage.error(e?.message || e?.response?.data?.detail || '保存失败')
  }
}

async function deleteAnnotation(annId: number) {
  if (!paperId.value) return
  try {
    await ElMessageBox.confirm('确定删除该标注？')
  } catch {
    return
  }
  try {
    await api.literature.deleteAnnotation(paperId.value, annId)
    ElMessage.success('已删除')
    await loadDetail()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

async function jumpToAnnotation(row: any) {
  const pageNum = Number(row?.page_number || 1)
  if (!pdfDoc.value || pageNum < 1 || pageNum > pdfPageCount.value) {
    ElMessage.warning('无法跳转到该标注页')
    return
  }
  activeAnnId.value = Number(row?.id ?? 0) || null
  pdfPage.value = pageNum
  await renderPdfPage()
  await nextTick()
  activeAnnBoxRef.value?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
}

async function onEditFromList(row: any) {
  if (paper.value?.pdf_path) await jumpToAnnotation(row)
  editAnnotation(row)
}

function focusAnnotation(ann: any) {
  activeAnnId.value = Number(ann?.id ?? 0) || null
  const el = annRowRefs.value[ann?.id]
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  editAnnotation(ann)
}

function setActiveAnnBoxRef(el: any) {
  activeAnnBoxRef.value = el as HTMLElement
}

function setAnnRowRef(id: number, el: any) {
  if (el) annRowRefs.value[id] = el as HTMLElement
  else delete annRowRefs.value[id]
}

async function moveToTrash() {
  if (!paper.value?.id) return
  try {
    await ElMessageBox.confirm('确定将该文献移入回收站？')
  } catch {
    return
  }
  try {
    await api.literature.deletePaper(paper.value.id)
    ElMessage.success('已移入回收站')
    await router.replace({ name: 'literature' })
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

async function openOther(id: number) {
  await router.replace({ name: 'literature-paper', params: { paperId: id } })
}

function openBindingArticle(row: any) {
  const articleId = Number(row?.article_id || 0)
  if (!articleId) return
  const query = row?.section_id ? { section_id: String(row.section_id) } : undefined
  router.push({ name: 'article', params: { id: articleId }, query })
}

function goBack() {
  router.push({ name: 'literature' })
}

function formatSize(n: number) {
  if (!n) return '-'
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

watch(() => route.params.paperId, loadDetail)
watch(tab, (v) => {
  if (v === 'fulltext' && !fulltextChunks.value.length) loadChunks()
})

onMounted(async () => {
  await loadBaseData()
  await loadDetail()
})

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onDocumentMouseDown)
  if (paperBodyRef.value) {
    paperBodyRef.value.removeEventListener('mouseup', onPaperBodyMouseUp)
  }
})
</script>

<style scoped>
.literature-detail { padding: 1.25rem; }
.top-row { margin-bottom: 0.5rem; }
.meta-line { display: flex; gap: 16px; color: var(--el-text-color-secondary); margin: 4px 0; flex-wrap: wrap; }
.fulltext-row { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin: 10px 0 12px; }
.fulltext-row .hint { margin-left: 6px; font-size: 13px; }
.control-row { display: flex; align-items: center; gap: 8px; margin: 12px 0; flex-wrap: wrap; }
.panel-text { line-height: 1.7; background: var(--el-fill-color-light); border-radius: 6px; padding: 10px; }
.tag-wrap { display: flex; gap: 8px; flex-wrap: wrap; }
.clickable { cursor: pointer; }
.muted { color: var(--el-text-color-placeholder); }
.cite-row { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
.danger-row { margin-top: 12px; display: flex; justify-content: flex-end; }
.pdf-panel { border: 1px solid var(--el-border-color); border-radius: 6px; margin-top: 0.5rem; }
.pdf-toolbar { display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem; border-bottom: 1px solid var(--el-border-color); }
.pdf-canvas-wrap { max-height: 520px; overflow: auto; background: #f6f7f9; padding: 0.75rem; display: flex; justify-content: center; }
.pdf-canvas-wrap canvas { background: #fff; box-shadow: 0 1px 6px rgba(0, 0, 0, 0.12); }
.pdf-page-shell { position: relative; }
.pdf-ann-layer { position: absolute; inset: 0; pointer-events: none; z-index: 2; }
.pdf-ann-box {
  position: absolute;
  border: 2px solid #ffd700;
  border-radius: 3px;
  box-sizing: border-box;
  pointer-events: auto;
  cursor: pointer;
}
.pdf-ann-box.active {
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.45);
  animation: ann-flash 0.5s ease-out;
}
@keyframes ann-flash {
  0% { box-shadow: 0 0 0 4px rgba(64, 158, 255, 0.7); }
  100% { box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.45); }
}
.ann-row-anchor { display: inline-block; width: 0; height: 0; overflow: hidden; vertical-align: middle; }
.pdf-text-layer { position: absolute; inset: 0; user-select: text; z-index: 3; }
.pdf-text-layer span { position: absolute; color: transparent; white-space: pre; transform-origin: 0 0; }
.pdf-text-layer ::selection { background: rgba(80, 160, 255, 0.35); }
/* --- 论文阅读器 --- */
.paper-viewer {
  display: flex; gap: 0; position: relative;
  max-height: 75vh; overflow: hidden;
}
.paper-toc {
  width: 160px; min-width: 140px; flex-shrink: 0;
  border-right: 1px solid var(--el-border-color-lighter);
  overflow-y: auto; padding: 12px 8px; position: sticky; top: 0;
  max-height: 75vh;
}
.toc-title { font-size: 13px; font-weight: 600; margin-bottom: 8px; color: var(--el-text-color-primary); }
.toc-item {
  font-size: 12px; line-height: 1.5; padding: 4px 8px; border-radius: 4px;
  cursor: pointer; color: var(--el-text-color-regular); margin-bottom: 2px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  transition: background 0.15s, color 0.15s;
}
.toc-item:hover { background: var(--el-fill-color); }
.toc-item.active { background: var(--el-color-primary-light-9); color: var(--el-color-primary); font-weight: 500; }

.paper-body {
  flex: 1; overflow-y: auto; padding: 24px 32px; max-height: 75vh;
  font-family: 'Georgia', 'Times New Roman', 'Noto Serif SC', serif;
  color: var(--el-text-color-primary); line-height: 1.8;
}
.paper-title {
  font-size: 22px; font-weight: 700; text-align: center; margin: 0 0 12px;
  line-height: 1.4; color: var(--el-text-color-primary);
}
.paper-authors {
  text-align: center; font-size: 14px; color: var(--el-text-color-regular);
  margin-bottom: 4px;
}
.paper-journal {
  text-align: center; font-size: 13px; color: var(--el-text-color-secondary);
  font-style: italic; margin-bottom: 4px;
}
.paper-ids {
  text-align: center; font-size: 12px; color: var(--el-text-color-placeholder);
  display: flex; justify-content: center; gap: 16px; margin-bottom: 8px;
}
.paper-hr {
  border: none; border-top: 1px solid var(--el-border-color-lighter);
  margin: 16px 0;
}
.section-heading {
  font-size: 17px; font-weight: 700; margin: 20px 0 10px;
  color: var(--el-text-color-primary); border-bottom: 2px solid var(--el-color-primary-light-7);
  padding-bottom: 4px;
}
.paper-abstract {
  font-size: 14px; line-height: 1.9; text-align: justify;
  background: var(--el-fill-color-light); border-left: 3px solid var(--el-color-primary-light-5);
  padding: 12px 16px; border-radius: 0 6px 6px 0; margin: 0 0 12px;
}
.paper-keywords {
  font-size: 13px; color: var(--el-text-color-secondary); margin: 8px 0 12px;
}
.paper-keywords strong { color: var(--el-text-color-primary); }
.section-paragraph {
  font-size: 14px; line-height: 1.9; text-align: justify;
  margin: 0 0 10px; text-indent: 2em;
}
.paper-references { font-size: 13px; line-height: 1.7; }
.ref-item { display: flex; gap: 6px; margin-bottom: 4px; }
.ref-num { flex-shrink: 0; color: var(--el-text-color-secondary); min-width: 28px; text-align: right; }
</style>

<style>
.translate-float-btn {
  position: fixed;
  z-index: 9999;
  background: var(--el-color-primary);
  color: #fff;
  padding: 4px 14px;
  border-radius: 4px;
  font-size: 13px;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.18);
  user-select: none;
  white-space: nowrap;
  transition: opacity 0.15s;
}
.translate-float-btn:hover {
  opacity: 0.9;
}

.translate-result-popover {
  position: fixed;
  z-index: 9998;
  width: 400px;
  max-width: calc(100vw - 32px);
  max-height: 400px;
  overflow-y: auto;
  background: #fff;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.14);
  padding: 12px 16px;
  font-size: 14px;
  line-height: 1.7;
}
.translate-result-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  padding-bottom: 6px;
  cursor: grab;
  user-select: none;
}
.translate-result-header:active {
  cursor: grabbing;
}
.translate-drag-hint {
  font-size: 11px;
  color: var(--el-text-color-placeholder);
}
.translate-result-provider {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  background: var(--el-fill-color);
  padding: 2px 8px;
  border-radius: 4px;
  flex-shrink: 0;
}
.translate-result-header .el-button {
  margin-left: auto;
}
.translate-result-header .el-button + .el-button {
  margin-left: 0;
}
.translate-result-text {
  color: var(--el-text-color-primary);
  font-size: 14px;
  line-height: 1.8;
}
.translate-original-text {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px dashed var(--el-border-color-lighter);
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.6;
  max-height: 120px;
  overflow-y: auto;
}
</style>
