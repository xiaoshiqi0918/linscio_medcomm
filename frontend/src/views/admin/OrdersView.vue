<template>
  <div class="orders-page">
    <div class="toolbar">
      <el-select v-model="statusFilter" clearable placeholder="订单状态" style="width: 140px;" @change="loadOrders">
        <el-option value="" label="全部" />
        <el-option value="created" label="待支付" />
        <el-option value="paying" label="支付中" />
        <el-option value="paid" label="已支付" />
        <el-option value="expired" label="已过期" />
        <el-option value="closed" label="已关闭" />
        <el-option value="partial_refund" label="部分退款" />
        <el-option value="full_refund" label="已退款" />
      </el-select>
      <el-input v-model="userIdFilter" placeholder="用户ID" clearable style="width: 120px;" @clear="loadOrders" @keyup.enter="loadOrders" />
      <el-button type="primary" @click="loadOrders" :loading="loading">查询</el-button>
    </div>

    <el-table :data="orders" v-loading="loading" stripe style="width: 100%; margin-top: 16px;">
      <el-table-column prop="order_no" label="订单号" width="180">
        <template #default="{ row }">
          <span style="font-family: monospace; font-size: 0.8rem;">{{ row.order_no.slice(0, 16) }}...</span>
        </template>
      </el-table-column>
      <el-table-column label="用户" width="130">
        <template #default="{ row }">
          <div>{{ row.user_phone || '-' }}</div>
          <div style="font-size: 0.75rem; color: #9ca3af;">ID: {{ row.user_id }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="channel_code" label="渠道" width="80" />
      <el-table-column label="金额" width="80">
        <template #default="{ row }">¥{{ row.amount_yuan }}</template>
      </el-table-column>
      <el-table-column label="积分" width="100">
        <template #default="{ row }">{{ row.credits_to_add }}+{{ row.bonus_credits }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="退款" width="80">
        <template #default="{ row }">
          <span v-if="parseFloat(row.refunded_amount) > 0" style="color: #dc2626;">¥{{ row.refunded_amount }}</span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="时间" width="150">
        <template #default="{ row }">
          {{ row.created_at ? new Date(row.created_at).toLocaleString('zh-CN') : '-' }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="row.status === 'paid' || row.status === 'partial_refund'"
            size="small" type="danger" @click="showRefund(row)"
          >退款</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-if="total > pageSize"
      style="margin-top: 16px; justify-content: center;"
      :current-page="page" :page-size="pageSize" :total="total"
      layout="prev, pager, next" @current-change="(p: number) => { page = p; loadOrders() }"
    />

    <el-dialog v-model="refundDialog" title="退款" width="400px">
      <el-form label-width="80px">
        <el-form-item label="订单号">{{ refundTarget?.order_no }}</el-form-item>
        <el-form-item label="订单金额">¥{{ refundTarget?.amount_yuan }}</el-form-item>
        <el-form-item label="已退款">¥{{ refundTarget?.refunded_amount }}</el-form-item>
        <el-form-item label="退款金额">
          <el-input-number v-model="refundAmount" :min="0.01" :precision="2" />
        </el-form-item>
        <el-form-item label="原因">
          <el-input v-model="refundReason" placeholder="退款原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="refundDialog = false">取消</el-button>
        <el-button type="danger" @click="doRefund" :loading="refunding">确认退款</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { http } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'

const orders = ref<any[]>([])
const loading = ref(false)
const statusFilter = ref('')
const userIdFilter = ref('')
const page = ref(1)
const pageSize = 20
const total = ref(0)

function statusLabel(s: string) {
  const m: Record<string, string> = {
    created: '待支付', paying: '支付中', paid: '已支付', expired: '已过期',
    closed: '已关闭', partial_refund: '部分退款', full_refund: '已退款',
  }
  return m[s] || s
}
function statusType(s: string) {
  const m: Record<string, string> = {
    paid: 'success', expired: 'info', closed: 'info',
    partial_refund: 'warning', full_refund: 'danger',
  }
  return m[s] || ''
}

async function loadOrders() {
  loading.value = true
  try {
    const params: any = { page: page.value, page_size: pageSize }
    if (statusFilter.value) params.status_filter = statusFilter.value
    if (userIdFilter.value) params.user_id = parseInt(userIdFilter.value)
    const res = await http.get('/api/v1/admin/orders', { params })
    orders.value = res.data.items
    total.value = res.data.total
  } catch { /* ignore */ }
  finally { loading.value = false }
}

const refundDialog = ref(false)
const refundTarget = ref<any>(null)
const refundAmount = ref(0)
const refundReason = ref('')
const refunding = ref(false)

function showRefund(order: any) {
  refundTarget.value = order
  refundAmount.value = parseFloat(order.amount_yuan) - parseFloat(order.refunded_amount)
  refundReason.value = ''
  refundDialog.value = true
}

async function doRefund() {
  await ElMessageBox.confirm(`确认退款 ¥${refundAmount.value}？退款将扣回对应积分。`, '退款确认', { type: 'warning' })
  refunding.value = true
  try {
    await http.post('/api/v1/admin/orders/refund', {
      order_no: refundTarget.value.order_no,
      refund_amount: refundAmount.value,
      reason: refundReason.value,
    })
    ElMessage.success('退款成功')
    refundDialog.value = false
    loadOrders()
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '退款失败') }
  finally { refunding.value = false }
}

onMounted(loadOrders)
</script>

<style scoped>
.toolbar { display: flex; align-items: center; gap: 12px; }
</style>
