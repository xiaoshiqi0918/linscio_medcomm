<template>
  <div class="config-page">
    <el-card shadow="never" style="margin-bottom: 20px;">
      <template #header>系统状态</template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="运行模式">{{ config.deployment_mode }}</el-descriptions-item>
        <el-descriptions-item label="已启用渠道">
          <el-tag v-for="ch in config.payment_channels" :key="ch" size="small" style="margin-right: 4px;">{{ ch }}</el-tag>
          <span v-if="!config.payment_channels?.length" style="color: #9ca3af;">无</span>
        </el-descriptions-item>
        <el-descriptions-item label="订单超时">{{ config.order_expire_minutes }} 分钟</el-descriptions-item>
        <el-descriptions-item label="新用户赠送">{{ config.new_user_gift_credits }} 积分</el-descriptions-item>
        <el-descriptions-item label="赠送有效期">{{ config.gift_credits_validity_days }} 天</el-descriptions-item>
        <el-descriptions-item label="推广折现率">1积分 = {{ config.promo_cash_rate }} 元</el-descriptions-item>
        <el-descriptions-item label="最低提现">{{ config.promo_min_withdraw }} 积分</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card shadow="never">
      <template #header>充值套餐配置</template>
      <el-table :data="planList" style="width: 100%;" stripe>
        <el-table-column prop="amount" label="金额(元)" width="100">
          <template #default="{ row }">¥{{ row.amount }}</template>
        </el-table-column>
        <el-table-column prop="credits" label="积分" width="100" />
        <el-table-column prop="bonus" label="赠送" width="100" />
        <el-table-column label="单价" width="140">
          <template #default="{ row }">
            {{ (row.amount / (row.credits + row.bonus) * 10).toFixed(2) }} 元/10积分
          </template>
        </el-table-column>
      </el-table>
      <p style="margin-top: 12px; color: #9ca3af; font-size: 0.85rem;">
        套餐配置目前在后端代码中定义，修改后需重启后端生效。
      </p>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { http } from '@/api'

const config = ref<any>({})

const planList = computed(() => {
  const plans = config.value.recharge_plans || {}
  return Object.entries(plans).map(([amount, plan]: [string, any]) => ({
    amount: parseInt(amount),
    credits: plan.credits,
    bonus: plan.bonus,
  })).sort((a, b) => a.amount - b.amount)
})

onMounted(async () => {
  try {
    const res = await http.get('/api/v1/admin/config')
    config.value = res.data
  } catch { /* ignore */ }
})
</script>
