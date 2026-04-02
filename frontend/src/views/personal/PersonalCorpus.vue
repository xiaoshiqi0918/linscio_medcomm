<template>
  <div class="personal-corpus-page">
    <div class="page-head">
      <h2>个人语料</h2>
      <p class="sub">
        生成科普正文时自动注入以下偏好（避免用语、倾向表述、备忘）。可随时开关单条。
        编辑文章时<strong>选中一段文字</strong>会出现<strong>浮动条</strong>，可直接收录；本页的「快速收录」适合从别处粘贴锚点。
      </p>
    </div>

    <el-card class="form-card" shadow="never">
      <template #header>新增条目</template>
      <el-form inline @submit.prevent="onCreate">
        <el-form-item label="类型">
          <el-select v-model="form.kind" style="width: 140px">
            <el-option label="避免用语" value="avoid" />
            <el-option label="倾向表述" value="prefer" />
            <el-option label="备忘" value="note" />
          </el-select>
        </el-form-item>
        <el-form-item label="锚点/主题词">
          <el-input v-model="form.anchor" placeholder="如：具体药名、常写错的词" style="width: 220px" clearable />
        </el-form-item>
        <el-form-item label="内容">
          <el-input v-model="form.content" placeholder="避免时写建议替换；倾向写希望用的整句或要点" style="width: 320px" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="creating" @click="onCreate">添加</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="form-card" shadow="never">
      <template #header>快速收录（capture）</template>
      <el-form inline @submit.prevent="onCapture">
        <el-form-item label="类型">
          <el-select v-model="captureForm.kind" style="width: 140px">
            <el-option label="倾向表述" value="prefer" />
            <el-option label="避免用语" value="avoid" />
            <el-option label="备忘" value="note" />
          </el-select>
        </el-form-item>
        <el-form-item label="锚点（必填）">
          <el-input v-model="captureForm.anchor" placeholder="原文关键词或概念" style="width: 200px" clearable />
        </el-form-item>
        <el-form-item label="希望写法">
          <el-input v-model="captureForm.content" placeholder="可选；可与编辑器侧「复制后粘贴」配合" style="width: 280px" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="success" plain :loading="capturing" @click="onCapture">收录到语料</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <template #header>
        <div class="card-header-row">
          <span>全部条目</span>
          <el-button size="small" @click="load" :loading="loading">刷新</el-button>
        </div>
      </template>
      <el-table :data="items" v-loading="loading" size="small">
        <el-table-column prop="kind" label="类型" width="100" />
        <el-table-column prop="anchor" label="锚点" min-width="140" show-overflow-tooltip />
        <el-table-column prop="content" label="内容" min-width="200" show-overflow-tooltip />
        <el-table-column prop="source" label="来源" width="88" />
        <el-table-column label="启用" width="80">
          <template #default="{ row }">
            <el-switch
              :model-value="row.enabled"
              @update:model-value="(v: string | number | boolean) => toggle(row, Boolean(v))"
            />
          </template>
        </el-table-column>
        <el-table-column label="" width="88" fixed="right">
          <template #default="{ row }">
            <el-button type="danger" link size="small" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, axiosErrorDetail } from '@/api'

const items = ref<any[]>([])
const loading = ref(false)
const creating = ref(false)
const capturing = ref(false)
const form = ref({ kind: 'prefer', anchor: '', content: '' })
const captureForm = ref({ kind: 'prefer', anchor: '', content: '' })

async function load() {
  loading.value = true
  try {
    const res = await api.personalCorpus.list()
    items.value = res.data?.items || []
  } catch (e: any) {
    ElMessage.error(axiosErrorDetail(e) || '加载失败')
  } finally {
    loading.value = false
  }
}

async function onCreate() {
  creating.value = true
  try {
    await api.personalCorpus.create({
      kind: form.value.kind,
      anchor: form.value.anchor.trim(),
      content: form.value.content.trim(),
      source: 'manual',
    })
    ElMessage.success('已添加')
    form.value = { kind: form.value.kind, anchor: '', content: '' }
    await load()
  } catch (e: any) {
    ElMessage.error(axiosErrorDetail(e) || '添加失败')
  } finally {
    creating.value = false
  }
}

async function onCapture() {
  const a = captureForm.value.anchor.trim()
  if (!a) {
    ElMessage.warning('请填写锚点')
    return
  }
  capturing.value = true
  try {
    await api.personalCorpus.capture({
      kind: captureForm.value.kind,
      anchor: a,
      content: captureForm.value.content.trim(),
    })
    ElMessage.success('已收录（来源：capture）')
    captureForm.value = { kind: captureForm.value.kind, anchor: '', content: '' }
    await load()
  } catch (e: any) {
    ElMessage.error(axiosErrorDetail(e) || '收录失败')
  } finally {
    capturing.value = false
  }
}

async function toggle(row: any, enabled: boolean) {
  try {
    await api.personalCorpus.patch(row.id, { enabled })
    row.enabled = enabled
  } catch (e: any) {
    ElMessage.error(axiosErrorDetail(e) || '更新失败')
    await load()
  }
}

async function remove(row: any) {
  try {
    await ElMessageBox.confirm('确定删除该条语料？', '确认', { type: 'warning' })
  } catch {
    return
  }
  try {
    await api.personalCorpus.delete(row.id)
    ElMessage.success('已删除')
    await load()
  } catch (e: any) {
    ElMessage.error(axiosErrorDetail(e) || '删除失败')
  }
}

onMounted(() => load())
</script>

<style scoped>
.personal-corpus-page {
  padding: 1rem 1.25rem 2rem;
  max-width: 960px;
}
.page-head h2 {
  margin: 0 0 0.35rem;
  font-size: 1.25rem;
}
.sub {
  margin: 0 0 1rem;
  color: #606266;
  font-size: 13px;
  line-height: 1.55;
}
.form-card {
  margin-bottom: 1rem;
}
.form-card :deep(.el-card__header) {
  font-weight: 600;
}
.card-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}
</style>
