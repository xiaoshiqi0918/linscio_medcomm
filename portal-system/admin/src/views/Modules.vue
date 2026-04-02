<template>
  <div class="modules-page">
    <h2>模块权限配置</h2>
    <p class="desc">配置各套餐可用的受控模块，修改后<strong>新生成的授权码</strong>将按此计算 module_mask；已激活用户需点击「批量更新凭证」后生效。也可在「用户管理」中对单个用户点击「更新凭证」。</p>
    <p class="hint">模块标识（code）必须与主产品一致，否则授权后对应功能仍会 403。受控模块请填写：<code>literature</code>、<code>schola</code>、<code>medcomm</code>、<code>qcc</code>、<code>analyzer</code>、<code>image_studio</code>；名称为展示用，可填中文或英文。</p>

    <div class="toolbar">
      <el-button type="primary" @click="showAdd">新增受控模块</el-button>
      <el-button type="warning" :loading="seeding" @click="seedControlledModules">一键初始化受控模块</el-button>
      <el-button type="success" :loading="syncing" @click="syncModules">批量更新凭证</el-button>
    </div>

    <el-table v-loading="loading" :data="list" size="default" border>
      <el-table-column prop="code" label="模块标识" width="140" />
      <el-table-column prop="name" label="名称" width="160" />
      <el-table-column prop="bit_position" label="位序" width="80" align="center" />
      <el-table-column label="基础版" width="90" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.is_controlled" :type="row.basic_enabled ? 'success' : 'info'" size="small">
            {{ row.basic_enabled ? '开' : '关' }}
          </el-tag>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="专业版" width="90" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.is_controlled" :type="row.pro_enabled ? 'success' : 'info'" size="small">
            {{ row.pro_enabled ? '开' : '关' }}
          </el-tag>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="团队版" width="90" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.is_controlled" :type="row.team_enabled ? 'success' : 'info'" size="small">
            {{ row.team_enabled ? '开' : '关' }}
          </el-tag>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="旗舰版" width="90" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.is_controlled" :type="row.enterprise_enabled ? 'success' : 'info'" size="small">
            {{ row.enterprise_enabled ? '开' : '关' }}
          </el-tag>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="内测版" width="90" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.is_controlled" :type="row.beta_enabled ? 'success' : 'info'" size="small">
            {{ row.beta_enabled ? '开' : '关' }}
          </el-tag>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column prop="sort_order" label="排序" width="80" align="center" />
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="edit(row)">编辑</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="editVisible" title="编辑模块" width="420px" @close="editForm = null">
      <el-form v-if="editForm" label-width="100px">
        <el-form-item label="模块">{{ editForm.code }} / {{ editForm.name }}</el-form-item>
        <el-form-item label="基础版">
          <el-switch v-model="editForm.basic_enabled" />
        </el-form-item>
        <el-form-item label="专业版">
          <el-switch v-model="editForm.pro_enabled" />
        </el-form-item>
        <el-form-item label="团队版">
          <el-switch v-model="editForm.team_enabled" />
        </el-form-item>
        <el-form-item label="旗舰版">
          <el-switch v-model="editForm.enterprise_enabled" />
        </el-form-item>
        <el-form-item label="内测版">
          <el-switch v-model="editForm.beta_enabled" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="editForm.sort_order" :min="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="addVisible" title="新增受控模块" width="420px" @close="resetAdd">
      <el-form ref="addFormRef" :model="addForm" label-width="100px">
        <el-form-item label="模块标识" required>
          <el-input v-model="addForm.code" placeholder="英文标识，如 doc_export" />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="addForm.name" placeholder="显示名称" />
        </el-form-item>
        <el-form-item label="基础版">
          <el-switch v-model="addForm.basic_enabled" />
        </el-form-item>
        <el-form-item label="专业版">
          <el-switch v-model="addForm.pro_enabled" />
        </el-form-item>
        <el-form-item label="团队版">
          <el-switch v-model="addForm.team_enabled" />
        </el-form-item>
        <el-form-item label="旗舰版">
          <el-switch v-model="addForm.enterprise_enabled" />
        </el-form-item>
        <el-form-item label="内测版">
          <el-switch v-model="addForm.beta_enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitAdd">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { admin } from '../api'

const list = ref([])
const loading = ref(false)
const syncing = ref(false)
const seeding = ref(false)
const saving = ref(false)
const editVisible = ref(false)
const addVisible = ref(false)
const editForm = ref(null)
const addForm = ref({
  code: '',
  name: '',
  basic_enabled: false,
  pro_enabled: true,
  team_enabled: true,
  enterprise_enabled: true,
  beta_enabled: true,
})
const addFormRef = ref(null)
let editingId = null

async function load() {
  loading.value = true
  try {
    const { data } = await admin.modules({ controlled_only: false })
    list.value = data || []
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

function edit(row) {
  editingId = row.id
  editForm.value = {
    code: row.code,
    name: row.name,
    basic_enabled: row.basic_enabled,
    pro_enabled: row.pro_enabled,
    team_enabled: row.team_enabled,
    enterprise_enabled: row.enterprise_enabled !== false,
    beta_enabled: row.beta_enabled !== false,
    sort_order: row.sort_order,
  }
  editVisible.value = true
}

async function saveEdit() {
  if (!editingId || !editForm.value) return
  saving.value = true
  try {
    await admin.moduleUpdate(editingId, {
      basic_enabled: editForm.value.basic_enabled,
      pro_enabled: editForm.value.pro_enabled,
      team_enabled: editForm.value.team_enabled,
      enterprise_enabled: editForm.value.enterprise_enabled,
      beta_enabled: editForm.value.beta_enabled,
      sort_order: editForm.value.sort_order,
    })
    ElMessage.success('已保存')
    editVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

function showAdd() {
  addVisible.value = true
}

function resetAdd() {
  addForm.value = { code: '', name: '', basic_enabled: false, pro_enabled: true, team_enabled: true, enterprise_enabled: true, beta_enabled: true }
}

async function submitAdd() {
  if (!addForm.value.code?.trim() || !addForm.value.name?.trim()) {
    ElMessage.warning('请填写模块标识和名称')
    return
  }
  saving.value = true
  try {
    await admin.moduleCreate(addForm.value)
    ElMessage.success('已新增')
    addVisible.value = false
    resetAdd()
    await load()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '新增失败')
  } finally {
    saving.value = false
  }
}

async function seedControlledModules() {
  seeding.value = true
  try {
    const { data } = await admin.seedControlledModules()
    const msg = data?.added != null ? `${data.message || '已初始化'}，本次新增 ${data.added} 个` : (data?.message || '已初始化')
    ElMessage.success(msg)
    await load()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '初始化失败')
  } finally {
    seeding.value = false
  }
}

async function syncModules() {
  syncing.value = true
  try {
    const { data } = await admin.syncModules()
    ElMessage.success((data?.message || '已更新凭证') + (data?.updated != null ? `，共 ${data.updated} 条` : ''))
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '批量更新失败')
  } finally {
    syncing.value = false
  }
}

onMounted(() => load())
</script>

<style scoped>
.modules-page { padding: 0 0 24px 0; }
.desc { font-size: 14px; color: #666; margin: 8px 0 16px 0; }
.hint { font-size: 13px; color: #888; margin: -8px 0 16px 0; }
.hint code { background: #f0f0f0; padding: 1px 6px; border-radius: 4px; }
.toolbar { margin-bottom: 16px; display: flex; gap: 12px; }
</style>
