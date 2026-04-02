<template>
  <div class="stats">
    <h2>数据总览</h2>
    <el-row :gutter="16" class="cards">
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover">
          <div class="stat-label">注册用户总数</div>
          <div class="stat-value">{{ stats?.total_users ?? '—' }}</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover">
          <div class="stat-label">已激活用户</div>
          <div class="stat-value">{{ stats?.activated_users ?? '—' }}</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover">
          <div class="stat-label">授权码总量</div>
          <div class="stat-value">{{ stats?.total_licenses ?? '—' }}</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover">
          <div class="stat-label">本月新增用户</div>
          <div class="stat-value">{{ stats?.new_users_this_month ?? '—' }}</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover">
          <div class="stat-label">本月新增激活</div>
          <div class="stat-value">{{ stats?.new_activations_this_month ?? '—' }}</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover">
          <div class="stat-label">机器绑定总数</div>
          <div class="stat-value">{{ stats?.machine_bindings_total ?? '—' }}</div>
        </el-card>
      </el-col>
    </el-row>
    <p v-if="!stats && !loading" class="tip">请先登录</p>
    <p v-if="error" class="error">{{ error }}</p>

    <el-row v-if="stats" :gutter="16" class="charts-row">
      <el-col :xs="24" :lg="14">
        <el-card shadow="hover" class="chart-card">
          <template #header>近 30 天注册趋势</template>
          <div ref="trendChartRef" class="chart"></div>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="10">
        <el-card shadow="hover" class="chart-card">
          <template #header>授权码状态分布</template>
          <div ref="pieChartRef" class="chart"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-row v-if="stats && (stats.plan_breakdown?.length || 0) > 0" :gutter="16" class="charts-row">
      <el-col :xs="24" :lg="12">
        <el-card shadow="hover" class="chart-card">
          <template #header>套餐存量分布</template>
          <div ref="planPieRef" class="chart"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-card v-if="stats?.expiring_7_days?.length" class="expiring-card" shadow="hover">
      <template #header>
        <span>⚠️ 7 天内到期</span>
      </template>
      <el-table :data="stats.expiring_7_days" size="small">
        <el-table-column prop="code" label="授权码" width="220" show-overflow-tooltip />
        <el-table-column prop="plan_name" label="套餐" width="100" />
        <el-table-column prop="expires_at" label="有效期至" width="120">
          <template #default="{ row }">{{ formatDate(row.expires_at) }}</template>
        </el-table-column>
        <el-table-column prop="assigned_username" label="绑定用户" width="120" />
        <el-table-column prop="status" label="状态" />
      </el-table>
    </el-card>

    <el-card v-if="stats && (stats.expiring_licenses?.length || 0) > 0" class="expiring-card" shadow="hover">
      <template #header>
        <span>即将到期（30 天内）的授权码</span>
      </template>
      <el-table :data="stats.expiring_licenses" size="small">
        <el-table-column prop="code" label="授权码" width="220" show-overflow-tooltip />
        <el-table-column prop="plan_name" label="套餐" width="100" />
        <el-table-column prop="expires_at" label="有效期至" width="120">
          <template #default="{ row }">{{ formatDate(row.expires_at) }}</template>
        </el-table-column>
        <el-table-column prop="assigned_username" label="绑定用户" width="120" />
      </el-table>
    </el-card>

    <el-card v-if="stats?.pull_top10_this_month?.length" class="top-card" shadow="hover">
      <template #header>本月拉取 Top 10</template>
      <el-table :data="stats.pull_top10_this_month" size="small">
        <el-table-column prop="username" label="用户" width="140" />
        <el-table-column prop="pull_count" label="拉取次数" width="120" />
      </el-table>
    </el-card>

    <el-card v-if="stats?.alerts?.length" class="alerts-card" shadow="hover">
      <template #header>⚠️ 异常监控</template>
      <ul class="alerts-list">
        <li v-for="(msg, i) in stats.alerts" :key="i">{{ msg }}</li>
      </ul>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { admin } from '../api'

const stats = ref(null)
const loading = ref(false)
const error = ref('')
const statsIntervalId = ref(null)
const trendChartRef = ref(null)
const pieChartRef = ref(null)
const planPieRef = ref(null)
let trendChart = null
let pieChart = null
let planPieChart = null

function formatDate(d) {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('zh-CN')
}

function initCharts() {
  if (!stats.value) return
  // 折线图：近 30 天注册趋势
  if (trendChartRef.value) {
    if (trendChart) trendChart.dispose()
    trendChart = echarts.init(trendChartRef.value)
    const trend = stats.value.registration_trend || []
    trendChart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: trend.map((t) => t.date.slice(5)) },
      yAxis: { type: 'value', minInterval: 1 },
      series: [{ name: '注册数', type: 'line', smooth: true, data: trend.map((t) => t.count), itemStyle: { color: '#1a3fcc' } }],
      grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
    })
  }
  // 环形图：授权码状态
  if (pieChartRef.value) {
    if (pieChart) pieChart.dispose()
    pieChart = echarts.init(pieChartRef.value)
    const ls = stats.value.license_status || { used: 0, unused: 0, revoked: 0 }
    const total = ls.used + ls.unused + ls.revoked
    const data = []
    if (ls.used > 0) data.push({ value: ls.used, name: '已使用', itemStyle: { color: '#67c23a' } })
    if (ls.unused > 0) data.push({ value: ls.unused, name: '未使用', itemStyle: { color: '#e6a23c' } })
    if (ls.revoked > 0) data.push({ value: ls.revoked, name: '已作废', itemStyle: { color: '#909399' } })
    if (data.length === 0) data.push({ value: 1, name: '暂无', itemStyle: { color: '#eee' } })
    pieChart.setOption({
      tooltip: { trigger: 'item' },
      legend: { bottom: 0 },
      series: [{ type: 'pie', radius: ['40%', '70%'], center: ['50%', '45%'], data, label: { show: true, formatter: '{b}: {c}' } }],
    })
  }
  // 套餐存量分布
  if (planPieRef.value && (stats.value.plan_breakdown?.length || 0) > 0) {
    if (planPieChart) planPieChart.dispose()
    planPieChart = echarts.init(planPieRef.value)
    const colors = ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de']
    const data = stats.value.plan_breakdown.map((p, i) => ({
      value: p.count,
      name: p.plan_name || p.plan_code,
      itemStyle: { color: colors[i % colors.length] },
    }))
    planPieChart.setOption({
      tooltip: { trigger: 'item' },
      legend: { bottom: 0 },
      series: [{ type: 'pie', radius: ['40%', '70%'], center: ['50%', '45%'], data, label: { show: true, formatter: '{b}: {c}' } }],
    })
  }
}

async function fetchStats() {
  error.value = ''
  try {
    const { data } = await admin.stats()
    stats.value = data
    setTimeout(() => initCharts(), 100)
  } catch (e) {
    const d = e.response?.data?.detail
    if (typeof d === 'string' && d.trim()) {
      error.value = d
    } else if (e.response?.data?.message) {
      error.value = e.response.data.message
    } else if (e.response?.status === 401) {
      error.value = '未登录或登录已过期，请重新登录'
    } else if (e.response?.status === 403) {
      error.value = '无权限访问'
    } else if (!e.response) {
      error.value = '网络错误，请确认门户 API（linscio-api）已启动且可访问'
    } else {
      error.value = '加载失败，请稍后重试'
    }
  }
}

onMounted(async () => {
  const token = localStorage.getItem('admin_token')
  error.value = ''
  if (!token) {
    return
  }
  loading.value = true
  try {
    await fetchStats()
  } finally {
    loading.value = false
  }
  // 7.2 看板数据每 60 秒自动刷新（异常预警随 stats 一起刷新）
  statsIntervalId.value = setInterval(fetchStats, 60 * 1000)
})

onUnmounted(() => {
  if (statsIntervalId.value) clearInterval(statsIntervalId.value)
})

watch(stats, () => setTimeout(() => initCharts(), 100), { deep: true })
</script>

<style scoped>
.stats { padding: 0 0 24px 0; }
.cards { margin-top: 16px; }
.stat-label { font-size: 14px; color: #666; }
.stat-value { font-size: 24px; font-weight: 600; margin-top: 8px; }
.tip, .error { margin-top: 16px; font-size: 14px; }
.error { color: #f56c6c; }
.expiring-card { margin-top: 24px; }
.top-card { margin-top: 24px; }
.alerts-card { margin-top: 24px; }
.alerts-list { margin: 0; padding-left: 20px; color: #e6a23c; }
.charts-row { margin-top: 24px; }
.chart-card { margin-bottom: 16px; }
.chart { height: 280px; }
</style>
