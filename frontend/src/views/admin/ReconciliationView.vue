<template>
  <div class="recon-page">
    <el-table :data="logs" v-loading="loading" stripe style="width: 100%;">
      <el-table-column prop="bill_date" label="账单日期" width="120" />
      <el-table-column prop="channel_code" label="渠道" width="100" />
      <el-table-column prop="total_orders" label="总订单" width="80" />
      <el-table-column prop="matched_orders" label="匹配" width="80" />
      <el-table-column label="差异" width="80">
        <template #default="{ row }">
          <span :style="{ color: row.mismatched_orders > 0 ? '#dc2626' : '#059669' }">
            {{ row.mismatched_orders }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="总金额" width="100">
        <template #default="{ row }">¥{{ row.total_amount }}</template>
      </el-table-column>
      <el-table-column label="差异金额" width="100">
        <template #default="{ row }">
          <span :style="{ color: parseFloat(row.diff_amount) > 0 ? '#dc2626' : '#059669' }">
            ¥{{ row.diff_amount }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'completed' ? 'success' : row.status === 'has_diff' ? 'danger' : 'info'" size="small">
            {{ row.status === 'completed' ? '正常' : row.status === 'has_diff' ? '有差异' : '待处理' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="详情" min-width="200">
        <template #default="{ row }">
          <el-button v-if="row.details" text size="small" @click="showDetails(row)">查看详情</el-button>
          <span v-else style="color: #9ca3af;">无差异</span>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="detailDialog" title="对账差异详情" width="600px">
      <pre style="white-space: pre-wrap; font-size: 0.85rem; background: #f8fafc; padding: 16px; border-radius: 8px;">{{ JSON.stringify(detailData, null, 2) }}</pre>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { http } from '@/api'

const logs = ref<any[]>([])
const loading = ref(false)
const detailDialog = ref(false)
const detailData = ref<any>(null)

async function loadLogs() {
  loading.value = true
  try {
    const res = await http.get('/api/v1/admin/reconciliation')
    logs.value = res.data
  } catch { /* ignore */ }
  finally { loading.value = false }
}

function showDetails(row: any) {
  detailData.value = row.details
  detailDialog.value = true
}

onMounted(loadLogs)
</script>
