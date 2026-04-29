<template>
  <div class="settings page-container page-cards">
    <h2>设置</h2>

    <!-- SaaS 模式：账户与积分 -->
    <el-card v-if="!isElectronEnv" class="settings-card">
      <template #header>账户信息</template>

      <!-- 未登录状态 -->
      <div v-if="!saasLoggedIn" class="about-section" style="text-align: center; padding: 32px 0;">
        <div style="font-size: 2.5rem; margin-bottom: 12px;">👋</div>
        <div style="font-size: 1.1rem; color: #374151; font-weight: 600; margin-bottom: 6px;">您还未登录</div>
        <div style="font-size: 0.9rem; color: #6b7280; margin-bottom: 20px; line-height: 1.6;">
          登录后即可使用 AI 写作、积分充值、推广返利等全部功能<br />
          新用户注册即赠 <strong style="color: #1e40af;">3 积分</strong>，可免费体验
        </div>
        <div style="display: flex; justify-content: center; gap: 12px;">
          <el-button type="primary" size="large" @click="router.push('/login?redirect=/settings')">登录</el-button>
          <el-button size="large" @click="router.push('/register')">注册账号</el-button>
        </div>
      </div>

      <!-- 已登录状态 -->
      <div v-if="saasLoggedIn">
      <div class="about-section">
        <div class="about-row"><span class="label">用户</span> {{ saasUser?.display_name || '-' }}</div>
        <div class="about-row"><span class="label">手机号</span> {{ saasUser?.phone || '-' }}</div>
        <div class="about-row"><span class="label">注册时间</span> {{ saasUser?.created_at ? new Date(saasUser.created_at).toLocaleDateString('zh-CN') : '-' }}</div>
      </div>
      <div class="about-section" style="margin-top: 12px; border-top: 1px solid #e5e7eb; padding-top: 12px;">
        <div class="about-row"><span class="label">积分余额</span>
          <span style="font-weight: 600; color: #1e40af;">{{ saasCredits.total_available ?? 0 }}</span>
          <span style="margin-left: 8px; color: #6b7280; font-size: 0.85rem;">
            （充值 {{ saasCredits.credits ?? 0 }} + 赠送 {{ saasCredits.gift_credits ?? 0 }}）
          </span>
        </div>
        <div v-if="saasCredits.gift_credits_expire_at" class="about-row">
          <span class="label">赠送到期</span> {{ new Date(saasCredits.gift_credits_expire_at).toLocaleDateString('zh-CN') }}
        </div>
        <div class="about-row"><span class="label">累计充值</span> {{ saasCredits.total_recharged ?? 0 }} 积分</div>
        <div class="about-row"><span class="label">累计消耗</span> {{ saasCredits.total_consumed ?? 0 }} 积分</div>
        <div class="about-row" style="margin-top: 8px; gap: 8px;">
          <el-button type="primary" size="small" @click="showRechargeDialog = true">充值积分</el-button>
          <router-link to="/help#credits" style="font-size: 0.82rem; color: #2563eb; text-decoration: none;">查看分档计费规则与模型策略 →</router-link>
        </div>
      </div>
      <div class="about-section" style="margin-top: 12px; border-top: 1px solid #e5e7eb; padding-top: 12px;">
        <div class="about-row" style="align-items: center;">
          <span class="label">推广积分</span>
          <span style="font-weight: 600; color: #059669;">{{ saasCredits.promo?.promo_credits ?? 0 }}</span>
          <el-tag size="small" type="success" style="margin-left: 8px;">可折现 / 可兑换授权码</el-tag>
        </div>
        <div class="about-row" style="color: #6b7280; font-size: 0.85rem;">
          折现比例：1 积分 = {{ saasCredits.promo?.cash_rate ?? 0.1 }} 元 · 当前可折现约
          <span style="font-weight: 600; color: #059669;">¥{{ saasCredits.promo?.cash_value_yuan ?? 0 }}</span>
        </div>
        <div v-if="saasCredits.promo?.promo_credits_expire_at" class="about-row" style="font-size: 0.85rem; color: #6b7280;">
          推广积分到期：{{ new Date(saasCredits.promo.promo_credits_expire_at).toLocaleDateString('zh-CN') }}
        </div>
      </div>

      <!-- 推广中心 -->
      <div class="about-section referral-center" style="margin-top: 12px; border-top: 1px solid #e5e7eb; padding-top: 12px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
          <span style="font-weight: 600; color: #374151;">推广中心</span>
          <el-button text size="small" @click="loadReferralInfo" :loading="loadingReferral">刷新</el-button>
        </div>

        <!-- 推广码 & 链接 -->
        <div v-if="referralInfo" class="referral-code-block">
          <div class="about-row" style="align-items: center; gap: 10px;">
            <span class="label">我的推广码</span>
            <span style="font-family: monospace; font-size: 1.1rem; font-weight: 700; color: #1e40af; user-select: all; letter-spacing: 1px;">{{ referralInfo.referral_code }}</span>
            <el-button text size="small" type="primary" @click="copyReferralLink">复制推广链接</el-button>
            <el-button text size="small" @click="resetReferralCode">重置推广码</el-button>
          </div>
          <div class="about-row" style="margin-top: 6px; font-size: 0.82rem; color: #6b7280; word-break: break-all;">
            {{ referralInfo.referral_link }}
          </div>
        </div>

        <!-- 推广统计 -->
        <div v-if="referralInfo" style="display: flex; gap: 24px; margin-top: 12px;">
          <div class="referral-stat">
            <div class="referral-stat-value">{{ referralInfo.total_referred }}</div>
            <div class="referral-stat-label">邀请人数</div>
          </div>
          <div class="referral-stat">
            <div class="referral-stat-value" style="color: #059669;">{{ referralInfo.total_reward_credits }}</div>
            <div class="referral-stat-label">累计推广积分</div>
          </div>
        </div>

        <!-- 推广规则 -->
        <div style="margin-top: 12px; padding: 10px 14px; background: #f0fdf4; border-radius: 8px; border: 1px solid #bbf7d0; font-size: 0.82rem; color: #166534; line-height: 1.7;">
          好友通过您的推广链接注册 → 您获得 <strong>5 推广积分</strong><br />
          好友充值 ≥50 元 → 您获得其充值积分 <strong>10%</strong> 的推广积分<br />
          好友首次充值 ≥50 元 → 好友本人获得充值积分 <strong>20%</strong> 的推广积分奖励
        </div>

        <!-- 推广明细 -->
        <div style="margin-top: 14px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <span style="font-size: 0.9rem; font-weight: 600; color: #374151;">推广明细</span>
            <el-button text size="small" @click="loadReferralDetails" :loading="loadingReferralDetails">刷新</el-button>
          </div>
          <el-table v-if="referralDetails.length > 0" :data="referralDetails" size="small" stripe style="width: 100%;" max-height="240">
            <el-table-column prop="referred_display_name" label="用户" width="120" />
            <el-table-column label="类型" width="120">
              <template #default="{ row }">
                <el-tag :type="referralTriggerTag(row.trigger_type)" size="small">{{ referralTriggerLabel(row.trigger_type) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="奖励积分" width="100">
              <template #default="{ row }">
                <span style="font-weight: 600; color: #059669;">+{{ row.reward_credits }}</span>
              </template>
            </el-table-column>
            <el-table-column label="时间" min-width="140">
              <template #default="{ row }">
                {{ row.created_at ? new Date(row.created_at).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '-' }}
              </template>
            </el-table-column>
          </el-table>
          <div v-else-if="!loadingReferralDetails" style="color: #9ca3af; font-size: 0.85rem;">暂无推广记录，分享推广链接邀请好友吧</div>
        </div>

        <!-- 推广积分兑现 -->
        <div style="margin-top: 14px;">
          <div style="font-size: 0.9rem; font-weight: 600; color: #374151; margin-bottom: 8px;">推广积分兑现</div>
          <div style="display: flex; gap: 10px; align-items: flex-end; flex-wrap: wrap;">
            <el-input v-model="withdrawForm.credits_amount" placeholder="兑现积分数" size="small" style="width: 120px;" type="number" />
            <el-input v-model="withdrawForm.platform_account" placeholder="平台注册手机号" size="small" style="width: 150px;" />
            <el-input v-model="withdrawForm.wechat_phone" placeholder="微信绑定手机号" size="small" style="width: 150px;" />
            <el-button type="success" size="small" :loading="submittingWithdraw" @click="applyWithdraw">申请兑现</el-button>
          </div>
          <div style="margin-top: 6px; font-size: 0.78rem; color: #f59e0b; line-height: 1.6;">
            ⚠ 请确保微信已开启「手机号转账」功能（微信 → 我 → 服务 → 收付款 → 向银行卡或手机号转账 → 开启允许通过手机号向我转账）
          </div>
          <div style="margin-top: 4px; font-size: 0.78rem; color: #9ca3af;">
            最低 {{ saasCredits.promo?.min_withdraw_credits ?? 100 }} 积分起提 · 折现比例 1 积分 = {{ saasCredits.promo?.cash_rate ?? 0.1 }} 元
          </div>
        </div>

        <!-- 兑现记录 -->
        <div v-if="withdrawals.length > 0" style="margin-top: 10px;">
          <div style="font-size: 0.85rem; color: #6b7280; margin-bottom: 4px;">兑现记录</div>
          <el-table :data="withdrawals" size="small" stripe style="width: 100%;" max-height="200">
            <el-table-column label="积分" width="80">
              <template #default="{ row }">{{ row.credits_used }}</template>
            </el-table-column>
            <el-table-column label="金额" width="80">
              <template #default="{ row }">¥{{ row.amount_yuan }}</template>
            </el-table-column>
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="withdrawStatusType(row.status)" size="small">{{ withdrawStatusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="申请时间" min-width="130">
              <template #default="{ row }">
                {{ row.created_at ? new Date(row.created_at).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="note" label="备注" min-width="150">
              <template #default="{ row }">
                <span v-if="row.status === 'rejected' && row.note" style="font-size: 0.8rem; color: #ef4444;">拒绝原因：{{ row.note }}</span>
                <span v-else style="font-size: 0.8rem; color: #6b7280;">{{ row.note || '-' }}</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>

      <div class="about-section" style="margin-top: 12px; border-top: 1px solid #e5e7eb; padding-top: 12px;">
        <div style="font-weight: 600; color: #374151; margin-bottom: 8px;">客户端授权码</div>

        <!-- 领取管理员分发的授权码 -->
        <div style="display: flex; gap: 8px; align-items: flex-end; margin-bottom: 12px;">
          <el-input
            v-model="claimCodeInput"
            placeholder="输入管理员分发的授权码（如 LINSCIO-XXXX-XXXX-XXXX）"
            :disabled="claimingCode"
            clearable
            style="max-width: 380px; font-family: monospace;"
            @keyup.enter="handleClaimCode"
          />
          <el-button type="primary" size="default" :loading="claimingCode" @click="handleClaimCode">领取</el-button>
        </div>

        <!-- 积分兑换 -->
        <div style="display: flex; gap: 12px; align-items: stretch; flex-wrap: wrap;">
          <div class="redeem-card">
            <div class="redeem-title">积分兑换</div>
            <div class="redeem-price">600 积分</div>
            <div class="redeem-desc">充值积分 + 赠送积分均可使用</div>
            <el-button size="small" type="primary" @click="redeemLicense('credits')" :loading="redeemingLicense">
              兑换
            </el-button>
          </div>
          <div class="redeem-card">
            <div class="redeem-title">推广积分兑换</div>
            <div class="redeem-price">6000 推广积分</div>
            <div class="redeem-desc">仅使用推广积分兑换</div>
            <el-button size="small" type="success" @click="redeemLicense('promo_credits')" :loading="redeemingLicense">
              兑换
            </el-button>
          </div>
        </div>
        <div v-if="redeemedCode" class="redeemed-result" style="margin-top: 12px;">
          <el-alert type="success" :closable="false">
            <template #title>
              兑换成功！授权码：<span style="font-family: monospace; font-weight: 700; user-select: all;">{{ redeemedCode }}</span>
              <el-button text size="small" style="margin-left: 8px;" @click="copyCode(redeemedCode)">复制</el-button>
            </template>
          </el-alert>
        </div>

        <!-- 我的授权码列表 -->
        <div v-if="myLicenseCodes.length > 0" style="margin-top: 12px;">
          <div style="font-size: 0.85rem; color: #6b7280; margin-bottom: 4px;">我的授权码</div>
          <el-table :data="myLicenseCodes" size="small" stripe style="width: 100%;">
            <el-table-column prop="code" label="授权码" width="200">
              <template #default="{ row }">
                <span style="font-family: monospace; font-size: 0.8rem; user-select: all;">{{ row.code }}</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag v-if="row.is_used" type="info" size="small">已激活</el-tag>
                <el-tag v-else type="success" size="small">未激活</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="绑定设备" min-width="140">
              <template #default="{ row }">
                <span v-if="row.device_id" style="font-size: 0.78rem; color: #6b7280; font-family: monospace;">
                  {{ row.device_id.slice(0, 16) }}...
                </span>
                <span v-else style="color: #9ca3af; font-size: 0.8rem;">未绑定</span>
              </template>
            </el-table-column>
            <el-table-column label="激活时间" width="140">
              <template #default="{ row }">
                <span v-if="row.activated_at">{{ new Date(row.activated_at).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) }}</span>
                <span v-else style="color: #9ca3af;">-</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="110">
              <template #default="{ row }">
                <el-button
                  v-if="row.is_used"
                  text type="warning" size="small"
                  :loading="unbindingDevice"
                  @click="handleUnbindDevice"
                >解绑设备</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
        <div style="margin-top: 8px; font-size: 0.78rem; color: #9ca3af; line-height: 1.6;">
          授权码在客户端首次登录时自动绑定设备，绑定后仅限该设备使用。每 30 天可自助解绑 1 次，解绑后可在新设备上重新激活。
        </div>
      </div>
      <div class="about-section" style="margin-top: 12px; border-top: 1px solid #e5e7eb; padding-top: 12px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <span class="label" style="font-weight: 600;">充值记录</span>
          <el-button text size="small" @click="loadOrderHistory" :loading="loadingOrders">
            {{ loadingOrders ? '加载中' : '刷新' }}
          </el-button>
        </div>
        <el-table v-if="orderHistory.length > 0" :data="orderHistory" size="small" stripe style="width: 100%;">
          <el-table-column prop="order_no" label="订单号" width="180">
            <template #default="{ row }">
              <span style="font-family: monospace; font-size: 0.8rem;">{{ row.order_no.slice(0, 12) }}...</span>
            </template>
          </el-table-column>
          <el-table-column prop="amount_yuan" label="金额" width="80">
            <template #default="{ row }">¥{{ row.amount_yuan }}</template>
          </el-table-column>
          <el-table-column prop="credits_to_add" label="积分" width="80">
            <template #default="{ row }">{{ row.credits_to_add + row.bonus_credits }}</template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="orderStatusType(row.status)" size="small">{{ orderStatusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="时间" width="140">
            <template #default="{ row }">
              {{ row.created_at ? new Date(row.created_at).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '-' }}
            </template>
          </el-table-column>
        </el-table>
        <div v-else style="color: #9ca3af; font-size: 0.85rem;">暂无充值记录</div>
        <div v-if="orderTotal > orderHistory.length" style="text-align: center; margin-top: 8px;">
          <el-button text size="small" @click="loadMoreOrders">加载更多</el-button>
        </div>
      </div>
      <div class="about-section" style="margin-top: 12px; border-top: 1px solid #e5e7eb; padding-top: 12px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <span class="label" style="font-weight: 600;">积分流水明细</span>
          <div style="display: flex; gap: 8px; align-items: center;">
            <el-select v-model="usageFilter" placeholder="全部类型" size="small" clearable style="width: 140px;">
              <el-option label="全部" value="" />
              <el-option label="生成消耗" value="generation" />
              <el-option label="文献分析" value="literature_analysis" />
              <el-option label="导出" value="export" />
              <el-option label="充值" value="recharge" />
              <el-option label="中断退还" value="refund" />
            </el-select>
            <el-date-picker
              v-model="usageMonth"
              type="month"
              placeholder="按月筛选"
              size="small"
              format="YYYY-MM"
              value-format="YYYY-MM"
              style="width: 140px;"
            />
            <el-button text size="small" @click="loadUsageLogs" :loading="loadingUsage">刷新</el-button>
            <el-button text size="small" type="success" @click="exportUsageCSV">导出 CSV</el-button>
          </div>
        </div>
        <el-table v-if="usageLogs.length > 0" :data="usageLogs" size="small" stripe style="width: 100%;">
          <el-table-column prop="created_at" label="时间" width="150">
            <template #default="{ row }">
              {{ row.created_at ? new Date(row.created_at).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="operation" label="操作" width="140">
            <template #default="{ row }">
              <span>{{ operationLabel(row.operation) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="cost" label="积分变动" width="100">
            <template #default="{ row }">
              <span :style="{ color: parseFloat(row.cost) > 0 ? '#ef4444' : '#059669', fontWeight: 600 }">
                {{ parseFloat(row.cost) > 0 ? '-' + row.cost : '+' + Math.abs(parseFloat(row.cost)) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="关联" min-width="160">
            <template #default="{ row }">
              <span v-if="row.article_id" style="font-size: 0.8rem; color: #6b7280;">
                文章#{{ row.article_id }}
                <span v-if="row.section_id"> / 章节#{{ row.section_id }}</span>
              </span>
              <span v-else-if="row.meta?.session_id" style="font-size: 0.8rem; color: #6b7280;">
                会话 {{ row.meta.session_id.slice(0, 8) }}...
              </span>
              <span v-else-if="row.meta?.reason" style="font-size: 0.8rem; color: #6b7280;">
                {{ row.meta.reason }}
              </span>
              <span v-else style="font-size: 0.8rem; color: #d1d5db;">-</span>
            </template>
          </el-table-column>
        </el-table>
        <div v-else-if="!loadingUsage" style="color: #9ca3af; font-size: 0.85rem;">暂无积分流水记录</div>
        <div v-if="usageTotal > usageLogs.length" style="text-align: center; margin-top: 8px;">
          <el-button text size="small" @click="loadMoreUsageLogs">加载更多</el-button>
        </div>
      </div>
      <div class="about-section" style="margin-top: 12px;">
        <el-button type="warning" size="small" @click="saasLogout">退出登录</el-button>
      </div>
      </div>
    </el-card>

    <!-- 桌面模式：账户与关于 -->
    <el-card v-if="isElectronEnv" class="settings-card">
      <template #header>账户与关于</template>
      <div class="about-section" style="margin-bottom: 12px;">
        <div class="about-row"><span class="label">当前用户</span> {{ authStore.user?.display_name || '未登录' }}</div>
        <div class="about-row"><span class="label">手机号</span> {{ authStore.user?.phone || '-' }}</div>
        <div class="about-row" style="gap: 8px; margin-top: 4px;">
          <el-button v-if="!authStore.user" size="small" type="primary" @click="router.push('/login')">登录 / 注册</el-button>
          <el-button v-if="authStore.user" size="small" type="warning" @click="logout">退出登录</el-button>
        </div>
      </div>
      <div class="about-section" style="margin-top: 12px; border-top: 1px solid #e5e7eb; padding-top: 12px;">
        <div class="about-row"><span class="label">软件版本</span> v{{ appVersion }}</div>
        <div class="about-row" style="gap: 8px; align-items: center; flex-wrap: wrap;">
          <span class="label">软件更新</span>
          <span v-if="licenseStore.hasSoftwareUpdate" style="color: #1e40af;">
            新版本 v{{ licenseStore.softwareUpdate?.latest_version }} 可用
          </span>
          <span v-else style="color: #9ca3af;">当前已是最新版本</span>
          <el-button size="small" :loading="checkingUpdate" @click="manualCheckUpdate">检查更新</el-button>

          <el-button
            v-if="licenseStore.hasSoftwareUpdate && licenseStore.updateDownloadStatus === 'idle' && hasInAppUpdate"
            size="small" type="primary"
            @click="startInAppUpdate"
          >立即更新</el-button>

          <el-button
            v-if="licenseStore.hasSoftwareUpdate && licenseStore.updateDownloadStatus === 'idle' && !hasInAppUpdate && licenseStore.softwareUpdate?.download_url"
            size="small"
            @click="downloadUpdateLegacy"
          >浏览器下载</el-button>

          <template v-if="licenseStore.updateDownloadStatus === 'downloading'">
            <el-button size="small" type="danger" plain @click="cancelUpdate">取消</el-button>
          </template>

          <el-button
            v-if="licenseStore.updateDownloadStatus === 'downloaded'"
            size="small" type="success"
            @click="installUpdate"
          >安装并重启</el-button>

          <el-button
            v-if="licenseStore.updateDownloadStatus === 'error'"
            size="small"
            @click="startInAppUpdate"
          >重试</el-button>
        </div>
        <div v-if="licenseStore.updateDownloadStatus === 'downloading'" style="margin-top: 8px;">
          <el-progress :percentage="licenseStore.updateDownloadProgress" :stroke-width="6" />
          <span style="font-size: 12px; color: #9ca3af;">正在下载更新...</span>
        </div>
        <div v-if="licenseStore.updateDownloadStatus === 'error' && licenseStore.updateDownloadError" style="margin-top: 4px;">
          <span style="font-size: 12px; color: #ef4444;">{{ licenseStore.updateDownloadError }}</span>
        </div>
        <div v-if="licenseStore.softwareUpdate?.release_notes && licenseStore.hasSoftwareUpdate" style="margin-top: 8px;">
          <span style="font-size: 12px; color: #6b7280;">更新说明：{{ licenseStore.softwareUpdate.release_notes }}</span>
        </div>
      </div>
    </el-card>

    <!-- SaaS 模式：客户端下载 -->
    <el-card v-if="!isElectronEnv" class="settings-card client-promo-card">
      <template #header>下载客户端</template>
      <p class="promo-desc">下载 LinScio MedComm 桌面客户端，解锁完整创作体验：</p>
      <div class="promo-features">
        <div class="promo-feature-item"><span class="promo-icon">🎨</span><span><b>医学绘图</b> — 文生图 / 图生图，AI 辅助生成医学插图</span></div>
        <div class="promo-feature-item"><span class="promo-icon">📦</span><span><b>学科包</b> — 定制学科词典、科普示例库，内容由 LinScio 专业团队维护更新</span></div>
        <div class="promo-feature-item"><span class="promo-icon">📖</span><span><b>医学词典管理</b> — 自定义术语表，生成时自动规范用词</span></div>
        <div class="promo-feature-item"><span class="promo-icon">📝</span><span><b>科普示例库</b> — 参考优质科普范例，提升内容质量</span></div>
        <div class="promo-feature-item"><span class="promo-icon">🔒</span><span><b>本地数据安全</b> — 所有数据存储在本地，隐私无忧</span></div>
        <div class="promo-feature-item"><span class="promo-icon">🔑</span><span><b>自选 AI 模型</b> — 支持 OpenAI / DeepSeek / Gemini 等 10+ 模型，自主配置 API Key</span></div>
        <div class="promo-feature-item"><span class="promo-icon">💾</span><span><b>数据备份恢复</b> — 一键完整备份与恢复，数据不丢失</span></div>
      </div>

      <div v-if="!clientProductInfo" style="margin-top: 16px; color: #9ca3af; font-size: 0.85rem;">
        加载产品信息中...
      </div>
      <div v-else style="margin-top: 16px;">
        <div style="font-weight: 600; color: #374151; margin-bottom: 8px;">
          {{ clientProductInfo.name || 'LinScio MedComm' }}
          <el-tag size="small" style="margin-left: 6px;">v{{ clientProductInfo.latest_version }}</el-tag>
        </div>
        <div v-if="!hasLicenseCode" class="download-notice">
          <el-alert type="warning" :closable="false" show-icon>
            <template #title>您还没有客户端授权码，请先在上方「兑换客户端授权码」中兑换后再下载。</template>
          </el-alert>
        </div>
        <div v-else class="download-platforms">
          <div
            v-for="plat in clientPlatforms"
            :key="plat.id"
            class="download-plat-card"
            :class="{ 'download-plat-card--disabled': plat.status === 'suspended' }"
          >
            <div class="plat-icon">{{ plat.icon }}</div>
            <div class="plat-name">{{ plat.name }}</div>
            <el-button
              v-if="plat.status !== 'suspended'"
              type="primary"
              size="small"
              :loading="downloadingPlatform === plat.id"
              @click="handleDownloadClient(plat.id)"
            >
              下载
            </el-button>
            <span v-else style="font-size: 12px; color: #9ca3af;">暂未开放</span>
          </div>
        </div>
        <div v-if="clientDownloadUrl" style="margin-top: 12px;">
          <el-alert type="success" :closable="false">
            <template #title>
              下载已开始。如果没有自动下载，<a :href="clientDownloadUrl" target="_blank" style="color: #1e40af;">点击此处</a>
            </template>
          </el-alert>
        </div>
        <div v-if="clientDownloadError" style="margin-top: 12px;">
          <el-alert type="error" :closable="false">
            <template #title>{{ clientDownloadError }}</template>
          </el-alert>
        </div>

        <!-- 下载记录 -->
        <div v-if="downloadHistory.length > 0" style="margin-top: 16px; border-top: 1px solid #e5e7eb; padding-top: 12px;">
          <div style="font-weight: 600; color: #374151; margin-bottom: 8px; font-size: 0.9rem;">下载记录</div>
          <el-table :data="downloadHistory" size="small" stripe style="width: 100%;">
            <el-table-column prop="version" label="版本" width="100">
              <template #default="{ row }"><span style="font-family: monospace;">v{{ row.version }}</span></template>
            </el-table-column>
            <el-table-column prop="platform" label="平台" width="180">
              <template #default="{ row }">{{ platformLabels[row.platform]?.name || row.platform }}</template>
            </el-table-column>
            <el-table-column prop="created_at" label="下载时间" width="160">
              <template #default="{ row }">{{ row.created_at ? new Date(row.created_at).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '-' }}</template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </el-card>

    <!-- 桌面模式：内容配置 -->
    <el-card v-if="isElectronEnv" class="settings-card">
      <template #header>内容配置</template>
      <div v-if="settingsStore.isBasic" class="content-config">
        <div class="config-row">
          <span class="config-label">医学词典</span>
          <span>通用预置（{{ contentStats.terms }} 条）</span>
          <el-button type="primary" text size="small">查看</el-button>
        </div>
        <div class="config-row">
          <span class="config-label">科普示例库</span>
          <span>通用示例（{{ contentStats.examples }} 个）</span>
          <el-button type="primary" text size="small">查看</el-button>
        </div>
        <div class="config-row">
          <span class="config-label">知识库</span>
          <span>{{ contentStats.docs }} 份文档</span>
          <el-button type="primary" text size="small" @click="$router.push('/knowledge')">去上传</el-button>
        </div>
      </div>
      <div v-else class="content-config">
        <div v-for="sp in settingsStore.license.customSpecialties" :key="sp" class="config-block">
          <div class="config-block-title">{{ sp }}</div>
          <div class="config-row">
            <span class="config-label">医学词典</span>
            <span>✦ 预置（{{ (settingsStore.license.specialtyStats[sp]?.terms ?? 0) }} 条，LinScio 维护） + 自定义</span>
            <el-button type="primary" text size="small">管理</el-button>
          </div>
          <div class="config-row">
            <span class="config-label">科普示例库</span>
            <span>✦ 预置（{{ (settingsStore.license.specialtyStats[sp]?.examples ?? 0) }} 个，LinScio 维护） + 自定义</span>
            <el-button type="primary" text size="small">管理</el-button>
          </div>
        </div>
        <div class="config-row">
          <span class="config-label">知识库</span>
          <span>{{ contentStats.docs }} 份文档</span>
          <el-button type="primary" text size="small" @click="$router.push('/knowledge')">管理</el-button>
        </div>
      </div>
    </el-card>

    <!-- 学科包管理 -->
    <el-card v-if="isElectronEnv" class="settings-card">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <span>学科包</span>
          <el-button size="small" type="primary" @click="triggerPackUpload">
            <el-icon style="margin-right: 4px;"><Upload /></el-icon>上传学科包
          </el-button>
          <input ref="packFileInput" type="file" accept=".zip,.linscio" style="display: none;" @change="handlePackFileSelected" />
        </div>
      </template>
      <div v-if="packUploading" style="padding: 12px 0;">
        <el-progress :percentage="packUploadPercent" :stroke-width="6" />
        <span style="font-size: 0.85rem; color: #6b7280; margin-top: 4px; display: block;">{{ packUploadDetail }}</span>
      </div>
      <div v-if="!packList.length && !packLoading && !packUploading" class="pack-empty">
        <p style="color:#9ca3af;">暂无学科包。点击「上传学科包」导入 .zip 或 .linscio 格式的学科包文件。</p>
      </div>
      <div v-if="packLoading" style="text-align:center;padding:1rem;color:#9ca3af;">加载中...</div>
      <div v-for="pack in packList" :key="pack.specialty_id" class="pack-item">
        <div class="pack-header">
          <span class="pack-name">{{ pack.name || pack.specialty_id }}</span>
          <el-tag v-if="pack.status === 'installed'" type="success" size="small">已安装 v{{ pack.local_version }}</el-tag>
          <el-tag v-else-if="pack.status === 'downloading'" type="warning" size="small">安装中</el-tag>
          <el-tag v-else type="info" size="small">未安装</el-tag>
        </div>
        <div v-if="pack.status === 'installed'" class="pack-stats">
          知识文档 {{ pack.knowledge_docs }} 篇 · 术语 {{ pack.terms }} 条 · 范例 {{ pack.examples }} 个
        </div>
        <div v-if="downloadingPack?.specialty_id === pack.specialty_id" class="pack-progress">
          <el-progress
            :percentage="downloadingPack.percent"
            :status="downloadingPack.status === 'done' ? 'success' : downloadingPack.status === 'error' ? 'exception' : undefined"
            :stroke-width="6"
          />
          <span class="pack-progress-detail">{{ downloadingPack.detail }}</span>
        </div>
      </div>
    </el-card>

    <el-card v-if="isElectronEnv" class="settings-card">
      <template #header>API Key（Keychain 安全存储）</template>
      <el-form label-width="170px" class="api-key-form">
        <div class="api-group-title">文本生成</div>
        <el-form-item label="OpenAI API Key">
          <el-input v-model="openaiKey" type="password" placeholder="sk-xxx" show-password />
          <a class="apply-link" href="https://platform.openai.com/api-keys" target="_blank">申请 ↗</a>
        </el-form-item>
        <el-form-item label="硅基流动 API Key">
          <el-input v-model="siliconflowKey" type="password" placeholder="sk-xxx" show-password />
          <a class="apply-link" href="https://cloud.siliconflow.cn/account/ak" target="_blank">申请 ↗</a>
        </el-form-item>
        <el-form-item label="DeepSeek API Key">
          <el-input v-model="deepseekKey" type="password" placeholder="sk-xxx" show-password />
          <a class="apply-link" href="https://platform.deepseek.com/api_keys" target="_blank">申请 ↗</a>
        </el-form-item>
        <el-form-item label="智谱 API Key">
          <el-input v-model="zhipuKey" type="password" placeholder="zhipu key" show-password />
          <a class="apply-link" href="https://open.bigmodel.cn/usercenter/apikeys" target="_blank">申请 ↗</a>
        </el-form-item>
        <el-form-item label="Moonshot API Key">
          <el-input v-model="moonshotKey" type="password" placeholder="moonshot key" show-password />
          <a class="apply-link" href="https://platform.moonshot.cn/console/api-keys" target="_blank">申请 ↗</a>
        </el-form-item>
        <el-form-item label="OpenRouter API Key">
          <el-input v-model="openrouterKey" type="password" placeholder="openrouter key" show-password />
          <a class="apply-link" href="https://openrouter.ai/keys" target="_blank">申请 ↗</a>
        </el-form-item>
        <el-form-item label="七牛 MaaS API Key">
          <el-input v-model="qiniuMaasKey" type="password" placeholder="qiniu maas key" show-password />
          <a class="apply-link" href="https://portal.qiniu.com/ai-inference/overview" target="_blank">申请 ↗</a>
        </el-form-item>
        <el-form-item label="Anthropic API Key">
          <el-input v-model="anthropicKey" type="password" placeholder="sk-ant-xxx" show-password />
          <a class="apply-link" href="https://console.anthropic.com/settings/keys" target="_blank">申请 ↗</a>
        </el-form-item>
        <el-form-item label="Google AI API Key">
          <el-input v-model="googleAiKey" type="password" placeholder="AIza..." show-password />
          <a class="apply-link" href="https://aistudio.google.com/apikey" target="_blank">申请 ↗</a>
        </el-form-item>
        <el-form-item label="通义千问 API Key">
          <el-input v-model="dashscopeKey" type="password" placeholder="DashScope Key（同时用于通义万相生图）" show-password />
          <a class="apply-link" href="https://bailian.console.aliyun.com/?apiKey=1" target="_blank">申请 ↗</a>
        </el-form-item>

        <div class="api-group-title">文献翻译（可选）</div>
        <el-form-item label="DeepL API Key">
          <el-input v-model="deeplKey" type="password" placeholder="DeepL Free 或 Pro Key" show-password />
          <a class="apply-link" href="https://www.deepl.com/pro-api" target="_blank">申请 ↗</a>
        </el-form-item>
        <el-form-item label="Google 翻译 API Key">
          <el-input v-model="googleTranslateKey" type="password" placeholder="Google Cloud Translation API Key" show-password />
          <a class="apply-link" href="https://console.cloud.google.com/apis/credentials" target="_blank">申请 ↗</a>
        </el-form-item>
        <el-form-item label="Azure 翻译 Key">
          <el-input v-model="azureTranslateKey" type="password" placeholder="Azure Translator Key" show-password />
          <a class="apply-link" href="https://portal.azure.com/#create/Microsoft.CognitiveServicesTextTranslation" target="_blank">申请 ↗</a>
        </el-form-item>
        <el-form-item label="Azure 翻译 Region">
          <el-input v-model="azureTranslateRegion" placeholder="如 eastasia、global" style="width: 200px" />
        </el-form-item>
        <div class="api-group-note">
          翻译优先级：DeepL > Google > Azure > 默认大模型。未配置任何翻译 Key 时，将使用当前文本生成模型翻译。推荐 DeepL（翻译质量最高、医学术语支持好）。
        </div>

        <el-form-item>
          <div class="action-row">
            <el-button type="primary" :loading="testing" @click="testApiKey">测试 OpenAI</el-button>
            <el-button v-if="hasElectronKeychain" type="success" :loading="saving" @click="saveApiKeys">保存到 Keychain</el-button>
          </div>
          <span v-if="apiKeyResult" :style="{ color: apiKeyResult.valid ? 'green' : 'red', marginLeft: '1rem' }">
            {{ apiKeyResult.valid ? '✓ 有效' : '✗ ' + (apiKeyResult.error || '无效') }}
          </span>
        </el-form-item>
        <el-form-item label="环境与连接自检">
          <el-button :loading="selfCheckLoading" @click="runSelfCheck">运行自检</el-button>
          <p class="api-group-note" style="margin-top: 0.35rem;">
            查看当前后端进程是否读到各厂商 API 环境变量、Ollama 是否可达。不消耗模型额度；真实鉴权仍以「测试 OpenAI」或实际生成为准。保存 Key 到 Keychain 后若来自荐重载失败，请重启应用再来自检。
          </p>
          <pre v-if="selfCheckText" class="self-check-pre">{{ selfCheckText }}</pre>
        </el-form-item>
      </el-form>
    </el-card>
    <el-card v-if="isElectronEnv" class="settings-card">
      <template #header>模型配置</template>
      <el-form label-width="140px">
        <el-form-item label="默认模型">
          <div class="model-select-row">
            <el-select v-model="selectedLlmProvider" placeholder="先选 Provider" style="width: 180px">
              <el-option v-for="p in llmProviders" :key="p" :label="p" :value="p" />
            </el-select>
            <el-select v-model="selectedDefaultModel" placeholder="再选模型" style="width: 380px" popper-class="medcomm-model-dropdown">
              <el-option v-for="m in filteredModelsByProvider" :key="m.id" :label="m.name" :value="m.id">
                <div class="model-option-row">
                  <span class="model-option-name">{{ m.name }}</span>
                  <span v-if="m.max_tokens" class="model-option-tokens">{{ formatTokens(m.max_tokens) }}</span>
                </div>
              </el-option>
            </el-select>
          </div>
          <span class="model-hint">
            所有文章生成均使用该模型，修改后即时生效。
            <span v-if="selectedModelTokens" class="model-ctx-badge">
              上下文窗口 {{ formatTokens(selectedModelTokens) }} tokens
            </span>
          </span>
        </el-form-item>
      </el-form>
    </el-card>
    <el-card v-if="isElectronEnv" class="settings-card">
      <template #header>隐私与调试</template>
      <el-form label-width="220px">
        <el-form-item label="记录网页采集历史">
          <el-switch
            v-model="captureHistoryEnabled"
            active-text="开启"
            inactive-text="关闭"
          />
          <el-tooltip
            content="仅保存到本机浏览器存储。关闭后将立即清空现有记录，后续不再保留本地采集历史。"
            placement="top"
          >
            <el-tag size="small" type="info" class="privacy-tip">?</el-tag>
          </el-tooltip>
        </el-form-item>
      </el-form>
    </el-card>
    <el-card v-if="hasElectronKeychain" class="settings-card">
      <template #header>数据备份与恢复</template>
      <p>完整备份包含：数据库 + images/ + uploads/。恢复时可选择冲突策略。</p>
      <el-form label-width="120px">
        <el-form-item>
          <el-button :loading="backupLoading" @click="handleBackup">完整备份</el-button>
        </el-form-item>
        <el-form-item label="从备份恢复">
          <el-button :loading="restoreLoading" @click="handleRestore">选择备份文件恢复</el-button>
          <span v-if="restoreResult" :style="{ color: restoreResult.ok ? 'green' : 'red', marginLeft: '0.5rem' }">
            {{ restoreResult.ok ? '✓ 恢复成功，请重启应用' : '✗ ' + (restoreResult.error || '恢复失败') }}
          </span>
        </el-form-item>
      </el-form>
    </el-card>
    <el-button @click="$router.back()" style="margin-top: 1rem;">返回</el-button>

    <!-- 充值弹窗 -->
    <el-dialog v-model="showRechargeDialog" title="积分充值" width="560px" :close-on-click-modal="false">
      <el-tabs v-model="rechargeTab">
        <el-tab-pane label="兑换码充值" name="redeem">
          <div style="padding: 12px 0;">
            <div class="recharge-plans" style="margin-bottom: 16px;">
              <div v-for="plan in rechargePlans" :key="plan.amount_yuan" class="plan-card plan-card--readonly">
                <div class="plan-price">¥{{ plan.amount_yuan }}</div>
                <div class="plan-credits">{{ plan.credits }} 积分</div>
                <div v-if="plan.bonus > 0" class="plan-bonus">赠送 {{ plan.bonus }}</div>
              </div>
            </div>
            <el-form @submit.prevent="handleRedeem" style="max-width: 420px;">
              <el-form-item label="兑换码" :error="redeemError">
                <el-input
                  v-model="redeemCodeInput"
                  placeholder="请输入兑换码，如 LS3B-XXXX-XXXX-XXXX-XXXX"
                  :disabled="redeemLoading"
                  clearable
                  style="font-family: monospace; letter-spacing: 0.5px;"
                  @keyup.enter="handleRedeem"
                />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="redeemLoading" @click="handleRedeem">
                  确认兑换
                </el-button>
              </el-form-item>
            </el-form>
            <div v-if="redeemResult" style="margin-top: 8px;">
              <el-alert :title="redeemResult.message" type="success" :closable="false" show-icon>
                <template #default>
                  <span style="font-size: 0.85rem; color: #166534;">
                    获得 {{ redeemResult.credits }} 积分
                    <span v-if="redeemResult.bonus_credits > 0"> + {{ redeemResult.bonus_credits }} 赠送积分</span>
                  </span>
                </template>
              </el-alert>
            </div>
            <div style="margin-top: 16px; padding: 10px 14px; background: #f0f9ff; border-radius: 8px; border: 1px solid #bae6fd; font-size: 0.82rem; color: #0c4a6e; line-height: 1.7;">
              兑换码由管理员生成并分发，不同价位对应不同的兑换码前缀。<br/>
              每个兑换码仅限使用一次，充值成功后积分立即到账。<br/>
              50 元及以上档位享有赠送积分，详见上方价位表。
            </div>
          </div>
        </el-tab-pane>
        <el-tab-pane label="在线支付" name="online">
          <div v-if="!payingOrder" style="padding: 12px 0;">
            <div class="recharge-plans">
              <div
                v-for="plan in rechargePlans"
                :key="plan.amount_yuan"
                :class="['plan-card', { active: selectedPlan === plan.amount_yuan }]"
                @click="selectedPlan = plan.amount_yuan"
              >
                <div class="plan-price">¥{{ plan.amount_yuan }}</div>
                <div class="plan-credits">{{ plan.credits }} 积分</div>
                <div v-if="plan.bonus > 0" class="plan-bonus">赠送 {{ plan.bonus }}</div>
                <div class="plan-unit">{{ plan.unit_price }}</div>
              </div>
            </div>
            <div style="margin-top: 16px;">
              <span style="font-size: 0.9rem; color: #374151;">支付方式：</span>
              <el-radio-group v-model="payType" style="margin-left: 8px;">
                <el-radio value="alipay">支付宝</el-radio>
                <el-radio value="wxpay">微信支付</el-radio>
              </el-radio-group>
            </div>
            <div style="margin-top: 12px; padding: 10px 12px; background: #fffbe6; border-radius: 6px; border: 1px solid #ffe58f;">
              <p style="font-size: 0.8rem; color: #8c6d1f; margin: 0; line-height: 1.6;">
                ⚠️ 退款政策：充值后 24 小时内未消费可全额退款；已消费部分退还未消费余额（扣 5% 手续费）；
                <strong>充值超过 7 天不退款</strong>，余额可继续使用。充值即视为同意以上政策。
              </p>
            </div>
            <div style="text-align: right; margin-top: 16px;">
              <el-button @click="showRechargeDialog = false">取消</el-button>
              <el-button type="primary" :loading="creatingOrder" @click="handleCreateOrder">
                确认充值 ¥{{ selectedPlan }}
              </el-button>
            </div>
          </div>
          <div v-else>
            <div class="pay-qrcode-area">
              <p style="text-align: center; margin-bottom: 12px; color: #374151;">
                请使用{{ payType === 'alipay' ? '支付宝' : '微信' }}扫码支付
              </p>
              <div v-if="payingOrder.img" style="text-align: center;">
                <img :src="payingOrder.img" alt="支付二维码" style="max-width: 240px; border: 1px solid #e5e7eb; border-radius: 8px;" />
              </div>
              <div v-else-if="payingOrder.qrcode" style="text-align: center;">
                <img :src="'https://api.qrserver.com/v1/create-qr-code/?size=240x240&data=' + encodeURIComponent(payingOrder.qrcode)" alt="支付二维码" style="max-width: 240px; border: 1px solid #e5e7eb; border-radius: 8px;" />
              </div>
              <div style="text-align: center; margin-top: 12px;">
                <p style="color: #6b7280; font-size: 0.85rem;">
                  充值 ¥{{ payingOrder.amount_yuan }} → {{ payingOrder.credits }} + {{ payingOrder.bonus }} 积分
                </p>
                <p style="color: #9ca3af; font-size: 0.8rem; margin-top: 4px;">
                  订单号：{{ payingOrder.order_no }}
                </p>
                <el-button v-if="payingOrder.pay_url" type="primary" text size="small" style="margin-top: 8px;" @click="openPayUrl">
                  打开收银台页面支付
                </el-button>
              </div>
              <div style="text-align: center; margin-top: 16px;">
                <el-button :loading="pollingPayment" @click="checkPaymentStatus">
                  {{ pollingPayment ? '查询中...' : '我已支付' }}
                </el-button>
                <el-button @click="cancelPayment">取消</el-button>
              </div>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import { api, http, setAuthToken, getAuthToken } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload } from '@element-plus/icons-vue'
import { useSettingsStore } from '@/stores/settings'
import { useAuthStore } from '@/stores/auth'
import { useMedcommLicenseStore } from '@/stores/medcommLicense'

const router = useRouter()
const settingsStore = useSettingsStore()
const contentStats = ref({ terms: 0, examples: 0, docs: 0 })
const authStore = useAuthStore()
const licenseStore = useMedcommLicenseStore()

const isElectronEnv = typeof window !== 'undefined' && !!(window as any).electronAPI?.isElectron

// SaaS 模式数据
const saasUser = ref<any>(null)
const saasCredits = ref<any>({})
const saasLoggedIn = computed(() => !isElectronEnv && !!getAuthToken())

async function loadSaasProfile() {
  if (isElectronEnv) return
  try {
    const res = await http.get('/api/v1/auth/me')
    saasUser.value = res.data
  } catch { /* ignore */ }
  try {
    const res = await http.get('/api/v1/credits/balance')
    saasCredits.value = res.data
  } catch { /* ignore */ }
}

// ── 客户端下载 ─────────────────────────────────────────────
const clientProductInfo = ref<any>(null)
const clientPlatforms = ref<{ id: string; name: string; icon: string; status: string }[]>([])
const hasLicenseCode = computed(() => myLicenseCodes.value.length > 0)
const downloadingPlatform = ref('')
const clientDownloadUrl = ref('')
const clientDownloadError = ref('')

const platformLabels: Record<string, { name: string; icon: string }> = {
  'mac-arm64': { name: 'macOS (Apple Silicon)', icon: '🍎' },
  'mac-x64':   { name: 'macOS (Intel)',         icon: '🍎' },
  'win-x64':   { name: 'Windows (x64)',         icon: '🪟' },
}

async function loadClientProductInfo() {
  try {
    const res = await http.get('/api/v1/download/product-info')
    const products = res.data?.products || {}
    const matched = products.MedComm || products.medcomm || Object.values(products)[0]
    if (matched) {
      clientProductInfo.value = matched
      const statusMap = matched.platform_status || {}
      const platIds = matched.platforms || Object.keys(matched.download_files || {})
      const allPlats = new Set([...platIds, ...Object.keys(statusMap)])
      clientPlatforms.value = [...allPlats].map(pid => ({
        id: pid,
        name: platformLabels[pid]?.name || pid,
        icon: platformLabels[pid]?.icon || '💻',
        status: statusMap[pid] || 'available',
      }))
    }
  } catch { /* product-info 公开接口，失败时静默 */ }
  loadDownloadHistory()
}

const downloadHistory = ref<any[]>([])

async function loadDownloadHistory() {
  try {
    const res = await http.get('/api/v1/download/my-downloads', { params: { limit: 10 } })
    downloadHistory.value = res.data || []
  } catch { /* ignore */ }
}

async function handleDownloadClient(platform: string) {
  downloadingPlatform.value = platform
  clientDownloadUrl.value = ''
  clientDownloadError.value = ''
  try {
    const res = await http.post('/api/v1/download/software', {
      product_id: 'medcomm',
      platform,
    })
    clientDownloadUrl.value = res.data.download_url
    window.location.href = res.data.download_url
    loadDownloadHistory()
  } catch (e: any) {
    const detail = e?.response?.data?.detail || ''
    if (detail === 'no_valid_license') {
      clientDownloadError.value = '您还没有授权码，请先兑换授权码'
    } else {
      clientDownloadError.value = detail || '下载失败，请稍后重试'
    }
  } finally {
    downloadingPlatform.value = ''
  }
}

// ── 充值 ─────────────────────────────────────────────────
const showRechargeDialog = ref(false)
const rechargeTab = ref('redeem')
const selectedPlan = ref(100)
const payType = ref('alipay')
const creatingOrder = ref(false)
const payingOrder = ref<any>(null)
const pollingPayment = ref(false)
let pollTimer: ReturnType<typeof setInterval> | null = null

// ── 兑换码充值 ────────────────────────────────────────────
const redeemCodeInput = ref('')
const redeemLoading = ref(false)
const redeemError = ref('')
const redeemResult = ref<{ credits: number; bonus_credits: number; total_added: number; message: string } | null>(null)

async function handleRedeem() {
  const code = redeemCodeInput.value.trim()
  if (!code) { redeemError.value = '请输入兑换码'; return }
  redeemError.value = ''
  redeemResult.value = null
  redeemLoading.value = true
  try {
    const res = await http.post('/api/v1/credits/redeem', { code })
    redeemResult.value = res.data
    redeemCodeInput.value = ''
    ElMessage.success(res.data.message || '兑换成功')
    await loadSaasProfile()
  } catch (e: any) {
    redeemError.value = e?.response?.data?.detail || '兑换失败'
  } finally { redeemLoading.value = false }
}

const rechargePlans = [
  { amount_yuan: 10, credits: 10, bonus: 0, unit_price: '1.00元/积分' },
  { amount_yuan: 50, credits: 50, bonus: 3, unit_price: '0.94元/积分' },
  { amount_yuan: 100, credits: 100, bonus: 8, unit_price: '0.93元/积分' },
  { amount_yuan: 300, credits: 300, bonus: 30, unit_price: '0.91元/积分' },
  { amount_yuan: 500, credits: 500, bonus: 60, unit_price: '0.89元/积分' },
]

async function handleCreateOrder() {
  creatingOrder.value = true
  try {
    const res = await http.post('/api/v1/payment/create-order', {
      amount_yuan: selectedPlan.value,
      pay_type: payType.value,
    })
    payingOrder.value = res.data
    startPolling()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '创建订单失败')
  } finally {
    creatingOrder.value = false
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(async () => {
    if (!payingOrder.value) return
    try {
      const res = await http.get('/api/v1/payment/order-status', {
        params: { order_no: payingOrder.value.order_no },
      })
      if (res.data.status === 'paid') {
        stopPolling()
        ElMessage.success('充值成功！积分已到账')
        payingOrder.value = null
        showRechargeDialog.value = false
        await loadSaasProfile()
      }
    } catch { /* ignore */ }
  }, 3000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function checkPaymentStatus() {
  if (!payingOrder.value) return
  pollingPayment.value = true
  try {
    const res = await http.get('/api/v1/payment/order-status', {
      params: { order_no: payingOrder.value.order_no },
    })
    if (res.data.status === 'paid') {
      stopPolling()
      ElMessage.success('充值成功！积分已到账')
      payingOrder.value = null
      showRechargeDialog.value = false
      await loadSaasProfile()
    } else {
      ElMessage.info('暂未查到支付结果，请稍后再试')
    }
  } catch {
    ElMessage.error('查询失败')
  } finally {
    pollingPayment.value = false
  }
}

function cancelPayment() {
  stopPolling()
  payingOrder.value = null
}

function openPayUrl() {
  if (payingOrder.value?.pay_url) {
    window.open(payingOrder.value.pay_url, '_blank')
  }
}

// ── 充值记录 ──────────────────────────────────────────────
const orderHistory = ref<any[]>([])
const orderTotal = ref(0)
const loadingOrders = ref(false)
let orderPage = 1

async function loadOrderHistory() {
  loadingOrders.value = true
  orderPage = 1
  try {
    const res = await http.get('/api/v1/payment/orders', {
      params: { page: 1, page_size: 10 },
    })
    orderHistory.value = res.data.items || []
    orderTotal.value = res.data.total || 0
  } catch { /* ignore */ }
  finally { loadingOrders.value = false }
}

async function loadMoreOrders() {
  orderPage++
  try {
    const res = await http.get('/api/v1/payment/orders', {
      params: { page: orderPage, page_size: 10 },
    })
    orderHistory.value.push(...(res.data.items || []))
  } catch { orderPage-- }
}

// ── 积分流水 ──────────────────────────────────────────────
const usageLogs = ref<any[]>([])
const usageTotal = ref(0)
const loadingUsage = ref(false)
const usageFilter = ref('')
const usageMonth = ref('')
let usagePage = 1

async function loadUsageLogs() {
  loadingUsage.value = true
  usagePage = 1
  try {
    const params: Record<string, any> = { page: 1, page_size: 20 }
    if (usageFilter.value) params.operation = usageFilter.value
    if (usageMonth.value) params.month = usageMonth.value
    const res = await http.get('/api/v1/credits/usage-logs', { params })
    usageLogs.value = res.data.items || res.data || []
    usageTotal.value = res.data.total || usageLogs.value.length
  } catch { /* ignore */ }
  finally { loadingUsage.value = false }
}

async function loadMoreUsageLogs() {
  usagePage++
  try {
    const params: Record<string, any> = { page: usagePage, page_size: 20 }
    if (usageFilter.value) params.operation = usageFilter.value
    if (usageMonth.value) params.month = usageMonth.value
    const res = await http.get('/api/v1/credits/usage-logs', { params })
    usageLogs.value.push(...(res.data.items || res.data || []))
  } catch { usagePage-- }
}

function operationLabel(op: string): string {
  const map: Record<string, string> = {
    generation: '生成消耗',
    literature_analysis: '文献分析',
    export: '导出',
    export_unwatermarked: '无水印导出',
    recharge: '充值',
    refund: '中断退还',
    admin_adjust: '管理员调整',
    section_optimization: '章节优化',
  }
  return map[op] || op
}

async function exportUsageCSV() {
  try {
    const params: Record<string, any> = {}
    if (usageFilter.value) params.operation = usageFilter.value
    if (usageMonth.value) params.month = usageMonth.value
    const res = await http.get('/api/v1/credits/usage-logs/export', {
      params,
      responseType: 'blob',
    })
    const blob = new Blob([res.data], { type: 'text/csv; charset=utf-8-sig' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `积分流水_${usageMonth.value || '全部'}.csv`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch {
    ElMessage.error('导出失败')
  }
}

function orderStatusLabel(status: string): string {
  const map: Record<string, string> = {
    created: '待支付', paying: '支付中', paid: '已支付',
    expired: '已过期', closed: '已关闭',
    partial_refund: '部分退款', full_refund: '已退款',
  }
  return map[status] || status
}

function orderStatusType(status: string): string {
  const map: Record<string, string> = {
    paid: 'success', expired: 'info', closed: 'info',
    partial_refund: 'warning', full_refund: 'danger',
    created: '', paying: '',
  }
  return map[status] || ''
}

// ── 授权码领取 & 兑换 ─────────────────────────────────────
const claimCodeInput = ref('')
const claimingCode = ref(false)

async function handleClaimCode() {
  const code = claimCodeInput.value.trim()
  if (!code) { ElMessage.warning('请输入授权码'); return }
  claimingCode.value = true
  try {
    const res = await http.post('/api/v1/credits/claim-license', { code })
    ElMessage.success(res.data.message || '领取成功')
    claimCodeInput.value = ''
    loadMyLicenseCodes()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '领取失败')
  } finally { claimingCode.value = false }
}

const redeemingLicense = ref(false)
const redeemedCode = ref('')
const myLicenseCodes = ref<any[]>([])

async function redeemLicense(creditType: string) {
  const costLabel = creditType === 'credits' ? '600 积分（充值积分 + 赠送积分）' : '6000 推广积分'
  await ElMessageBox.confirm(`确认使用 ${costLabel} 兑换一个客户端授权码？`, '兑换确认')
  redeemingLicense.value = true
  try {
    const res = await http.post('/api/v1/credits/redeem-license', { credit_type: creditType })
    redeemedCode.value = res.data.code
    ElMessage.success('兑换成功')
    loadSaasProfile()
    loadMyLicenseCodes()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '兑换失败')
  } finally { redeemingLicense.value = false }
}

async function loadMyLicenseCodes() {
  try {
    const res = await http.get('/api/v1/credits/my-licenses')
    myLicenseCodes.value = res.data
  } catch { /* ignore */ }
}

const unbindingDevice = ref(false)

async function handleUnbindDevice() {
  try {
    await ElMessageBox.confirm(
      '解绑后当前设备将无法使用客户端，您可以在新设备上重新激活。\n注意：每 30 天仅可解绑 1 次。',
      '解绑设备确认',
      { confirmButtonText: '确认解绑', cancelButtonText: '取消', type: 'warning' }
    )
  } catch { return }

  unbindingDevice.value = true
  try {
    const res = await http.post('/api/v1/credits/unbind-device')
    if (res.data.success) {
      ElMessage.success(res.data.message || '设备已解绑')
      loadMyLicenseCodes()
    } else {
      ElMessage.warning(res.data.message || '解绑失败')
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '解绑失败')
  } finally { unbindingDevice.value = false }
}

function copyCode(code: string) {
  navigator.clipboard.writeText(code).then(() => ElMessage.success('已复制')).catch(() => {})
}

// ── 推广中心 ──────────────────────────────────────────────
const referralInfo = ref<{ referral_code: string; referral_link: string; total_referred: number; total_reward_credits: number } | null>(null)
const referralDetails = ref<any[]>([])
const loadingReferral = ref(false)
const loadingReferralDetails = ref(false)
const withdrawals = ref<any[]>([])
const submittingWithdraw = ref(false)
const withdrawForm = ref({ credits_amount: '', platform_account: '', wechat_phone: '' })

async function loadReferralInfo() {
  loadingReferral.value = true
  try {
    const res = await api.referral.getInfo()
    referralInfo.value = res.data
  } catch { /* ignore */ }
  finally { loadingReferral.value = false }
}

async function loadReferralDetails() {
  loadingReferralDetails.value = true
  try {
    const res = await api.referral.getDetails()
    referralDetails.value = res.data
  } catch { /* ignore */ }
  finally { loadingReferralDetails.value = false }
}

async function loadWithdrawals() {
  try {
    const res = await api.referral.getWithdrawals()
    withdrawals.value = res.data
  } catch { /* ignore */ }
}

function copyReferralLink() {
  if (!referralInfo.value) return
  navigator.clipboard.writeText(referralInfo.value.referral_link)
    .then(() => ElMessage.success('推广链接已复制'))
    .catch(() => {})
}

async function resetReferralCode() {
  try {
    await ElMessageBox.confirm('重置后旧推广码将失效，已分享的链接需要重新分享。确认重置？', '重置推广码', {
      confirmButtonText: '确认重置', cancelButtonText: '取消', type: 'warning',
    })
    const res = await api.referral.resetCode()
    referralInfo.value = {
      ...referralInfo.value!,
      referral_code: res.data.referral_code,
      referral_link: res.data.referral_link,
    }
    ElMessage.success('推广码已重置')
  } catch { /* user cancel */ }
}

async function applyWithdraw() {
  const amount = parseFloat(withdrawForm.value.credits_amount)
  if (!amount || amount <= 0) { ElMessage.warning('请输入兑现积分数'); return }
  if (!withdrawForm.value.platform_account.trim()) { ElMessage.warning('请输入平台注册手机号'); return }
  if (!withdrawForm.value.wechat_phone.trim()) { ElMessage.warning('请输入微信绑定手机号'); return }
  submittingWithdraw.value = true
  try {
    const res = await api.referral.applyWithdraw({
      credits_amount: amount,
      platform_account: withdrawForm.value.platform_account.trim(),
      wechat_phone: withdrawForm.value.wechat_phone.trim(),
    })
    ElMessage.success(res.data.message || '兑现申请已提交，等待管理员审核')
    withdrawForm.value = { credits_amount: '', platform_account: '', wechat_phone: '' }
    loadWithdrawals()
    loadSaasProfile()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '兑现申请失败')
  } finally { submittingWithdraw.value = false }
}

function referralTriggerLabel(type: string): string {
  const map: Record<string, string> = { register: '注册奖励', recharge: '充值返利', first_recharge_bonus: '首充奖励' }
  return map[type] || type
}

function referralTriggerTag(type: string): string {
  const map: Record<string, string> = { register: 'success', recharge: '', first_recharge_bonus: 'warning' }
  return map[type] || ''
}

function withdrawStatusLabel(status: string): string {
  const map: Record<string, string> = { pending: '审核中', approved: '已通过', rejected: '已拒绝', paid: '已打款' }
  return map[status] || status
}

function withdrawStatusType(status: string): string {
  const map: Record<string, string> = { pending: 'warning', approved: 'success', rejected: 'danger', paid: 'success' }
  return map[status] || ''
}

async function saasLogout() {
  try {
    await ElMessageBox.confirm('确认退出当前账号？', '退出登录', {
      confirmButtonText: '退出', cancelButtonText: '取消', type: 'warning',
    })
    try { await http.post('/api/v1/auth/logout') } catch { /* ignore */ }
    setAuthToken(null)
    router.push('/login').catch(() => {})
    ElMessage.success('已退出')
  } catch { /* user cancel */ }
}
const appVersion = ref('0.0.0')
if (isElectronEnv && window.electronAPI?.getAppVersion) {
  window.electronAPI.getAppVersion().then((v: string) => { appVersion.value = v }).catch(() => {})
}

// 学科包
interface PackItem {
  specialty_id: string; name: string; local_version?: string | null;
  remote_version?: string | null; status: string;
  knowledge_docs: number; terms: number; examples: number;
}
interface DownloadProgress {
  specialty_id: string; name?: string; percent: number;
  status: string; detail?: string;
}
const packList = ref<PackItem[]>([])
const packLoading = ref(false)
const downloadingPack = ref<DownloadProgress | null>(null)
const packFileInput = ref<HTMLInputElement | null>(null)
const packUploading = ref(false)
const packUploadPercent = ref(0)
const packUploadDetail = ref('')

const checkingUpdate = ref(false)

const hasInAppUpdate = computed(() => {
  const su = licenseStore.softwareUpdate
  return !!(su?.update_download_url && su?.update_filename)
})

async function manualCheckUpdate() {
  const eApi = window.electronAPI
  if (!eApi?.checkForUpdate) {
    ElMessage.info('当前环境不支持检查更新')
    return
  }
  checkingUpdate.value = true
  try {
    await eApi.checkForUpdate()
    await new Promise(r => setTimeout(r, 2000))
    if (!licenseStore.hasSoftwareUpdate) {
      ElMessage.success('当前已是最新版本')
    }
  } catch {
    ElMessage.error('检查更新失败')
  } finally {
    checkingUpdate.value = false
  }
}

async function downloadUpdateLegacy() {
  const url = licenseStore.softwareUpdate?.download_url
  if (url && window.electronAPI?.openExternal) {
    await window.electronAPI.openExternal(url)
  }
}

async function startInAppUpdate() {
  const eApi = window.electronAPI
  const su = licenseStore.softwareUpdate
  if (!eApi?.downloadSoftwareUpdate || !su?.update_download_url || !su?.update_filename) return

  licenseStore.setUpdateDownloadStatus('downloading')
  licenseStore.setUpdateDownloadProgress(0)

  eApi.onSoftwareUpdateProgress?.((progress) => {
    licenseStore.setUpdateDownloadProgress(progress.percent || 0)
  })

  try {
    const result = await eApi.downloadSoftwareUpdate({
      url: su.update_download_url,
      filename: su.update_filename,
      size_bytes: su.update_size_bytes || 0,
      sha256: su.update_sha256 || '',
    })
    if (result.ok) {
      licenseStore.setUpdateDownloadStatus('downloaded')
      ElMessage.success('更新下载完成，点击「安装并重启」应用更新')
    } else {
      licenseStore.setUpdateDownloadStatus('error', result.error || '下载失败')
    }
  } catch (e: any) {
    licenseStore.setUpdateDownloadStatus('error', e.message || '下载出错')
  }
}

async function cancelUpdate() {
  await window.electronAPI?.cancelSoftwareUpdate?.()
  licenseStore.setUpdateDownloadStatus('idle')
}

async function installUpdate() {
  const eApi = window.electronAPI
  if (!eApi?.installSoftwareUpdate) return

  licenseStore.setUpdateDownloadStatus('installing')
  try {
    const result = await eApi.installSoftwareUpdate()
    if (!result.ok) {
      licenseStore.setUpdateDownloadStatus('error', result.error || '安装失败')
      ElMessage.error(result.error || '安装失败')
    }
  } catch (e: any) {
    licenseStore.setUpdateDownloadStatus('error', e.message || '安装出错')
    ElMessage.error(e.message || '安装出错')
  }
}

function formatExpiry(iso: string) {
  try {
    return new Date(iso).toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
  } catch {
    return iso
  }
}


async function loadPackStatus() {
  const eApi = window.electronAPI
  if (!eApi?.getPackStatus) return
  packLoading.value = true
  try {
    const list: any[] = (await eApi.getPackStatus()) || []
    packList.value = list.filter(item => item.category !== 'drawing' && !(item.specialty_id || '').startsWith('medpic-'))

    for (const sp of licenseStore.specialties) {
      if (sp.id.startsWith('medpic-')) continue
      if (!packList.value.find(p => p.specialty_id === sp.id)) {
        packList.value.push({
          specialty_id: sp.id,
          name: sp.name,
          local_version: sp.local_version,
          remote_version: sp.remote_version,
          status: sp.local_version ? 'installed' : 'not_installed',
          knowledge_docs: 0, terms: 0, examples: 0,
        })
      } else {
        const existing = packList.value.find(p => p.specialty_id === sp.id)!
        if (sp.remote_version && existing.local_version && sp.remote_version !== existing.local_version) {
          existing.status = 'update_available'
          existing.remote_version = sp.remote_version
        }
        if (!existing.name || existing.name === existing.specialty_id) {
          existing.name = sp.name
        }
      }
    }
  } finally {
    packLoading.value = false
  }
}

function triggerPackUpload() {
  packFileInput.value?.click()
}

async function handlePackFileSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  input.value = ''

  const eApi = window.electronAPI
  if (!eApi?.installSpecialtyFromFile) {
    ElMessage.error('当前环境不支持学科包上传安装')
    return
  }

  packUploading.value = true
  packUploadPercent.value = 0
  packUploadDetail.value = `正在安装 ${file.name}...`

  try {
    const arrayBuffer = await file.arrayBuffer()
    const filePath = (file as any).path || file.name

    packUploadPercent.value = 30
    packUploadDetail.value = '正在解析学科包...'

    const res = await eApi.installSpecialtyFromFile(filePath, file.name)

    if (res?.ok) {
      packUploadPercent.value = 100
      packUploadDetail.value = '安装完成'
      ElMessage.success(`学科包「${res.name || file.name}」安装成功`)
      await loadPackStatus()
    } else {
      ElMessage.error(res?.error || '学科包安装失败')
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '学科包安装失败')
  } finally {
    setTimeout(() => {
      packUploading.value = false
      packUploadPercent.value = 0
      packUploadDetail.value = ''
    }, 1500)
  }
}



const openaiKey = ref('')
const dashscopeKey = ref('')
const siliconflowKey = ref('')
const deepseekKey = ref('')
const zhipuKey = ref('')
const moonshotKey = ref('')
const googleAiKey = ref('')
const openrouterKey = ref('')
const qiniuMaasKey = ref('')
const anthropicKey = ref('')
const deeplKey = ref('')
const googleTranslateKey = ref('')
const azureTranslateKey = ref('')
const azureTranslateRegion = ref('')
interface LlmModel { id: string; name: string; provider: string; max_tokens?: number }
const llmModels = ref<LlmModel[]>([])
const selectedDefaultModel = ref(settingsStore.defaultModel)
const selectedLlmProvider = ref('openai')
const MODEL_TOKENS: Record<string, number> = {
  'gpt-4o-mini': 128000, 'gpt-4o': 128000, 'gpt-4.1-mini': 1047576, 'gpt-4.1': 1047576,
  'claude-sonnet-4-6': 1000000, 'claude-opus-4-6': 1000000, 'claude-haiku-4-5': 200000,
  'gemini-2.5-flash': 1048576, 'gemini-3.1-pro-preview': 1048576,
  'deepseek-chat': 64000, 'deepseek-coder': 16000, 'deepseek-reasoner': 64000,
  'kimi-k2.5': 262144, 'kimi-k2-0905-preview': 262144, 'kimi-k2-turbo-preview': 262144, 'kimi-k2-thinking': 131072, 'kimi-k2-thinking-turbo': 262144, 'kimi-k2-0711-preview': 131072,
  'qwen3-235b-a22b': 131072, 'qwen-turbo': 131072, 'qwen-turbo-latest': 1000000,
  'qwen-plus': 131072, 'qwen-plus-latest': 131072, 'qwen-max': 32768, 'qwen-max-latest': 32768, 'qwen-long': 10000000,
  'glm-4.7': 205000, 'glm-4.7-flash': 205000, 'glm-4-flash': 128000, 'glm-4-plus': 128000,
  'Qwen/Qwen3-32B': 131072, 'Qwen/Qwen2.5-7B-Instruct': 32768,
  'deepseek-ai/DeepSeek-V3': 164000, 'deepseek-ai/DeepSeek-R1': 164000,
  'meta-llama/Llama-4-Scout-17B-16E-Instruct': 131072,
  'openrouter/openai/gpt-4o-mini': 128000, 'openrouter/openai/gpt-4o': 128000,
  'openrouter/anthropic/claude-sonnet-4.6': 1000000, 'openrouter/anthropic/claude-opus-4.6': 1000000,
  'openrouter/anthropic/claude-haiku-4.5': 200000,
  'openrouter/google/gemini-2.5-flash': 1048576, 'openrouter/google/gemini-3.1-pro-preview': 1048576,
  'openrouter/deepseek/deepseek-r1': 64000, 'openrouter/deepseek/deepseek-v3': 64000,
  'openrouter/meta-llama/llama-4-scout': 131072,
  'qiniu/deepseek-v3': 64000, 'qiniu/deepseek-r1': 64000,
  'qiniu/qwen2.5-72b-instruct': 32768, 'qiniu/qwen2.5-32b-instruct': 32768, 'qiniu/glm-4-plus': 128000,
}

function formatTokens(tokens: number | undefined): string {
  if (!tokens) return ''
  if (tokens >= 1000000) return `${(tokens / 1000000).toFixed(tokens % 1000000 === 0 ? 0 : 1)}M`
  if (tokens >= 1000) return `${Math.round(tokens / 1000)}K`
  return String(tokens)
}

const llmProviders = computed(() => Array.from(new Set(llmModels.value.map((m) => m.provider))))
const filteredModelsByProvider = computed(() =>
  llmModels.value.filter((m) => m.provider === selectedLlmProvider.value)
)
const selectedModelTokens = computed(() => {
  const m = llmModels.value.find(m => m.id === selectedDefaultModel.value)
  return m?.max_tokens || MODEL_TOKENS[selectedDefaultModel.value] || 0
})
const testing = ref(false)
const saving = ref(false)
const apiKeyResult = ref<{ valid: boolean; error?: string } | null>(null)
const selfCheckLoading = ref(false)
const selfCheckText = ref('')
const backupLoading = ref(false)
const restoreLoading = ref(false)
const restoreResult = ref<{ ok: boolean; error?: string } | null>(null)
const hasElectronKeychain = typeof window !== 'undefined' && !!(window as any).electronAPI?.saveApiKey
const CAPTURE_HISTORY_ENABLED_KEY = 'literature_browser_capture_history_enabled_v1'
const CAPTURE_HISTORY_KEY = 'literature_browser_capture_history_v1'
const captureHistoryEnabled = ref(true)

function hasNonAscii(value: string) {
  for (const ch of value) {
    if (ch.charCodeAt(0) > 127) return true
  }
  return false
}

function buildLocalModels(): LlmModel[] {
  const local: LlmModel[] = []
  if (openaiKey.value) {
    local.push(
      { id: 'gpt-4o-mini', name: 'GPT-4o Mini', provider: 'openai' },
      { id: 'gpt-4o', name: 'GPT-4o', provider: 'openai' },
      { id: 'gpt-4.1-mini', name: 'GPT-4.1 Mini', provider: 'openai' },
      { id: 'gpt-4.1', name: 'GPT-4.1', provider: 'openai' }
    )
  }
  if (anthropicKey.value) {
    local.push(
      { id: 'claude-sonnet-4-6', name: 'Claude Sonnet 4.6', provider: 'anthropic' },
      { id: 'claude-opus-4-6', name: 'Claude Opus 4.6', provider: 'anthropic' },
      { id: 'claude-haiku-4-5', name: 'Claude Haiku 4.5', provider: 'anthropic' }
    )
  }
  if (openrouterKey.value) {
    local.push(
      { id: 'openrouter/openai/gpt-4o-mini', name: 'openai/gpt-4o-mini', provider: 'openrouter' },
      { id: 'openrouter/openai/gpt-4o', name: 'openai/gpt-4o', provider: 'openrouter' },
      { id: 'openrouter/anthropic/claude-sonnet-4.6', name: 'anthropic/claude-sonnet-4.6', provider: 'openrouter' },
      { id: 'openrouter/anthropic/claude-opus-4.6', name: 'anthropic/claude-opus-4.6', provider: 'openrouter' },
      { id: 'openrouter/anthropic/claude-haiku-4.5', name: 'anthropic/claude-haiku-4.5', provider: 'openrouter' },
      { id: 'openrouter/google/gemini-2.5-flash', name: 'google/gemini-2.5-flash', provider: 'openrouter' },
      { id: 'openrouter/google/gemini-3.1-pro-preview', name: 'google/gemini-3.1-pro-preview', provider: 'openrouter' },
      { id: 'openrouter/deepseek/deepseek-r1', name: 'deepseek/deepseek-r1', provider: 'openrouter' },
      { id: 'openrouter/deepseek/deepseek-v3', name: 'deepseek/deepseek-v3', provider: 'openrouter' },
      { id: 'openrouter/meta-llama/llama-4-scout', name: 'meta-llama/llama-4-scout', provider: 'openrouter' }
    )
  }
  if (googleAiKey.value) {
    local.push(
      { id: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash', provider: 'google_ai' },
      { id: 'gemini-3.1-pro-preview', name: 'Gemini 3.1 Pro Preview', provider: 'google_ai' }
    )
  }
  if (siliconflowKey.value) {
    local.push(
      { id: 'Qwen/Qwen3-32B', name: 'Qwen3-32B', provider: 'siliconflow' },
      { id: 'Qwen/Qwen2.5-7B-Instruct', name: 'Qwen2.5-7B-Instruct', provider: 'siliconflow' },
      { id: 'deepseek-ai/DeepSeek-V3', name: 'DeepSeek-V3', provider: 'siliconflow' },
      { id: 'deepseek-ai/DeepSeek-R1', name: 'DeepSeek-R1', provider: 'siliconflow' },
      { id: 'meta-llama/Llama-4-Scout-17B-16E-Instruct', name: 'Llama 4 Scout', provider: 'siliconflow' }
    )
  }
  if (deepseekKey.value) {
    local.push(
      { id: 'deepseek-chat', name: 'DeepSeek V3', provider: 'deepseek' },
      { id: 'deepseek-reasoner', name: 'DeepSeek R1', provider: 'deepseek' }
    )
  }
  if (zhipuKey.value) {
    local.push(
      { id: 'glm-4.7', name: 'GLM-4.7', provider: 'zhipu' },
      { id: 'glm-4.7-flash', name: 'GLM-4.7 Flash', provider: 'zhipu' },
      { id: 'glm-4-flash', name: 'GLM-4 Flash', provider: 'zhipu' },
      { id: 'glm-4-plus', name: 'GLM-4 Plus', provider: 'zhipu' }
    )
  }
  if (moonshotKey.value) {
    local.push(
      { id: 'kimi-k2.5', name: 'Kimi K2.5', provider: 'moonshot' },
      { id: 'kimi-k2-turbo-preview', name: 'Kimi K2 Turbo', provider: 'moonshot' },
      { id: 'kimi-k2-thinking', name: 'Kimi K2 Thinking', provider: 'moonshot' },
      { id: 'kimi-k2-thinking-turbo', name: 'Kimi K2 Thinking Turbo', provider: 'moonshot' },
      { id: 'kimi-k2-0905-preview', name: 'Kimi K2 0905', provider: 'moonshot' },
      { id: 'kimi-k2-0711-preview', name: 'Kimi K2 0711', provider: 'moonshot' }
    )
  }
  if (dashscopeKey.value) {
    local.push(
      { id: 'qwen3-235b-a22b', name: 'Qwen3 235B', provider: 'dashscope' },
      { id: 'qwen-max-latest', name: 'Qwen Max (Latest)', provider: 'dashscope' },
      { id: 'qwen-plus-latest', name: 'Qwen Plus (Latest)', provider: 'dashscope' },
      { id: 'qwen-turbo-latest', name: 'Qwen Turbo (Latest)', provider: 'dashscope' },
      { id: 'qwen-turbo', name: 'Qwen Turbo', provider: 'dashscope' },
      { id: 'qwen-plus', name: 'Qwen Plus', provider: 'dashscope' },
      { id: 'qwen-max', name: 'Qwen Max', provider: 'dashscope' },
      { id: 'qwen-long', name: 'Qwen Long', provider: 'dashscope' }
    )
  }
  if (qiniuMaasKey.value) {
    local.push(
      { id: 'qiniu/deepseek-v3', name: 'deepseek-v3', provider: 'qiniu' },
      { id: 'qiniu/deepseek-r1', name: 'deepseek-r1', provider: 'qiniu' },
      { id: 'qiniu/qwen2.5-32b-instruct', name: 'qwen2.5-32b-instruct', provider: 'qiniu' },
      { id: 'qiniu/qwen2.5-72b-instruct', name: 'qwen2.5-72b-instruct', provider: 'qiniu' },
      { id: 'qiniu/glm-4-plus', name: 'glm-4-plus', provider: 'qiniu' }
    )
  }
  return local.map(m => ({ ...m, max_tokens: m.max_tokens || MODEL_TOKENS[m.id] || 0 }))
}

onMounted(async () => {
  if (!isElectronEnv && getAuthToken()) {
    await loadSaasProfile()
    loadOrderHistory()
    loadMyLicenseCodes()
    loadClientProductInfo()
    loadUsageLogs()
    loadReferralInfo()
    loadReferralDetails()
    loadWithdrawals()
  }
  await authStore.refreshMe()
  await settingsStore.loadDefaultModelFromServer()
  selectedDefaultModel.value = settingsStore.defaultModel

  // 学科包状态 + 进度监听
  loadPackStatus()
  window.electronAPI?.onSpecialtyDownloadProgress?.((p) => {
    downloadingPack.value = {
      specialty_id: p.specialty_id,
      name: p.name,
      percent: p.percent,
      status: p.status,
      detail: p.detail,
    }
    if (p.status === 'done') {
      setTimeout(() => loadPackStatus(), 500)
    }
  })
  window.electronAPI?.onNewSpecialtiesAvailable?.(async () => {
    await loadPackStatus()
  })

  try {
    const enabledRaw = localStorage.getItem(CAPTURE_HISTORY_ENABLED_KEY)
    captureHistoryEnabled.value = enabledRaw !== '0'
  } catch {
    captureHistoryEnabled.value = true
  }
  try {
    const res = await api.data.getContentStats()
    contentStats.value = {
      terms: res.data?.terms ?? 0,
      examples: res.data?.examples ?? 0,
      docs: res.data?.docs ?? 0,
    }
  } catch {
    contentStats.value = { terms: 0, examples: 0, docs: 0 }
  }
  if (hasElectronKeychain) {
    const api = (window as any).electronAPI
    const [openai, dashscope, siliconflow, deepseek, zhipu, moonshot, googleAi, openrouter, qiniuMaas, anthropic, deepl, googleTrans, azureTrans, azureTransRegion] = await Promise.all([
      api.getApiKey('openai'),
      api.getApiKey('dashscope'),
      api.getApiKey('siliconflow'),
      api.getApiKey('deepseek'),
      api.getApiKey('zhipu'),
      api.getApiKey('moonshot'),
      api.getApiKey('google_ai'),
      api.getApiKey('openrouter'),
      api.getApiKey('qiniu_maas'),
      api.getApiKey('anthropic'),
      api.getApiKey('deepl'),
      api.getApiKey('google_translate'),
      api.getApiKey('azure_translate'),
      api.getApiKey('azure_translate_region'),
    ])
    if (openai) openaiKey.value = openai
    if (dashscope) dashscopeKey.value = dashscope
    if (siliconflow) siliconflowKey.value = siliconflow
    if (deepseek) deepseekKey.value = deepseek
    if (zhipu) zhipuKey.value = zhipu
    if (moonshot) moonshotKey.value = moonshot
    if (googleAi) googleAiKey.value = googleAi
    if (openrouter) openrouterKey.value = openrouter
    if (qiniuMaas) qiniuMaasKey.value = qiniuMaas
    if (anthropic) anthropicKey.value = anthropic
    if (deepl) deeplKey.value = deepl
    if (googleTrans) googleTranslateKey.value = googleTrans
    if (azureTrans) azureTranslateKey.value = azureTrans
    if (azureTransRegion) azureTranslateRegion.value = azureTransRegion
  }
  try {
    const res = await api.system.getLlmModels()
    llmModels.value = res.data?.models || []
  } catch {
    llmModels.value = []
  }
  if (!llmModels.value.length) {
    llmModels.value = buildLocalModels()
  }
  // 智能选择最佳默认模型（偏好大上下文、主流模型）
  const PREFERRED_DEFAULTS = [
    'deepseek-chat', 'gemini-2.5-flash', 'kimi-k2.5',
    'glm-4-flash', 'qwen-turbo', 'kimi-k2-turbo-preview',
    'gpt-4o-mini',
  ]
  function pickBestModel(): LlmModel | undefined {
    for (const pid of PREFERRED_DEFAULTS) {
      const found = llmModels.value.find(m => m.id === pid)
      if (found) return found
    }
    return llmModels.value[0]
  }

  // 兼容旧版本遗留值：default 不是实际模型 ID
  if (selectedDefaultModel.value === 'default' || !selectedDefaultModel.value) {
    const best = pickBestModel()
    if (best?.id) {
      selectedDefaultModel.value = best.id
      settingsStore.setDefaultModel(best.id)
    }
  }
  if (!llmModels.value.some((m) => m.id === selectedDefaultModel.value)) {
    const best = pickBestModel()
    if (best?.id) {
      selectedDefaultModel.value = best.id
      settingsStore.setDefaultModel(best.id)
    } else if (selectedDefaultModel.value) {
      llmModels.value.unshift({
        id: selectedDefaultModel.value,
        name: selectedDefaultModel.value,
        provider: 'default',
      })
    }
  }
  const current = llmModels.value.find((m) => m.id === selectedDefaultModel.value)
  if (current) selectedLlmProvider.value = current.provider
})

async function logout() {
  try {
    await ElMessageBox.confirm('将清空本地会话 token，下次请求会重新登录。', '退出登录', {
      confirmButtonText: '退出',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await authStore.logout()
    ElMessage.success('已退出')
  } catch {
    // ignore
  }
}

watch(selectedDefaultModel, (v) => {
  settingsStore.setDefaultModel(v)
})
watch(selectedLlmProvider, (provider) => {
  if (!filteredModelsByProvider.value.some((m) => m.id === selectedDefaultModel.value)) {
    selectedDefaultModel.value = filteredModelsByProvider.value[0]?.id || selectedDefaultModel.value
  }
})
watch(usageFilter, () => { loadUsageLogs() })
watch(usageMonth, () => { loadUsageLogs() })
watch(captureHistoryEnabled, (enabled) => {
  try {
    localStorage.setItem(CAPTURE_HISTORY_ENABLED_KEY, enabled ? '1' : '0')
    if (!enabled) localStorage.removeItem(CAPTURE_HISTORY_KEY)
  } catch {
    // ignore localStorage failures
  }
})

async function testApiKey() {
  testing.value = true
  apiKeyResult.value = null
  try {
    const res = await api.system.testApiKey(openaiKey.value)
    apiKeyResult.value = { valid: res.data?.valid ?? false, error: res.data?.error }
  } catch {
    apiKeyResult.value = { valid: false, error: '请求失败' }
  } finally {
    testing.value = false
  }
}

async function runSelfCheck() {
  selfCheckLoading.value = true
  selfCheckText.value = ''
  try {
    const res = await api.system.selfCheck()
    const d = res.data
    const lines: string[] = []
    lines.push(`Ollama: ${d.ollama?.available ? '可达' : '不可用（本地向量重排需启动 Ollama）'}`)
    lines.push(`Ollama 向量模型环境变量 OLLAMA_EMBED_MODEL: ${d.ollama_embed_model || '-'}`)
    lines.push(`至少一种 LLM 相关环境 Key: ${d.llm_any_configured ? '是' : '否'}`)
    lines.push('LLM / 网关（进程环境）:')
    for (const [k, v] of Object.entries(d.llm_env_keys || {})) {
      lines.push(`  ${k}: ${v ? '已配置' : '未配置'}`)
    }
    lines.push('翻译专用:')
    for (const [k, v] of Object.entries(d.translate_env_keys || {})) {
      lines.push(`  ${k}: ${v ? '已配置' : '未配置'}`)
    }
    if (d.translate_note) lines.push(String(d.translate_note))
    lines.push('生图（节选）:')
    for (const [k, v] of Object.entries(d.image_env_keys || {})) {
      lines.push(`  ${k}: ${v ? '已配置' : '未配置'}`)
    }
    selfCheckText.value = lines.join('\n')
  } catch (e: any) {
    selfCheckText.value = e?.response?.data?.detail || e?.message || '自检请求失败'
  } finally {
    selfCheckLoading.value = false
  }
}

async function saveApiKeys() {
  if (!hasElectronKeychain) return
  saving.value = true
  try {
    const api = (window as any).electronAPI
    const keyItems: Array<{ account: string; label: string; value: string }> = [
      { account: 'openai', label: 'OpenAI API Key', value: openaiKey.value.trim() },
      { account: 'dashscope', label: '通义千问 API Key', value: dashscopeKey.value.trim() },
      { account: 'siliconflow', label: '硅基流动 API Key', value: siliconflowKey.value.trim() },
      { account: 'deepseek', label: 'DeepSeek API Key', value: deepseekKey.value.trim() },
      { account: 'zhipu', label: '智谱 API Key', value: zhipuKey.value.trim() },
      { account: 'moonshot', label: 'Moonshot API Key', value: moonshotKey.value.trim() },
      { account: 'google_ai', label: 'Google AI API Key', value: googleAiKey.value.trim() },
      { account: 'openrouter', label: 'OpenRouter API Key', value: openrouterKey.value.trim() },
      { account: 'qiniu_maas', label: '七牛 MaaS API Key', value: qiniuMaasKey.value.trim() },
      { account: 'anthropic', label: 'Anthropic API Key', value: anthropicKey.value.trim() },
      { account: 'deepl', label: 'DeepL API Key', value: deeplKey.value.trim() },
      { account: 'google_translate', label: 'Google 翻译 API Key', value: googleTranslateKey.value.trim() },
      { account: 'azure_translate', label: 'Azure 翻译 Key', value: azureTranslateKey.value.trim() },
      { account: 'azure_translate_region', label: 'Azure 翻译 Region', value: azureTranslateRegion.value.trim() },
    ]
    for (const item of keyItems) {
      if (!item.value) continue
      if (hasNonAscii(item.value)) {
        throw new Error(`${item.label} 包含非 ASCII 字符，请重新粘贴纯英文 Key`)
      }
      await api.saveApiKey(item.account, item.value)
    }
    let reloadRes: { ok: boolean; error?: string } = { ok: false }
    try {
      reloadRes = api.reloadBackendEnv ? await api.reloadBackendEnv() : { ok: false, error: '未注入重载接口' }
    } catch (e: any) {
      reloadRes = { ok: false, error: e?.message || '后端重载调用失败' }
    }
    if (reloadRes?.ok) {
      ElMessage.success('已保存并自动重载后端，立即生效')
      try {
        const res = await api.system.getLlmModels()
        llmModels.value = res.data?.models || []
        if (!llmModels.value.length) llmModels.value = buildLocalModels()
      } catch {
        llmModels.value = buildLocalModels()
      }
    } else {
      ElMessage.warning(`已保存到系统 Keychain，后端重载失败（${reloadRes?.error || '未知原因'}），请手动重启应用后生效`)
      llmModels.value = buildLocalModels()
    }
  } catch (e: any) {
    ElMessage.error(`保存失败：${e?.message || '未知错误'}`)
  } finally {
    saving.value = false
  }
}

async function handleBackup() {
  if (!(window as any).electronAPI?.backupFull) return
  backupLoading.value = true
  restoreResult.value = null
  try {
    const res = await (window as any).electronAPI.backupFull()
    if (res?.ok) ElMessage.success('备份完成')
    else ElMessage.error(res?.error || '备份失败')
  } catch (e) {
    ElMessage.error('备份失败')
  } finally {
    backupLoading.value = false
  }
}

async function handleRestore() {
  const api = (window as any).electronAPI
  if (!api?.showOpenBackupDialog || !api?.restoreFromZip) return
  restoreLoading.value = true
  restoreResult.value = null
  try {
    const zipPath = await api.showOpenBackupDialog()
    if (!zipPath) return
    let strategy: string = 'cancel'
    try {
      await ElMessageBox.confirm('覆盖已存在的文件？', '恢复策略', {
        confirmButtonText: '覆盖',
        cancelButtonText: '否',
        type: 'warning',
      })
      strategy = 'overwrite'
    } catch (a) {
      try {
        await ElMessageBox.confirm('仅导入缺失（不覆盖已有文件）？', '恢复策略', {
          confirmButtonText: '仅导入缺失',
          cancelButtonText: '取消',
          type: 'info',
        })
        strategy = 'missing_only'
      } catch {
        strategy = 'cancel'
      }
    }
    if (strategy === 'cancel') return
    const res = await api.restoreFromZip(zipPath, strategy)
    restoreResult.value = res?.ok ? { ok: true } : { ok: false, error: res?.error }
    if (res?.ok) ElMessage.success('恢复成功，请重启应用')
  } catch (e) {
    restoreResult.value = { ok: false, error: String(e) }
  } finally {
    restoreLoading.value = false
  }
}
</script>

<style scoped>
.settings { }
h2 { margin-bottom: 1rem; }
.about-section .about-row { margin: 0.5rem 0; }
.about-section .label { display: inline-block; width: 6em; color: #6b7280; }
.content-config .config-row { margin: 0.5rem 0; display: flex; align-items: center; gap: 0.5rem; }
.content-config .config-label { display: inline-block; width: 8em; }
.content-config .config-block { margin-bottom: 1rem; padding-bottom: 1rem; border-bottom: 1px solid #eee; }
.content-config .config-block:last-of-type { border-bottom: none; }
.content-config .config-block-title { font-weight: 600; margin-bottom: 0.5rem; }
.action-row { display: flex; flex-direction: column; align-items: flex-start; gap: 0.5rem; }
.action-row :deep(.el-button + .el-button) { margin-left: 0; }
.model-select-row { display: flex; align-items: center; gap: 0.5rem; }
.model-hint { margin-left: 0.75rem; color: #6b7280; font-size: 0.85rem; display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
.model-ctx-badge {
  display: inline-block;
  padding: 1px 8px;
  background: #eff6ff;
  color: #1d4ed8;
  border-radius: 10px;
  font-size: 0.78rem;
  font-weight: 500;
  white-space: nowrap;
}
.model-option-row { display: flex; justify-content: space-between; align-items: center; width: 100%; }
.model-option-name { flex: 1; overflow: hidden; text-overflow: ellipsis; }
.model-option-tokens { flex-shrink: 0; margin-left: 12px; color: #8492a6; font-size: 12px; font-weight: 500; }
.privacy-tip { margin-left: 0.5rem; cursor: help; }
.api-key-form :deep(.el-form-item__label) { white-space: nowrap; }
.api-group-title {
  margin: 0.5rem 0 0.25rem;
  font-weight: 600;
  color: #374151;
}
.api-group-note {
  margin: 0.25rem 0 0.75rem;
  color: #6b7280;
  font-size: 0.85rem;
}
.apply-link {
  margin-left: 8px;
  font-size: 12px;
  color: #409eff;
  white-space: nowrap;
  text-decoration: none;
  flex-shrink: 0;
}
.apply-link:hover {
  text-decoration: underline;
}
.pack-empty { padding: 0.5rem 0; }
.pack-item { padding: 0.75rem 0; border-bottom: 1px solid #f0f0f0; }
.pack-item:last-child { border-bottom: none; }
.pack-header { display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.25rem; }
.pack-name { font-weight: 600; font-size: 0.95rem; }
.pack-stats { color: #6b7280; font-size: 0.85rem; margin-bottom: 0.25rem; }
.pack-progress { margin: 0.5rem 0; }
.pack-progress-detail { color: #6b7280; font-size: 0.8rem; margin-top: 0.2rem; display: block; }
.pack-actions { margin-top: 0.35rem; }
.self-check-pre {
  margin: 0.5rem 0 0;
  padding: 0.65rem 0.75rem;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  font-size: 0.78rem;
  line-height: 1.45;
  max-height: 280px;
  overflow: auto;
  white-space: pre-wrap;
}
.client-promo-card .promo-desc {
  color: #374151;
  margin-bottom: 12px;
  font-size: 0.9rem;
}
.promo-features {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.promo-feature-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: 0.9rem;
  color: #4b5563;
  line-height: 1.5;
}
.promo-icon {
  flex-shrink: 0;
  font-size: 1.1rem;
}
.download-notice { margin-top: 12px; }
.download-platforms {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.download-plat-card {
  border: 2px solid #e5e7eb;
  border-radius: 10px;
  padding: 16px 20px;
  text-align: center;
  min-width: 140px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}
.download-plat-card--disabled { opacity: 0.5; }
.plat-icon { font-size: 1.6rem; }
.plat-name { font-size: 0.85rem; font-weight: 500; color: #374151; }
.referral-code-block {
  padding: 10px 14px;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
}
.referral-stat {
  text-align: center;
  padding: 10px 20px;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  min-width: 100px;
}
.referral-stat-value {
  font-size: 1.3rem;
  font-weight: 700;
  color: #1e40af;
}
.referral-stat-label {
  font-size: 0.78rem;
  color: #6b7280;
  margin-top: 2px;
}
.redeem-card {
  border: 2px solid #e5e7eb;
  border-radius: 10px;
  padding: 16px;
  text-align: center;
  min-width: 160px;
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}
.redeem-title { font-weight: 600; color: #374151; font-size: 0.9rem; }
.redeem-price { font-size: 1.3rem; font-weight: 700; color: #1e40af; }
.redeem-desc { font-size: 0.8rem; color: #9ca3af; margin-bottom: 4px; }
.recharge-plans {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
.plan-card {
  border: 2px solid #e5e7eb;
  border-radius: 10px;
  padding: 16px 12px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
}
.plan-card:not(.plan-card--readonly):hover {
  border-color: #93c5fd;
}
.plan-card.active {
  border-color: #3b82f6;
  background: #eff6ff;
}
.plan-card--readonly {
  cursor: default;
  padding: 10px 8px;
}
.plan-price {
  font-size: 1.4rem;
  font-weight: 700;
  color: #1e40af;
}
.plan-credits {
  font-size: 0.95rem;
  color: #374151;
  margin-top: 4px;
}
.plan-bonus {
  font-size: 0.8rem;
  color: #059669;
  font-weight: 600;
  margin-top: 2px;
}
.plan-unit {
  font-size: 0.75rem;
  color: #9ca3af;
  margin-top: 4px;
}
</style>

<!-- 下拉挂载在 body，需非 scoped 样式 -->
<style>
.medcomm-model-dropdown {
  min-width: 380px !important;
}
.medcomm-model-dropdown .el-select-dropdown__item {
  padding-right: 16px;
}
</style>
