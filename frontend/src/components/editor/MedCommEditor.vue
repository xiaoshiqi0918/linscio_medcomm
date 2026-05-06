<template>
  <div class="medcomm-editor" :data-format="contentFormat || ''">
    <EditorToolbar :editor="editor || null" :content-format="contentFormat" />
    <editor-content :editor="editor" class="prose" />
    <bubble-menu
      v-if="editor"
      :editor="editor"
      plugin-key="corpusCaptureBubble"
      :should-show="corpusBubbleShouldShow"
      :tippy-options="corpusBubbleTippy"
      class="corpus-bubble-root"
    >
      <div class="corpus-float-bar" @mousedown.prevent>
        <div class="corpus-float-preview" :title="selectionPreviewFull">
          <span class="corpus-float-tag">收录</span>{{ selectionPreviewShort }}
        </div>
        <div class="corpus-float-row">
          <el-select v-model="captureKind" size="small" class="corpus-float-select">
            <el-option label="倾向" value="prefer" />
            <el-option label="避免" value="avoid" />
            <el-option label="备忘" value="note" />
          </el-select>
          <el-input
            v-model="captureExtra"
            size="small"
            placeholder="说明（可选）"
            class="corpus-float-input"
          />
          <el-button
            type="primary"
            size="small"
            :loading="captureLoading"
            class="corpus-float-submit"
            @click="submitCorpusCapture"
          >收录</el-button>
        </div>
      </div>
    </bubble-menu>
  </div>
</template>

<script setup lang="ts">
import { useEditor, EditorContent, BubbleMenu } from '@tiptap/vue-3'
import { watch, onBeforeUnmount, computed, nextTick, ref } from 'vue'
import type { Node as PMNode } from 'prosemirror-model'
import { useFormatEditor } from '@/composables/useFormatEditor'
import { MedCommImageContext } from '@/components/editor/extensions/MedCommImageContext'
import EditorToolbar from './EditorToolbar.vue'
import { ElMessage } from 'element-plus'
import { api, axiosErrorDetail } from '@/api'
import { useArticleStore } from '@/stores/article'
import 'tippy.js/dist/tippy.css'

const articleStore = useArticleStore()

let _selectionTimer: ReturnType<typeof setTimeout> | null = null
function syncSelectionToStore(ed: any) {
  if (_selectionTimer) clearTimeout(_selectionTimer)
  _selectionTimer = setTimeout(() => {
    if (!ed) { articleStore.setEditorSelection(null); return }
    const { from, to, empty } = ed.state.selection
    if (empty) { articleStore.setEditorSelection(null); return }
    const text = ed.state.doc.textBetween(from, to, '\n').trim()
    if (!text) { articleStore.setEditorSelection(null); return }
    const docSize = ed.state.doc.content.size
    const beforeStart = Math.max(0, from - 500)
    const afterEnd = Math.min(docSize, to + 500)
    const contextBefore = ed.state.doc.textBetween(beforeStart, from, '\n').trim()
    const contextAfter = ed.state.doc.textBetween(to, afterEnd, '\n').trim()
    articleStore.setEditorSelection({ text, from, to, contextBefore, contextAfter })
  }, 150)
}

const CORPUS_SELECTION_MAX = 500

const captureKind = ref<'prefer' | 'avoid' | 'note'>('prefer')
const captureExtra = ref('')
const captureLoading = ref(false)
const selectionPreviewFull = ref('')
const selectionPreviewShort = ref('')

const corpusBubbleTippy = {
  duration: [120, 80],
  placement: 'top' as const,
  maxWidth: 320,
  appendTo: () => document.body,
  zIndex: 5000,
  interactive: true,
}

function corpusBubbleShouldShow({
  editor: ed,
  state,
  from,
  to,
}: {
  editor: { isEditable: boolean }
  state: { doc: { textBetween: (a: number, b: number, block: string) => string } }
  from: number
  to: number
}): boolean {
  if (!ed || !ed.isEditable) return false
  if (from === to) return false
  const text = state.doc.textBetween(from, to, '\n').trim()
  if (text.length < 1 || text.length > CORPUS_SELECTION_MAX) return false
  selectionPreviewFull.value = text
  selectionPreviewShort.value = text.length > 28 ? `${text.slice(0, 26)}…` : text
  return true
}

async function submitCorpusCapture() {
  const inst = editor.value
  if (!inst) return
  const { from, to } = inst.state.selection
  const anchor = inst.state.doc.textBetween(from, to, '\n').trim()
  if (!anchor) {
    ElMessage.warning('请先选中要收录的文本')
    return
  }
  if (anchor.length > CORPUS_SELECTION_MAX) {
    ElMessage.warning(`选区过长，请控制在 ${CORPUS_SELECTION_MAX} 字以内`)
    return
  }
  captureLoading.value = true
  try {
    await api.personalCorpus.capture({
      kind: captureKind.value,
      anchor,
      content: captureExtra.value.trim(),
    })
    ElMessage.success('已收录到个人语料')
    captureExtra.value = ''
    inst.chain().focus().run()
  } catch (e: unknown) {
    ElMessage.error(axiosErrorDetail(e as any) || '收录失败')
  } finally {
    captureLoading.value = false
  }
}

const props = defineProps<{
  modelValue: any
  contentFormat?: string
  locateRequest?: { text: string; token: number } | null
  /** 条漫/分镜等生图时写入 storage，供 ComicPanel 等读取 */
  articleId?: number | null
}>()

const contentFormat = computed(() => props.contentFormat)

const emit = defineEmits<{
  'update:modelValue': [value: any]
  'locate-result': [ok: boolean]
  'citation-click': [payload: { paperId: number; externalRefId?: number; articleId?: number; sectionId?: number; title?: string }]
  'claim-click': [
    payload: {
      paperId: number
      evidenceSnippet: string
      evidenceSource: string
      chunkId: string
      text: string
    },
  ]
}>()

const editor = useEditor({
  content: props.modelValue || { type: 'doc', content: [] },
  extensions: [MedCommImageContext, ...useFormatEditor(props.contentFormat)],
  editorProps: {
    attributes: {
      class: 'prose-editor focus:outline-none min-h-[300px]',
    },
    handleClick: (_view, _pos, event) => {
      const target = event.target as HTMLElement | null
      const el = target?.closest?.('a[data-citation-ref]') as HTMLElement | null
      if (el) {
        const paperId = Number(el.getAttribute('paperId') || el.getAttribute('data-paper-id') || 0)
        const externalRefId = Number(el.getAttribute('externalRefId') || el.getAttribute('data-external-ref-id') || 0)
        if (!paperId && !externalRefId) return false
        const articleId = Number(el.getAttribute('articleId') || el.getAttribute('data-article-id') || 0) || undefined
        const sectionId = Number(el.getAttribute('sectionId') || el.getAttribute('data-section-id') || 0) || undefined
        const title = el.getAttribute('title') || undefined
        emit('citation-click', { paperId: paperId || 0, externalRefId: externalRefId || 0, articleId, sectionId, title })
        event.preventDefault()
        return true
      }
      const claimEl = target?.closest?.('span[data-med-claim]') as HTMLElement | null
      if (claimEl) {
        const paperId = Number(claimEl.getAttribute('data-paper-id') || 0)
        const rawSnip = claimEl.getAttribute('data-evidence-snippet')
        let evidenceSnippet = ''
        if (rawSnip) {
          try {
            evidenceSnippet = decodeURIComponent(rawSnip)
          } catch {
            evidenceSnippet = rawSnip
          }
        }
        const evidenceSource = claimEl.getAttribute('data-evidence-source') || ''
        const chunkId = claimEl.getAttribute('data-chunk-id') || ''
        const text = (claimEl.textContent || '').trim()
        emit('claim-click', { paperId, evidenceSnippet, evidenceSource, chunkId, text })
        return true
      }
      return false
    },
  },
  onUpdate: ({ editor }) => {
    emit('update:modelValue', editor.getJSON())
  },
  onSelectionUpdate: ({ editor }) => {
    syncSelectionToStore(editor)
  },
})

watch(
  () => props.modelValue,
  (val) => {
    if (val && editor.value && JSON.stringify(editor.value.getJSON()) !== JSON.stringify(val)) {
      editor.value.commands.setContent(val, false)
    }
  },
  { deep: true }
)

function syncArticleIdToStorage() {
  const inst = editor.value
  if (!inst?.storage?.medCommImageContext) return
  const id = props.articleId
  inst.storage.medCommImageContext.articleId =
    id != null && Number.isFinite(id) && id > 0 ? id : null
}

watch(
  () => [props.articleId, editor.value],
  () => syncArticleIdToStorage(),
  { immediate: true }
)

function insertCitationRef(payload: { paperId?: number; externalRefId?: number; articleId?: number; sectionId?: number; index: number; title?: string }) {
  const inst = editor.value
  if (!inst || !payload.index || (!payload.paperId && !payload.externalRefId)) return false
  return inst
    .chain()
    .focus()
    .insertContent({
      type: 'text',
      text: `[${payload.index}]`,
      marks: [
        {
          type: 'citationRef',
          attrs: {
            paperId: payload.paperId ?? null,
            externalRefId: payload.externalRefId ?? null,
            articleId: payload.articleId ?? null,
            sectionId: payload.sectionId ?? null,
            index: payload.index,
            title: payload.title || '查看引用文献',
          },
        },
      ],
    })
    .insertContent(' ')
    .run()
}

function normalizeCitationRefs(indexByPaperId: Record<string, number>) {
  const inst = editor.value
  if (!inst) return 0
  const state = inst.state
  const markType = state.schema.marks.citationRef
  if (!markType) return 0

  const updates: Array<{ from: number; to: number; text: string; marks: any[] }> = []
  state.doc.descendants((node, pos) => {
    if (!node.isText || !node.text) return
    const citationMark = node.marks.find((m) => m.type.name === 'citationRef')
    if (!citationMark) return
    const paperId = Number(citationMark.attrs?.paperId || 0)
    if (!paperId) return
    const nextIdx = Number(indexByPaperId[String(paperId)] || 0)
    if (!nextIdx) return
    const nextText = `[${nextIdx}]`
    const sameText = node.text === nextText
    const sameIndex = Number(citationMark.attrs?.index || 0) === nextIdx
    if (sameText && sameIndex) return
    const nextMarks = node.marks.map((m) => (m.type.name === 'citationRef'
      ? m.type.create({ ...m.attrs, index: nextIdx })
      : m))
    updates.push({
      from: pos,
      to: pos + node.nodeSize,
      text: nextText,
      marks: nextMarks,
    })
  })

  if (!updates.length) return 0
  const tr = state.tr
  for (const u of updates.sort((a, b) => b.from - a.from)) {
    tr.replaceWith(u.from, u.to, state.schema.text(u.text, u.marks))
  }
  inst.view.dispatch(tr)
  return updates.length
}

function getComicPanels(): Array<{ panelIndex: number; sceneDesc: string; dialogue: string; narration: string; imagePath: string | null; pos: number }> {
  const inst = editor.value
  if (!inst) return []
  const panels: Array<{ panelIndex: number; sceneDesc: string; dialogue: string; narration: string; imagePath: string | null; pos: number }> = []
  inst.state.doc.descendants((node, pos) => {
    if (node.type.name === 'comicPanel') {
      const a = node.attrs
      const textContent = node.textContent?.trim() || ''
      panels.push({
        panelIndex: Number(a.panelIndex ?? panels.length + 1),
        sceneDesc: String(a.sceneDesc || ''),
        dialogue: String(a.dialogue || ''),
        narration: String(a.narration || ''),
        imagePath: a.imagePath as string | null,
        pos,
      })
      if (!a.sceneDesc && !a.dialogue && !a.narration && textContent) {
        panels[panels.length - 1].sceneDesc = textContent
      }
    }
  })
  return panels
}

function updateComicPanelImage(panelIndex: number, imagePath: string) {
  const inst = editor.value
  if (!inst) return false
  let updated = false
  inst.state.doc.descendants((node, pos) => {
    if (updated) return false
    if (node.type.name === 'comicPanel' && Number(node.attrs.panelIndex) === panelIndex) {
      inst.view.dispatch(
        inst.state.tr.setNodeMarkup(pos, undefined, { ...node.attrs, imagePath })
      )
      updated = true
      return false
    }
  })
  return updated
}

function replaceRange(from: number, to: number, text: string) {
  const inst = editor.value
  if (!inst) return false
  inst.chain().focus()
    .deleteRange({ from, to })
    .insertContentAt(from, text)
    .run()
  return true
}

function insertAtCursor(text: string) {
  const inst = editor.value
  if (!inst) return false
  inst.chain().focus().insertContent(text).run()
  return true
}

function applyAigcWarnings(paragraphs: Array<{ full_text?: string; text: string; risk_level: string; suggestions: string[] }>) {
  const inst = editor.value
  if (!inst) return 0
  const markType = inst.state.schema.marks.aigcWarning
  if (!markType) return 0

  const tr = inst.state.tr
  tr.removeMark(0, inst.state.doc.content.size, markType)

  let applied = 0
  for (const p of paragraphs) {
    if (p.risk_level === 'low') continue
    const searchText = (p.full_text || p.text || '').replace(/\.\.\.$/g, '').trim()
    if (!searchText || searchText.length < 10) continue
    const range = findTextRangeInDoc(inst.state.doc, searchText)
    if (!range) continue
    const tooltip = p.suggestions.slice(0, 2).join('；') || (p.risk_level === 'high' ? 'AIGC高风险' : 'AIGC中风险')
    tr.addMark(range.from, range.to, markType.create({ level: p.risk_level, tooltip }))
    applied++
  }

  if (applied > 0) inst.view.dispatch(tr)
  return applied
}

function clearAigcWarnings() {
  const inst = editor.value
  if (!inst) return
  const markType = inst.state.schema.marks.aigcWarning
  if (!markType) return
  const tr = inst.state.tr
  tr.removeMark(0, inst.state.doc.content.size, markType)
  inst.view.dispatch(tr)
}

defineExpose({
  insertCitationRef,
  normalizeCitationRefs,
  getComicPanels,
  updateComicPanelImage,
  replaceRange,
  insertAtCursor,
  applyAigcWarnings,
  clearAigcWarnings,
})

onBeforeUnmount(() => {
  if (_selectionTimer) clearTimeout(_selectionTimer)
  articleStore.setEditorSelection(null)
  editor.value?.destroy()
})

/** 跨文本节点拼接后定位，避免关键词被 mark 拆成多节点时匹配失败 */
function findTextRangeInDoc(doc: PMNode, keyword: string): { from: number; to: number } | null {
  const k = keyword.trim()
  if (!k.length) return null
  type Span = { absStart: number; absEnd: number; pmFrom: number }
  const spans: Span[] = []
  let full = ''
  doc.descendants((node, pos) => {
    if (node.isText && node.text) {
      const pmFrom = pos + 1
      const absStart = full.length
      full += node.text
      spans.push({ absStart, absEnd: full.length, pmFrom })
    }
  })

  let matchStart = full.indexOf(k)
  let matchLast = matchStart >= 0 ? matchStart + k.length - 1 : -1

  if (matchStart < 0) {
    const _strip = /[「」""''《》【】\s]/g
    const normK = k.replace(_strip, '')
    if (!normK.length) return null
    const origIdx: number[] = []
    let normFull = ''
    for (let ci = 0; ci < full.length; ci++) {
      if (!/[「」""''《》【】\s]/.test(full[ci])) {
        origIdx.push(ci)
        normFull += full[ci]
      }
    }
    const ni = normFull.indexOf(normK)
    if (ni < 0) return null
    matchStart = origIdx[ni]
    matchLast = origIdx[ni + normK.length - 1]
  }

  let from = -1
  let to = -1
  for (const s of spans) {
    if (from < 0 && matchStart >= s.absStart && matchStart < s.absEnd) {
      from = s.pmFrom + (matchStart - s.absStart)
    }
    if (matchLast >= s.absStart && matchLast < s.absEnd) {
      to = s.pmFrom + (matchLast - s.absStart) + 1
      break
    }
  }
  if (from < 0 || to <= from) return null
  return { from, to }
}

function locateTextAndHighlight(text: string): boolean {
  const inst = editor.value
  if (!inst || !text?.trim()) return false
  const keyword = text.trim()
  const range = findTextRangeInDoc(inst.state.doc, keyword)
  if (!range) return false

  const markType = inst.state.schema.marks.locateHit
  if (!markType) return false

  const { from, to } = range
  const tr = inst.state.tr
  tr.removeMark(0, inst.state.doc.content.size, markType)
  tr.addMark(from, to, markType.create())
  inst.view.dispatch(tr)
  inst.chain().focus().setTextSelection({ from, to }).scrollIntoView().run()
  return true
}

function runLocateWhenReady() {
  const text = props.locateRequest?.text
  if (!text?.trim()) {
    emit('locate-result', false)
    return
  }
  let editorWait = 0
  let locateRetry = 0
  const tick = () => {
    const inst = editor.value
    if (!inst) {
      if (++editorWait < 45) {
        requestAnimationFrame(tick)
        return
      }
      emit('locate-result', false)
      return
    }
    const ok = locateTextAndHighlight(text)
    if (ok) {
      emit('locate-result', true)
      return
    }
    if (++locateRetry < 30) {
      requestAnimationFrame(tick)
      return
    }
    emit('locate-result', false)
  }
  nextTick(() => requestAnimationFrame(tick))
}

watch(
  () => props.locateRequest?.token,
  () => {
    if (!props.locateRequest?.text?.trim()) return
    runLocateWhenReady()
  },
  { immediate: true }
)
</script>

<style scoped>
.medcomm-editor {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 1rem;
  background: #fff;
}

.prose :deep(.prose-editor p) {
  margin: 0.5em 0;
}

/* 叙事/正文类格式：段落默认首行缩进 2em，与 docx / 海报模板保持一致 */
.medcomm-editor[data-format="article"] :deep(.prose-editor p),
.medcomm-editor[data-format="contest_article"] :deep(.prose-editor p),
.medcomm-editor[data-format="story"] :deep(.prose-editor p),
.medcomm-editor[data-format="debunk"] :deep(.prose-editor p),
.medcomm-editor[data-format="qa_article"] :deep(.prose-editor p),
.medcomm-editor[data-format="research_read"] :deep(.prose-editor p),
.medcomm-editor[data-format="patient_handbook"] :deep(.prose-editor p),
.medcomm-editor[data-format="quiz_article"] :deep(.prose-editor p) {
  text-indent: 2em;
}

/* 例外：标题、列表、引用、首段、显式取消缩进的段落 不缩进 */
.medcomm-editor :deep(.prose-editor p[data-indent="false"]),
.medcomm-editor :deep(.prose-editor p[style*="text-indent:0"]),
.medcomm-editor :deep(.prose-editor p[style*="text-indent: 0"]),
.medcomm-editor :deep(.prose-editor p:first-child),
.medcomm-editor :deep(.prose-editor blockquote p),
.medcomm-editor :deep(.prose-editor li p) {
  text-indent: 0;
}

.prose :deep(.prose-editor h1) {
  font-size: 1.5rem;
  font-weight: 600;
  margin: 1em 0 0.5em;
}

.prose :deep(.prose-editor h2) {
  font-size: 1.25rem;
  font-weight: 600;
  margin: 0.75em 0 0.5em;
}

.prose :deep(.med-claim) {
  background: rgba(34, 197, 94, 0.2);
  padding: 0 2px;
}
.prose :deep(.pending-claim) {
  background: rgba(234, 179, 8, 0.2);
  padding: 0 2px;
}
.prose :deep(.reading-level) {
  background: rgba(59, 130, 246, 0.15);
  padding: 0 2px;
}
.prose :deep(.fact-warning) {
  background: rgba(249, 115, 22, 0.2);
  padding: 0 2px;
}
.prose :deep(.med-term) {
  text-decoration: underline;
  text-decoration-color: rgba(59, 130, 246, 0.6);
  text-underline-offset: 2px;
}
.prose :deep(.med-image-wrapper) {
  margin: 1em 0;
}
.prose :deep(.med-image) {
  max-width: 100%;
  height: auto;
  border-radius: 4px;
}
.prose :deep(.image-caption) {
  font-size: 0.875em;
  color: #6b7280;
  margin-top: 0.25em;
}
.prose :deep(.prose-editor .is-empty::before) {
  content: attr(data-placeholder);
  color: #9ca3af;
  float: left;
  pointer-events: none;
  height: 0;
}

.prose :deep(.comic-panel-view .panel-content) {
  outline: none;
}

.prose :deep(.comic-panel-view .panel-content p) {
  margin: 0.25em 0;
}

.prose :deep(.storyboard-frame-view .frame-content) {
  outline: none;
}

.prose :deep(.storyboard-frame-view .frame-content p) {
  margin: 0.25em 0;
}

.prose :deep(.card-block-view .card-content) {
  outline: none;
}

.prose :deep(.card-block-view .card-content p) {
  margin: 0.25em 0;
}

.prose :deep(.locate-hit) {
  background: rgba(239, 68, 68, 0.18);
  box-shadow: 0 0 0 1px rgba(239, 68, 68, 0.35);
  border-radius: 2px;
}

.prose :deep(.aigc-warning-high) {
  background: rgba(239, 68, 68, 0.15);
  border-bottom: 2px wavy rgba(239, 68, 68, 0.6);
  cursor: help;
}

.prose :deep(.aigc-warning-medium) {
  background: rgba(245, 158, 11, 0.12);
  border-bottom: 2px wavy rgba(245, 158, 11, 0.5);
  cursor: help;
}

.prose :deep(.citation-ref) {
  color: #2563eb;
  text-decoration: underline;
  text-underline-offset: 2px;
  cursor: pointer;
  font-weight: 500;
}

.corpus-float-bar {
  min-width: 240px;
  max-width: 300px;
  padding: 6px 8px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.12);
}
.corpus-float-preview {
  font-size: 11px;
  color: #6b7280;
  line-height: 1.35;
  max-height: 1.5em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 5px;
  display: flex;
  align-items: center;
  gap: 4px;
}
.corpus-float-tag {
  display: inline-block;
  flex-shrink: 0;
  padding: 0 5px;
  height: 16px;
  line-height: 16px;
  border-radius: 3px;
  background: #eff6ff;
  color: #2563eb;
  font-size: 10px;
  font-weight: 600;
}
.corpus-float-row {
  display: flex;
  align-items: center;
  gap: 5px;
}
.corpus-float-select {
  width: 64px;
  flex-shrink: 0;
}
.corpus-float-input {
  flex: 1;
  min-width: 0;
}
.corpus-float-submit {
  flex-shrink: 0;
  padding-left: 9px;
  padding-right: 9px;
}
.corpus-float-bar :deep(.el-input__wrapper),
.corpus-float-bar :deep(.el-select__wrapper) {
  padding: 0 6px;
  min-height: 24px;
}
.corpus-float-bar :deep(.el-input__inner),
.corpus-float-bar :deep(.el-select__placeholder) {
  font-size: 12px;
}
.corpus-float-bar :deep(.el-button--small) {
  padding: 4px 10px;
  font-size: 12px;
  height: 24px;
}
</style>
