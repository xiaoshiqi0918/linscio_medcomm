<template>
  <div v-if="report" class="verification-panel">
    <h4>防编造检查</h4>

    <!-- 医学声明 -->
    <div v-if="report.claims" class="section">
      <span class="label">医学声明：</span>
      <span v-if="report.claims.skipped">{{ report.claims.reason }}</span>
      <span v-else-if="report.claims.verified_count != null">
        已核实 {{ report.claims.verified_count }} 条，
        <span v-if="report.claims.pending_count > 0" class="warning">待核实 {{ report.claims.pending_count }} 条</span>
        <span v-else>全部匹配到参考片段</span>
      </span>
      <span v-else>已分析</span>
    </div>

    <!-- 数据占位符 摘要 -->
    <div v-if="report.data_warnings?.length" class="section">
      <span class="label">数据占位符：</span>
      <span class="warning">{{ report.data_warnings.length }} 处需补充</span>
    </div>

    <!-- 绝对化表述 摘要 -->
    <div v-if="report.absolute_terms?.length" class="section">
      <span class="label">绝对化表述：</span>
      <span class="warning">{{ report.absolute_terms.length }} 处建议修改</span>
    </div>

    <!-- 阅读难度 摘要 -->
    <div v-if="report.reading_level" class="section">
      <span class="label">阅读难度：</span>
      <span v-if="report.reading_level.skipped">{{ report.reading_level.reason }}</span>
      <span v-else-if="report.reading_level.passed">通过</span>
      <span v-else class="warning">建议简化（{{ readingIssueCount }} 项）</span>
    </div>

    <!-- ========== 详情列表 ========== -->

    <!-- 绝对化表述 详情 -->
    <div v-if="report.absolute_terms?.length" class="issue-block abs-block">
      <div class="issue-title">绝对化表述</div>
      <ul class="issue-list">
        <li v-for="(item, idx) in report.absolute_terms" :key="'abs-' + idx" class="issue-item">
          <span class="issue-keyword">{{ item.text }}</span>
          <span v-if="item.suggestion" class="issue-suggestion">→ {{ item.suggestion }}</span>
          <el-button type="primary" link size="small" @click="locate(item.text)">定位</el-button>
        </li>
      </ul>
    </div>

    <!-- 数据占位符 详情 -->
    <div v-if="report.data_warnings?.length" class="issue-block data-block">
      <div class="issue-title">数据占位符</div>
      <ul class="issue-list">
        <li v-for="(item, idx) in report.data_warnings" :key="'dw-' + idx" class="issue-item">
          <span class="issue-keyword">{{ item.text }}</span>
          <span v-if="item.message" class="issue-suggestion">{{ item.message }}</span>
          <el-button type="primary" link size="small" @click="locate(item.text)">定位</el-button>
        </li>
      </ul>
    </div>

    <!-- 阅读难度 详情 -->
    <div v-if="readingIssues.length" class="issue-block level-block">
      <div class="issue-title">阅读难度问题</div>
      <ul class="issue-list">
        <li v-for="(item, idx) in readingIssues" :key="'lv-' + idx" class="issue-item">
          <span class="issue-msg">{{ typeof item === 'string' ? item : (item.message || item.text || JSON.stringify(item)) }}</span>
          <el-button
            v-if="readingIssueLocatable(item)"
            type="primary"
            link
            size="small"
            @click="locate(readingIssueLocatable(item))"
          >
            定位
          </el-button>
        </li>
      </ul>
      <div v-if="readingSuggestions.length" class="reading-suggestions">
        <span class="issue-suggestion" v-for="(s, idx) in readingSuggestions" :key="'ls-' + idx">
          · {{ typeof s === 'string' ? s : (s.message || s.text || '') }}
        </span>
      </div>
    </div>

    <!-- 已核实声明 -->
    <div v-if="verifiedRows.length" class="evidence-block">
      <div class="evidence-title">已匹配依据（可点开核对原文片段）</div>
      <ul class="evidence-list">
        <li v-for="(row, idx) in verifiedRows" :key="'v-' + idx" class="evidence-item">
          <span class="claim-text">{{ row.text }}</span>
          <span class="evidence-actions">
            <el-button type="primary" link size="small" @click="openEvidence(row)">依据</el-button>
            <el-button v-if="locateText(row)" type="info" link size="small" @click="locate(locateText(row))">
              定位
            </el-button>
          </span>
        </li>
      </ul>
    </div>

    <!-- 待核实声明 -->
    <div v-if="pendingRows.length" class="evidence-block pending-block">
      <div class="evidence-title">待核实</div>
      <ul class="evidence-list">
        <li v-for="(row, idx) in pendingRows" :key="'p-' + idx" class="evidence-item">
          <span class="claim-text">{{ row.text }}</span>
          <span class="pending-msg">{{ row.message || '建议补充文献或改为「可能/研究显示」等表述' }}</span>
          <el-button v-if="locateText(row)" type="info" link size="small" @click="locate(locateText(row))">
            定位
          </el-button>
        </li>
      </ul>
    </div>

    <el-dialog v-model="evidenceDialogVisible" title="文献依据片段" width="560px" destroy-on-close>
      <div v-if="activeEvidence" class="ev-dialog-body">
        <p v-if="activeEvidence.evidence_source" class="ev-source">
          <span class="ev-label">来源</span>{{ activeEvidence.evidence_source }}
        </p>
        <p v-if="activeEvidence.chunk_id != null && activeEvidence.chunk_id !== ''" class="ev-chunk">
          <span class="ev-label">Chunk</span>{{ activeEvidence.chunk_id }}
        </p>
        <div class="ev-snippet">{{ activeEvidence.evidence_snippet || '（无片段，可直接打开文献对照）' }}</div>
      </div>
      <template #footer>
        <el-button @click="evidenceDialogVisible = false">关闭</el-button>
        <el-button
          v-if="activeEvidence?.paper_id"
          type="primary"
          @click="goPaper(activeEvidence!.paper_id!)"
        >
          打开文献
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useArticleStore } from '@/stores/article'

type ClaimRow = {
  text?: string
  match_text?: string
  message?: string
  evidence_snippet?: string
  evidence_source?: string
  paper_id?: number
  chunk_id?: string | number | null
}

const props = defineProps<{
  report?: {
    claims?: any
    data_warnings?: any[]
    absolute_terms?: any[]
    reading_level?: any
  }
}>()

const router = useRouter()
const articleStore = useArticleStore()

const evidenceDialogVisible = ref(false)
const activeEvidence = ref<ClaimRow | null>(null)

const readingIssues = computed((): any[] => {
  const rl = props.report?.reading_level
  if (!rl || rl.skipped || rl.passed) return []
  return Array.isArray(rl.issues) ? rl.issues : []
})

const readingSuggestions = computed((): any[] => {
  const rl = props.report?.reading_level
  if (!rl) return []
  return Array.isArray(rl.suggestions) ? rl.suggestions : []
})

const readingIssueCount = computed(() => readingIssues.value.length)

function readingIssueLocatable(item: any): string {
  if (typeof item === 'string') return ''
  const t = (item.text || item.term || item.sentence || '').trim()
  return t.length >= 2 ? t : ''
}

const verifiedRows = computed((): ClaimRow[] => {
  const c = props.report?.claims
  if (!c || c.skipped) return []
  const raw = c.verified
  return Array.isArray(raw) ? raw : []
})

const pendingRows = computed((): ClaimRow[] => {
  const c = props.report?.claims
  if (!c || c.skipped) return []
  const raw = c.pending
  return Array.isArray(raw) ? raw : []
})

function openEvidence(row: ClaimRow) {
  activeEvidence.value = row
  evidenceDialogVisible.value = true
}

function locateText(row: ClaimRow): string {
  const m = (row.match_text || '').trim()
  if (m) return m
  let t = (row.text || '').trim()
  if (t.endsWith('…')) t = t.slice(0, -1).trim()
  return t
}

function locate(text: string | undefined) {
  if (!text) return
  articleStore.requestEditorLocate(text)
}

function goPaper(paperId: number) {
  if (!paperId) return
  evidenceDialogVisible.value = false
  router.push({ name: 'literature-paper', params: { paperId } })
}
</script>

<style scoped>
.verification-panel {
  padding: 0.75rem;
  background: #f0fdf4;
  border-radius: 6px;
  font-size: 0.875rem;
}
.section {
  margin: 0.25rem 0;
}
.label {
  font-weight: 500;
  margin-right: 0.5rem;
}
.warning {
  color: #d97706;
}
.issue-block {
  margin-top: 0.75rem;
  padding-top: 0.5rem;
  border-top: 1px solid rgba(217, 119, 6, 0.25);
}
.issue-title {
  font-weight: 600;
  font-size: 0.8rem;
  color: #b45309;
  margin-bottom: 0.3rem;
}
.issue-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.issue-item {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.2rem 0.5rem;
  margin: 0.3rem 0;
  padding: 0.35rem 0.5rem;
  background: #fffbeb;
  border-radius: 5px;
  font-size: 0.8rem;
  line-height: 1.45;
}
.issue-keyword {
  font-weight: 600;
  color: #dc2626;
  flex-shrink: 0;
}
.issue-suggestion {
  color: #059669;
  font-size: 0.78rem;
  flex: 1;
}
.issue-msg {
  color: #374151;
  flex: 1;
}
.abs-block {
  border-top-color: rgba(220, 38, 38, 0.25);
}
.abs-block .issue-title {
  color: #dc2626;
}
.data-block .issue-title {
  color: #d97706;
}
.level-block {
  border-top-color: rgba(99, 102, 241, 0.25);
}
.level-block .issue-title {
  color: #4f46e5;
}
.level-block .issue-item {
  background: #eef2ff;
}
.reading-suggestions {
  margin-top: 0.3rem;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  font-size: 0.78rem;
  color: #4f46e5;
  padding-left: 0.25rem;
}
.evidence-block {
  margin-top: 0.75rem;
  padding-top: 0.5rem;
  border-top: 1px solid rgba(16, 185, 129, 0.25);
}
.pending-block {
  border-top-color: rgba(245, 158, 11, 0.35);
}
.evidence-title {
  font-weight: 600;
  font-size: 0.8rem;
  color: #047857;
  margin-bottom: 0.35rem;
}
.pending-block .evidence-title {
  color: #b45309;
}
.evidence-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.evidence-item {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.25rem 0.5rem;
  margin: 0.35rem 0;
  font-size: 0.8rem;
  line-height: 1.45;
}
.claim-text {
  flex: 1 1 200px;
  color: #374151;
}
.pending-msg {
  flex: 1 1 100%;
  color: #9a3412;
  font-size: 0.75rem;
}
.evidence-actions {
  flex-shrink: 0;
}
.ev-dialog-body {
  font-size: 0.875rem;
  line-height: 1.5;
}
.ev-label {
  display: inline-block;
  min-width: 3.5em;
  color: #6b7280;
  margin-right: 0.35rem;
}
.ev-source,
.ev-chunk {
  margin: 0 0 0.5rem;
}
.ev-snippet {
  white-space: pre-wrap;
  padding: 0.65rem 0.75rem;
  background: #f9fafb;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
  max-height: 240px;
  overflow-y: auto;
}
</style>
