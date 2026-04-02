<template>
  <div v-if="report" class="verification-panel">
    <h4>防编造检查</h4>
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
    <div v-if="report.data_warnings?.length" class="section">
      <span class="label">数据占位符：</span>
      <span class="warning">{{ report.data_warnings.length }} 处需补充</span>
    </div>
    <div v-if="report.absolute_terms?.length" class="section">
      <span class="label">绝对化表述：</span>
      <span class="warning">{{ report.absolute_terms.length }} 处建议修改</span>
    </div>
    <div v-if="report.reading_level" class="section">
      <span class="label">阅读难度：</span>
      <span v-if="report.reading_level.skipped">{{ report.reading_level.reason }}</span>
      <span v-else-if="report.reading_level.passed">通过</span>
      <span v-else class="warning">建议简化</span>
    </div>

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
