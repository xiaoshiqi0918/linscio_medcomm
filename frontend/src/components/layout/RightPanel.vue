<template>
  <aside class="right-panel">
    <el-tabs v-model="activeTab" class="panel-tabs">
      <el-tab-pane label="AI 写作" name="ai" />
      <el-tab-pane name="image">
        <template #label>
          配图建议
          <el-badge
            v-if="imageSuggestions.length"
            :value="imageSuggestions.length"
            :max="9"
            class="suggest-badge"
          />
        </template>
      </el-tab-pane>
      <el-tab-pane label="核实状态" name="verify" />
      <el-tab-pane label="版本" name="versions" />
      <el-tab-pane label="文章信息" name="info" />
    </el-tabs>
    <div class="panel-content">
      <div v-if="activeTab === 'ai'" class="tab-body ai-assist-body">
        <template v-if="!editorSel">
          <div class="ai-empty">
            <p class="hint">在编辑器中选中文本，即可使用 AI 续写、润色等功能</p>
          </div>
        </template>
        <template v-else>
          <div class="ai-selection-block">
            <div class="ai-sel-label">已选中 {{ editorSel.text.length }} 字</div>
            <div class="ai-sel-preview">{{ editorSel.text.length > 120 ? editorSel.text.slice(0, 118) + '…' : editorSel.text }}</div>
          </div>
          <div class="ai-actions">
            <el-button size="small" :loading="aiRunning && aiCurrentAction === 'continue'" :disabled="aiRunning && aiCurrentAction !== 'continue'" @click="runAiAssist('continue')">续写</el-button>
            <el-button size="small" :loading="aiRunning && aiCurrentAction === 'polish'" :disabled="aiRunning && aiCurrentAction !== 'polish'" @click="runAiAssist('polish')">润色</el-button>
            <el-button size="small" :loading="aiRunning && aiCurrentAction === 'rewrite'" :disabled="aiRunning && aiCurrentAction !== 'rewrite'" @click="runAiAssist('rewrite')">改写</el-button>
            <el-button size="small" :loading="aiRunning && aiCurrentAction === 'simplify'" :disabled="aiRunning && aiCurrentAction !== 'simplify'" @click="runAiAssist('simplify')">通俗化</el-button>
            <el-button size="small" :loading="aiRunning && aiCurrentAction === 'expand'" :disabled="aiRunning && aiCurrentAction !== 'expand'" @click="runAiAssist('expand')">扩展</el-button>
          </div>
          <div class="ai-custom-row">
            <el-input v-model="customInstruction" size="small" placeholder="自定义指令（可选）" clearable />
            <el-button size="small" type="primary" :loading="aiRunning && aiCurrentAction === 'custom'" :disabled="aiRunning && aiCurrentAction !== 'custom'" @click="runAiAssist('custom')">执行</el-button>
          </div>
          <div v-if="aiRunning" class="ai-running-hint">
            <el-icon class="is-loading"><Loading /></el-icon>
            <span>AI 生成中…</span>
            <el-button size="small" text type="danger" @click="cancelAiAssist">取消</el-button>
          </div>
          <div v-if="aiResultText" class="ai-result-block">
            <div class="ai-result-label">AI 结果 <el-tag size="small" type="info">{{ actionLabel(aiCurrentAction) }}</el-tag></div>
            <div class="ai-result-content" v-html="aiResultHtml"></div>
            <div class="ai-result-actions">
              <el-button v-if="aiCurrentAction !== 'continue'" size="small" type="primary" @click="$emit('aiReplace', { from: editorSel!.from, to: editorSel!.to, text: aiResultText })">替换选区</el-button>
              <el-button size="small" @click="$emit('aiInsert', aiResultText)">插入光标处</el-button>
              <el-button size="small" text @click="copyResult">复制</el-button>
              <el-button size="small" text type="info" @click="clearResult">清除</el-button>
            </div>
          </div>
          <div v-if="aiError" class="ai-error">{{ aiError }}</div>
        </template>
      </div>
      <div v-else-if="activeTab === 'image'" class="tab-body">
        <div v-if="isVisualFormat" class="suggest-visual-hint">
          当前为图示类形式（{{ formatLabel(article?.content_format) }}），每格/页已内置画面描述，可在编辑器中逐格生成配图。
        </div>
        <div v-else-if="imageSuggestions.length" class="suggest-list">
          <div
            v-for="(s, idx) in imageSuggestions"
            :key="idx"
            class="suggest-card"
            :class="{ 'high-priority': s.priority === 'high' }"
          >
            <div class="suggest-header">
              <span class="suggest-index">#{{ idx + 1 }}</span>
              <el-tag size="small" :type="imageTypeTagType(s.image_type as string)">
                {{ imageTypeLabel(s.image_type as string) }}
              </el-tag>
              <el-tag v-if="s.priority === 'high'" size="small" type="danger">高优</el-tag>
              <el-tag v-if="s.style" size="small" type="info">{{ styleLabel(s.style as string) }}</el-tag>
            </div>
            <div v-if="s.description" class="suggest-desc">{{ s.description }}</div>
            <div v-if="s.en_description" class="suggest-en-desc">{{ s.en_description }}</div>
            <div v-if="s.reason" class="suggest-reason">{{ s.reason }}</div>
            <div v-if="s.anchor_text" class="suggest-anchor">
              <span class="suggest-anchor-label">锚点：</span>{{ s.anchor_text }}
            </div>
            <div class="suggest-tool-row">
              <el-tag
                size="small"
                :type="toolTagType(s._tool as string)"
                effect="light"
                class="suggest-tool-tag"
              >
                {{ s._toolLabel }}
              </el-tag>
              <span v-if="s.tool_reason" class="suggest-tool-hint">{{ s.tool_reason }}</span>
            </div>
            <div class="suggest-actions">
              <el-button
                v-if="s.anchor_text"
                size="small"
                text
                type="primary"
                @click="$emit('locateSuggestion', String(s.anchor_text))"
              >
                定位
              </el-button>
              <el-button
                size="small"
                :type="toolTagType(s._tool as string)"
                @click="$emit('generateFromSuggestion', { ...s, recommended_tool: s._tool })"
              >
                {{ s._toolLabel }}
              </el-button>
            </div>
          </div>
        </div>
        <div v-else class="suggest-empty">
          <p class="hint">AI 生成全文后，此处将展示配图建议。</p>
          <p class="hint">也可在生成完成后手动刷新获取。</p>
          <el-button
            v-if="article && !isVisualFormat"
            size="small"
            :loading="refreshingSuggestions"
            @click="$emit('refreshSuggestions')"
          >
            刷新建议
          </el-button>
        </div>
      </div>
      <div v-else-if="activeTab === 'verify'" class="tab-body">
        <div v-if="ollamaWarning" class="ollama-warning">
          {{ ollamaWarning }}
        </div>
        <VerificationPanel :report="verificationReport" />
        <div v-if="verificationReport" class="verify-summary">
          <div class="row"><span>声明</span> {{ claimSummary }}</div>
          <div class="row"><span>可疑</span> {{ suspiciousCount }}处</div>
          <div class="row"><span>层级</span> {{ levelSummary }}</div>
          <div class="recheck-row">
            <el-button
              size="small"
              :loading="recheckingLocal"
              @click="doRecheck"
            >
              重新检测
            </el-button>
          </div>
        </div>

        <!-- AI 味检测 -->
        <div v-if="aiPatterns" class="ai-pattern-block" :class="{ 'clean-block': !aiPatterns.total_issues }">
          <div class="block-title">
            <span>AI 味检测</span>
            <el-tag v-if="aiPatterns.total_issues > 0" :type="aiPatterns.needs_polish ? 'danger' : 'warning'" size="small">
              {{ aiPatterns.score }}分
            </el-tag>
            <el-tag v-else type="success" size="small">通过</el-tag>
          </div>
          <template v-if="aiPatterns.total_issues > 0">
            <div v-for="(items, cat) in aiPatterns.details" :key="cat" class="pattern-category">
              <span class="cat-label">{{ aiCategoryLabel(cat as string) }}</span>
              <div v-for="(item, j) in items" :key="j" class="pattern-item">
                <span class="pattern-text">「{{ typeof item === 'string' ? item.slice(0, 40) : item }}」</span>
                <el-button
                  size="small"
                  text
                  type="primary"
                  @click="locateInEditor(typeof item === 'string' ? item : '')"
                >定位</el-button>
              </div>
            </div>
            <ul v-if="aiPatterns.warnings?.length" class="pattern-warnings">
              <li v-for="(w, i) in aiPatterns.warnings" :key="i">{{ w }}</li>
            </ul>
          </template>
          <p v-else class="clean-hint">未发现 AI 痕迹</p>
        </div>

        <!-- 共识标注缺失检测 -->
        <div v-if="uncitedFacts" class="uncited-block" :class="{ 'clean-block': !uncitedFacts.uncited_count }">
          <div class="block-title">
            <span>[共识] 标注缺失</span>
            <el-tag v-if="uncitedFacts.uncited_count > 0" type="warning" size="small">{{ uncitedFacts.uncited_count }}处</el-tag>
            <el-tag v-else type="success" size="small">通过</el-tag>
          </div>
          <template v-if="uncitedFacts.uncited_count > 0">
            <div v-for="(u, i) in uncitedFacts.uncited_sentences?.slice(0, 8)" :key="i" class="uncited-item">
              <span class="uncited-text">"{{ u.sentence }}"</span>
              <el-button
                size="small"
                text
                type="primary"
                @click="locateInEditor(u.sentence)"
              >定位</el-button>
            </div>
            <p v-if="uncitedFacts.uncited_count > 8" class="more-hint">
              … 还有 {{ uncitedFacts.uncited_count - 8 }} 处
            </p>
          </template>
          <p v-else class="clean-hint">所有医学事实均已标注来源</p>
        </div>

        <!-- 溯源统计 -->
        <div v-if="provenanceData" class="provenance-block" :class="{ 'clean-block': !provenanceData.total_claims }">
          <div class="block-title">溯源统计</div>
          <div v-if="provenanceData.total_claims > 0" class="provenance-grid">
            <div class="prov-item"><span class="prov-label">文献引用</span><span class="prov-val">{{ provenanceData.literature }}</span></div>
            <div class="prov-item"><span class="prov-label">[共识]</span><span class="prov-val">{{ provenanceData.consensus }}</span></div>
            <div class="prov-item"><span class="prov-label">[推断]</span><span class="prov-val">{{ provenanceData.inference }}</span></div>
            <div class="prov-item"><span class="prov-label">[[待补充]]</span><span class="prov-val">{{ provenanceData.gaps }}</span></div>
            <div class="prov-item"><span class="prov-label">可信度</span><span class="prov-val">{{ provenanceData.trust_score }}</span></div>
          </div>
          <p v-else class="clean-hint">暂无溯源声明</p>
          <ul v-if="provenanceData.warnings?.length" class="provenance-warnings">
            <li v-for="(w, i) in provenanceData.warnings" :key="i">{{ w }}</li>
          </ul>
        </div>
        <div v-if="settingsStore.showUpgradeHint" class="upgrade-hint">
          当前使用通用内容库核实。升级定制版后，核实准确率将基于学科专属文献显著提升。
        </div>
      </div>
      <div v-else-if="activeTab === 'versions'" class="tab-body">
        <p class="vs-hint">章节每次保存滚动保留约 30 个版本；整篇快照手动打点，便于大改前备份。</p>
        <div v-if="articleStore.currentSectionId" class="vs-block">
          <div class="vs-label">当前章节版本</div>
          <el-button size="small" @click="fetchSectionVersions" :loading="versionsLoading">刷新列表</el-button>
          <el-table :data="sectionVersions" size="small" max-height="200" style="margin-top: 8px">
            <el-table-column prop="version" label="#" width="44" />
            <el-table-column prop="version_type" label="类型" width="80" />
            <el-table-column prop="created_at" label="时间" min-width="130" />
            <el-table-column label="" width="72" fixed="right">
              <template #default="{ row }">
                <el-button v-if="!row.is_current" type="primary" link size="small" @click="revertToVersion(row)">恢复</el-button>
                <el-tag v-else size="small">当前</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </div>
        <div v-else class="vs-no-section">选择章节后可查看版本历史</div>
        <div class="vs-block">
          <div class="vs-label">整篇文章快照</div>
          <div class="vs-row">
            <el-input v-model="snapshotLabel" placeholder="快照名称（可选）" size="small" clearable style="max-width: 180px" />
            <el-button size="small" type="primary" :loading="snapshotSaving" @click="createArticleSnapshot">保存</el-button>
            <el-button size="small" @click="fetchSnapshots" :loading="snapshotsLoading">刷新</el-button>
          </div>
          <el-table :data="articleSnapshots" size="small" max-height="220" style="margin-top: 8px">
            <el-table-column prop="label" label="名称" min-width="100" show-overflow-tooltip />
            <el-table-column prop="created_at" label="时间" min-width="130" />
            <el-table-column label="" width="120" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="restoreSnapshot(row)">恢复</el-button>
                <el-button type="danger" link size="small" @click="deleteSnapshot(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
      <div v-else class="tab-body">
        <div v-if="article" class="info-list">
          <div class="row"><span>形式</span>{{ formatLabel(article.content_format) }}</div>
          <div class="row"><span>平台</span>{{ platformLabel(article.platform) }}</div>
          <div class="row"><span>主题</span>{{ article.topic }}</div>
          <div class="row"><span>受众</span>{{ article.target_audience || '-' }}</div>
        </div>
        <p v-else class="hint">选择文章查看信息</p>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import VerificationPanel from '@/components/verification/VerificationPanel.vue'
import { formatLabel, platformLabel } from '@/composables/useFormats'
import { useSettingsStore } from '@/stores/settings'
import { useArticleStore } from '@/stores/article'
import { api } from '@/api'

const settingsStore = useSettingsStore()
const articleStore = useArticleStore()

const props = defineProps<{
  article?: any
  verificationReport?: { claims?: any; reading_level?: any }
  ollamaWarning?: string | null
  imageSuggestions?: Array<Record<string, unknown>>
  refreshingSuggestions?: boolean
  recheckLoading?: boolean
}>()

defineEmits<{
  locateSuggestion: [anchor: string]
  generateFromSuggestion: [suggestion: Record<string, unknown>]
  refreshSuggestions: []
  recheckSection: []
  aiReplace: [payload: { from: number; to: number; text: string }]
  aiInsert: [text: string]
}>()

const activeTab = ref('verify')

// ── AI 辅助写作 ──
const editorSel = computed(() => articleStore.editorSelection)
const customInstruction = ref('')
const aiRunning = ref(false)
const aiCurrentAction = ref('')
const aiResultText = ref('')
const aiError = ref('')
let _abortCtrl: AbortController | null = null

const _ACTION_LABELS: Record<string, string> = {
  continue: '续写', polish: '润色', rewrite: '改写',
  simplify: '通俗化', expand: '扩展', custom: '自定义',
}
function actionLabel(action: string) { return _ACTION_LABELS[action] || action }

const aiResultHtml = computed(() => {
  return (aiResultText.value || '').replace(/\n/g, '<br>')
})

function runAiAssist(action: string) {
  const sel = editorSel.value
  if (!sel) { ElMessage.warning('请先选中文本'); return }
  if (action === 'custom' && !customInstruction.value.trim()) {
    ElMessage.warning('请输入自定义指令')
    return
  }
  aiRunning.value = true
  aiCurrentAction.value = action
  aiResultText.value = ''
  aiError.value = ''
  _abortCtrl = api.medcomm.aiAssistStream(
    {
      selected_text: sel.text,
      action,
      context_before: sel.contextBefore,
      context_after: sel.contextAfter,
      custom_instruction: action === 'custom' ? customInstruction.value : '',
      article_id: articleStore.current?.id,
    },
    (token) => { aiResultText.value += token },
    () => { aiRunning.value = false },
    (msg) => { aiError.value = msg; aiRunning.value = false },
  )
}

function cancelAiAssist() {
  _abortCtrl?.abort()
  aiRunning.value = false
}

function clearResult() {
  aiResultText.value = ''
  aiError.value = ''
  aiCurrentAction.value = ''
}

async function copyResult() {
  try {
    await navigator.clipboard.writeText(aiResultText.value)
    ElMessage.success('已复制')
  } catch {
    ElMessage.error('复制失败')
  }
}

watch(editorSel, () => {
  aiError.value = ''
})

// ── 版本与快照 ──
const sectionVersions = ref<Array<{ id: number; version: number; version_type: string; is_current: boolean; created_at: string | null }>>([])
const versionsLoading = ref(false)
const articleSnapshots = ref<Array<{ id: number; label: string; created_at: string | null }>>([])
const snapshotsLoading = ref(false)
const snapshotSaving = ref(false)
const snapshotLabel = ref('')

const articleId = computed(() => articleStore.current?.id)

async function fetchSectionVersions() {
  const sid = articleStore.currentSectionId
  if (!sid) return
  versionsLoading.value = true
  try {
    const res = await api.medcomm.getSectionVersions(sid)
    sectionVersions.value = res.data?.items || []
  } catch {
    ElMessage.error('加载版本失败')
  } finally {
    versionsLoading.value = false
  }
}

async function revertToVersion(row: { id: number }) {
  const sid = articleStore.currentSectionId
  if (!sid) return
  try {
    await api.medcomm.revertSection(sid, row.id)
    ElMessage.success('已恢复到该版本')
    articleStore.requestReload()
  } catch {
    ElMessage.error('恢复失败')
  }
}

async function fetchSnapshots() {
  if (!articleId.value) return
  snapshotsLoading.value = true
  try {
    const res = await api.medcomm.listSnapshots(articleId.value)
    articleSnapshots.value = res.data?.items || []
  } catch {
    ElMessage.error('加载快照失败')
  } finally {
    snapshotsLoading.value = false
  }
}

async function createArticleSnapshot() {
  if (!articleId.value) return
  snapshotSaving.value = true
  try {
    await api.medcomm.createSnapshot(articleId.value, { label: snapshotLabel.value.trim() })
    snapshotLabel.value = ''
    ElMessage.success('快照已保存')
    await fetchSnapshots()
  } catch {
    ElMessage.error('保存快照失败')
  } finally {
    snapshotSaving.value = false
  }
}

async function restoreSnapshot(row: { id: number }) {
  if (!articleId.value) return
  try {
    await ElMessageBox.confirm('将从快照恢复所有章节当前平台下的内容，并产生新版本。是否继续？', '恢复快照', {
      type: 'warning', confirmButtonText: '恢复', cancelButtonText: '取消',
    })
  } catch { return }
  try {
    await api.medcomm.restoreSnapshot(articleId.value, row.id)
    ElMessage.success('已从快照恢复')
    articleStore.requestReload()
    await fetchSnapshots()
  } catch {
    ElMessage.error('恢复失败')
  }
}

async function deleteSnapshot(row: { id: number }) {
  if (!articleId.value) return
  try {
    await api.medcomm.deleteSnapshot(articleId.value, row.id)
    ElMessage.success('已删除')
    await fetchSnapshots()
  } catch {
    ElMessage.error('删除失败')
  }
}

watch(() => articleStore.currentSectionId, () => {
  sectionVersions.value = []
})

watch(articleId, () => {
  sectionVersions.value = []
  articleSnapshots.value = []
  if (articleId.value) fetchSnapshots()
})

const STRUCTURED_IMAGE_TYPES = new Set(['comparison', 'infographic', 'flowchart', 'data_viz'])
const STRUCTURED_KEYWORDS_ZH = ['对比图', '对比', '流程图', '信息图', '数据图', '图表', '柱状图', '曲线图', '统计', '坐标']
const STRUCTURED_KEYWORDS_EN = ['comparison', 'infographic', 'flowchart', 'chart', 'graph', 'diagram', 'data viz', 'versus', 'vs.', 'side-by-side']

const TOOL_LABELS: Record<string, string> = {
  artgen: '创意绘图',
  api: 'AI 绘图（API）',
  medpic: 'MedPic 绘图',
}

function inferTool(s: Record<string, unknown>): 'artgen' | 'api' | 'medpic' {
  const rt = String(s.recommended_tool || '')
  if (rt === 'artgen' || rt === 'api' || rt === 'medpic') return rt
  const it = String(s.image_type || '')
  if (STRUCTURED_IMAGE_TYPES.has(it) || s.style === 'data_viz') return 'artgen'
  const desc = String(s.description || '').toLowerCase()
  const enDesc = String(s.en_description || '').toLowerCase()
  if (STRUCTURED_KEYWORDS_ZH.some((kw) => desc.includes(kw))) return 'artgen'
  if (STRUCTURED_KEYWORDS_EN.some((kw) => enDesc.includes(kw))) return 'artgen'
  return 'medpic'
}

function toolTagType(tool: string): '' | 'success' | 'warning' | 'danger' | 'info' {
  if (tool === 'artgen') return ''
  if (tool === 'api') return 'warning'
  return 'success'
}

const imageSuggestions = computed(() =>
  (props.imageSuggestions || []).map((s) => {
    const tool = inferTool(s)
    return {
      ...s,
      _tool: tool,
      _toolLabel: s.tool_label || TOOL_LABELS[tool] || tool,
    }
  }),
)

const VISUAL_FORMATS = ['comic_strip', 'storyboard', 'card_series']
const isVisualFormat = computed(() => VISUAL_FORMATS.includes(props.article?.content_format))

const IMAGE_TYPE_MAP: Record<string, string> = {
  anatomy: '解剖图',
  pathology: '病理图',
  flowchart: '流程图',
  infographic: '信息图',
  comparison: '对比图',
  symptom: '症状图',
  prevention: '预防图',
  illustration: '插图',
  data_viz: '数据可视化',
}

const STYLE_MAP: Record<string, string> = {
  medical_illustration: '医学插图',
  flat_design: '扁平设计',
  realistic: '写实',
  cartoon: '卡通',
  data_viz: '数据可视化',
}

function imageTypeLabel(t: string) {
  return IMAGE_TYPE_MAP[t] || t || '插图'
}

function imageTypeTagType(t: string): '' | 'success' | 'warning' | 'danger' | 'info' {
  const m: Record<string, '' | 'success' | 'warning' | 'danger' | 'info'> = {
    anatomy: '', pathology: 'danger', flowchart: 'success',
    infographic: 'warning', comparison: 'info', symptom: 'danger',
  }
  return m[t] || ''
}

function styleLabel(s: string) {
  return STYLE_MAP[s] || s
}

const claimSummary = computed(() => {
  const r = props.verificationReport?.claims
  if (r?.skipped) return r.reason || '-'
  return r ? '已核实' : '8/10'
})

const suspiciousCount = computed(() => {
  const c = props.verificationReport?.claims
  if (!c || c.skipped) return 0
  return Number(c.pending_count ?? (Array.isArray(c.pending) ? c.pending.length : 0)) || 0
})

const levelSummary = computed(() => {
  const r = props.verificationReport?.reading_level
  if (r?.skipped) return r.reason || '-'
  return r ? '适合' : '-'
})

const aiPatterns = computed(() => props.verificationReport?.ai_patterns ?? null)
const uncitedFacts = computed(() => props.verificationReport?.uncited_facts ?? null)
const provenanceData = computed(() => props.verificationReport?.provenance ?? null)

function locateInEditor(text: string) {
  const clean = (text || '').replace(/[「」""\s]/g, '').trim()
  if (!clean) return
  const needle = clean.length > 20 ? clean.slice(0, 20) : clean
  articleStore.requestEditorLocate(needle)
}

const _AI_CATEGORY_LABELS: Record<string, string> = {
  share_call: '分享号召',
  list_cliche: '清单套话',
  mechanical_transition: '机械过渡',
  excessive_modifier: '学术腔/堆叠修饰',
  ai_ending: 'AI 套路结尾',
  ai_connector: '高频连接词',
}
function aiCategoryLabel(cat: string): string {
  return _AI_CATEGORY_LABELS[cat] || cat
}

const recheckingLocal = ref(false)
async function doRecheck() {
  const sectionId = articleStore.currentSectionId
  if (!sectionId) {
    ElMessage.warning('无法获取当前章节 ID')
    return
  }
  recheckingLocal.value = true
  try {
    const res = await api.medcomm.recheckSection(sectionId)
    const report = res.data?.verify_report
    if (report) {
      articleStore.setVerificationReport(report)
      const aiCount = report.ai_patterns?.total_issues ?? 0
      const uncited = report.uncited_facts?.uncited_count ?? 0
      const provClaims = report.provenance?.total_claims ?? 0
      if (aiCount === 0 && uncited === 0 && provClaims === 0) {
        ElMessage.success('检测完成：未发现问题')
      } else {
        ElMessage.success(`检测完成：AI味 ${aiCount} 处 / 缺标注 ${uncited} 处 / 溯源声明 ${provClaims} 条`)
      }
    } else {
      ElMessage.warning('检测返回数据为空，请重试')
    }
  } catch {
    ElMessage.error('检测失败，请稍后重试')
  } finally {
    recheckingLocal.value = false
  }
}
</script>

<style scoped>
.right-panel {
  background: #fff;
  border-left: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  flex-shrink: 0;
}
.panel-tabs { flex-shrink: 0; }
.panel-tabs :deep(.el-tabs__header) { margin: 0; padding: 0 0.5rem; }
.panel-tabs :deep(.el-tabs__content) { display: none; }
.panel-content { flex: 1; overflow-y: auto; padding: 0.75rem; }
.tab-body { font-size: 0.875rem; }
.hint { color: #9ca3af; font-size: 0.85rem; }
.verify-summary { margin-top: 0.75rem; }
.verify-summary .row { margin: 0.25rem 0; }
.verify-summary .row span { margin-right: 0.5rem; }
.ollama-warning {
  padding: 0.5rem 0.75rem;
  background: #fef3c7;
  color: #92400e;
  border-radius: 6px;
  font-size: 0.8rem;
  margin-bottom: 0.75rem;
}
.upgrade-hint {
  margin-top: 0.75rem;
  padding: 0.5rem 0.75rem;
  background: #f0f9ff;
  color: #0369a1;
  border-radius: 6px;
  font-size: 0.8rem;
}
.info-list .row { margin: 0.5rem 0; }
.info-list .row span { display: inline-block; width: 4em; color: #6b7280; }
.suggest-badge { margin-left: 4px; }
.suggest-badge :deep(.el-badge__content) { font-size: 10px; }
.suggest-visual-hint {
  padding: 0.75rem;
  background: #f0f9ff;
  border-radius: 8px;
  color: #0369a1;
  font-size: 0.85rem;
  line-height: 1.5;
}
.suggest-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.suggest-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 0.65rem 0.75rem;
  transition: border-color 0.2s;
}
.suggest-card:hover {
  border-color: var(--el-color-primary-light-5);
}
.suggest-card.high-priority {
  border-left: 3px solid var(--el-color-danger);
}
.suggest-header {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  margin-bottom: 0.35rem;
  flex-wrap: wrap;
}
.suggest-index {
  font-weight: 600;
  color: #374151;
  font-size: 0.8rem;
}
.suggest-desc {
  font-size: 0.85rem;
  color: #111827;
  line-height: 1.5;
  margin-bottom: 0.25rem;
}
.suggest-en-desc {
  font-size: 0.78rem;
  color: #6b7280;
  font-style: italic;
  margin-bottom: 0.25rem;
}
.suggest-reason {
  font-size: 0.78rem;
  color: #059669;
  margin-bottom: 0.25rem;
}
.suggest-anchor {
  font-size: 0.78rem;
  color: #9ca3af;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.suggest-anchor-label {
  color: #6b7280;
}
.suggest-tool-row {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  margin-top: 0.25rem;
  flex-wrap: wrap;
}
.suggest-tool-tag {
  flex-shrink: 0;
}
.suggest-tool-hint {
  font-size: 0.72rem;
  color: #9ca3af;
  line-height: 1.3;
}
.suggest-actions {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  margin-top: 0.35rem;
}
.suggest-empty {
  text-align: center;
  padding: 1.5rem 0;
}
.suggest-empty .hint {
  margin: 0 0 0.5rem;
}
.vs-hint {
  font-size: 0.8rem;
  color: #9ca3af;
  margin: 0 0 0.75rem;
  line-height: 1.5;
}
.vs-block {
  margin-bottom: 1rem;
}
.vs-label {
  font-weight: 600;
  font-size: 0.85rem;
  color: #374151;
  margin-bottom: 0.4rem;
}
.vs-row {
  display: flex;
  gap: 0.4rem;
  align-items: center;
  flex-wrap: wrap;
}
.vs-no-section {
  color: #9ca3af;
  font-size: 0.85rem;
  margin-bottom: 1rem;
}

.recheck-row {
  margin-top: 0.4rem;
  display: flex;
  justify-content: flex-end;
}

/* AI 味检测 / 共识缺失 / 溯源统计 */
.ai-pattern-block,
.uncited-block,
.provenance-block {
  margin-top: 0.75rem;
  padding: 0.5rem 0.6rem;
  border-radius: 6px;
  background: #fefce8;
  border: 1px solid #fde68a;
  font-size: 0.8rem;
}
.uncited-block {
  background: #fff7ed;
  border-color: #fed7aa;
}
.provenance-block {
  background: #f0fdf4;
  border-color: #bbf7d0;
}
.block-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
  font-size: 0.82rem;
  margin-bottom: 0.35rem;
  color: #374151;
}
.pattern-category {
  margin-bottom: 0.35rem;
}
.cat-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: #92400e;
  display: block;
  margin-bottom: 0.15rem;
}
.pattern-item,
.uncited-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.3rem;
  padding: 0.15rem 0;
  line-height: 1.5;
}
.pattern-text,
.uncited-text {
  flex: 1;
  min-width: 0;
  font-size: 0.78rem;
  color: #6b7280;
  word-break: break-all;
}
.pattern-item .el-button,
.uncited-item .el-button {
  flex-shrink: 0;
}
.pattern-warnings,
.provenance-warnings {
  margin: 0.3rem 0 0;
  padding-left: 1.2em;
  line-height: 1.6;
  color: #6b7280;
  font-size: 0.75rem;
}
.provenance-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.25rem 0.5rem;
  margin-bottom: 0.3rem;
}
.prov-item {
  display: flex;
  justify-content: space-between;
}
.prov-label {
  color: #6b7280;
}
.prov-val {
  font-weight: 600;
  color: #374151;
}
.more-hint {
  font-size: 0.75rem;
  color: #9ca3af;
  margin: 0.2rem 0 0;
}
.clean-block {
  background: #f0fdf4 !important;
  border-color: #bbf7d0 !important;
}
.clean-hint {
  font-size: 0.78rem;
  color: #15803d;
  margin: 0;
}

/* AI 辅助写作 */
.ai-assist-body { display: flex; flex-direction: column; gap: 0.6rem; }
.ai-empty { text-align: center; padding: 2rem 0; }
.ai-selection-block {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 0.5rem 0.6rem;
}
.ai-sel-label {
  font-size: 0.75rem;
  color: #64748b;
  margin-bottom: 0.25rem;
  font-weight: 500;
}
.ai-sel-preview {
  font-size: 0.82rem;
  color: #334155;
  line-height: 1.5;
  max-height: 4.5em;
  overflow: hidden;
  word-break: break-all;
}
.ai-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}
.ai-custom-row {
  display: flex;
  gap: 0.35rem;
  align-items: center;
}
.ai-custom-row .el-input { flex: 1; }
.ai-running-hint {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.8rem;
  color: #2563eb;
}
.ai-result-block {
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  padding: 0.6rem;
  background: #eff6ff;
}
.ai-result-label {
  font-size: 0.78rem;
  font-weight: 600;
  color: #1e40af;
  margin-bottom: 0.35rem;
  display: flex;
  align-items: center;
  gap: 0.35rem;
}
.ai-result-content {
  font-size: 0.85rem;
  color: #1e293b;
  line-height: 1.65;
  max-height: 16rem;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
  margin-bottom: 0.5rem;
}
.ai-result-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}
.ai-error {
  font-size: 0.8rem;
  color: #dc2626;
  padding: 0.4rem 0.6rem;
  background: #fef2f2;
  border-radius: 6px;
}
</style>
