<template>
  <div class="download-v7">
    <section class="hero">
      <div class="container container-shell">
        <div class="tag tag-pill">DOWNLOAD CENTER</div>
        <h1>下载中心</h1>
        <p>同时提供桌面客户端入口与服务端部署包入口，满足个人研究与机构部署两类场景。</p>
      </div>
    </section>

    <section class="section">
      <div class="container container-shell two-cols">
        <article class="panel card-base">
          <h2>入口一：桌面安装包</h2>
          <p class="desc">用于本地客户端安装（Windows / macOS / Linux）。你可在发布后将链接替换为 COS 预签名地址。</p>
          <div class="desktop-grid">
            <div v-for="item in desktopPackages" :key="item.os" class="pkg-card card-base">
              <div class="pkg-icon">{{ item.icon }}</div>
              <h3>{{ item.os }}</h3>
              <p>{{ item.desc }}</p>
              <a :href="item.url || '#'" target="_blank" rel="noopener noreferrer" class="btn btn-base btn-primary-ui" :class="{ disabled: !item.url }">
                {{ item.url ? '下载' : '即将发布' }}
              </a>
            </div>
          </div>
        </article>

        <article class="panel card-base">
          <h2>入口二：服务端部署包</h2>
          <p class="desc">输入授权码获取当前版本服务端部署包，链接短时有效，适用于 Docker 部署。</p>

          <div class="code-row">
            <input
              v-model="licenseCode"
              type="text"
              placeholder="LINSCIO-XXXX-XXXX-XXXX-XXXX"
              class="code-input"
              @keydown.enter="getLink"
            />
            <button class="btn btn-base btn-primary-ui" :disabled="loading || !licenseCode.trim()" @click="getLink">
              {{ loading ? '获取中…' : '验证并获取链接' }}
            </button>
          </div>
          <p v-if="error" class="error">{{ error }}</p>
          <p class="hint">当前版本：{{ currentVersion ? `v ${currentVersion}` : (currentVersionError === 404 ? '暂无可用版本' : '加载中…') }}</p>

          <div v-if="result" class="result-box">
            <h3>✅ 链接已生成</h3>
            <p>版本：v {{ result.version }} <span v-if="result.file_size">· {{ formatSize(result.file_size) }}</span></p>
            <p class="hint">链接 2 小时内有效，请尽快下载。</p>
            <div class="result-actions">
              <a :href="result.download_url" target="_blank" rel="noopener noreferrer" class="btn btn-base btn-primary-ui">下载安装包</a>
              <a href="/docs/" target="_blank" rel="noopener noreferrer" class="btn btn-base btn-outline-ui">查看部署文档</a>
            </div>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { download as downloadApi } from '../api'

const currentVersion = ref(null)
const currentVersionError = ref(null)
const licenseCode = ref('')
const loading = ref(false)
const error = ref('')
const result = ref(null)

const desktopPackages = ref([
  { icon: '🍎', os: 'macOS (Apple Silicon)', desc: 'M1/M2/M3 ARM64', url: '' },
  { icon: '🖥', os: 'macOS (Intel)', desc: 'x64', url: '' },
  { icon: '🪟', os: 'Windows', desc: 'Windows 10/11 x64', url: '' },
  { icon: '🐧', os: 'Linux', desc: 'x64 / arm64', url: '' },
])

function formatSize(bytes) {
  if (bytes == null || bytes === 0) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

async function loadCurrentVersion() {
  try {
    const { data } = await downloadApi.getCurrentVersion()
    currentVersion.value = data.version
    currentVersionError.value = null
  } catch (e) {
    currentVersionError.value = e.response?.status ?? 500
  }
}

async function getLink() {
  error.value = ''
  result.value = null
  const code = licenseCode.value.trim()
  if (!code) return
  loading.value = true
  try {
    const { data } = await downloadApi.getPresignUrl(code)
    result.value = data
  } catch (e) {
    const detail = e.response?.data?.detail
    if (typeof detail === 'string') error.value = detail
    else if (Array.isArray(detail) && detail[0]?.msg) error.value = detail[0].msg
    else error.value = '获取下载链接失败，请检查授权码或稍后重试'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadCurrentVersion()
})
</script>

<style scoped>
.download-v7 { min-height: calc(100vh - 68px); background: var(--color-bg-base); color: var(--color-text-body); }
.hero { padding: 52px 0 24px; border-bottom: 1px solid var(--color-border-soft); background: linear-gradient(160deg, #f0f7ff 0%, #e8f2ff 40%, #f5f9ff 70%, #ffffff 100%); }
.container { max-width: var(--container-max); margin: 0 auto; padding: 0 var(--space-6); }
.hero h1 { margin: 14px 0 10px; font-size: clamp(30px, 4vw, 46px); color: var(--color-text-strong); }
.hero p { color: var(--color-text-muted); max-width: 780px; }

.section { padding: 26px 0 44px; background: #f8fafc; }
.two-cols { display: grid; grid-template-columns: 1.1fr 1fr; gap: 18px; align-items: start; }
.panel { border-radius: var(--radius-xl); padding: var(--space-6); transition: all .25s ease; box-shadow: none; }
.panel:hover { border-color: var(--color-border-brand); box-shadow: var(--shadow-card-hover); }
.panel h2 { font-size: 24px; margin-bottom: 10px; color: #0f172a; }
.desc { color: #64748b; margin-bottom: 16px; line-height: 1.7; }

.desktop-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.pkg-card { border-radius: var(--radius-lg); padding: 14px; transition: all .2s; box-shadow: none; }
.pkg-card:hover { border-color: var(--color-border-brand); box-shadow: var(--shadow-card); }
.pkg-icon { font-size: 24px; }
.pkg-card h3 { margin-top: 6px; font-size: 16px; color: #0f172a; }
.pkg-card p { color: #64748b; font-size: 13px; margin: 6px 0 10px; min-height: 34px; }

.code-row { display: flex; gap: 10px; }
.code-input {
  flex: 1; background: #fff; color: #0f172a; border: 1.5px solid #cbd5e1;
  border-radius: 10px; padding: 11px 12px; font-family: 'JetBrains Mono', monospace;
}
.code-input:focus { outline: none; border-color: #60a5fa; box-shadow: 0 0 0 3px rgba(59,130,246,.08); }
.error { margin-top: 8px; color: #ef4444; font-size: 14px; }
.hint { margin-top: 10px; color: #64748b; font-size: 13px; }

.result-box { margin-top: 16px; padding: 14px; border-radius: 10px; background: #f0fdf4; border: 1px solid #bbf7d0; }
.result-box h3 { font-size: 16px; margin-bottom: 6px; }
.result-box p { color: #166534; font-size: 14px; }
.result-actions { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 12px; }

.btn { text-decoration: none; }
.btn.disabled { opacity: .5; pointer-events: none; }

@media (max-width: 920px) {
  .two-cols { grid-template-columns: 1fr; }
}
@media (max-width: 620px) {
  .desktop-grid { grid-template-columns: 1fr; }
  .code-row { flex-direction: column; }
}
</style>
