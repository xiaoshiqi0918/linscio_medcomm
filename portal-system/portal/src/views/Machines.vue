<template>
  <div class="machines-page page-shell" :class="{ compact: isCompact }">
    <header class="dash-header">
      <div class="container">
        <h1 class="page-title">机器管理</h1>
        <router-link to="/dashboard" class="back-link">← 返回用户中心</router-link>
      </div>
    </header>

    <div class="container main">
      <section class="card card-base">
        <template v-if="!license?.is_activated">
          <p class="locked-hint">请先在用户中心完成授权激活后，再管理已绑定机器。</p>
          <router-link to="/dashboard" class="btn btn-base btn-primary-ui">去激活</router-link>
        </template>
        <template v-else>
          <div class="summary">
            <p><strong>套餐：</strong>{{ data?.plan_name ?? '—' }}</p>
            <p><strong>已绑定：</strong>{{ data?.binding_count ?? 0 }} / {{ data?.machine_limit ?? 0 }} 台</p>
            <p v-if="data?.slots_remaining != null"><strong>剩余槽位：</strong>{{ data.slots_remaining }} 台</p>
            <p class="hint-text">{{ data?.can_self_unbind ? '支持自助解绑。解绑后该机器可重新绑定到其他授权。' : (data?.unbind_hint || '') }}</p>
          </div>

          <div v-if="!list.length" class="empty">暂无已绑定机器。安装并运行 LinScio AI 客户端并完成激活后，机器将出现在此列表。</div>
          <div v-else class="table-wrap">
            <table class="machine-table">
              <thead>
                <tr>
                  <th>机器 ID</th>
                  <th>名称</th>
                  <th>首次上报</th>
                  <th>最近心跳</th>
                  <th>状态</th>
                  <th v-if="data?.can_self_unbind">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="b in list" :key="b.id">
                  <td class="mono">{{ b.machine_id_display || b.machine_id || '—' }}</td>
                  <td>{{ b.machine_name || '—' }}</td>
                  <td>{{ b.first_seen ? formatDate(b.first_seen) : '—' }}</td>
                  <td>{{ b.last_heartbeat ? formatDate(b.last_heartbeat) : '—' }}</td>
                  <td>
                    <span class="status" :class="b.is_online ? 'online' : 'offline'">{{ b.is_online ? '在线' : '离线' }}</span>
                  </td>
                  <td v-if="data?.can_self_unbind">
                    <button class="btn btn-base btn-sm btn-danger" :disabled="unbinding === b.id" @click="unbind(b.id)">
                      {{ unbinding === b.id ? '解绑中…' : '解绑' }}
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-if="data && !data.can_self_unbind && list.length" class="hint-text margin-top">如需解绑机器，请联系管理员。</p>
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
const data = ref(null)
const list = ref([])
const unbinding = ref(null)
const isCompact = ref(false)

function formatDate(d) {
  if (!d) return '—'
  const date = typeof d === 'string' ? new Date(d) : d
  return date.toLocaleString('zh-CN', { dateStyle: 'short', timeStyle: 'short' })
}

async function load() {
  const ok = await authStore.fetchProfile()
  if (!ok) return
  try {
    const [licRes, machinesRes] = await Promise.all([
      userApi.license(),
      userApi.machines(),
    ])
    license.value = licRes.data
    data.value = machinesRes.data
    list.value = machinesRes.data?.bindings ?? []
  } catch (e) {
    if (e.response?.status === 401) return
    list.value = []
  }
}

async function unbind(bindingId) {
  if (!confirm('确定要解绑该机器吗？解绑后可重新绑定到其他授权。')) return
  unbinding.value = bindingId
  try {
    await userApi.deleteMachine(bindingId)
    await load()
  } catch (e) {
    alert(e.response?.data?.detail || '解绑失败')
  } finally {
    unbinding.value = null
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
.machines-page { padding-top: 68px; color: var(--color-text-body); }
.dash-header { background: var(--color-bg-base); border-bottom: 1px solid var(--color-border-soft); padding: 18px 24px; }
.container { max-width: 980px; margin: 0 auto; }
.page-title { font-size: 21px; margin: 0 0 6px 0; font-weight: 700; letter-spacing: -.2px; }
.back-link { font-size: var(--fs-md); color: var(--color-brand-700); }
.main { padding: 18px 24px 28px; }
.card { padding: 20px; border-radius: 14px; }
.summary p { margin: 8px 0; font-size: 15px; }
.hint-text { font-size: var(--fs-sm); color: var(--color-text-muted); margin-top: 8px; }
.margin-top { margin-top: 14px; }
.empty { color: var(--color-text-muted); padding: 20px 0; text-align: center; }
.table-wrap { overflow-x: auto; margin-top: 16px; }
.machine-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.machine-table th, .machine-table td { padding: 7px 10px; text-align: left; border-bottom: 1px solid var(--color-border-soft); line-height: 1.35; }
.machine-table th { color: var(--color-text-muted); font-weight: 600; font-size: var(--fs-xs); }
.mono { font-family: 'JetBrains Mono', monospace; }
.status { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; }
.status.online { background: rgba(0,229,160,.15); color: #00e5a0; }
.status.offline { background: #e5e7eb; color: #64748b; }
.btn { padding: 6px 10px; border-radius: 9px; font-weight: 600; font-size: 12px; cursor: pointer; border: 1px solid transparent; }
.btn-primary { color: #fff; text-decoration: none; display: inline-block; }
.btn-sm { padding: 4px 8px; font-size: 11px; }
.btn-danger { background: rgba(239,68,68,.15); color: #ff7d95; border-color: rgba(239,68,68,.25); }
.btn-danger:disabled { opacity: .6; cursor: not-allowed; }
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
