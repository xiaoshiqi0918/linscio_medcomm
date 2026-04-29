<template>
  <div class="redeem-codes-page">
    <div class="toolbar">
      <el-select v-model="tierFilter" clearable placeholder="价位档" style="width: 130px;" @change="reload">
        <el-option v-for="t in tiers" :key="t.tier" :value="t.tier" :label="`${t.tier}元档`" />
      </el-select>
      <el-select v-model="statusFilter" clearable placeholder="状态" style="width: 120px;" @change="reload">
        <el-option value="" label="全部" />
        <el-option value="unused" label="未使用" />
        <el-option value="used" label="已使用" />
        <el-option value="revoked" label="已作废" />
      </el-select>
      <el-input v-model="batchFilter" clearable placeholder="批次号" style="width: 180px;" @change="reload" />
      <el-button type="primary" @click="reload" :loading="loading">查询</el-button>
      <div style="flex: 1;" />
      <el-button type="success" @click="showGenerateDialog = true">批量生成兑换码</el-button>
    </div>

    <el-table :data="items" v-loading="loading" stripe style="width: 100%; margin-top: 16px;">
      <el-table-column type="selection" width="40" />
      <el-table-column prop="code" label="兑换码" width="280">
        <template #default="{ row }">
          <span style="font-family: monospace; font-size: 0.85rem; user-select: all; letter-spacing: 0.3px;">{{ row.code }}</span>
        </template>
      </el-table-column>
      <el-table-column label="档位" width="100">
        <template #default="{ row }">
          <el-tag size="small">{{ row.tier }}元</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="积分" width="90">
        <template #default="{ row }">{{ row.credits }}</template>
      </el-table-column>
      <el-table-column label="赠送" width="80">
        <template #default="{ row }">
          <span v-if="row.bonus_credits > 0" style="color: #10b981;">+{{ row.bonus_credits }}</span>
          <span v-else style="color: #9ca3af;">-</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="使用者" width="130">
        <template #default="{ row }">
          <span v-if="row.used_by_phone">{{ row.used_by_phone }}</span>
          <span v-else style="color: #9ca3af;">-</span>
        </template>
      </el-table-column>
      <el-table-column label="使用时间" width="160">
        <template #default="{ row }">
          <span v-if="row.used_at">{{ new Date(row.used_at).toLocaleString('zh-CN') }}</span>
          <span v-else style="color: #9ca3af;">-</span>
        </template>
      </el-table-column>
      <el-table-column label="批次" width="140">
        <template #default="{ row }">
          <span v-if="row.batch_id" style="font-family: monospace; font-size: 0.8rem; color: #6b7280;">{{ row.batch_id }}</span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="生成时间" width="160">
        <template #default="{ row }">{{ new Date(row.created_at).toLocaleString('zh-CN') }}</template>
      </el-table-column>
      <el-table-column label="操作" width="80" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.status === 'unused'" text type="danger" size="small" @click="revokeOne(row)">作废</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-if="total > pageSize"
      style="margin-top: 16px; justify-content: center;"
      :current-page="page" :page-size="pageSize" :total="total"
      layout="prev, pager, next" @current-change="(p: number) => { page = p; reload() }"
    />

    <!-- 批量生成对话框 -->
    <el-dialog v-model="showGenerateDialog" title="批量生成兑换码" width="460px">
      <el-form label-width="80px">
        <el-form-item label="价位档">
          <el-select v-model="genTier" style="width: 100%;">
            <el-option v-for="t in tiers" :key="t.tier" :value="t.tier"
              :label="`${t.tier}元 — ${t.credits}积分${t.bonus ? ' + ' + t.bonus + '赠送' : ''} (${t.prefix}-****)`" />
          </el-select>
        </el-form-item>
        <el-form-item label="数量">
          <el-input-number v-model="genCount" :min="1" :max="200" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showGenerateDialog = false">取消</el-button>
        <el-button type="primary" @click="doGenerate" :loading="generating">生成</el-button>
      </template>
    </el-dialog>

    <!-- 生成结果对话框 -->
    <el-dialog v-model="showResultDialog" title="生成结果" width="560px">
      <p style="margin-bottom: 8px; color: #6b7280;">共生成 {{ generatedCodes.length }} 个兑换码，请妥善保存：</p>
      <div class="generated-codes">
        <div v-for="code in generatedCodes" :key="code" class="code-row">
          <span style="font-family: monospace; user-select: all; letter-spacing: 0.3px;">{{ code }}</span>
          <el-button text size="small" @click="copyOne(code)">复制</el-button>
        </div>
      </div>
      <template #footer>
        <el-button @click="copyAll">复制全部</el-button>
        <el-button type="primary" @click="showResultDialog = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { http } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'

interface Tier { tier: number; prefix: string; credits: number; bonus: number }

const tiers = ref<Tier[]>([])
const items = ref<any[]>([])
const loading = ref(false)
const tierFilter = ref<number | null>(null)
const statusFilter = ref('')
const batchFilter = ref('')
const page = ref(1)
const pageSize = 20
const total = ref(0)

function statusTagType(s: string) {
  return s === 'unused' ? 'success' : s === 'used' ? 'info' : 'danger'
}
function statusLabel(s: string) {
  return s === 'unused' ? '未使用' : s === 'used' ? '已使用' : '已作废'
}

async function loadTiers() {
  try {
    const res = await http.get('/api/v1/admin/redeem-codes/tiers')
    tiers.value = res.data
  } catch { /* ignore */ }
}

async function reload() {
  loading.value = true
  try {
    const params: any = { page: page.value, page_size: pageSize }
    if (tierFilter.value !== null) params.tier = tierFilter.value
    if (statusFilter.value) params.status_filter = statusFilter.value
    if (batchFilter.value) params.batch_id = batchFilter.value
    const res = await http.get('/api/v1/admin/redeem-codes', { params })
    items.value = res.data.items
    total.value = res.data.total
  } catch { /* ignore */ }
  finally { loading.value = false }
}

async function revokeOne(row: any) {
  await ElMessageBox.confirm(`确认作废兑换码 ${row.code}？此操作不可恢复。`, '作废确认', { type: 'warning' })
  try {
    await http.post('/api/v1/admin/redeem-codes/revoke', { code_ids: [row.id] })
    ElMessage.success('已作废')
    reload()
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '操作失败') }
}

const showGenerateDialog = ref(false)
const genTier = ref(10)
const genCount = ref(10)
const generating = ref(false)
const showResultDialog = ref(false)
const generatedCodes = ref<string[]>([])

async function doGenerate() {
  generating.value = true
  try {
    const res = await http.post('/api/v1/admin/redeem-codes/generate', {
      tier: genTier.value,
      count: genCount.value,
    })
    generatedCodes.value = res.data.codes
    showGenerateDialog.value = false
    showResultDialog.value = true
    ElMessage.success(`已生成 ${res.data.count} 个兑换码`)
    reload()
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '生成失败') }
  finally { generating.value = false }
}

function copyOne(code: string) {
  navigator.clipboard.writeText(code).then(() => ElMessage.success('已复制')).catch(() => {})
}
function copyAll() {
  navigator.clipboard.writeText(generatedCodes.value.join('\n')).then(() => ElMessage.success('已复制全部')).catch(() => {})
}

onMounted(() => {
  loadTiers()
  reload()
})
</script>

<style scoped>
.toolbar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.generated-codes {
  max-height: 340px;
  overflow-y: auto;
  background: #f8fafc;
  border-radius: 8px;
  padding: 12px;
}
.code-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
  border-bottom: 1px solid #e5e7eb;
}
.code-row:last-child { border-bottom: none; }
</style>
