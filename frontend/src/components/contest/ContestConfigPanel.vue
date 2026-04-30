<template>
  <div class="contest-config-panel">
    <div class="source-status">
      <el-tag
        :type="statusTagType"
        effect="plain"
        size="small"
      >{{ statusText }}</el-tag>
    </div>

    <el-tabs v-model="activeTab" class="config-tabs">
      <!-- 赛制包选择 -->
      <el-tab-pane label="赛制包" name="pack">
        <div class="pack-search">
          <el-select
            v-model="selectedPackId"
            filterable
            clearable
            placeholder="搜索赛制包"
            style="width: 100%;"
            @change="onPackSelect"
          >
            <el-option
              v-for="pack in packs"
              :key="pack.id"
              :label="pack.name"
              :value="pack.id"
            >
              <div class="pack-option">
                <span>{{ pack.name }}</span>
                <el-tag size="small" type="info" effect="plain">{{ levelLabel(pack.level) }}</el-tag>
              </div>
            </el-option>
          </el-select>
        </div>
        <div v-if="selectedPack" class="pack-detail">
          <el-descriptions :column="2" size="small" border>
            <el-descriptions-item label="主办单位">{{ selectedPack.organizer || '—' }}</el-descriptions-item>
            <el-descriptions-item label="赛事级别">{{ levelLabel(selectedPack.level) }}</el-descriptions-item>
            <el-descriptions-item label="字数上限">{{ selectedPack.word_limit ? `${selectedPack.word_limit} 字` : '—' }}</el-descriptions-item>
            <el-descriptions-item label="文件格式">{{ selectedPack.file_format || '—' }}</el-descriptions-item>
            <el-descriptions-item label="配图格式">{{ selectedPack.image_format || '—' }}</el-descriptions-item>
            <el-descriptions-item label="AI 声明">{{ disclosureLabel(selectedPack.ai_disclosure) }}</el-descriptions-item>
            <el-descriptions-item v-if="selectedPack.naming_template" label="命名模板" :span="2">
              {{ selectedPack.naming_template }}
            </el-descriptions-item>
            <el-descriptions-item v-if="selectedPack.font" label="字体要求">{{ selectedPack.font }}</el-descriptions-item>
            <el-descriptions-item v-if="selectedPack.deadline" label="截止日期">{{ selectedPack.deadline }}</el-descriptions-item>
            <el-descriptions-item v-if="selectedPack.updated_at" label="最后更新">{{ selectedPack.updated_at?.slice(0, 10) }}</el-descriptions-item>
          </el-descriptions>
          <el-alert
            v-if="selectedPack.source_note"
            :title="selectedPack.source_note"
            type="warning"
            show-icon
            :closable="false"
            class="pack-warning"
          />
        </div>
        <el-empty v-if="!packs.length && packsLoaded" description="暂无赛制包" />
        <div class="missing-contest">
          <el-button text type="primary" size="small" @click="showMissingDialog = true">我没找到我的赛事</el-button>
        </div>
      </el-tab-pane>

      <!-- 上传公告解析 -->
      <el-tab-pane label="上传公告" name="parse">
        <el-upload
          :auto-upload="false"
          :show-file-list="false"
          accept=".pdf,.docx,.doc,.txt,.png,.jpg,.jpeg"
          @change="onFileSelected"
        >
          <el-button type="primary" :loading="parsing">
            {{ parsing ? '解析中...' : '选择公告文件' }}
          </el-button>
          <template #tip>
            <div class="upload-tip">支持 PDF / Word / TXT / 图片格式</div>
          </template>
        </el-upload>

        <div v-if="parsedFields.length" class="parsed-result">
          <h4>解析结果</h4>
          <el-form label-width="100px" size="small">
            <el-form-item
              v-for="field in parsedFields"
              :key="field.key"
              :label="field.label"
            >
              <div class="parsed-field">
                <el-input
                  v-model="field.value"
                  :placeholder="field.detected ? '' : '未识别'"
                  @change="onParsedFieldChange"
                />
                <el-tag
                  :type="field.detected ? 'success' : 'info'"
                  size="small"
                  effect="plain"
                  class="detect-badge"
                >{{ field.detected ? '已识别' : '未识别' }}</el-tag>
              </div>
            </el-form-item>
          </el-form>
          <div class="parsed-actions">
            <el-button size="small" type="primary" @click="applyParsedRules">确认使用</el-button>
            <el-button size="small" @click="saveAsMyRule('parsed')">保存为我的赛制</el-button>
          </div>
        </div>
      </el-tab-pane>

      <!-- 我的赛制 -->
      <el-tab-pane label="我的赛制" name="my">
        <div v-if="myRules.length" class="my-rules-list">
          <div
            v-for="r in myRules"
            :key="r.id"
            class="my-rule-item"
            @click="applyMyRule(r)"
          >
            <div class="my-rule-name">
              {{ r.name }}
              <el-tag size="small" type="info" effect="plain">{{ r.source === 'parsed' ? '公告解析' : '手工' }}</el-tag>
            </div>
            <div class="my-rule-meta">
              {{ r.updated_at?.slice(0, 10) }}
              <el-button
                v-if="!r.submitted_as_public"
                text
                type="primary"
                size="small"
                @click.stop="contributeRule(r.id)"
              >贡献为公共赛制包</el-button>
              <el-button text type="danger" size="small" @click.stop="deleteMyRule(r.id)">删除</el-button>
            </div>
          </div>
        </div>
        <el-empty v-else description="暂无保存的赛制，可在「上传公告」或「手工填写」后保存" />
      </el-tab-pane>

      <!-- 手工填写 -->
      <el-tab-pane label="手工填写" name="manual">
        <el-form :model="manualForm" label-width="100px" size="small">
          <el-form-item label="字数上限">
            <el-input-number v-model="manualForm.word_limit" :min="500" :max="10000" :step="100" />
          </el-form-item>
          <el-form-item label="字体要求">
            <el-input v-model="manualForm.font" placeholder="如：仿宋三号" />
          </el-form-item>
          <el-form-item label="文件格式">
            <el-select v-model="manualForm.file_format" placeholder="选择提交格式">
              <el-option label="Word (docx)" value="docx" />
              <el-option label="PDF" value="pdf" />
              <el-option label="Word + PDF" value="docx+pdf" />
            </el-select>
          </el-form-item>
          <el-form-item label="配图格式">
            <el-select v-model="manualForm.image_format" placeholder="选择配图格式">
              <el-option label="JPG" value="jpg" />
              <el-option label="PNG" value="png" />
            </el-select>
          </el-form-item>
          <el-form-item label="命名模板">
            <el-input v-model="manualForm.naming_template" placeholder="如：单位-科室-第一作者-作品名" />
          </el-form-item>
          <el-form-item label="AI 声明">
            <el-select v-model="manualForm.ai_disclosure">
              <el-option label="强制要求" value="required" />
              <el-option label="建议声明" value="recommended" />
              <el-option label="无要求" value="none" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" size="small" @click="applyManualRules">确认使用</el-button>
            <el-button size="small" @click="saveAsMyRule('manual')">保存为我的赛制</el-button>
          </el-form-item>
        </el-form>
      </el-tab-pane>
    </el-tabs>

    <!-- 我没找到我的赛事 -->
    <el-dialog v-model="showMissingDialog" title="反馈缺失赛事" width="400px" destroy-on-close>
      <el-form label-width="80px" size="small">
        <el-form-item label="赛事名称" required>
          <el-input v-model="missingForm.contest_name" placeholder="如：第五届健康科普大赛" />
        </el-form-item>
        <el-form-item label="补充说明">
          <el-input v-model="missingForm.description" type="textarea" :rows="2" placeholder="主办单位、来源链接等（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showMissingDialog = false">取消</el-button>
        <el-button type="primary" :loading="reportingMissing" @click="submitMissingReport">提交</el-button>
      </template>
    </el-dialog>

    <!-- 保存为我的赛制 -->
    <el-dialog v-model="showSaveDialog" title="保存为我的赛制" width="380px" destroy-on-close>
      <el-input v-model="saveRuleName" placeholder="赛制名称（如：2026 健康中国大赛）" />
      <template #footer>
        <el-button @click="showSaveDialog = false">取消</el-button>
        <el-button type="primary" :loading="savingRule" @click="confirmSaveRule">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/api'

const props = defineProps<{
  contestPackId: number | null
  contestRuleSource: string | null
  contestCustomRules: Record<string, any> | null
}>()

const emit = defineEmits<{
  'update:contestPackId': [v: number | null]
  'update:contestRuleSource': [v: string | null]
  'update:contestCustomRules': [v: Record<string, any> | null]
  'wordLimitChange': [v: number]
}>()

const activeTab = ref('pack')

// ── Pack selection ──
const packs = ref<any[]>([])
const packsLoaded = ref(false)
const selectedPackId = ref<number | null>(null)
const selectedPack = ref<any>(null)

onMounted(async () => {
  try {
    const res = await api.contest.getPacks()
    packs.value = res.data?.items || []
    packsLoaded.value = true
  } catch {
    packsLoaded.value = true
  }
})

async function onPackSelect(packId: number | null) {
  if (!packId) {
    selectedPack.value = null
    emit('update:contestPackId', null)
    emit('update:contestRuleSource', null)
    return
  }
  try {
    const res = await api.contest.getPack(packId)
    selectedPack.value = res.data
    emit('update:contestPackId', packId)
    emit('update:contestRuleSource', 'pack')
    if (res.data?.word_limit) {
      emit('wordLimitChange', res.data.word_limit)
    }
  } catch {
    selectedPack.value = null
  }
}

// ── Announcement parsing ──
const parsing = ref(false)
const parsedFields = ref<Array<{ key: string; label: string; value: string | null; detected: boolean }>>([])

async function onFileSelected(uploadFile: any) {
  if (!uploadFile?.raw) return
  parsing.value = true
  try {
    const formData = new FormData()
    formData.append('file', uploadFile.raw)
    const res = await api.contest.parseAnnouncement(formData)
    parsedFields.value = res.data?.fields || []
  } catch {
    parsedFields.value = []
  } finally {
    parsing.value = false
  }
}

function onParsedFieldChange() {
  // Mark user-edited fields as confirmed
}

function applyParsedRules() {
  const rules: Record<string, any> = {}
  for (const f of parsedFields.value) {
    if (f.value) rules[f.key] = f.value
  }
  emit('update:contestRuleSource', 'parsed')
  emit('update:contestCustomRules', rules)
  emit('update:contestPackId', null)
  if (rules.word_limit) {
    emit('wordLimitChange', parseInt(rules.word_limit))
  }
}

// ── Manual form ──
const manualForm = reactive({
  word_limit: 2000,
  font: '',
  file_format: 'docx',
  image_format: 'jpg',
  naming_template: '',
  ai_disclosure: 'none',
})

function applyManualRules() {
  const rules: Record<string, any> = {}
  for (const [k, v] of Object.entries(manualForm)) {
    if (v !== '' && v !== null && v !== undefined) rules[k] = v
  }
  emit('update:contestRuleSource', 'manual')
  emit('update:contestCustomRules', rules)
  emit('update:contestPackId', null)
  if (manualForm.word_limit) {
    emit('wordLimitChange', manualForm.word_limit)
  }
}

// ── My rules ──
const myRules = ref<any[]>([])

async function loadMyRules() {
  try {
    const res = await api.contest.getMyRules()
    myRules.value = res.data?.items || []
  } catch { /* ignore */ }
}

onMounted(() => { loadMyRules() })

function applyMyRule(rule: any) {
  emit('update:contestRuleSource', rule.source)
  emit('update:contestCustomRules', rule.rules)
  emit('update:contestPackId', null)
  if (rule.rules?.word_limit) {
    emit('wordLimitChange', parseInt(rule.rules.word_limit))
  }
  ElMessage.success(`已应用赛制「${rule.name}」`)
}

async function deleteMyRule(ruleId: number) {
  try {
    await api.contest.deleteMyRule(ruleId)
    myRules.value = myRules.value.filter(r => r.id !== ruleId)
    ElMessage.success('已删除')
  } catch { /* ignore */ }
}

async function contributeRule(ruleId: number) {
  try {
    await api.contest.contributeMyRule(ruleId)
    const r = myRules.value.find(r => r.id === ruleId)
    if (r) r.submitted_as_public = true
    ElMessage.success('已提交，运营审核后将加入公共赛制包')
  } catch { /* ignore */ }
}

// ── Save as my rule dialog ──
const showSaveDialog = ref(false)
const saveRuleName = ref('')
const savingRule = ref(false)
let pendingSaveSource = 'manual'

function saveAsMyRule(source: string) {
  pendingSaveSource = source
  saveRuleName.value = ''
  showSaveDialog.value = true
}

async function confirmSaveRule() {
  if (!saveRuleName.value.trim()) {
    ElMessage.warning('请输入赛制名称')
    return
  }
  savingRule.value = true
  try {
    let rules: Record<string, any> = {}
    if (pendingSaveSource === 'parsed') {
      for (const f of parsedFields.value) {
        if (f.value) rules[f.key] = f.value
      }
    } else {
      for (const [k, v] of Object.entries(manualForm)) {
        if (v !== '' && v !== null && v !== undefined) rules[k] = v
      }
    }
    await api.contest.saveMyRules({
      name: saveRuleName.value.trim(),
      rules,
      source: pendingSaveSource,
    })
    ElMessage.success('已保存为我的赛制')
    showSaveDialog.value = false
    await loadMyRules()
  } finally {
    savingRule.value = false
  }
}

// ── Missing contest report ──
const showMissingDialog = ref(false)
const reportingMissing = ref(false)
const missingForm = reactive({ contest_name: '', description: '' })

async function submitMissingReport() {
  if (!missingForm.contest_name.trim()) {
    ElMessage.warning('请输入赛事名称')
    return
  }
  reportingMissing.value = true
  try {
    await api.contest.reportMissing(missingForm)
    ElMessage.success('感谢反馈！我们将尽快收录该赛事')
    showMissingDialog.value = false
    missingForm.contest_name = ''
    missingForm.description = ''
  } finally {
    reportingMissing.value = false
  }
}

// ── Status display ──
const statusText = computed(() => {
  if (props.contestRuleSource === 'pack' && selectedPack.value) {
    return `已绑定：${selectedPack.value.name}（赛制包）`
  }
  if (props.contestRuleSource === 'parsed') return '已配置（公告解析）'
  if (props.contestRuleSource === 'manual') return '已配置（手工填写）'
  return '未绑定赛制'
})

const statusTagType = computed(() => {
  if (props.contestRuleSource) return 'success'
  return 'warning'
})

function levelLabel(level: string | null): string {
  const map: Record<string, string> = {
    national: '全国级',
    provincial: '省级',
    association: '学会级',
  }
  return map[level || ''] || level || '—'
}

function disclosureLabel(val: string | null): string {
  const map: Record<string, string> = {
    required: '强制要求',
    recommended: '建议声明',
    none: '无要求',
  }
  return map[val || ''] || val || '—'
}
</script>

<style scoped>
.contest-config-panel {
  width: 100%;
}

.source-status {
  margin-bottom: 0.75rem;
}

.config-tabs :deep(.el-tabs__header) {
  margin-bottom: 1rem;
}

.pack-search {
  margin-bottom: 1rem;
}

.pack-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.pack-detail {
  margin-top: 0.75rem;
}

.pack-warning {
  margin-top: 0.75rem;
}

.upload-tip {
  font-size: 0.8rem;
  color: #999;
  margin-top: 0.5rem;
}

.parsed-result {
  margin-top: 1rem;
  padding: 1rem;
  background: #fafafa;
  border-radius: 8px;
}

.parsed-result h4 {
  margin: 0 0 0.75rem;
  font-size: 0.95rem;
}

.parsed-field {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
}

.parsed-field .el-input {
  flex: 1;
}

.detect-badge {
  flex-shrink: 0;
}

.parsed-actions {
  margin-top: 0.75rem;
  text-align: right;
}

.missing-contest {
  margin-top: 0.5rem;
  text-align: center;
}

.my-rules-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.my-rule-item {
  padding: 0.5rem 0.75rem;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  cursor: pointer;
  transition: border-color 0.15s;
}

.my-rule-item:hover {
  border-color: #409eff;
}

.my-rule-name {
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.my-rule-meta {
  font-size: 0.8rem;
  color: #999;
  margin-top: 0.25rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
</style>
