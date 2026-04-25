<template>
  <div class="page">
    <h1 class="page__title">激活授权码</h1>
    <p class="page__subtitle">输入授权码后系统自动识别类型，确认信息无误后再点击激活。</p>

    <!-- Preview states -->
    <div v-if="step === 1" class="preview-section">
      <p class="section-label">预览不同状态</p>
      <div class="preview-tags">
        <span class="preview-tag">基础版续费</span>
        <span class="preview-tag">基础版首次激活</span>
        <span class="preview-tag">学科包激活</span>
      </div>
    </div>

    <div v-if="error" class="alert alert--error">{{ error }}</div>

    <!-- Step 1: Input -->
    <div v-if="step === 1">
      <p class="step-label">第一步 · 输入授权码</p>

      <form @submit.prevent="goToConfirm" class="input-section">
        <div class="input-row">
          <div class="input-group">
            <label class="field-label">授权码</label>
            <input
              v-model="code"
              type="text"
              class="code-input"
              placeholder="LINSCIO-XXXX-XXXX-XXXX"
              required
            />
          </div>
          <button type="submit" class="btn btn--ghost verify-btn">验证</button>
        </div>
        <p class="input-hint">格式：LINSCIO-XXXX-XXXX-XXXX，大小写不敏感，横杠自动补全</p>
      </form>
    </div>

    <!-- Step 2: Confirm -->
    <div v-else-if="step === 2">
      <p class="step-label">第二步 · 确认信息</p>
      <div class="confirm-card card">
        <p class="confirm-text">请确认以下授权码：</p>
        <div class="code-display">{{ code }}</div>
        <p class="text-muted" style="text-align:center;margin-top:8px;">点击「激活」后将立即生效，请确认无误。</p>
        <div class="btn-row mt-3">
          <button class="btn btn--ghost" @click="step = 1; error = ''">返回修改</button>
          <button class="btn btn--outline" :disabled="loading" @click="handleActivate">
            {{ loading ? '激活中...' : '激活' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Step 3: Complete -->
    <div v-else-if="step === 3 && result">
      <p class="step-label">第三步 · 激活完成</p>
      <div class="confirm-card card">
        <div class="alert alert--success">
          <p v-if="result.token_unchanged">授权已更新，有效期延长至 {{ formatDate(result.new_expires_at!) }}</p>
          <p v-else-if="result.deep_link">授权激活成功！</p>
          <p v-else>激活成功！</p>
          <p v-if="result.specialty_ids" class="mt-1">已激活学科包：{{ result.specialty_ids.join(', ') }}</p>
        </div>
        <p v-if="result.deep_link" class="mt-2">
          <a :href="result.deep_link" class="btn btn--outline btn--block">打开软件完成绑定</a>
        </p>
        <router-link to="/license" class="btn btn--ghost btn--block mt-2">返回我的授权</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { licenseActivate } from '@/api'

const code = ref('')
const step = ref(1)
const loading = ref(false)
const error = ref('')
const result = ref<any>(null)

function goToConfirm() {
  error.value = ''
  let val = code.value.trim().toUpperCase()
  val = val.replace(/[^A-Z0-9]/g, '')
  if (val.length >= 4 && !val.startsWith('LINSCIO')) {
    val = 'LINSCIO' + val
  }
  if (val.startsWith('LINSCIO') && val.length === 19) {
    val = `${val.slice(0, 7)}-${val.slice(7, 11)}-${val.slice(11, 15)}-${val.slice(15, 19)}`
  }
  code.value = val

  const pattern = /^LINSCIO-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$/
  if (!pattern.test(code.value)) {
    error.value = '授权码格式错误，正确格式为 LINSCIO-XXXX-XXXX-XXXX'
    return
  }
  step.value = 2
}

async function handleActivate() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await licenseActivate({ code: code.value })
    result.value = data
    step.value = 3
  } catch (e: any) {
    const detail = e.response?.data?.detail || ''
    const messages: Record<string, string> = {
      code_format_invalid: '授权码格式错误，请检查后重新输入',
      code_invalid_or_used: '授权码无效或已被使用',
      phone_not_verified: '请先完成手机号验证',
      rate_limit_exceeded: '操作过于频繁，请稍后再试',
      trial_cannot_activate_specialty: '试用用户无法激活学科包，请先激活正式授权',
      already_has_formal_license: '已拥有正式授权，无法再激活试用码',
    }
    error.value = messages[detail] || detail || '激活失败'
    step.value = 1
  } finally {
    loading.value = false
  }
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('zh-CN')
}
</script>

<style scoped lang="scss">
/* ── Preview ── */
.preview-section { margin-bottom: 32px; }
.section-label {
  font-size: 14px; color: var(--text-muted); margin-bottom: 14px;
}
.preview-tags {
  display: flex; gap: 12px;
}
.preview-tag {
  padding: 8px 20px; border: 1px solid var(--border); border-radius: 6px;
  font-size: 13px; color: var(--text-secondary);
}

/* ── Step label ── */
.step-label {
  font-size: 14px; font-weight: 600; color: var(--text-primary);
  margin-bottom: 16px;
}

/* ── Input section ── */
.input-section { max-width: 700px; }
.field-label {
  display: block; font-size: 13px; color: var(--text-muted); margin-bottom: 8px;
}
.input-row {
  display: flex; gap: 12px; align-items: flex-end;
}
.input-group { flex: 1; }
.code-input {
  width: 100%; padding: 14px 18px;
  border: 1px solid var(--border); border-radius: var(--radius);
  background: var(--bg-surface); color: var(--text-primary);
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 16px; letter-spacing: 1px; outline: none;
  transition: border-color 0.15s;
  &:focus { border-color: var(--primary); }
  &::placeholder { color: var(--text-muted); }
}
.verify-btn {
  height: 48px; padding: 0 24px; flex-shrink: 0;
}
.input-hint {
  font-size: 12px; color: var(--text-muted); margin-top: 10px;
}

/* ── Confirm / Result ── */
.confirm-card {
  max-width: 560px; padding: 32px;
}
.confirm-text {
  text-align: center; color: var(--text-secondary); margin-bottom: 8px;
}
.code-display {
  background: var(--bg-surface); border: 1px solid var(--border);
  padding: 14px 20px; border-radius: 8px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 18px; letter-spacing: 2px;
  text-align: center; font-weight: 600;
  color: var(--text-primary);
}
.btn-row {
  display: flex; gap: 12px; justify-content: center;
  .btn { min-width: 120px; }
}
</style>
