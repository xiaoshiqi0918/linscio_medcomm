<template>
  <div class="licenses">
    <h2>授权码管理</h2>
    <el-card>
      <div class="toolbar">
        <el-button type="primary" @click="openBatch">批量生成</el-button>
        <el-button @click="exportCsv">导出 CSV</el-button>
      </div>
      <el-table :data="list" v-loading="loading" style="margin-top:16px">
        <el-table-column label="授权码" width="260">
          <template #default="{ row }">
            <span class="code-cell">{{ row.code }}</span>
            <el-button link type="primary" size="small" @click="copyCode(row.code)">复制</el-button>
          </template>
        </el-table-column>
        <el-table-column label="套餐" width="90">
          <template #default="{ row }">{{ row.plan_name || row.plan_type || '—' }}</template>
        </el-table-column>
        <el-table-column label="周期" width="72">
          <template #default="{ row }">{{ row.period_name || '—' }}</template>
        </el-table-column>
        <el-table-column label="机器数" width="88">
          <template #default="{ row }">
            {{ formatLimit(row.machine_bound_count, row.machine_limit, '台') }}
          </template>
        </el-table-column>
        <el-table-column label="并发数" width="88">
          <template #default="{ row }">
            {{ formatLimit(row.instance_active_count, row.concurrent_limit, '') }}
          </template>
        </el-table-column>
        <el-table-column label="本月拉取" width="95">
          <template #default="{ row }">
            {{ formatLimit(row.pull_used_this_month, row.pull_limit_monthly, '次') }}
          </template>
        </el-table-column>
        <el-table-column label="有效期至" width="120">
          <template #default="{ row }">
            {{ formatDate(row.expires_at) }}
            <span v-if="row.expires_at" class="days-left" :class="daysLeftClass(row)">{{ daysLeft(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="绑定用户" width="100">
          <template #default="{ row }">{{ row.assigned_username || '—' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="92">
          <template #default="{ row }">
            <el-tag v-if="row.is_revoked" type="info">已作废</el-tag>
            <el-tag v-else-if="row.status === '已过期'" type="danger">已过期</el-tag>
            <el-tag v-else-if="row.is_used" type="success">已激活</el-tag>
            <el-tag v-else type="warning">未使用</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="showDetail(row)">详情</el-button>
            <el-button
              v-if="!row.is_revoked"
              link
              type="primary"
              size="small"
              @click="showExtend(row)"
            >延期</el-button>
            <el-button
              v-if="!row.is_used && !row.is_revoked"
              link
              type="danger"
              size="small"
              @click="revoke(row)"
            >作废</el-button>
            <span v-if="row.is_revoked">—</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 批量生成：分级授权方案（套餐 + 周期） -->
    <el-dialog v-model="showBatch" title="批量生成授权码" width="500" @open="onBatchDialogOpen">
      <el-alert
        v-if="!hasPlansAndPeriods"
        type="warning"
        show-icon
        class="batch-seed-alert"
      >
        <template #title>暂无套餐与周期数据</template>
        <p class="batch-seed-desc">
          <strong>请先在「套餐与周期」中添加套餐和付费周期</strong>，然后即可在此批量生成授权码。
        </p>
        <p class="batch-seed-link">
          <router-link to="/plans-periods">前往 套餐与周期 →</router-link>
        </p>
        <div class="batch-seed-commands">
          <div class="batch-seed-label">若曾使用预置脚本，也可在服务器执行：</div>
          <code class="batch-seed-cmd">docker compose exec linscio-api python scripts/seed_plans_periods_modules.py</code>
          <div class="batch-seed-label">本地 API（在 api 目录下）：</div>
          <code class="batch-seed-cmd">python scripts/seed_plans_periods_modules.py</code>
        </div>
      </el-alert>
      <el-form v-else :model="batchForm" label-width="110">
        <el-form-item label="套餐类型">
          <el-select v-model="batchForm.plan_code" placeholder="请选择套餐" style="width:100%">
            <el-option
              v-for="p in plans"
              :key="p.code"
              :label="p.name"
              :value="p.code"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="selectedPlanLimit" label="套餐限制">
          <div class="plan-limit-desc">
            {{ selectedPlanLimit }}
            <div class="plan-limit-hint">激活后按套餐享有对应镜像 Tag 与拉取限制；模块权限由「模块权限配置」决定。</div>
          </div>
        </el-form-item>
        <el-form-item label="付费周期">
          <el-radio-group v-model="batchForm.period_code">
            <el-radio
              v-for="pr in periodsFiltered"
              :key="pr.code"
              :value="pr.code"
            >{{ pr.name }}</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="生成数量">
          <el-input-number v-model="batchForm.count" :min="1" :max="100" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="batchForm.notes" type="textarea" rows="2" placeholder="如：2026年Q1 渠道推广批次" />
        </el-form-item>
        <el-form-item label="预览样例">
          <div class="preview-row">
            <el-button size="small" :loading="previewLoading" @click="doPreview">生成一条样例</el-button>
            <span v-if="previewCode" class="preview-code">{{ previewCode }}</span>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showBatch = false">取消</el-button>
        <el-button
          type="primary"
          :loading="batchLoading"
          :disabled="!hasPlansAndPeriods"
          @click="doBatch"
        >生成</el-button>
      </template>
    </el-dialog>

    <!-- 生成结果：可复制或下载 CSV -->
    <el-dialog v-model="showCodes" title="生成的授权码" width="560">
      <p class="tip">请妥善保存，以下授权码仅显示一次。可复制全部或下载 CSV。</p>
      <el-input type="textarea" :model-value="generatedCodes" readonly rows="10" />
      <template #footer>
        <el-button type="primary" @click="copyCodes">复制全部</el-button>
        <el-button @click="downloadGeneratedCsv">下载 CSV</el-button>
        <el-button @click="showCodes = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 授权码详情 -->
    <el-dialog v-model="showDetailVisible" title="授权码详情" width="520">
      <template v-if="detailRow">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="授权码">{{ detailRow.code }}</el-descriptions-item>
          <el-descriptions-item label="套餐">{{ detailRow.plan_name || detailRow.plan_type || '—' }}</el-descriptions-item>
          <el-descriptions-item label="周期">{{ detailRow.period_name || '—' }}</el-descriptions-item>
          <el-descriptions-item label="机器数">{{ formatLimit(detailRow.machine_bound_count, detailRow.machine_limit, '台') }}</el-descriptions-item>
          <el-descriptions-item label="并发数">{{ formatLimit(detailRow.instance_active_count, detailRow.concurrent_limit, '') }}</el-descriptions-item>
          <el-descriptions-item label="本月拉取">{{ formatLimit(detailRow.pull_used_this_month, detailRow.pull_limit_monthly, '次') }}</el-descriptions-item>
          <el-descriptions-item label="有效期至">{{ formatDate(detailRow.expires_at) }} {{ daysLeft(detailRow) }}</el-descriptions-item>
          <el-descriptions-item label="绑定用户">{{ detailRow.assigned_username || '—' }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ detailRow.status }}</el-descriptions-item>
          <el-descriptions-item label="备注">{{ detailRow.notes || '—' }}</el-descriptions-item>
        </el-descriptions>
      </template>
    </el-dialog>

    <!-- 延期 -->
    <el-dialog v-model="showExtendVisible" title="授权码延期" width="380">
      <p v-if="extendRow" class="extend-hint">授权码：{{ extendRow.code }}，当前有效期至 {{ formatDate(extendRow.expires_at) }}</p>
      <el-form label-width="100">
        <el-form-item label="延期月数">
          <el-radio-group v-model="extendMonths">
            <el-radio :value="1">1 个月</el-radio>
            <el-radio :value="3">3 个月</el-radio>
            <el-radio :value="6">6 个月</el-radio>
            <el-radio :value="12">12 个月</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showExtendVisible = false">取消</el-button>
        <el-button type="primary" :loading="extendLoading" @click="doExtend">确认延期</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { admin } from '../api'

const list = ref([])
const loading = ref(false)
const showBatch = ref(false)
const batchLoading = ref(false)
const showCodes = ref(false)
const generatedCodes = ref('')
const generatedList = ref([]) // 本次生成用于下载 CSV
const plans = ref([])
const periods = ref([])
const showDetailVisible = ref(false)
const detailRow = ref(null)
const showExtendVisible = ref(false)
const extendRow = ref(null)
const extendMonths = ref(12)
const extendLoading = ref(false)
const previewLoading = ref(false)
const previewCode = ref('')

const batchForm = reactive({
  plan_code: 'professional',
  period_code: 'yearly',
  count: 10,
  notes: '',
})

const periodsFiltered = computed(() => periods.value.filter(p => p.code !== 'internal'))

const hasPlansAndPeriods = computed(() =>
  plans.value.length > 0 && periodsFiltered.value.length > 0
)

const selectedPlanLimit = computed(() => {
  const p = plans.value.find(x => x.code === batchForm.plan_code)
  if (!p) return ''
  const ml = p.machine_limit != null ? p.machine_limit : '—'
  const cl = p.concurrent_limit != null ? p.concurrent_limit : '—'
  const pl = p.pull_limit_monthly != null && p.pull_limit_monthly > 0 ? p.pull_limit_monthly : '不限'
  return `机器数 ${ml} 台、并发数 ${cl}、月拉取 ${pl} 次`
})

function formatDate(d) {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('zh-CN')
}

function formatLimit(used, limit, unit) {
  const u = used != null ? used : '—'
  if (limit == null || limit === 0) return `${u} / ∞ ${unit}`.trim()
  return `${u} / ${limit} ${unit}`.trim()
}

function daysLeft(row) {
  if (!row || !row.expires_at) return ''
  const now = new Date()
  const end = new Date(row.expires_at)
  const days = Math.ceil((end - now) / (24 * 60 * 60 * 1000))
  if (days < 0) return `(已过期 ${-days} 天)`
  if (days === 0) return '(今日到期)'
  return `(剩余 ${days} 天)`
}

function daysLeftClass(row) {
  if (!row || !row.expires_at) return ''
  const end = new Date(row.expires_at)
  const days = (end - new Date()) / (24 * 60 * 60 * 1000)
  if (days < 0) return 'danger'
  if (days <= 7) return 'warning'
  return ''
}

function copyCode(code) {
  navigator.clipboard.writeText(code).then(() => ElMessage.success('已复制'))
}

function openBatch() {
  showBatch.value = true
  previewCode.value = ''
}

async function onBatchDialogOpen() {
  if (plans.value.length === 0 || periods.value.length === 0) {
    await loadPlansAndPeriods()
  }
  if (plans.value.length && !plans.value.some(p => p.code === batchForm.plan_code)) {
    batchForm.plan_code = plans.value[0].code
  }
  if (periodsFiltered.value.length && !periodsFiltered.value.some(p => p.code === batchForm.period_code)) {
    batchForm.period_code = periodsFiltered.value[0].code
  }
}

async function loadPlansAndPeriods() {
  try {
    const [pRes, prRes] = await Promise.all([admin.plans(), admin.billingPeriods()])
    plans.value = pRes.data || []
    periods.value = prRes.data || []
    if (plans.value.length && !batchForm.plan_code) batchForm.plan_code = plans.value[0].code
    if (periodsFiltered.value.length && !batchForm.period_code) batchForm.period_code = periodsFiltered.value[0].code
    if (plans.value.length && !plans.value.some(p => p.code === batchForm.plan_code)) batchForm.plan_code = plans.value[0].code
    if (periodsFiltered.value.length && !periodsFiltered.value.some(p => p.code === batchForm.period_code)) batchForm.period_code = periodsFiltered.value[0].code
  } catch (_) {}
}

async function doPreview() {
  if (!batchForm.plan_code || !batchForm.period_code) {
    ElMessage.warning('请先选择套餐和付费周期')
    return
  }
  previewLoading.value = true
  previewCode.value = ''
  try {
    const { data } = await admin.licensePreview({
      plan_code: batchForm.plan_code,
      period_code: batchForm.period_code,
    })
    previewCode.value = data.sample_code || ''
    if (previewCode.value) ElMessage.success('样例仅供参考，正式生成以实际为准')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '预览失败')
  } finally {
    previewLoading.value = false
  }
}

async function load() {
  loading.value = true
  try {
    const { data } = await admin.licenses({ limit: 100 })
    list.value = data || []
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

async function doBatch() {
  if (!batchForm.plan_code || !batchForm.period_code) {
    ElMessage.warning('请选择套餐和付费周期')
    return
  }
  batchLoading.value = true
  try {
    const payload = {
      plan_code: batchForm.plan_code,
      period_code: batchForm.period_code,
      count: batchForm.count,
      notes: batchForm.notes || undefined,
    }
    const { data } = await admin.licensesBatch(payload)
    generatedCodes.value = (data.codes || []).join('\n')
    generatedList.value = data.codes || []
    showBatch.value = false
    showCodes.value = true
    load()
    ElMessage.success(`已生成 ${data.created} 个授权码`)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '生成失败')
  } finally {
    batchLoading.value = false
  }
}

function showDetail(row) {
  detailRow.value = row
  showDetailVisible.value = true
}

function showExtend(row) {
  extendRow.value = row
  extendMonths.value = 12
  showExtendVisible.value = true
}

async function doExtend() {
  if (!extendRow.value) return
  extendLoading.value = true
  try {
    await admin.licenseExtend(extendRow.value.id, { months: extendMonths.value })
    ElMessage.success('已延期')
    showExtendVisible.value = false
    extendRow.value = null
    load()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '延期失败')
  } finally {
    extendLoading.value = false
  }
}

async function revoke(row) {
  try {
    await admin.licenseRevoke(row.id)
    ElMessage.success('已作废')
    load()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}

async function exportCsv() {
  try {
    const { data } = await admin.licensesExport()
    const url = URL.createObjectURL(data)
    const a = document.createElement('a')
    a.href = url
    a.download = `licenses_${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('已导出')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '导出失败')
  }
}

function copyCodes() {
  navigator.clipboard.writeText(generatedCodes.value).then(() => ElMessage.success('已复制'))
}

function downloadGeneratedCsv() {
  if (!generatedList.value.length) return
  const p = plans.value.find(x => x.code === batchForm.plan_code)
  const planName = p?.name || batchForm.plan_code
  const periodOpt = periods.value.find(pr => pr.code === batchForm.period_code)
  const periodName = periodOpt?.name || batchForm.period_code
  const machineLimit = p?.machine_limit != null ? p.machine_limit : ''
  const concurrentLimit = p?.concurrent_limit != null ? p.concurrent_limit : ''
  const pullLimit = p?.pull_limit_monthly != null && p.pull_limit_monthly > 0 ? p.pull_limit_monthly : '不限'
  const header = '授权码,套餐,周期,机器数上限,并发数上限,月拉取上限,生成时间,备注\n'
  const now = new Date().toISOString().slice(0, 19).replace('T', ' ')
  const line = (code) => `${code},${planName},${periodName},${machineLimit},${concurrentLimit},${pullLimit},${now},${batchForm.notes || ''}\n`
  const body = generatedList.value.map(line).join('')
  const blob = new Blob(['\ufeff' + header + body], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `licenses_generated_${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('已下载')
}

onMounted(() => {
  loadPlansAndPeriods()
  load()
})
</script>

<style scoped>
.licenses { padding: 0 0 24px 0; }
.toolbar { margin-bottom: 8px; }
.tip { font-size: 13px; color: #666; margin-bottom: 12px; }
.code-cell { font-family: monospace; font-size: 12px; }
.days-left { font-size: 12px; margin-left: 4px; }
.days-left.warning { color: #e6a23c; }
.days-left.danger { color: #f56c6c; }
.extend-hint { margin-bottom: 16px; color: #666; font-size: 13px; }
.plan-limit-desc { font-size: 13px; color: #606266; }
.plan-limit-hint { font-size: 12px; color: #909399; margin-top: 6px; }
.preview-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.preview-code { font-family: monospace; font-size: 13px; color: #303133; }

.batch-seed-alert { margin-bottom: 0; }
.batch-seed-desc { margin: 0 0 10px 0; font-size: 13px; line-height: 1.5; }
.batch-seed-commands { margin-top: 8px; }
.batch-seed-label { font-size: 12px; color: #909399; margin-top: 10px; margin-bottom: 4px; }
.batch-seed-label:first-of-type { margin-top: 0; }
.batch-seed-cmd { display: block; padding: 8px 10px; background: var(--el-fill-color-light); border-radius: 4px; font-size: 12px; margin-bottom: 4px; overflow-x: auto; }
.batch-seed-link { margin: 10px 0 0 0; font-size: 14px; }
.batch-seed-link a { color: var(--el-color-primary); }
</style>
