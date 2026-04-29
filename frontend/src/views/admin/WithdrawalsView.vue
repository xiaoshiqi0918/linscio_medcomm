<template>
  <div class="withdrawals-admin">
    <div class="page-header">
      <h2>兑现审批</h2>
      <div class="header-actions">
        <el-radio-group v-model="statusFilter" size="small" @change="loadList">
          <el-radio-button label="">全部</el-radio-button>
          <el-radio-button label="pending">待审核</el-radio-button>
          <el-radio-button label="approved">已通过</el-radio-button>
          <el-radio-button label="paid">已打款</el-radio-button>
          <el-radio-button label="rejected">已拒绝</el-radio-button>
        </el-radio-group>
        <el-button size="small" @click="loadList" :loading="loading">刷新</el-button>
      </div>
    </div>

    <el-table :data="list" v-loading="loading" stripe border size="small" style="width: 100%;">
      <el-table-column label="ID" prop="id" width="60" />
      <el-table-column label="用户" min-width="120">
        <template #default="{ row }">
          <div>{{ row.display_name || '-' }}</div>
          <div style="font-size: 0.78rem; color: #9ca3af;">{{ row.phone || '-' }}</div>
        </template>
      </el-table-column>
      <el-table-column label="推广积分余额" width="110" align="center">
        <template #default="{ row }">
          <span style="font-weight: 600; color: #059669;">{{ row.promo_credits }}</span>
        </template>
      </el-table-column>
      <el-table-column label="兑现积分" width="90" align="center">
        <template #default="{ row }">{{ row.credits_used }}</template>
      </el-table-column>
      <el-table-column label="折算金额" width="90" align="center">
        <template #default="{ row }">¥{{ row.amount_yuan }}</template>
      </el-table-column>
      <el-table-column label="平台账号" width="130">
        <template #default="{ row }">{{ row.platform_account || '-' }}</template>
      </el-table-column>
      <el-table-column label="微信手机号" width="130">
        <template #default="{ row }">
          <span style="font-family: monospace;">{{ row.wechat_phone || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="申请时间" width="150">
        <template #default="{ row }">
          {{ row.created_at ? new Date(row.created_at).toLocaleString('zh-CN') : '-' }}
        </template>
      </el-table-column>
      <el-table-column label="备注" min-width="150">
        <template #default="{ row }">
          <span style="font-size: 0.8rem; color: #6b7280;">{{ row.note || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <template v-if="row.status === 'pending'">
            <el-button text type="success" size="small" @click="handleReview(row, 'approve')">通过</el-button>
            <el-button text type="danger" size="small" @click="handleReject(row)">拒绝</el-button>
          </template>
          <template v-else-if="row.status === 'approved'">
            <el-button text type="primary" size="small" @click="handleReview(row, 'paid')">标记已打款</el-button>
            <el-button text type="danger" size="small" @click="handleReject(row)">驳回</el-button>
          </template>
          <span v-else style="font-size: 0.8rem; color: #9ca3af;">-</span>
        </template>
      </el-table-column>
    </el-table>

    <!-- 拒绝理由弹窗 -->
    <el-dialog v-model="rejectDialogVisible" title="拒绝兑现申请" width="420px" :close-on-click-modal="false">
      <div style="margin-bottom: 8px; color: #6b7280; font-size: 0.85rem;">
        用户：{{ rejectTarget?.display_name }} · 兑现 {{ rejectTarget?.credits_used }} 积分 (¥{{ rejectTarget?.amount_yuan }})
      </div>
      <el-input
        v-model="rejectReason"
        type="textarea"
        :rows="3"
        placeholder="请输入拒绝理由（将展示给用户）"
        maxlength="200"
        show-word-limit
      />
      <template #footer>
        <el-button @click="rejectDialogVisible = false">取消</el-button>
        <el-button type="danger" :loading="reviewing" @click="submitReject">确认拒绝</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { http } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'

interface WithdrawalItem {
  id: number
  user_id: number
  display_name: string | null
  phone: string | null
  credits_used: number
  amount_yuan: number
  platform_account: string | null
  wechat_phone: string | null
  promo_credits: number
  status: string
  created_at: string
  reviewed_at: string | null
  paid_at: string | null
  note: string | null
}

const list = ref<WithdrawalItem[]>([])
const loading = ref(false)
const statusFilter = ref('')
const reviewing = ref(false)
const rejectDialogVisible = ref(false)
const rejectTarget = ref<WithdrawalItem | null>(null)
const rejectReason = ref('')

function statusLabel(s: string): string {
  const map: Record<string, string> = { pending: '待审核', approved: '已通过', rejected: '已拒绝', paid: '已打款' }
  return map[s] || s
}

function statusType(s: string): string {
  const map: Record<string, string> = { pending: 'warning', approved: 'success', rejected: 'danger', paid: '' }
  return map[s] || ''
}

async function loadList() {
  loading.value = true
  try {
    const params: any = {}
    if (statusFilter.value) params.status = statusFilter.value
    const res = await http.get('/api/v1/admin/withdrawals', { params })
    list.value = res.data
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载失败')
  } finally { loading.value = false }
}

async function handleReview(row: WithdrawalItem, action: 'approve' | 'paid') {
  const labels: Record<string, string> = { approve: '审核通过', paid: '标记已打款' }
  try {
    await ElMessageBox.confirm(
      `确认将此兑现申请（¥${row.amount_yuan}）${labels[action]}？`,
      labels[action],
      { confirmButtonText: '确认', cancelButtonText: '取消', type: 'info' }
    )
  } catch { return }

  reviewing.value = true
  try {
    const res = await http.post('/api/v1/admin/withdrawals/review', {
      withdrawal_id: row.id,
      action,
    })
    ElMessage.success(res.data.message || '操作成功')
    loadList()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '操作失败')
  } finally { reviewing.value = false }
}

function handleReject(row: WithdrawalItem) {
  rejectTarget.value = row
  rejectReason.value = ''
  rejectDialogVisible.value = true
}

async function submitReject() {
  if (!rejectReason.value.trim()) {
    ElMessage.warning('请输入拒绝理由')
    return
  }
  reviewing.value = true
  try {
    const res = await http.post('/api/v1/admin/withdrawals/review', {
      withdrawal_id: rejectTarget.value!.id,
      action: 'reject',
      note: rejectReason.value.trim(),
    })
    ElMessage.success(res.data.message || '已拒绝')
    rejectDialogVisible.value = false
    loadList()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '操作失败')
  } finally { reviewing.value = false }
}

onMounted(() => { loadList() })
</script>

<style scoped>
.withdrawals-admin { padding: 0; }
.page-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 16px; flex-wrap: wrap; gap: 8px;
}
.page-header h2 { margin: 0; font-size: 1.2rem; color: #1e293b; }
.header-actions { display: flex; gap: 8px; align-items: center; }
</style>
