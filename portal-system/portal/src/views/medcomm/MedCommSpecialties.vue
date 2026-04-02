<template>
  <div class="page container-shell">
    <h1>我的学科包</h1>
    <p v-if="!items.length" class="empty">暂无已购学科包，或尚未加载。</p>
    <div v-for="s in items" :key="s.id" class="card">
      <h3 class="card-title">{{ s.name }} <code class="card-id">{{ s.id }}</code></h3>
      <p class="version-line">
        最新版本：v{{ s.remote_version || '—' }} · 你的软件：v{{ s.local_version || '—' }}
        <span v-if="hasUpdate(s)" class="warn">⚠️ 有更新</span>
      </p>
      <p class="muted">购买日期：{{ formatDate(s.purchased_at) }} · 永久有效</p>

      <div v-if="docList(s.id)?.length" class="docs-section">
        <p class="docs-label">预置文献：</p>
        <div v-for="doc in docList(s.id)" :key="doc.filename" class="doc-row">
          <span class="doc-icon">📄</span>
          <span class="doc-title">{{ doc.title }}</span>
          <span v-if="doc.size_mb" class="doc-size">{{ doc.size_mb }}MB</span>
          <a
            v-if="doc.deep_link"
            :href="doc.deep_link"
            class="doc-dl"
            target="_blank"
            rel="noopener"
          >下载</a>
          <a
            v-else-if="doc.download_url"
            :href="doc.download_url"
            class="doc-dl"
            target="_blank"
            rel="noopener"
          >下载</a>
        </div>
        <p class="docs-hint">点击下载后，若软件正在运行将收到导入提示</p>
      </div>
      <div v-else-if="docsLoading[s.id]" class="docs-loading">加载文档中…</div>
      <div v-else-if="docsError[s.id]" class="docs-err">{{ docsError[s.id] }}</div>
      <button v-else type="button" class="link" @click="loadDocs(s.id)">加载预置文献</button>

      <button type="button" class="link link-changelog" @click="toggleChangelog(s.id)">
        {{ expandedChangelog === s.id ? '收起更新日志' : '查看更新日志' }}
      </button>
      <div v-if="expandedChangelog === s.id && changelog[s.id]" class="changelog">
        <pre>{{ changelog[s.id] }}</pre>
      </div>
    </div>
    <p class="footnote">注："你的软件"版本来源：软件上次启动时上报的已安装版本</p>
    <nav class="subnav">
      <router-link to="/medcomm/activate">← 激活授权码</router-link>
      <router-link to="/medcomm/help">帮助中心</router-link>
    </nav>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useMedcommAuthStore } from '../../stores/medcommAuth'
import { medcommDownload, medcommUpdate } from '../../api/medcomm'

const store = useMedcommAuthStore()
const items = ref([])
const docs = ref({})
const docsLoading = ref({})
const docsError = ref({})
const expandedChangelog = ref(null)
const changelog = ref({})

function formatDate(s) {
  if (!s) return '—'
  try {
    return new Date(s).toLocaleDateString('zh-CN')
  } catch {
    return s
  }
}

function hasUpdate(s) {
  if (!s.remote_version || !s.local_version) return false
  return s.remote_version !== s.local_version
}

function docList(sid) {
  const d = docs.value[sid]
  return Array.isArray(d) ? d : []
}

onMounted(async () => {
  const data = await store.fetchLicenseStatus()
  if (data?.specialties) items.value = data.specialties
})

async function loadDocs(sid) {
  docsLoading.value[sid] = true
  docsError.value[sid] = ''
  try {
    const { data } = await medcommDownload.specialtyDocuments(sid)
    docs.value[sid] = data.documents || []
  } catch (e) {
    docsError.value[sid] = e.response?.data?.detail || '加载失败'
  } finally {
    docsLoading.value[sid] = false
  }
}

async function toggleChangelog(sid) {
  if (expandedChangelog.value === sid) {
    expandedChangelog.value = null
    return
  }
  if (changelog.value[sid]) {
    expandedChangelog.value = sid
    return
  }
  try {
    const specialties = {}
    const s = items.value.find((x) => x.id === sid)
    if (s?.local_version) specialties[sid] = s.local_version
    const { data } = await medcommUpdate.check({
      platform: 'mac-arm64',
      software_version: '1.0.0',
      specialties,
    })
    const u = (data.specialty_updates || []).find((x) => x.id === sid)
    if (u?.changelog?.length) {
      changelog.value[sid] = u.changelog.join('\n')
    } else {
      changelog.value[sid] = '暂无更新日志'
    }
    expandedChangelog.value = sid
  } catch {
    changelog.value[sid] = '获取失败'
    expandedChangelog.value = sid
  }
}
</script>

<style scoped>
.page { max-width: 720px; margin: 0 auto; padding: 100px 16px 48px; }
.empty { color: #64748b; }
.card {
  border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; margin-bottom: 16px;
  background: #fff;
}
.card-title { font-size: 16px; margin-bottom: 8px; }
.card-id { font-size: 12px; color: #64748b; font-weight: normal; }
.version-line { margin: 8px 0; }
.warn { color: #d97706; font-weight: 600; margin-left: 6px; }
.muted { color: #94a3b8; font-size: 13px; margin: 4px 0 12px; }
.docs-section { margin-top: 12px; padding-top: 12px; border-top: 1px solid #f1f5f9; }
.docs-label { font-size: 13px; color: #475569; margin-bottom: 8px; }
.doc-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; font-size: 14px; }
.doc-icon { }
.doc-title { flex: 1; }
.doc-size { color: #64748b; font-size: 13px; }
.doc-dl { color: #2563eb; text-decoration: none; }
.doc-dl:hover { text-decoration: underline; }
.docs-hint { font-size: 12px; color: #94a3b8; margin-top: 8px; }
.docs-loading, .docs-err { font-size: 13px; color: #64748b; margin-top: 8px; }
.docs-err { color: #dc2626; }
.link { background: none; border: none; color: #2563eb; cursor: pointer; margin-top: 8px; font-size: 14px; }
.link-changelog { display: block; margin-top: 12px; }
.changelog { margin-top: 12px; padding: 12px; background: #f8fafc; border-radius: 8px; font-size: 13px; }
.changelog pre { margin: 0; white-space: pre-wrap; }
.footnote { font-size: 12px; color: #94a3b8; margin-top: 24px; line-height: 1.6; }
.subnav { margin-top: 20px; display: flex; gap: 16px; }
.subnav a { color: #2563eb; }
</style>
