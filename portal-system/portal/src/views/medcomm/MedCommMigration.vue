<template>
  <div class="page container-shell">
    <h1>账号迁移申请</h1>
    <p class="sub">若原邮箱/手机号无法使用，可提交申请由客服处理（1–3 个工作日）。</p>
    <div class="box">
      <label>目标联系方式（新邮箱或手机号）</label>
      <input v-model="toCred" type="text" class="wide" />
      <label>原因说明</label>
      <textarea v-model="reason" rows="4" class="wide" />
      <button class="btn" :disabled="loading" @click="submit">提交申请</button>
      <p v-if="msg" class="ok">{{ msg }}</p>
      <p v-if="err" class="err">{{ err }}</p>
    </div>
    <nav class="subnav">
      <router-link to="/medcomm/activate">← 返回</router-link>
      <router-link to="/medcomm/help">帮助中心</router-link>
    </nav>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { medcommAccount } from '../../api/medcomm'

const toCred = ref('')
const reason = ref('')
const loading = ref(false)
const msg = ref('')
const err = ref('')

async function submit() {
  msg.value = ''
  err.value = ''
  loading.value = true
  try {
    const { data } = await medcommAccount.migrationRequest({
      to_credential: toCred.value.trim(),
      reason: reason.value.trim(),
    })
    msg.value = data.message || '已提交'
  } catch (e) {
    err.value = e.response?.data?.detail || '提交失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.page { max-width: 560px; margin: 0 auto; padding: 100px 16px; }
.sub { color: #64748b; margin-bottom: 20px; }
.box { background: #fff; padding: 24px; border-radius: 12px; border: 1px solid #e2e8f0; }
label { display: block; font-size: 13px; margin: 12px 0 6px; }
.wide { width: 100%; padding: 10px; border-radius: 8px; border: 1px solid #cbd5e1; box-sizing: border-box; }
.btn { margin-top: 16px; padding: 12px 24px; background: #2563eb; color: #fff; border: none; border-radius: 8px; cursor: pointer; }
.ok { color: #059669; margin-top: 12px; }
.err { color: #dc2626; margin-top: 12px; }
.subnav { margin-top: 24px; display: flex; gap: 16px; }
.subnav a { color: #2563eb; }
</style>
