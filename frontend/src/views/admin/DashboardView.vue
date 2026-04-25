<template>
  <div class="dashboard">
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">总用户数</div>
        <div class="stat-value">{{ stats.total_users }}</div>
        <div class="stat-sub">今日新增 {{ stats.new_users_today }} · 近7天 {{ stats.new_users_7d }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">累计收入</div>
        <div class="stat-value">¥{{ stats.total_revenue }}</div>
        <div class="stat-sub">今日 ¥{{ stats.revenue_today }} · 近7天 ¥{{ stats.revenue_7d }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">成功订单</div>
        <div class="stat-value">{{ stats.total_orders }}</div>
        <div class="stat-sub">累计已支付订单</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">积分消耗</div>
        <div class="stat-value">{{ stats.total_credits_consumed }}</div>
        <div class="stat-sub">7日活跃用户 {{ stats.active_users_7d }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { http } from '@/api'

const stats = ref({
  total_users: 0, new_users_today: 0, new_users_7d: 0,
  total_orders: 0, total_revenue: 0, revenue_today: 0, revenue_7d: 0,
  total_credits_consumed: 0, active_users_7d: 0,
})

onMounted(async () => {
  try {
    const res = await http.get('/api/v1/admin/dashboard')
    stats.value = res.data
  } catch { /* ignore */ }
})
</script>

<style scoped>
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 20px;
}
.stat-card {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}
.stat-label { font-size: 0.85rem; color: #64748b; margin-bottom: 8px; }
.stat-value { font-size: 2rem; font-weight: 700; color: #1e293b; }
.stat-sub { font-size: 0.8rem; color: #94a3b8; margin-top: 8px; }
</style>
