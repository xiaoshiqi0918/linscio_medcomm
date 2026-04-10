<template>
  <div class="new-article">
    <h2>新建科普文章</h2>

    <el-steps :active="currentStep" finish-status="success" class="wizard-steps">
      <el-step title="参考文献" description="选择支撑文献" />
      <el-step title="文献分析" description="AI 通读与分析" />
      <el-step title="文章配置" description="选题与写作设置" />
    </el-steps>

    <!-- ═══ Step 1: 参考文献绑定 ═══ -->
    <div v-show="currentStep === 0" class="step-content">
      <div class="step-header">
        <h3>选择参考文献</h3>
        <p class="step-desc">从文献库中选择与本次科普写作相关的参考文献，系统将通读分析后辅助写作</p>
      </div>

      <div class="search-bar">
        <el-input
          v-model="paperSearch"
          placeholder="搜索文献（标题、关键词、作者）"
          clearable
          @keyup.enter="searchPapers"
        >
          <template #append>
            <el-button @click="searchPapers" :loading="searching">搜索</el-button>
          </template>
        </el-input>
      </div>

      <div class="selected-papers" v-if="selectedPapers.length">
        <div class="section-label">已选文献（{{ selectedPapers.length }}）</div>
        <div class="paper-chip" v-for="p in selectedPapers" :key="p.id">
          <el-icon v-if="p.fulltext_status === 'done' || p.pdf_indexed" class="chip-icon text-success"><CircleCheckFilled /></el-icon>
          <el-icon v-else class="chip-icon text-muted"><Document /></el-icon>
          <span class="chip-title">{{ p.title }}</span>
          <span class="chip-meta" v-if="p.year">{{ p.year }}</span>
          <el-icon class="chip-remove" @click="removePaper(p.id)"><Close /></el-icon>
        </div>
      </div>

      <div class="paper-list" v-if="paperResults.length">
        <div class="section-label">文献库</div>
        <div
          v-for="paper in paperResults"
          :key="paper.id"
          class="paper-item"
          :class="{ selected: selectedPaperIds.has(paper.id) }"
          @click="togglePaper(paper)"
        >
          <el-checkbox :model-value="selectedPaperIds.has(paper.id)" @click.stop />
          <div class="paper-info">
            <div class="paper-title">
              {{ paper.title }}
              <el-tag
                v-if="paper.fulltext_status === 'done' || paper.pdf_indexed"
                size="small"
                type="success"
                effect="plain"
                class="fulltext-tag"
              >有全文</el-tag>
              <el-tag
                v-else-if="paper.fulltext_status === 'pending'"
                size="small"
                type="warning"
                effect="plain"
                class="fulltext-tag"
              >获取中</el-tag>
              <el-tag
                v-else
                size="small"
                type="info"
                effect="plain"
                class="fulltext-tag"
              >仅摘要</el-tag>
            </div>
            <div class="paper-meta">
              <span v-if="paper.journal">{{ paper.journal }}</span>
              <span v-if="paper.year">{{ paper.year }}</span>
              <span v-if="paper.doi" class="doi">DOI: {{ paper.doi }}</span>
            </div>
          </div>
        </div>
        <div v-if="paperTotal > paperResults.length" class="load-more">
          <el-button text type="primary" @click="loadMorePapers">加载更多</el-button>
        </div>
      </div>
      <el-empty v-else-if="!searching && paperSearched" description="未找到匹配的文献" />

      <div class="step-actions">
        <el-button @click="$router.back()">取消</el-button>
        <el-button type="default" @click="skipLiterature">跳过，直接配置</el-button>
        <el-button type="primary" @click="startAnalysis" :disabled="!selectedPapers.length">
          分析文献（{{ selectedPapers.length }}篇）
        </el-button>
      </div>
    </div>

    <!-- ═══ Step 2: 文献分析报告 ═══ -->
    <div v-show="currentStep === 1" class="step-content">
      <div class="step-header">
        <h3>文献分析报告</h3>
        <p class="step-desc">AI 正在通读您选择的文献，生成结构化分析…</p>
      </div>

      <div v-if="analyzing" class="analysis-loading">
        <el-icon class="is-loading" :size="24"><Loading /></el-icon>
        <span>{{ analysisMessage }}</span>
      </div>

      <div v-if="analysisStreamText && !analysisReport" class="analysis-stream">
        <pre class="stream-text">{{ analysisStreamText }}</pre>
      </div>

      <div v-if="analysisReport" class="analysis-report">
        <el-card shadow="never" class="report-card">
          <template #header>
            <div class="report-header">
              <el-icon color="#409eff"><DataAnalysis /></el-icon>
              <span>核心研究主题</span>
            </div>
          </template>
          <p class="report-topic">{{ analysisReport.research_topic }}</p>
        </el-card>

        <el-card shadow="never" class="report-card" v-if="analysisReport.key_findings?.length">
          <template #header>
            <div class="report-header">
              <el-icon color="#67c23a"><CircleCheckFilled /></el-icon>
              <span>关键发现</span>
            </div>
          </template>
          <ul class="report-list">
            <li v-for="(f, i) in analysisReport.key_findings" :key="i">{{ f }}</li>
          </ul>
        </el-card>

        <div class="report-grid">
          <el-card shadow="never" class="report-card" v-if="analysisReport.methodology_summary">
            <template #header><span>研究方法</span></template>
            <p>{{ analysisReport.methodology_summary }}</p>
          </el-card>
          <el-card shadow="never" class="report-card" v-if="analysisReport.population">
            <template #header><span>研究对象</span></template>
            <p>{{ analysisReport.population }}</p>
          </el-card>
        </div>

        <el-card shadow="never" class="report-card" v-if="analysisReport.clinical_significance">
          <template #header><span>临床意义</span></template>
          <p>{{ analysisReport.clinical_significance }}</p>
        </el-card>

        <el-card shadow="never" class="report-card" v-if="analysisReport.key_data_points?.length">
          <template #header><span>核心数据</span></template>
          <el-table :data="analysisReport.key_data_points" size="small" stripe>
            <el-table-column prop="label" label="指标" />
            <el-table-column prop="value" label="数值" />
            <el-table-column prop="source" label="来源" />
          </el-table>
        </el-card>

        <el-card shadow="never" class="report-card highlight-card" v-if="analysisReport.suggested_topics?.length">
          <template #header>
            <div class="report-header">
              <el-icon color="#e6a23c"><Promotion /></el-icon>
              <span>建议科普选题</span>
            </div>
          </template>
          <div class="topic-chips">
            <el-tag
              v-for="(t, i) in analysisReport.suggested_topics"
              :key="i"
              :type="form.topic === t ? 'success' : 'warning'"
              :effect="form.topic === t ? 'dark' : 'plain'"
              size="large"
              class="topic-tag"
              @click="useSuggestedTopic(t)"
            >
              <el-icon v-if="form.topic === t" style="margin-right: 4px;"><CircleCheckFilled /></el-icon>
              {{ t }}
            </el-tag>
          </div>
          <p class="hint">点击选题将自动跳转到文章配置</p>
        </el-card>

        <el-card shadow="never" class="report-card" v-if="analysisReport.writing_angles?.length">
          <template #header><span>写作角度</span></template>
          <ul class="report-list">
            <li v-for="(a, i) in analysisReport.writing_angles" :key="i">{{ a }}</li>
          </ul>
        </el-card>

        <el-card shadow="never" class="report-card" v-if="analysisReport.limitations?.length">
          <template #header><span>局限性</span></template>
          <ul class="report-list muted">
            <li v-for="(l, i) in analysisReport.limitations" :key="i">{{ l }}</li>
          </ul>
        </el-card>
      </div>

      <div v-if="analysisError" class="analysis-error">
        <el-alert :title="analysisError" type="error" show-icon :closable="false" />
      </div>

      <div class="step-actions">
        <el-button @click="goBackToLiterature">重选文献</el-button>
        <el-button type="primary" @click="proceedToConfig" :disabled="analyzing">
          开始写作配置
        </el-button>
      </div>
    </div>

    <!-- ═══ Step 3: 文章配置（原有表单） ═══ -->
    <div v-show="currentStep === 2" class="step-content">
      <div class="step-header">
        <h3>文章配置</h3>
        <p class="step-desc" v-if="selectedPapers.length">
          已绑定 {{ selectedPapers.length }} 篇参考文献，配置科普写作参数后开始创作
        </p>
        <p class="step-desc" v-else>配置科普写作参数</p>
      </div>

      <el-form :model="form" label-width="100px" style="max-width: 720px;">
        <el-form-item label="科普形式" required>
          <div class="format-mode">
            <el-switch v-model="platformFirst" active-text="平台优先" inactive-text="形式优先" />
          </div>
          <FormatPicker
            v-model="form.content_format"
            :platform="form.platform"
            :matrix="formatMatrix"
            :platform-first="platformFirst"
            @update:platform="form.platform = $event"
          />
        </el-form-item>
        <el-form-item label="主题" required>
          <el-input v-model="form.topic" placeholder="如：糖尿病日常管理" />
          <div v-if="analysisReport?.suggested_topics?.length" class="topic-suggestions">
            <span class="suggestions-label">分析建议：</span>
            <el-tag
              v-for="(t, i) in analysisReport.suggested_topics"
              :key="i"
              size="small"
              :type="form.topic === t ? 'success' : 'info'"
              :effect="form.topic === t ? 'dark' : 'plain'"
              class="suggestion-tag"
              @click="form.topic = t"
            >{{ t }}</el-tag>
          </div>
        </el-form-item>
        <el-form-item v-if="showTargetAudience" label="目标受众">
          <el-select v-model="form.target_audience" placeholder="选择受众">
            <el-option label="公众" value="public" />
            <el-option label="患者" value="patient" />
            <el-option label="学生" value="student" />
            <el-option label="专业人士" value="professional" />
            <el-option label="儿童" value="children" />
          </el-select>
          <span v-if="analysisReport?.suggested_audience" class="field-hint">
            分析建议：{{ audienceLabel(analysisReport.suggested_audience) }}
          </span>
        </el-form-item>
        <el-form-item v-if="showReadingLevel" label="阅读难度">
          <el-select v-model="form.reading_level" placeholder="选择难度" clearable>
            <el-option label="通俗" value="layman" />
            <el-option label="专业" value="professional" />
          </el-select>
        </el-form-item>
        <el-form-item label="选择专科">
          <div class="specialty-picker">
            <el-radio-group v-model="form.specialty" class="specialty-options">
              <el-radio
                v-for="opt in SPECIALTY_OPTIONS"
                :key="opt.value"
                :value="opt.value"
                border
              >
                <span v-if="settingsStore.hasCustomSpecialty(opt.value)" class="custom-badge">
                  {{ opt.label }} ✦定制
                </span>
                <span v-else>{{ opt.label }}</span>
              </el-radio>
            </el-radio-group>
          </div>
          <span v-if="analysisReport?.suggested_specialty" class="field-hint">
            分析建议：{{ analysisReport.suggested_specialty }}
          </span>
          <div v-if="settingsStore.isBasic" class="upgrade-hint">
            当前使用通用预置内容，如需{{ form.specialty || '学科' }}专属词典和高质量示例，可升级为定制版
          </div>
          <div v-else-if="form.specialty && settingsStore.hasCustomSpecialty(form.specialty)" class="specialty-pack-info">
            ✦ {{ form.specialty }}：专属词典 {{ specialtyStats.terms }} 条 · 示例 {{ specialtyStats.examples }} 个
            <span v-if="specialtyStats.docs">· 知识库 {{ specialtyStats.docs }} 份文献</span>
            <span v-if="specialtyStats.updated_at"> · 最后更新 {{ specialtyStats.updated_at }}</span>
          </div>
        </el-form-item>
        <el-form-item label="目标字数">
          <div class="word-count-picker">
            <el-radio-group v-model="form.target_word_count">
              <el-radio-button
                v-for="opt in wordCountOptions"
                :key="opt.value"
                :value="opt.value"
              >{{ opt.label }}</el-radio-button>
            </el-radio-group>
            <el-input-number
              v-if="form.target_word_count === 0"
              v-model="customWordCount"
              :min="200"
              :max="8000"
              :step="100"
              placeholder="自定义"
              style="width: 160px; margin-left: 8px;"
            />
          </div>
          <span class="field-hint">{{ wordCountHint }}</span>
        </el-form-item>
        <el-form-item v-if="sectionOptions.length > 0" label="包含章节">
          <el-checkbox-group v-model="includedSections">
            <el-checkbox
              v-for="sec in sectionOptions"
              :key="sec.value"
              :value="sec.value"
              :disabled="sec.required"
            >{{ sec.label }}</el-checkbox>
          </el-checkbox-group>
          <span class="field-hint" v-if="skipSections.length">
            已跳过 {{ skipSections.join('、') }}，字数将重分配给其余章节
          </span>
        </el-form-item>
        <el-form-item label="模板">
          <el-select v-model="form.template_id" placeholder="选择模板（可选）" clearable>
            <el-option
              v-for="t in filteredTemplates"
              :key="t.id"
              :label="t.name"
              :value="t.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button @click="currentStep = selectedPapers.length ? 1 : 0">上一步</el-button>
          <el-button type="primary" @click="handleCreate" :loading="creating">创建文章</el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Close, Loading, DataAnalysis, CircleCheckFilled, Promotion, Document } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import FormatPicker from '@/components/common/FormatPicker.vue'
import { api, API_BASE, getLocalApiKeyHeaderForFetch } from '@/api'
import { useSettingsStore } from '@/stores/settings'
import { SPECIALTY_OPTIONS } from '@/constants/specialties'

const router = useRouter()
const settingsStore = useSettingsStore()

// ── Wizard state ──
const currentStep = ref(0)

// ── Step 1: Literature selection ──
const paperSearch = ref('')
const searching = ref(false)
const paperSearched = ref(false)
const paperResults = ref<any[]>([])
const paperTotal = ref(0)
const paperPage = ref(1)
const selectedPapers = ref<any[]>([])
const selectedPaperIds = computed(() => new Set(selectedPapers.value.map(p => p.id)))

async function searchPapers() {
  searching.value = true
  paperPage.value = 1
  try {
    const res = await api.literature.getPapers({
      q: paperSearch.value || undefined,
      page: 1,
      page_size: 20,
      sort_by: 'created_at',
      sort_dir: 'desc',
    })
    paperResults.value = res.data?.items || []
    paperTotal.value = res.data?.total || 0
    paperSearched.value = true
  } finally {
    searching.value = false
  }
}

async function loadMorePapers() {
  paperPage.value++
  try {
    const res = await api.literature.getPapers({
      q: paperSearch.value || undefined,
      page: paperPage.value,
      page_size: 20,
      sort_by: 'created_at',
      sort_dir: 'desc',
    })
    const items = res.data?.items || []
    paperResults.value.push(...items)
  } catch {
    paperPage.value--
  }
}

function togglePaper(paper: any) {
  if (selectedPaperIds.value.has(paper.id)) {
    selectedPapers.value = selectedPapers.value.filter(p => p.id !== paper.id)
  } else {
    selectedPapers.value.push(paper)
  }
}

function removePaper(id: number) {
  selectedPapers.value = selectedPapers.value.filter(p => p.id !== id)
}

// ── Step 2: Literature Analysis ──
const analyzing = ref(false)
const analysisMessage = ref('')
const analysisStreamText = ref('')
const analysisReport = ref<any>(null)
const analysisError = ref('')

async function startAnalysis() {
  currentStep.value = 1
  analyzing.value = true
  analysisMessage.value = '正在读取文献内容…'
  analysisStreamText.value = ''
  analysisReport.value = null
  analysisError.value = ''

  const paperIds = selectedPapers.value.map(p => p.id)

  try {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      ...(await getLocalApiKeyHeaderForFetch()),
    }
    const token = window.localStorage.getItem('linscio_auth_token')
    if (token) headers['Authorization'] = `Bearer ${token}`

    const resp = await fetch(`${API_BASE}/api/v1/literature/analyze`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ paper_ids: paperIds }),
    })

    if (!resp.ok || !resp.body) {
      analysisError.value = `请求失败 (${resp.status})`
      analyzing.value = false
      return
    }

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const evt = JSON.parse(line.slice(6))
          if (evt.type === 'start' || evt.type === 'progress') {
            analysisMessage.value = evt.message || ''
          } else if (evt.type === 'delta') {
            analysisStreamText.value += evt.text
          } else if (evt.type === 'report') {
            analysisReport.value = evt.data
            analysisStreamText.value = ''
          } else if (evt.type === 'report_text') {
            analysisStreamText.value = evt.text
          } else if (evt.type === 'done') {
            analyzing.value = false
            applyAnalysisSuggestions()
          } else if (evt.type === 'error') {
            analysisError.value = evt.message
            analyzing.value = false
          }
        } catch {
          // skip malformed SSE
        }
      }
    }
    analyzing.value = false
  } catch (err: any) {
    analysisError.value = err?.message || '分析请求失败'
    analyzing.value = false
  }
}

function applyAnalysisSuggestions() {
  if (!analysisReport.value) return
  const r = analysisReport.value
  if (r.suggested_topics?.[0] && !form.topic) {
    form.topic = r.suggested_topics[0]
  }
  if (r.suggested_audience) {
    form.target_audience = r.suggested_audience
  }
  if (r.suggested_specialty) {
    const match = SPECIALTY_OPTIONS.find(
      o => o.value === r.suggested_specialty || o.label === r.suggested_specialty
    )
    if (match) form.specialty = match.value
  }
}

function useSuggestedTopic(t: string) {
  form.topic = t
  ElMessage.success(`已选择选题：${t.length > 20 ? t.slice(0, 20) + '…' : t}`)
  setTimeout(() => {
    currentStep.value = 2
  }, 300)
}

function goBackToLiterature() {
  currentStep.value = 0
  analysisReport.value = null
  analysisStreamText.value = ''
  analysisError.value = ''
}

function proceedToConfig() {
  currentStep.value = 2
}

function skipLiterature() {
  currentStep.value = 2
}

// ── Step 3: Article config (original logic) ──
const creating = ref(false)
const platformFirst = ref(false)
const formatMatrix = ref<Record<string, Record<string, number>>>({})
const fieldVisibility = ref<Record<string, Record<string, boolean>>>({})

onMounted(async () => {
  searchPapers()
  try {
    const res = await api.formats.getFormats()
    formatMatrix.value = res.data?.matrix || {}
    const fmts = res.data?.formats || []
    const vis: Record<string, Record<string, boolean>> = {}
    for (const f of fmts) {
      vis[f.id] = f.field_visibility || {}
    }
    fieldVisibility.value = vis
  } catch {
    formatMatrix.value = {}
  }
})

const showTargetAudience = computed(() => {
  if (form.content_format === 'picture_book') return false
  const vis = fieldVisibility.value[form.content_format]
  return vis?.target_audience !== false
})

const showReadingLevel = computed(() => {
  const vis = fieldVisibility.value[form.content_format]
  return vis?.reading_level !== false
})

const PLATFORM_DEFAULT_WORD_COUNT: Record<string, number> = {
  wechat: 1200,
  xiaohongshu: 800,
  douyin: 300,
  journal: 3000,
  offline: 2000,
}

const form = reactive({
  content_format: 'article',
  topic: '',
  platform: 'wechat',
  target_audience: 'public',
  reading_level: null as string | null,
  specialty: '内分泌科',
  template_id: null as number | null,
  target_word_count: 1200,
})

const customWordCount = ref(1500)

const FORMAT_SECTION_CONFIGS: Record<string, { sections: { value: string; label: string; required: boolean }[]; optionalKeys: string[] }> = {
  article: {
    sections: [
      { value: 'intro', label: '引言', required: true },
      { value: 'body', label: '正文', required: true },
      { value: 'case', label: '案例', required: false },
      { value: 'qa', label: 'Q&A', required: false },
      { value: 'summary', label: '小结', required: true },
    ],
    optionalKeys: ['case', 'qa'],
  },
  story: {
    sections: [
      { value: 'hook', label: '引子', required: true },
      { value: 'development', label: '发展', required: true },
      { value: 'turning_point', label: '转折·就医', required: true },
      { value: 'science_core', label: '科普核心', required: true },
      { value: 'resolution', label: '结局', required: true },
      { value: 'action_list', label: '行动清单', required: false },
      { value: 'closing_quote', label: '结尾金句', required: false },
    ],
    optionalKeys: ['action_list', 'closing_quote'],
  },
  debunk: {
    sections: [
      { value: 'rumor_present', label: '谣言还原', required: true },
      { value: 'verdict', label: '真相判定', required: true },
      { value: 'debunk_1', label: '拆解·漏洞1', required: true },
      { value: 'debunk_2', label: '拆解·漏洞2', required: true },
      { value: 'debunk_3', label: '拆解·漏洞3', required: false },
      { value: 'correct_practice', label: '正确做法', required: true },
      { value: 'anti_fraud', label: '防骗指南', required: true },
    ],
    optionalKeys: ['debunk_3'],
  },
  qa_article: {
    sections: [
      { value: 'qa_intro', label: '问题引入', required: true },
      { value: 'qa_1', label: '问答1·入门', required: true },
      { value: 'qa_2', label: '问答2·入门', required: true },
      { value: 'qa_3', label: '问答3·进阶', required: true },
      { value: 'qa_4', label: '问答4·实操', required: false },
      { value: 'qa_5', label: '问答5·特殊', required: false },
      { value: 'qa_summary', label: '总结', required: true },
    ],
    optionalKeys: ['qa_4', 'qa_5'],
  },
  research_read: {
    sections: [
      { value: 'one_liner', label: '一句话摘要', required: true },
      { value: 'study_card', label: '研究信息卡', required: true },
      { value: 'why_matters', label: '为什么值得关注', required: true },
      { value: 'methods', label: '研究怎么做的', required: true },
      { value: 'findings', label: '核心发现', required: true },
      { value: 'implication', label: '对普通人意味着什么', required: true },
      { value: 'limitation', label: '注意事项·研究局限', required: true },
    ],
    optionalKeys: [],
  },
  comic_strip: {
    sections: [
      { value: 'planner', label: '条漫规划', required: true },
      { value: 'panel_1', label: '第1格·封面', required: true },
      { value: 'panel_2', label: '第2格·日常引入', required: true },
      { value: 'panel_3', label: '第3格·问题出现', required: true },
      { value: 'panel_4', label: '第4格·误区展示', required: true },
      { value: 'panel_5', label: '第5格·误区展示', required: true },
      { value: 'panel_6', label: '第6格·知识讲解', required: true },
      { value: 'panel_7', label: '第7格·知识讲解', required: true },
      { value: 'panel_8', label: '第8格·知识讲解', required: true },
      { value: 'panel_9', label: '第9格·正确做法', required: true },
      { value: 'panel_10', label: '第10格·正确做法', required: false },
      { value: 'panel_11', label: '第11格·正确做法', required: false },
      { value: 'panel_12', label: '第12格·总结收尾', required: false },
    ],
    optionalKeys: ['panel_10', 'panel_11', 'panel_12'],
  },
  card_series: {
    sections: [
      { value: 'series_plan', label: '系列规划', required: true },
      { value: 'cover_card', label: '封面卡', required: true },
      { value: 'card_1', label: '内容卡1', required: true },
      { value: 'card_2', label: '内容卡2', required: true },
      { value: 'card_3', label: '内容卡3', required: true },
      { value: 'card_4', label: '内容卡4', required: true },
      { value: 'card_5', label: '内容卡5', required: true },
      { value: 'card_6', label: '内容卡6', required: false },
      { value: 'card_7', label: '内容卡7', required: false },
      { value: 'ending_card', label: '结尾卡', required: true },
    ],
    optionalKeys: ['card_6', 'card_7'],
  },
  poster: {
    sections: [
      { value: 'poster_brief', label: '海报概要', required: true },
      { value: 'headline', label: '标题区', required: true },
      { value: 'body_visual', label: '主体·视觉', required: true },
      { value: 'cta_footer', label: '行动号召·底部', required: true },
      { value: 'design_spec', label: '设计规格', required: true },
    ],
    optionalKeys: [],
  },
  picture_book: {
    sections: [
      { value: 'book_plan', label: '绘本规划', required: true },
      { value: 'cover', label: '封面P1', required: true },
      { value: 'spread_1', label: '跨页1·开场P2-3', required: true },
      { value: 'spread_2', label: '跨页2·问题P4-5', required: true },
      { value: 'spread_3', label: '跨页3·展开P6-7', required: true },
      { value: 'spread_4', label: '跨页4·深入P8-9', required: true },
      { value: 'spread_5', label: '跨页5·知识核心P10-11', required: true },
      { value: 'spread_6', label: '跨页6·转折P12-13', required: false },
      { value: 'spread_7', label: '跨页7·结局P14-15', required: false },
      { value: 'back_cover', label: '封底·家长指南P16', required: true },
    ],
    optionalKeys: ['spread_6', 'spread_7'],
  },
  long_image: {
    sections: [
      { value: 'image_plan', label: '长图规划', required: true },
      { value: 'title_block', label: '封面标题区', required: true },
      { value: 'intro_block', label: '引入区', required: true },
      { value: 'core_1', label: '核心内容1', required: true },
      { value: 'core_2', label: '核心内容2', required: true },
      { value: 'core_3', label: '核心内容3', required: true },
      { value: 'core_4', label: '核心内容4', required: false },
      { value: 'tips_block', label: '实用建议区', required: true },
      { value: 'warning_block', label: '特别提醒区', required: false },
      { value: 'summary_cta', label: '总结/CTA区', required: true },
      { value: 'footer_info', label: '尾部信息区', required: true },
    ],
    optionalKeys: ['core_4', 'warning_block'],
  },
  oral_script: {
    sections: [
      { value: 'script_plan', label: '脚本规划', required: true },
      { value: 'golden_hook', label: '黄金开头(0-5s)', required: true },
      { value: 'problem_setup', label: '问题铺垫(5-20s)', required: true },
      { value: 'core_knowledge', label: '核心科普(20-50s)', required: true },
      { value: 'practical_tips', label: '实用建议(50-65s)', required: true },
      { value: 'closing_hook', label: '收尾钩子(最后10s)', required: true },
      { value: 'extras', label: '附加信息', required: true },
    ],
    optionalKeys: [],
  },
  drama_script: {
    sections: [
      { value: 'drama_plan', label: '剧本概况', required: true },
      { value: 'cast_table', label: '角色表', required: true },
      { value: 'act_1', label: '第一场·日常建立', required: true },
      { value: 'act_2', label: '第二场·冲突触发', required: true },
      { value: 'act_3', label: '第三场·错误应对', required: true },
      { value: 'act_4', label: '第四场·专业介入', required: true },
      { value: 'act_5', label: '第五场·结局升华', required: true },
      { value: 'finale', label: '终场·字幕总结', required: true },
      { value: 'filming_notes', label: '拍摄备注', required: true },
    ],
    optionalKeys: [],
  },
  storyboard: {
    sections: [
      { value: 'anim_plan', label: '动画概况', required: true },
      { value: 'char_design', label: '角色/元素设定', required: true },
      { value: 'reel_1', label: '第一幕·引入', required: true },
      { value: 'reel_2', label: '第二幕·问题呈现', required: true },
      { value: 'reel_3', label: '第三幕·机制解释', required: true },
      { value: 'reel_4', label: '第四幕·正确做法', required: true },
      { value: 'reel_5', label: '第五幕·总结收尾', required: true },
      { value: 'prod_notes', label: '制作备注', required: true },
    ],
    optionalKeys: [],
  },
  patient_handbook: {
    sections: [
      { value: 'handbook_plan', label: '手册信息', required: true },
      { value: 'cover', label: '封面', required: true },
      { value: 'disease_know', label: '认识疾病', required: true },
      { value: 'treatment', label: '治疗方案', required: true },
      { value: 'daily_care', label: '日常管理', required: true },
      { value: 'followup', label: '复诊与随访', required: true },
      { value: 'emergency', label: '紧急情况', required: true },
      { value: 'faq', label: '常见问题', required: true },
      { value: 'back_cover', label: '封底', required: true },
    ],
    optionalKeys: [],
  },
}

const sectionOptions = computed(() => {
  const cfg = FORMAT_SECTION_CONFIGS[form.content_format]
  return cfg ? cfg.sections : []
})

const includedSections = ref<string[]>([])
watch(() => form.content_format, (fmt) => {
  const cfg = FORMAT_SECTION_CONFIGS[fmt]
  if (cfg) {
    includedSections.value = cfg.sections.map(s => s.value)
  } else {
    includedSections.value = []
  }
}, { immediate: true })

const skipSections = computed(() => {
  const cfg = FORMAT_SECTION_CONFIGS[form.content_format]
  if (!cfg) return []
  const labelMap: Record<string, string> = {}
  cfg.sections.forEach(s => { labelMap[s.value] = s.label })
  return cfg.optionalKeys
    .filter(s => !includedSections.value.includes(s))
    .map(s => labelMap[s] || s)
})

const skipSectionTypes = computed(() => {
  const cfg = FORMAT_SECTION_CONFIGS[form.content_format]
  if (!cfg) return []
  return cfg.optionalKeys.filter(s => !includedSections.value.includes(s))
})

const wordCountOptions = computed(() => {
  const base = [
    { label: '短篇 (~800)', value: 800 },
    { label: '中篇 (~1200)', value: 1200 },
    { label: '长篇 (~2000)', value: 2000 },
    { label: '投稿 (~3000)', value: 3000 },
    { label: '自定义', value: 0 },
  ]
  return base
})

const FORMAT_WORD_RATIOS: Record<string, Record<string, number>> = {
  article: { intro: 0.10, body: 0.45, case: 0.0, qa: 0.22, summary: 0.15 },
  story: { hook: 0.08, development: 0.22, turning_point: 0.16, science_core: 0.27, resolution: 0.14, action_list: 0.08, closing_quote: 0.05 },
  debunk: { rumor_present: 0.11, verdict: 0.05, debunk_1: 0.15, debunk_2: 0.15, debunk_3: 0.15, correct_practice: 0.18, anti_fraud: 0.09 },
  qa_article: { qa_intro: 0.03, qa_1: 0.18, qa_2: 0.18, qa_3: 0.18, qa_4: 0.18, qa_5: 0.18, qa_summary: 0.07 },
  research_read: { one_liner: 0.03, study_card: 0.05, why_matters: 0.15, methods: 0.20, findings: 0.27, implication: 0.18, limitation: 0.12 },
}

const FORMAT_HINT_SECTIONS: Record<string, { key: string; label: string }[]> = {
  article: [
    { key: 'body', label: '正文' },
    { key: 'qa', label: 'Q&A' },
    { key: 'summary', label: '小结' },
  ],
  story: [
    { key: 'development', label: '发展' },
    { key: 'science_core', label: '科普核心' },
    { key: 'turning_point', label: '转折·就医' },
    { key: 'resolution', label: '结局' },
  ],
  debunk: [
    { key: 'debunk_1', label: '拆解1' },
    { key: 'debunk_2', label: '拆解2' },
    { key: 'debunk_3', label: '拆解3' },
    { key: 'correct_practice', label: '正确做法' },
  ],
  qa_article: [
    { key: 'qa_1', label: '问答1' },
    { key: 'qa_2', label: '问答2' },
    { key: 'qa_3', label: '问答3' },
    { key: 'qa_4', label: '问答4' },
    { key: 'qa_5', label: '问答5' },
  ],
  research_read: [
    { key: 'why_matters', label: '关注理由' },
    { key: 'methods', label: '方法' },
    { key: 'findings', label: '发现' },
    { key: 'implication', label: '意义' },
    { key: 'limitation', label: '局限' },
  ],
}

const wordCountHint = computed(() => {
  const wc = form.target_word_count === 0 ? customWordCount.value : form.target_word_count
  if (!wc) return ''
  const fmt = form.content_format
  const ratios = FORMAT_WORD_RATIOS[fmt]
  if (!ratios) return `目标 ${wc} 字`
  const skip = new Set(skipSectionTypes.value)
  const activeTotal = Object.entries(ratios).reduce((s, [k, v]) => s + (v > 0 && !skip.has(k) ? v : 0), 0)
  const totalPositive = Object.values(ratios).reduce((s, v) => s + (v > 0 ? v : 0), 0)
  const adj = (key: string) => activeTotal > 0 ? Math.round(wc * ratios[key] / activeTotal * totalPositive) : 0
  const hintSections = FORMAT_HINT_SECTIONS[fmt] || []
  const parts = hintSections
    .filter(s => !skip.has(s.key))
    .map(s => `${s.label} ~${adj(s.key)}字`)
  return parts.length ? `预计分配：${parts.join(' · ')}` : `目标 ${wc} 字`
})

const specialtyStats = computed(() => {
  if (!form.specialty) return { terms: 0, examples: 0, docs: 0, updated_at: undefined }
  return settingsStore.license.specialtyStats[form.specialty] ?? { terms: 0, examples: 0, docs: 0, updated_at: undefined }
})

const templates = ref<any[]>([])
const filteredTemplates = computed(() =>
  templates.value.filter((t: any) => t.content_format === form.content_format)
)

watch(() => form.content_format, async (fmt) => {
  if (fmt === 'picture_book') form.target_audience = 'children'
  const res = await api.templates.getTemplates(form.content_format)
  templates.value = res.data?.items || []
}, { immediate: true })

watch(() => form.platform, (plat) => {
  const defaultWc = PLATFORM_DEFAULT_WORD_COUNT[plat] || 1500
  if (form.target_word_count !== 0) {
    form.target_word_count = defaultWc
  }
})

const AUDIENCE_LABELS: Record<string, string> = {
  public: '公众',
  patient: '患者',
  student: '学生',
  professional: '专业人士',
  children: '儿童',
}

function audienceLabel(key: string) {
  return AUDIENCE_LABELS[key] || key
}

async function handleCreate() {
  if (!form.topic?.trim()) {
    ElMessage.warning('请填写主题')
    return
  }
  creating.value = true
  try {
    const finalWordCount = form.target_word_count === 0 ? customWordCount.value : form.target_word_count
    const res = await api.medcomm.createArticle({
      ...form,
      target_word_count: finalWordCount,
      skip_sections: skipSectionTypes.value.length ? skipSectionTypes.value : undefined,
      default_model: settingsStore.defaultModel,
      analysis_report: analysisReport.value || undefined,
    })
    const id = res.data?.id
    if (id) {
      if (selectedPapers.value.length) {
        try {
          await api.literature.bindPapers(id, {
            paper_ids: selectedPapers.value.map(p => p.id),
          })
        } catch (e) {
          console.warn('Auto-bind papers failed:', e)
        }
      }
      router.push(`/medcomm/article/${id}`)
    }
  } finally {
    creating.value = false
  }
}
</script>

<style scoped>
.new-article {
  padding: 2rem;
  max-width: 960px;
  margin: 0 auto;
}

h2 {
  margin-bottom: 1.5rem;
}

.wizard-steps {
  margin-bottom: 2rem;
}

.step-content {
  min-height: 300px;
}

.step-header h3 {
  margin: 0 0 0.25rem;
  font-size: 1.1rem;
}

.step-desc {
  color: #666;
  font-size: 0.9rem;
  margin: 0 0 1.5rem;
}

/* ── Step 1 ── */
.search-bar {
  margin-bottom: 1rem;
}

.section-label {
  font-size: 0.85rem;
  font-weight: 600;
  color: #999;
  margin: 0.75rem 0 0.5rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.selected-papers {
  margin-bottom: 1rem;
}

.paper-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.3rem 0.6rem;
  margin: 0.2rem;
  background: #ecf5ff;
  border: 1px solid #b3d8ff;
  border-radius: 4px;
  font-size: 0.85rem;
}

.chip-title {
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chip-meta {
  color: #999;
  font-size: 0.8rem;
}

.chip-icon {
  font-size: 14px;
  flex-shrink: 0;
}

.chip-icon.text-success {
  color: #67c23a;
}

.chip-icon.text-muted {
  color: #c0c4cc;
}

.chip-remove {
  cursor: pointer;
  color: #999;
  font-size: 14px;
}

.chip-remove:hover {
  color: #f56c6c;
}

.fulltext-tag {
  margin-left: 0.4rem;
  vertical-align: middle;
}

.paper-list {
  max-height: 400px;
  overflow-y: auto;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 0.5rem;
}

.paper-item {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.75rem;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}

.paper-item:hover {
  background: #f5f7fa;
}

.paper-item.selected {
  background: #ecf5ff;
}

.paper-info {
  flex: 1;
  min-width: 0;
}

.paper-title {
  font-weight: 500;
  line-height: 1.4;
}

.paper-meta {
  display: flex;
  gap: 0.75rem;
  color: #999;
  font-size: 0.8rem;
  margin-top: 0.25rem;
}

.paper-meta .doi {
  color: #409eff;
  font-family: monospace;
  font-size: 0.75rem;
}

.load-more {
  text-align: center;
  padding: 0.5rem;
}

/* ── Step 2 ── */
.analysis-loading {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1.5rem;
  background: #f0f9ff;
  border-radius: 8px;
  color: #0369a1;
  margin-bottom: 1rem;
}

.analysis-stream {
  margin-bottom: 1rem;
}

.stream-text {
  background: #fafafa;
  border: 1px solid #eee;
  border-radius: 8px;
  padding: 1rem;
  font-size: 0.85rem;
  line-height: 1.6;
  white-space: pre-wrap;
  max-height: 400px;
  overflow-y: auto;
}

.analysis-report {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.report-card {
  border-radius: 8px;
}

.report-card :deep(.el-card__header) {
  padding: 0.75rem 1rem;
  font-weight: 600;
  font-size: 0.95rem;
}

.report-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.report-topic {
  font-size: 1.05rem;
  font-weight: 500;
  color: #333;
  margin: 0;
}

.report-list {
  margin: 0;
  padding-left: 1.25rem;
}

.report-list li {
  margin-bottom: 0.5rem;
  line-height: 1.5;
}

.report-list.muted {
  color: #999;
}

.report-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.highlight-card {
  border: 1px solid #faecd8;
  background: #fdf6ec;
}

.topic-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.topic-tag {
  cursor: pointer;
  transition: transform 0.1s;
}

.topic-tag:hover {
  transform: scale(1.03);
}

.hint {
  margin: 0.5rem 0 0;
  font-size: 0.8rem;
  color: #999;
}

.analysis-error {
  margin-bottom: 1rem;
}

/* ── Step 3 ── */
.topic-suggestions {
  margin-top: 0.5rem;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.suggestions-label {
  font-size: 0.8rem;
  color: #999;
}

.suggestion-tag {
  cursor: pointer;
}

.suggestion-tag:hover {
  color: #409eff;
}

.field-hint {
  margin-left: 0.75rem;
  font-size: 0.8rem;
  color: #409eff;
}

.format-mode {
  margin-bottom: 0.5rem;
}

.specialty-picker {
  width: 100%;
}

.specialty-options {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.specialty-options :deep(.el-radio) {
  margin-right: 0;
}

.custom-badge {
  color: var(--el-color-primary);
  font-weight: 500;
}

.upgrade-hint {
  margin-top: 0.5rem;
  padding: 0.5rem 0.75rem;
  background: #f0f9ff;
  color: #0369a1;
  border-radius: 6px;
  font-size: 0.85rem;
}

.specialty-pack-info {
  margin-top: 0.5rem;
  font-size: 0.9rem;
  color: #059669;
}

.word-count-picker {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
}

/* ── Actions ── */
.step-actions {
  margin-top: 2rem;
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
}
</style>
