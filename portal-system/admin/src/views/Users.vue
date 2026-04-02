<template>
  <div class="users">
    <h2>用户管理</h2>
    <p class="desc">支持启用/禁用、更新凭证。更新凭证：按当前套餐刷新该用户的镜像仓库权限与密码，仅对已激活且有关联授权码的用户有效；批量更新请在「模块权限配置」页操作。</p>
    <el-card>
      <el-input v-model="search" placeholder="搜索用户名" clearable style="width:240px;margin-bottom:16px" @keyup.enter="load" />
      <el-button type="primary" @click="load">查询</el-button>
      <el-table :data="list" v-loading="loading" style="margin-top:16px">
        <el-table-column prop="username" label="用户名" width="120" />
        <el-table-column prop="email" label="邮箱" />
        <el-table-column prop="is_active" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'">{{ row.is_active ? '正常' : '已禁用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="注册时间" width="180">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button type="success" size="small" :loading="refreshingId === row.id" @click="refreshCredential(row)">更新凭证</el-button>
            <el-button link type="primary" size="small" @click="toggleUser(row)">
              {{ row.is_active ? '禁用' : '启用' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { admin } from '../api'

const list = ref([])
const search = ref('')
const loading = ref(false)
const refreshingId = ref(null)

function formatDate(d) {
  if (!d) return '—'
  return new Date(d).toLocaleString('zh-CN')
}

async function load() {
  loading.value = true
  try {
    const { data } = await admin.users({ search: search.value || undefined, limit: 100 })
    list.value = data
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

async function toggleUser(row) {
  try {
    await admin.userUpdate(row.id, { is_active: !row.is_active })
    ElMessage.success('已更新')
    load()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}

async function refreshCredential(row) {
  refreshingId.value = row.id
  try {
    await admin.refreshUserCredential(row.id)
    ElMessage.success('已更新该用户凭证')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '更新凭证失败')
  } finally {
    refreshingId.value = null
  }
}

onMounted(load)
</script>

<style scoped>
.users { padding: 0 0 24px 0; }
.desc { font-size: 14px; color: #666; margin: 8px 0 16px 0; }
</style>
