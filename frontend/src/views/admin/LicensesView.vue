<template>
  <div class="licenses-page">
    <div class="toolbar">
      <el-select v-model="sourceFilter" clearable placeholder="来源" style="width: 140px;" @change="loadLicenses">
        <el-option value="" label="全部" />
        <el-option value="redeem" label="用户兑换" />
        <el-option value="admin_generate" label="管理员生成" />
      </el-select>
      <el-select v-model="usedFilter" clearable placeholder="状态" style="width: 120px;" @change="loadLicenses">
        <el-option value="" label="全部" />
        <el-option value="unused" label="未使用" />
        <el-option value="used" label="已使用" />
      </el-select>
      <el-button type="primary" @click="loadLicenses" :loading="loading">查询</el-button>
      <div style="flex: 1;" />
      <el-button type="success" @click="showGenerateDialog = true">批量生成授权码</el-button>
    </div>

    <el-table :data="licenses" v-loading="loading" stripe style="width: 100%; margin-top: 16px;">
      <el-table-column prop="code" label="授权码" width="220">
        <template #default="{ row }">
          <span style="font-family: monospace; font-size: 0.85rem; user-select: all;">{{ row.code }}</span>
        </template>
      </el-table-column>
      <el-table-column label="来源" width="120">
        <template #default="{ row }">
          <el-tag v-if="row.source === 'admin_generate'" type="warning" size="small">管理员生成</el-tag>
          <el-tag v-else size="small">用户兑换</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="兑换类型" width="120">
        <template #default="{ row }">
          <span v-if="row.credit_type === 'admin'">-</span>
          <span v-else-if="row.credit_type === 'credits'">充值积分 (6000)</span>
          <span v-else>推广积分 (10000)</span>
        </template>
      </el-table-column>
      <el-table-column label="归属用户" width="130">
        <template #default="{ row }">
          <span v-if="row.owner_phone">{{ row.owner_phone }}</span>
          <span v-else style="color: #9ca3af;">无 (待分配)</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_used ? 'info' : 'success'" size="small">{{ row.is_used ? '已使用' : '未使用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="使用者" width="120">
        <template #default="{ row }">{{ row.used_by || '-' }}</template>
      </el-table-column>
      <el-table-column label="备注" width="140">
        <template #default="{ row }">{{ row.note || '-' }}</template>
      </el-table-column>
      <el-table-column label="生成时间" width="150">
        <template #default="{ row }">
          {{ new Date(row.created_at).toLocaleString('zh-CN') }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="80" fixed="right">
        <template #default="{ row }">
          <el-button v-if="!row.is_used" text type="danger" size="small" @click="revokeLicense(row)">作废</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-if="total > pageSize"
      style="margin-top: 16px; justify-content: center;"
      :current-page="page" :page-size="pageSize" :total="total"
      layout="prev, pager, next" @current-change="(p: number) => { page = p; loadLicenses() }"
    />

    <el-dialog v-model="showGenerateDialog" title="批量生成授权码" width="420px">
      <el-form label-width="80px">
        <el-form-item label="数量">
          <el-input-number v-model="generateCount" :min="1" :max="100" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="generateNote" placeholder="可选备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showGenerateDialog = false">取消</el-button>
        <el-button type="primary" @click="doGenerate" :loading="generating">生成</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showCodesDialog" title="生成结果" width="500px">
      <p style="margin-bottom: 8px; color: #6b7280;">共生成 {{ generatedCodes.length }} 个授权码，请妥善保存：</p>
      <div class="generated-codes">
        <div v-for="code in generatedCodes" :key="code" class="code-row">
          <span style="font-family: monospace; user-select: all;">{{ code }}</span>
          <el-button text size="small" @click="copyCode(code)">复制</el-button>
        </div>
      </div>
      <template #footer>
        <el-button @click="copyAllCodes">复制全部</el-button>
        <el-button type="primary" @click="showCodesDialog = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { http } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'

const licenses = ref<any[]>([])
const loading = ref(false)
const sourceFilter = ref('')
const usedFilter = ref('')
const page = ref(1)
const pageSize = 20
const total = ref(0)

async function loadLicenses() {
  loading.value = true
  try {
    const params: any = { page: page.value, page_size: pageSize }
    if (sourceFilter.value) params.source_filter = sourceFilter.value
    if (usedFilter.value) params.used_filter = usedFilter.value
    const res = await http.get('/api/v1/admin/licenses', { params })
    licenses.value = res.data.items
    total.value = res.data.total
  } catch { /* ignore */ }
  finally { loading.value = false }
}

async function revokeLicense(row: any) {
  await ElMessageBox.confirm(`确认作废授权码 ${row.code}？此操作不可恢复。`, '作废确认', { type: 'warning' })
  try {
    await http.post('/api/v1/admin/licenses/revoke', null, { params: { license_id: row.id } })
    ElMessage.success('已作废')
    loadLicenses()
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '操作失败') }
}

const showGenerateDialog = ref(false)
const generateCount = ref(1)
const generateNote = ref('')
const generating = ref(false)
const showCodesDialog = ref(false)
const generatedCodes = ref<string[]>([])

async function doGenerate() {
  generating.value = true
  try {
    const res = await http.post('/api/v1/admin/licenses/generate', {
      count: generateCount.value,
      note: generateNote.value,
    })
    generatedCodes.value = res.data.codes
    showGenerateDialog.value = false
    showCodesDialog.value = true
    ElMessage.success(`已生成 ${res.data.count} 个授权码`)
    loadLicenses()
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '生成失败') }
  finally { generating.value = false }
}

function copyCode(code: string) {
  navigator.clipboard.writeText(code).then(() => ElMessage.success('已复制')).catch(() => {})
}
function copyAllCodes() {
  navigator.clipboard.writeText(generatedCodes.value.join('\n')).then(() => ElMessage.success('已复制全部')).catch(() => {})
}

onMounted(loadLicenses)
</script>

<style scoped>
.toolbar { display: flex; align-items: center; gap: 12px; }
.generated-codes {
  max-height: 300px;
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
