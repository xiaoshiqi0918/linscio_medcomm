<template>
  <div class="page container-shell">
    <h1>软件更新与下载</h1>
    <p class="sub">检查 MedComm 客户端是否有新版本，并在授权有效期内获取安装包下载链接（依赖服务端发布与 COS 配置）。</p>

    <div class="box">
      <label>当前软件版本</label>
      <input v-model="softwareVersion" type="text" class="wide" placeholder="例如 1.0.0" />
      <label>平台</label>
      <select v-model="platform" class="wide">
        <option value="mac-arm64">macOS (Apple Silicon)</option>
        <option value="mac-x64">macOS (Intel)</option>
        <option value="win-x64">Windows x64</option>
      </select>
      <label>本机学科包版本（可选，JSON 或留空）</label>
      <textarea v-model="specialtiesJson" rows="3" class="wide mono" placeholder='{"cardiology":"1.0.0"}' />
      <button class="btn" type="button" :disabled="loading" @click="checkUpdate">检查更新</button>
      <p v-if="checkMsg" class="hint">{{ checkMsg }}</p>

      <div v-if="softwareInfo?.download_url" class="block">
        <h3>软件更新</h3>
        <p>新版本：{{ softwareInfo.version }}</p>
        <p v-if="softwareInfo.release_notes" class="notes">{{ softwareInfo.release_notes }}</p>
        <a :href="softwareInfo.download_url" class="link-btn" target="_blank" rel="noopener">下载安装包</a>
      </div>

      <div v-if="specialtyUpdates.length" class="block">
        <h3>学科包更新</h3>
        <div v-for="u in specialtyUpdates" :key="u.id" class="spec-row">
          <strong>{{ u.id }}</strong>
          <span v-if="u.has_update">可更新至 {{ u.latest_version }}</span>
          <span v-else class="muted">已是最新</span>
          <span v-if="u.force_update" class="warn">{{ u.force_message || '需强制更新' }}</span>
        </div>
      </div>

      <hr class="sep" />
      <h3>直接获取当前正式版安装包</h3>
      <button class="btn secondary" type="button" :disabled="dlLoading" @click="downloadSoftware">获取下载链接</button>
      <p v-if="dlMsg" :class="dlOk ? 'ok' : 'err'">{{ dlMsg }}</p>
      <a v-if="swUrl" :href="swUrl" class="link-btn" target="_blank" rel="noopener">{{ swUrl }}</a>
    </div>

    <nav class="subnav">
      <router-link to="/medcomm/activate">激活</router-link>
      <router-link to="/medcomm/specialties">我的学科包</router-link>
      <router-link to="/medcomm/help">帮助中心</router-link>
    </nav>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { medcommUpdate, medcommDownload } from '../../api/medcomm'

const softwareVersion = ref('1.0.0')
const platform = ref('mac-arm64')
const specialtiesJson = ref('{}')
const loading = ref(false)
const checkMsg = ref('')
const softwareInfo = ref(null)
const specialtyUpdates = ref([])

const dlLoading = ref(false)
const dlMsg = ref('')
const dlOk = ref(false)
const swUrl = ref('')

function parseSpecialties() {
  try {
    const o = JSON.parse(specialtiesJson.value || '{}')
    return typeof o === 'object' && o !== null ? o : {}
  } catch {
    return {}
  }
}

async function checkUpdate() {
  checkMsg.value = ''
  softwareInfo.value = null
  specialtyUpdates.value = []
  loading.value = true
  try {
    const { data } = await medcommUpdate.check({
      platform: platform.value,
      software_version: softwareVersion.value.trim() || '0.0.0',
      specialties: parseSpecialties(),
    })
    if (!data.base_valid) {
      checkMsg.value = '当前账号授权无效或已过期，请先激活基础版。'
    } else if (!data.has_software_update && !(data.specialty_updates || []).some((x) => x.has_update)) {
      checkMsg.value = '暂无软件或学科包更新。'
    } else {
      checkMsg.value = '检查完成，见下方结果。'
    }
    if (data.has_software_update && data.software) softwareInfo.value = data.software
    specialtyUpdates.value = data.specialty_updates || []
  } catch (e) {
    checkMsg.value = e.response?.data?.detail || '检查失败'
  } finally {
    loading.value = false
  }
}

async function downloadSoftware() {
  dlMsg.value = ''
  swUrl.value = ''
  dlLoading.value = true
  try {
    const { data } = await medcommDownload.software({ platform: platform.value })
    if (data.success && data.download_url) {
      dlOk.value = true
      dlMsg.value = `已生成链接（约 1 小时有效）${data.filename ? ` · ${data.filename}` : ''}`
      swUrl.value = data.download_url
      if (data.download_log_id) {
        window.setTimeout(() => {
          medcommDownload.complete({ download_log_id: data.download_log_id }).catch(() => {})
        }, 2000)
      }
    } else {
      dlOk.value = false
      const errMap = {
        license_expired: '授权已过期',
        not_activated: '尚未在软件端完成激活',
        no_release: '服务端未配置当前版本',
        cos_not_configured: '下载服务未配置（COS）',
      }
      dlMsg.value = errMap[data.error] || data.error || '获取失败'
    }
  } catch (e) {
    dlOk.value = false
    dlMsg.value = e.response?.data?.detail || '请求失败'
  } finally {
    dlLoading.value = false
  }
}
</script>

<style scoped>
.page { max-width: 720px; margin: 0 auto; padding: 100px 16px 48px; }
.sub { color: #64748b; margin-bottom: 20px; line-height: 1.6; }
.box {
  background: #fff; border-radius: 12px; padding: 24px;
  border: 1px solid #e2e8f0;
}
label { display: block; font-size: 13px; margin: 14px 0 6px; color: #475569; }
.wide { width: 100%; padding: 10px; border-radius: 8px; border: 1px solid #cbd5e1; box-sizing: border-box; }
.mono { font-family: ui-monospace, monospace; font-size: 13px; }
.btn {
  margin-top: 16px; padding: 12px 20px; background: #2563eb; color: #fff;
  border: none; border-radius: 8px; font-weight: 600; cursor: pointer;
}
.btn.secondary { background: #475569; margin-top: 8px; }
.hint { margin-top: 12px; color: #64748b; font-size: 14px; }
.block { margin-top: 24px; padding: 16px; background: #f8fafc; border-radius: 8px; }
.block h3 { margin-bottom: 10px; font-size: 1rem; }
.notes { white-space: pre-wrap; font-size: 13px; color: #475569; margin: 8px 0; }
.spec-row { display: flex; flex-wrap: wrap; gap: 8px 16px; margin-bottom: 8px; align-items: center; }
.muted { color: #94a3b8; }
.warn { color: #d97706; font-weight: 600; }
.link-btn { display: inline-block; margin-top: 8px; word-break: break-all; color: #2563eb; }
.sep { margin: 28px 0; border: none; border-top: 1px solid #e2e8f0; }
.ok { color: #059669; margin-top: 10px; }
.err { color: #dc2626; margin-top: 10px; }
.subnav { margin-top: 28px; display: flex; gap: 16px; }
.subnav a { color: #2563eb; }
</style>
