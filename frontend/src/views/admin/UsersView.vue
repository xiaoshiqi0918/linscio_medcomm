<template>
  <div class="users-page">
    <div class="toolbar">
      <el-input v-model="search" placeholder="搜索手机号/用户名" clearable style="width: 260px;" @clear="loadUsers" @keyup.enter="loadUsers" />
      <el-checkbox v-model="bannedOnly" @change="loadUsers">仅封禁</el-checkbox>
      <el-button type="primary" @click="loadUsers" :loading="loading">搜索</el-button>
    </div>

    <el-table :data="users" v-loading="loading" stripe style="width: 100%; margin-top: 16px;">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="display_name" label="用户名" width="120" />
      <el-table-column prop="phone" label="手机号" width="130" />
      <el-table-column label="积分" width="100">
        <template #default="{ row }">{{ row.credits }}</template>
      </el-table-column>
      <el-table-column label="充值/消耗" width="140">
        <template #default="{ row }">
          <span style="color: #059669;">+{{ row.total_recharged }}</span> /
          <span style="color: #dc2626;">-{{ row.total_consumed }}</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.is_admin" type="warning" size="small">管理员</el-tag>
          <el-tag v-else-if="row.is_banned" type="danger" size="small">已封禁</el-tag>
          <el-tag v-else type="success" size="small">正常</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="注册时间" width="160">
        <template #default="{ row }">
          {{ row.created_at ? new Date(row.created_at).toLocaleString('zh-CN') : '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="admin_note" label="备注" width="120" show-overflow-tooltip />
      <el-table-column label="操作" width="320" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="showDetail(row)">详情</el-button>
          <el-button size="small" @click="showAdjust(row)">调积分</el-button>
          <el-button size="small" @click="showNote(row)">备注</el-button>
          <el-button size="small" :type="row.is_banned ? 'success' : 'danger'" @click="toggleBan(row)">
            {{ row.is_banned ? '解封' : '封禁' }}
          </el-button>
          <el-button v-if="!row.is_admin" size="small" type="warning" @click="setAdmin(row)">设管理员</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-if="total > pageSize"
      style="margin-top: 16px; justify-content: center;"
      :current-page="page" :page-size="pageSize" :total="total"
      layout="prev, pager, next" @current-change="(p: number) => { page = p; loadUsers() }"
    />

    <el-dialog v-model="adjustDialog" title="调整积分" width="400px">
      <el-form label-width="80px">
        <el-form-item label="用户">{{ adjustTarget?.display_name || adjustTarget?.phone }}</el-form-item>
        <el-form-item label="类型">
          <el-select v-model="adjustType" style="width: 100%;">
            <el-option value="credits" label="充值积分" />
            <el-option value="gift_credits" label="赠送积分" />
            <el-option value="promo_credits" label="推广积分" />
          </el-select>
        </el-form-item>
        <el-form-item label="数量">
          <el-input-number v-model="adjustAmount" :step="10" />
          <span style="margin-left: 8px; color: #6b7280; font-size: 0.85rem;">正数加，负数扣</span>
        </el-form-item>
        <el-form-item label="原因">
          <el-input v-model="adjustReason" placeholder="管理员备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="adjustDialog = false">取消</el-button>
        <el-button type="primary" @click="doAdjust" :loading="adjusting">确认</el-button>
      </template>
    </el-dialog>

    <!-- 用户详情弹窗 -->
    <el-dialog v-model="detailDialog" title="用户详情" width="700px" top="5vh">
      <div v-if="detailLoading" v-loading="true" style="min-height: 200px;" />
      <template v-else-if="detailData">
        <el-descriptions :column="2" border size="small" style="margin-bottom: 16px;">
          <el-descriptions-item label="ID">{{ detailData.user.id }}</el-descriptions-item>
          <el-descriptions-item label="用户名">{{ detailData.user.display_name }}</el-descriptions-item>
          <el-descriptions-item label="手机号">{{ detailData.user.phone }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag v-if="detailData.user.is_admin" type="warning" size="small">管理员</el-tag>
            <el-tag v-else-if="detailData.user.is_banned" type="danger" size="small">已封禁</el-tag>
            <el-tag v-else type="success" size="small">正常</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="积分">{{ detailData.user.credits }}</el-descriptions-item>
          <el-descriptions-item label="赠送积分">{{ detailData.user.gift_credits }}</el-descriptions-item>
          <el-descriptions-item label="推广积分">{{ detailData.user.promo_credits }}</el-descriptions-item>
          <el-descriptions-item label="冻结积分">{{ detailData.user.frozen_credits }}</el-descriptions-item>
          <el-descriptions-item label="总充值">{{ detailData.user.total_recharged }}</el-descriptions-item>
          <el-descriptions-item label="总消耗">{{ detailData.user.total_consumed }}</el-descriptions-item>
          <el-descriptions-item label="注册时间">{{ detailData.user.created_at ? new Date(detailData.user.created_at).toLocaleString('zh-CN') : '-' }}</el-descriptions-item>
          <el-descriptions-item label="最近登录">{{ detailData.user.last_login_at ? new Date(detailData.user.last_login_at).toLocaleString('zh-CN') : '-' }}</el-descriptions-item>
          <el-descriptions-item label="管理员备注" :span="2">{{ detailData.user.admin_note || '-' }}</el-descriptions-item>
        </el-descriptions>

        <el-tabs>
          <el-tab-pane label="积分流水">
            <el-table :data="detailData.usage_logs" size="small" max-height="260" stripe>
              <el-table-column prop="operation" label="操作" width="120" />
              <el-table-column prop="cost" label="积分" width="80" />
              <el-table-column prop="created_at" label="时间" width="160">
                <template #default="{ row }">{{ row.created_at ? new Date(row.created_at).toLocaleString('zh-CN') : '-' }}</template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="充值记录">
            <el-table :data="detailData.recharge_logs" size="small" max-height="260" stripe>
              <el-table-column prop="order_no" label="订单号" width="180" show-overflow-tooltip />
              <el-table-column prop="amount_yuan" label="金额(元)" width="90" />
              <el-table-column prop="credits_added" label="积分" width="80" />
              <el-table-column prop="status" label="状态" width="80" />
              <el-table-column prop="created_at" label="时间" width="160">
                <template #default="{ row }">{{ row.created_at ? new Date(row.created_at).toLocaleString('zh-CN') : '-' }}</template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="文章">
            <el-table :data="detailData.articles" size="small" max-height="260" stripe>
              <el-table-column prop="id" label="ID" width="60" />
              <el-table-column prop="topic" label="主题" show-overflow-tooltip />
              <el-table-column prop="content_format" label="类型" width="100" />
              <el-table-column prop="created_at" label="创建时间" width="160">
                <template #default="{ row }">{{ row.created_at ? new Date(row.created_at).toLocaleString('zh-CN') : '-' }}</template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="操作日志">
            <el-table :data="detailData.audit_logs" size="small" max-height="260" stripe>
              <el-table-column prop="action" label="操作" width="120" />
              <el-table-column prop="reason" label="原因" show-overflow-tooltip />
              <el-table-column prop="created_at" label="时间" width="160">
                <template #default="{ row }">{{ row.created_at ? new Date(row.created_at).toLocaleString('zh-CN') : '-' }}</template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
        </el-tabs>
      </template>
    </el-dialog>

    <!-- 备注弹窗 -->
    <el-dialog v-model="noteDialog" title="设置备注" width="400px">
      <el-form label-width="80px">
        <el-form-item label="用户">{{ noteTarget?.display_name || noteTarget?.phone }}</el-form-item>
        <el-form-item label="备注">
          <el-input v-model="noteText" type="textarea" :rows="3" placeholder="仅管理员可见" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="noteDialog = false">取消</el-button>
        <el-button type="primary" @click="doSetNote" :loading="noteSaving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { http } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'

const users = ref<any[]>([])
const loading = ref(false)
const search = ref('')
const bannedOnly = ref(false)
const page = ref(1)
const pageSize = 20
const total = ref(0)

async function loadUsers() {
  loading.value = true
  try {
    const res = await http.get('/api/v1/admin/users', {
      params: { page: page.value, page_size: pageSize, search: search.value || undefined, banned_only: bannedOnly.value || undefined },
    })
    users.value = res.data.items
    total.value = res.data.total
  } catch { /* ignore */ }
  finally { loading.value = false }
}

async function toggleBan(user: any) {
  const action = user.is_banned ? '解封' : '封禁'
  await ElMessageBox.confirm(`确认${action}用户 ${user.display_name || user.phone}？`, action)
  try {
    await http.post('/api/v1/admin/users/ban', { user_id: user.id, banned: !user.is_banned })
    ElMessage.success(`已${action}`)
    loadUsers()
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '操作失败') }
}

const adjustDialog = ref(false)
const adjustTarget = ref<any>(null)
const adjustType = ref('credits')
const adjustAmount = ref(0)
const adjustReason = ref('')
const adjusting = ref(false)

function showAdjust(user: any) {
  adjustTarget.value = user
  adjustAmount.value = 0
  adjustReason.value = ''
  adjustType.value = 'credits'
  adjustDialog.value = true
}

async function doAdjust() {
  adjusting.value = true
  try {
    await http.post('/api/v1/admin/users/adjust-credits', {
      user_id: adjustTarget.value.id,
      amount: adjustAmount.value,
      credit_type: adjustType.value,
      reason: adjustReason.value,
    })
    ElMessage.success('积分调整成功')
    adjustDialog.value = false
    loadUsers()
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '调整失败') }
  finally { adjusting.value = false }
}

// 用户详情
const detailDialog = ref(false)
const detailLoading = ref(false)
const detailData = ref<any>(null)

async function showDetail(user: any) {
  detailDialog.value = true
  detailLoading.value = true
  detailData.value = null
  try {
    const res = await http.get(`/api/v1/admin/users/${user.id}`)
    detailData.value = res.data
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '加载失败') }
  finally { detailLoading.value = false }
}

// 备注
const noteDialog = ref(false)
const noteTarget = ref<any>(null)
const noteText = ref('')
const noteSaving = ref(false)

function showNote(user: any) {
  noteTarget.value = user
  noteText.value = user.admin_note || ''
  noteDialog.value = true
}

async function doSetNote() {
  noteSaving.value = true
  try {
    await http.post('/api/v1/admin/users/note', { user_id: noteTarget.value.id, note: noteText.value })
    ElMessage.success('备注已保存')
    noteDialog.value = false
    loadUsers()
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '保存失败') }
  finally { noteSaving.value = false }
}

// 设管理员
async function setAdmin(user: any) {
  await ElMessageBox.confirm(`确认将 ${user.display_name || user.phone} 设为管理员？此操作不可撤销。`, '设为管理员', { type: 'warning' })
  try {
    await http.post('/api/v1/admin/users/set-admin', { user_id: user.id, is_admin: true })
    ElMessage.success('已设为管理员')
    loadUsers()
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '操作失败') }
}

onMounted(loadUsers)
</script>

<style scoped>
.toolbar { display: flex; align-items: center; gap: 12px; }
</style>
