<template>
  <div class="quota-page page-shell" :class="{ compact: isCompact }">
    <header class="dash-header">
      <div class="container">
        <h1 class="page-title">生成次数</h1>
        <router-link to="/dashboard" class="back-link">← 返回用户中心</router-link>
      </div>
    </header>

    <div class="container main">
      <section class="card card-base">
        <template v-if="!license?.is_activated">
          <p class="locked-hint">请先在用户中心完成授权激活后，再查看生成次数。</p>
          <router-link to="/dashboard" class="btn btn-base btn-primary-ui">去激活</router-link>
        </template>
        <template v-else>
          <div v-if="summary?.cycle_start" class="cycle-info">
            <p><strong>当前周期：</strong>{{ summary.cycle_start }} ～ {{ summary.cycle_end }}</p>
            <p><strong>下次重置：</strong>{{ summary.next_reset_date }}</p>
          </div>
          <div v-if="!summary?.machines?.length" class="empty">
            暂无已绑定机器；安装并运行 LinScio AI 客户端并完成激活后，本机生成次数将显示在此。
          </div>
          <div v-else class="table-wrap">
            <table class="quota-table">
              <thead>
                <tr>
                  <th>机器</th>
                  <th>学术论文</th>
                  <th>医学科普</th>
                  <th>质控助手</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="m in summary.machines" :key="m.machine_id">
                  <td>
                    <span class="mono">{{ m.machine_id_display || m.machine_id }}</span>
                    <span v-if="m.machine_name" class="name">（{{ m.machine_name }}）</span>
                  </td>
                  <td v-for="t in typeOrder(m.types)" :key="t.content_type" :class="{ exhausted: t.exhausted }">
                    {{ t.used }} / {{ t.limit === 0 ? '不限' : t.limit }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="hint">生成次数按「每台机器每 90 天周期」统计，在主应用内新建项目时会扣减对应类型次数。</p>
        </template>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { user as userApi } from '../api'

const authStore = useAuthStore()
const license = ref(null)
const summary = ref(null)
const isCompact = ref(false)

const TYPE_ORDER = ['schola', 'medcomm', 'qcc']

function typeOrder(types) {
  if (!types?.length) return []
  return TYPE_ORDER.map(ct => types.find(t => t.content_type === ct)).filter(Boolean)
}

async function load() {
  const ok = await authStore.fetchProfile()
  if (!ok) return
  try {
    const [licRes, summaryRes] = await Promise.all([
      userApi.license(),
      userApi.quotaSummary(),
    ])
    license.value = licRes.data
    summary.value = summaryRes.data
  } catch (e) {
    if (e.response?.status === 401) return
    summary.value = { machines: [] }
  }
}


function setupCompactMode() {
  const forced = localStorage.getItem('portal_compact')
  if (forced === '1') {
    isCompact.value = true
    return
  }
  if (forced === '0') {
    isCompact.value = false
    return
  }
  isCompact.value = window.innerWidth <= 1366
}

onMounted(() => {
  setupCompactMode()
  load()
})
</script>

<style scoped>
.quota-page { padding-top: 68px; color: var(--color-text-body); }
.dash-header { background: var(--color-bg-base); border-bottom: 1px solid var(--color-border-soft); padding: 18px 24px; }
.container { max-width: 980px; margin: 0 auto; }
.page-title { font-size: 21px; margin: 0 0 6px 0; font-weight: 700; letter-spacing: -.2px; }
.back-link { font-size: var(--fs-md); color: var(--color-brand-700); }
.main { padding: 18px 24px 28px; }
.card { padding: 20px; border-radius: 14px; }
.cycle-info p { margin: 8px 0; font-size: 15px; }
.empty { color: var(--color-text-muted); padding: 20px 0; text-align: center; }
.table-wrap { overflow-x: auto; margin-top: 16px; }
.quota-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.quota-table th, .quota-table td { padding: 7px 10px; text-align: left; border-bottom: 1px solid var(--color-border-soft); line-height: 1.35; }
.quota-table th { color: var(--color-text-muted); font-weight: 600; font-size: var(--fs-xs); }
.mono { font-family: 'JetBrains Mono', monospace; }
.name { color: var(--color-text-muted); font-size: var(--fs-xs); }
.exhausted { color: #ef4444; }
.hint { font-size: var(--fs-sm); color: var(--color-text-muted); margin-top: 12px; }
.btn { padding: 6px 10px; border-radius: 9px; font-weight: 600; font-size: 12px; }
.btn-primary { color: #fff; text-decoration: none; display: inline-block; }
.locked-hint { color: var(--color-text-muted); margin-bottom: 10px; }


/* compact 开关：可通过 localStorage.portal_compact = "1" 强制启用；"0" 强制关闭 */
.compact .main { padding-top: 14px; padding-bottom: 20px; }
.compact .card { padding: 18px; border-radius: 12px; }
.compact .btn { padding: 5px 9px; font-size: 11px; }
.compact .table-wrap { margin-top: 12px; }
.compact .machine-table,
.compact .quota-table { font-size: 11px; }
.compact .machine-table th,
.compact .machine-table td,
.compact .quota-table th,
.compact .quota-table td { padding: 6px 8px; }
.compact .machine-table th,
.compact .quota-table th { font-size: 11px; }

</style>
