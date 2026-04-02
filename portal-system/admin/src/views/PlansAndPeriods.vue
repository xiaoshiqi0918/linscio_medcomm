<template>
  <div class="plans-periods-page">
    <h2>套餐与周期</h2>
    <p class="desc">在此配置套餐和付费周期后，即可在「授权码管理」中批量生成授权码。请先添加至少一个套餐和一个付费周期。也可点击「加载默认套餐与周期」一键写入系统预置规则。</p>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="套餐" name="plans">
        <div class="toolbar">
          <el-button type="primary" @click="showAddPlan">新增套餐</el-button>
          <el-button :loading="seedLoading" @click="seedDefaults">加载默认套餐与周期</el-button>
        </div>
        <el-table v-loading="plansLoading" :data="plansList" size="default" border>
          <el-table-column prop="code" label="标识" width="120" />
          <el-table-column prop="name" label="名称" width="100" />
          <el-table-column prop="plan_char" label="授权码字符" width="100" align="center" />
          <el-table-column prop="machine_limit" label="机器数" width="80" align="center" />
          <el-table-column prop="concurrent_limit" label="并发数" width="80" align="center" />
          <el-table-column label="月拉取" width="90" align="center">
            <template #default="{ row }">{{ row.pull_limit_monthly != null ? row.pull_limit_monthly : '不限' }}</template>
          </el-table-column>
          <el-table-column prop="price_monthly" label="月价" width="90" align="right" />
          <el-table-column label="状态" width="80" align="center">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '停用' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="90" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="editPlan(row)">编辑</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="付费周期" name="periods">
        <div class="toolbar">
          <el-button type="primary" @click="showAddPeriod">新增周期</el-button>
        </div>
        <el-table v-loading="periodsLoading" :data="periodsList" size="default" border>
          <el-table-column prop="code" label="标识" width="120" />
          <el-table-column prop="name" label="显示名称" width="120" />
          <el-table-column prop="period_char" label="授权码字符" width="100" align="center" />
          <el-table-column prop="months" label="月数" width="80" align="center" />
          <el-table-column prop="discount_rate" label="折扣率" width="90" align="center" />
          <el-table-column label="操作" width="90" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="editPeriod(row)">编辑</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- 套餐 新增/编辑 -->
    <el-dialog v-model="planDialogVisible" :title="planForm?.id ? '编辑套餐' : '新增套餐'" width="480" @close="planForm = null">
      <el-form v-if="planForm" :model="planForm" label-width="120">
        <el-form-item label="标识(code)" required>
          <el-input v-model="planForm.code" placeholder="如 professional" :disabled="!!planForm.id" />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="planForm.name" placeholder="如 专业版" />
        </el-form-item>
        <el-form-item label="授权码字符" required>
          <el-input v-model="planForm.plan_char" placeholder="单字符，如 P" maxlength="1" style="width:80px" />
          <span class="form-hint">用于生成授权码前缀，需唯一</span>
        </el-form-item>
        <el-form-item label="机器数上限">
          <el-input-number v-model="planForm.machine_limit" :min="0" />
          <span class="form-hint">0 表示不限</span>
        </el-form-item>
        <el-form-item label="并发数上限">
          <el-input-number v-model="planForm.concurrent_limit" :min="0" />
        </el-form-item>
        <el-form-item label="月拉取上限">
          <el-input-number v-model="planForm.pull_limit_monthly" :min="0" placeholder="不填为不限" />
        </el-form-item>
        <el-form-item label="月价">
          <el-input-number v-model="planForm.price_monthly" :min="0" :precision="2" />
        </el-form-item>
        <el-form-item v-if="planForm.id" label="状态">
          <el-switch v-model="planForm.is_active" active-text="启用" inactive-text="停用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="planDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="planSaving" @click="savePlan">保存</el-button>
      </template>
    </el-dialog>

    <!-- 周期 新增/编辑 -->
    <el-dialog v-model="periodDialogVisible" :title="periodForm?.id ? '编辑周期' : '新增周期'" width="440" @close="periodForm = null">
      <el-form v-if="periodForm" :model="periodForm" label-width="120">
        <el-form-item label="标识(code)" required>
          <el-input v-model="periodForm.code" placeholder="如 yearly" :disabled="!!periodForm.id" />
        </el-form-item>
        <el-form-item label="显示名称">
          <el-input v-model="periodForm.name" placeholder="如 年付" />
        </el-form-item>
        <el-form-item label="授权码字符" required>
          <el-input v-model="periodForm.period_char" placeholder="单字符，如 Y" maxlength="1" style="width:80px" />
          <span class="form-hint">用于生成授权码，需唯一</span>
        </el-form-item>
        <el-form-item label="月数" required>
          <el-input-number v-model="periodForm.months" :min="1" />
        </el-form-item>
        <el-form-item label="折扣率">
          <el-input-number v-model="periodForm.discount_rate" :min="0" :max="1" :step="0.01" :precision="2" />
          <span class="form-hint">1=原价，0.8=8折</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="periodDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="periodSaving" @click="savePeriod">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { admin } from '../api'

const activeTab = ref('plans')
const plansList = ref([])
const periodsList = ref([])
const plansLoading = ref(false)
const periodsLoading = ref(false)
const planDialogVisible = ref(false)
const periodDialogVisible = ref(false)
const planForm = ref(null)
const periodForm = ref(null)
const planSaving = ref(false)
const periodSaving = ref(false)
const seedLoading = ref(false)

async function seedDefaults() {
  seedLoading.value = true
  try {
    const { data } = await admin.plansPeriodsSeedDefaults()
    const msg = data.added_plans || data.added_periods
      ? `已加载默认：新增 ${data.added_plans || 0} 个套餐、${data.added_periods || 0} 个周期`
      : (data.message || '默认数据已存在，未新增')
    ElMessage.success(msg)
    await loadPlans()
    await loadPeriods()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '加载默认失败')
  } finally {
    seedLoading.value = false
  }
}

async function loadPlans() {
  plansLoading.value = true
  try {
    const { data } = await admin.plansManage()
    plansList.value = Array.isArray(data) ? data.filter(Boolean) : []
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '加载套餐失败')
  } finally {
    plansLoading.value = false
  }
}

async function loadPeriods() {
  periodsLoading.value = true
  try {
    const { data } = await admin.billingPeriodsManage()
    periodsList.value = Array.isArray(data) ? data.filter(Boolean) : []
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '加载周期失败')
  } finally {
    periodsLoading.value = false
  }
}

function showAddPlan() {
  planForm.value = {
    code: '',
    name: '',
    plan_char: '',
    machine_limit: 1,
    concurrent_limit: 1,
    pull_limit_monthly: undefined,
    price_monthly: 0,
    is_active: true,
  }
  planDialogVisible.value = true
}

function editPlan(row) {
  if (!row) return
  planForm.value = {
    id: row.id,
    code: row.code,
    name: row.name,
    plan_char: row.plan_char,
    machine_limit: row.machine_limit,
    concurrent_limit: row.concurrent_limit,
    pull_limit_monthly: row.pull_limit_monthly ?? undefined,
    price_monthly: row.price_monthly,
    is_active: row.is_active,
  }
  planDialogVisible.value = true
}

async function savePlan() {
  const f = planForm.value
  if (!f || !f.code?.trim() || !f.name?.trim() || !f.plan_char?.trim()) {
    ElMessage.warning('请填写标识、名称和授权码字符')
    return
  }
  planSaving.value = true
  try {
    if (f.id) {
      await admin.planUpdate(f.id, {
        name: f.name,
        plan_char: f.plan_char,
        machine_limit: f.machine_limit,
        concurrent_limit: f.concurrent_limit,
        pull_limit_monthly: f.pull_limit_monthly ?? null,
        price_monthly: f.price_monthly,
        is_active: f.is_active,
      })
    } else {
      await admin.planCreate({
        code: f.code.trim(),
        name: f.name.trim(),
        plan_char: f.plan_char.trim(),
        machine_limit: f.machine_limit ?? 1,
        concurrent_limit: f.concurrent_limit ?? 1,
        pull_limit_monthly: f.pull_limit_monthly ?? null,
        price_monthly: f.price_monthly ?? 0,
        is_active: f.is_active !== false,
      })
    }
    ElMessage.success('已保存')
    planDialogVisible.value = false
    await loadPlans()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    planSaving.value = false
  }
}

function showAddPeriod() {
  periodForm.value = {
    code: '',
    name: '',
    period_char: '',
    months: 1,
    discount_rate: 1,
  }
  periodDialogVisible.value = true
}

function editPeriod(row) {
  if (!row) return
  periodForm.value = {
    id: row.id,
    code: row.code,
    name: row.name || '',
    period_char: row.period_char,
    months: row.months,
    discount_rate: row.discount_rate,
  }
  periodDialogVisible.value = true
}

async function savePeriod() {
  const f = periodForm.value
  if (!f || !f.code?.trim() || !f.period_char?.trim()) {
    ElMessage.warning('请填写标识和授权码字符')
    return
  }
  if (!f.months || f.months < 1) {
    ElMessage.warning('月数至少为 1')
    return
  }
  periodSaving.value = true
  try {
    if (f.id) {
      await admin.billingPeriodUpdate(f.id, {
        name: f.name?.trim() || null,
        period_char: f.period_char.trim(),
        months: f.months,
        discount_rate: f.discount_rate ?? 1,
      })
    } else {
      await admin.billingPeriodCreate({
        code: f.code.trim(),
        name: f.name?.trim() || null,
        period_char: f.period_char.trim(),
        months: f.months,
        discount_rate: f.discount_rate ?? 1,
      })
    }
    ElMessage.success('已保存')
    periodDialogVisible.value = false
    await loadPeriods()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    periodSaving.value = false
  }
}

onMounted(() => {
  loadPlans()
  loadPeriods()
})
</script>

<style scoped>
.plans-periods-page { padding: 0 0 24px 0; }
.desc { font-size: 14px; color: #666; margin: 8px 0 16px 0; }
.toolbar { margin-bottom: 16px; }
.form-hint { margin-left: 8px; font-size: 12px; color: #909399; }
</style>
