<template>
  <div class="settings page-container page-cards">
    <h2>设置</h2>

    <!-- 账户与关于 -->
    <el-card class="settings-card">
      <template #header>账户与关于</template>
      <div class="about-section" style="margin-bottom: 12px;">
        <div class="about-row"><span class="label">本地用户</span> {{ authStore.user?.display_name || '未登录' }}{{ authStore.user ? `（ID: ${authStore.user.id}）` : '' }}</div>
        <div class="about-row" style="gap: 8px;">
          <el-button v-if="!authStore.user" size="small" type="primary" @click="loginLocalUser">登录本地</el-button>
          <el-button v-else size="small" @click="switchUser">切换本地用户</el-button>
          <el-button v-if="authStore.user" size="small" type="warning" @click="logout">退出本地</el-button>
        </div>
      </div>
      <div class="about-section" style="margin-bottom: 12px;">
        <div class="about-row"><span class="label">门户授权</span>
          <span v-if="licenseStore.isValid" style="color: #16a34a;">已激活</span>
          <span v-else-if="licenseStore.base" style="color: #dc2626;">已过期</span>
          <span v-else style="color: #9ca3af;">未绑定</span>
          <span v-if="portalEmail" style="margin-left: 8px; color: #374151;">{{ portalEmail }}</span>
          <span v-if="licenseStore.expiresAt" style="margin-left: 8px; color: #6b7280;">
            到期 {{ formatExpiry(licenseStore.expiresAt) }}
          </span>
        </div>
        <div v-if="!licenseStore.isValid && !licenseStore.base" class="about-row" style="gap: 8px; flex-wrap: wrap; align-items: flex-end;">
          <el-input v-model="portalEmailInput" placeholder="门户邮箱" size="small" style="width: 180px;" />
          <el-input v-model="portalPasswordInput" type="password" placeholder="密码" size="small" style="width: 160px;" show-password />
          <el-button size="small" type="primary" :loading="portalLoginLoading" @click="portalLogin">登录绑定</el-button>
          <el-button size="small" @click="goPortal">去门户注册</el-button>
        </div>
        <div v-else class="about-row" style="gap: 8px;">
          <el-button size="small" @click="goPortal">前往门户</el-button>
          <el-button v-if="hasElectronKeychain" size="small" type="danger" @click="deactivateLicense">解除授权绑定</el-button>
        </div>
        <div v-if="portalLoginError" class="about-row" style="color: #dc2626; font-size: 0.85rem;">{{ portalLoginError }}</div>
      </div>
      <div v-if="settingsStore.isBasic" class="about-section">
        <div class="about-row"><span class="label">当前版本</span> 基础版</div>
        <div class="about-row"><span class="label">学科配置</span> 通用预置</div>
        <div class="about-row"><span class="label">内容更新</span> 软件版本更新时同步</div>
        <el-button type="primary" text size="small" @click="openMedcommSite">了解定制版</el-button>
      </div>
      <div v-else class="about-section">
        <div class="about-row"><span class="label">当前版本</span> {{ settingsStore.license.customSpecialties.join('、') || '定制' }}定制版</div>
        <div class="about-row"><span class="label">学科配置</span> {{ settingsStore.license.customSpecialties.join(' · ') || '-' }}</div>
        <div v-if="settingsStore.license.serviceExpiry" class="about-row"><span class="label">服务到期</span> {{ settingsStore.license.serviceExpiry }}</div>
        <div class="about-row"><span class="label">内容更新</span> 季度更新 · 下次更新 {{ settingsStore.license.nextContentUpdate || '-' }}</div>
        <el-button type="primary" text size="small" @click="openContact">联系服务支持</el-button>
      </div>
      <div v-if="isElectronEnv" class="about-section" style="margin-top: 12px; border-top: 1px solid #e5e7eb; padding-top: 12px;">
        <div class="about-row"><span class="label">软件版本</span> v{{ appVersion }}</div>
        <div class="about-row" style="gap: 8px; align-items: center; flex-wrap: wrap;">
          <span class="label">软件更新</span>
          <span v-if="licenseStore.hasSoftwareUpdate" style="color: #1e40af;">
            新版本 v{{ licenseStore.softwareUpdate?.latest_version }} 可用
          </span>
          <span v-else style="color: #9ca3af;">当前已是最新版本</span>
          <el-button size="small" :loading="checkingUpdate" @click="manualCheckUpdate">检查更新</el-button>

          <!-- 阶段一：有更新可下载 -->
          <el-button
            v-if="licenseStore.hasSoftwareUpdate && licenseStore.updateDownloadStatus === 'idle' && hasInAppUpdate"
            size="small" type="primary"
            @click="startInAppUpdate"
          >立即更新</el-button>

          <!-- 回退：无应用内更新信息时走浏览器 -->
          <el-button
            v-if="licenseStore.hasSoftwareUpdate && licenseStore.updateDownloadStatus === 'idle' && !hasInAppUpdate && licenseStore.softwareUpdate?.download_url"
            size="small"
            @click="downloadUpdateLegacy"
          >浏览器下载</el-button>

          <!-- 阶段二：下载中 -->
          <template v-if="licenseStore.updateDownloadStatus === 'downloading'">
            <el-button size="small" type="danger" plain @click="cancelUpdate">取消</el-button>
          </template>

          <!-- 阶段三：下载完成 -->
          <el-button
            v-if="licenseStore.updateDownloadStatus === 'downloaded'"
            size="small" type="success"
            @click="installUpdate"
          >安装并重启</el-button>

          <!-- 错误 -->
          <el-button
            v-if="licenseStore.updateDownloadStatus === 'error'"
            size="small"
            @click="startInAppUpdate"
          >重试</el-button>
        </div>
        <!-- 进度条 -->
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

    <!-- 内容配置 -->
    <el-card class="settings-card">
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

    <!-- MedPic 绘图设置 -->
    <el-card v-if="isElectronEnv" class="settings-card">
      <template #header>MedPic 绘图设置</template>
      <div class="content-config">
        <div class="config-row">
          <span class="config-label">硬件档位</span>
          <el-select v-model="medpicTier" style="width: 220px;" @change="saveMedpicTier">
            <el-option label="普通办公电脑 / 轻薄本" value="low" />
            <el-option label="游戏本 / 主流台式机" value="standard" />
            <el-option label="专业工作站 / 高性能主机" value="high" />
          </el-select>
          <span v-if="medpicTier" style="color: #6b7280; font-size: 0.8rem; margin-left: 0.5rem;">{{ medpicTierDesc }}</span>
        </div>
        <div class="config-row">
          <span class="config-label">ComfyUI 组件</span>
          <span v-if="comfyBundleVersion" style="color: #16a34a;">已安装 v{{ comfyBundleVersion }}</span>
          <span v-else style="color: #9ca3af;">未安装</span>
        </div>
      </div>
    </el-card>

    <!-- 学科包管理 -->
    <el-card v-if="isElectronEnv" class="settings-card">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <span>学科包</span>
          <el-button size="small" text type="primary" @click="goPortalSpecialties">前往门户选购</el-button>
        </div>
      </template>
      <div v-if="!packList.length && !packLoading" class="pack-empty">
        <p style="color:#9ca3af;">暂无学科包。前往门户网站选购后，软件将自动识别并提示安装。</p>
      </div>
      <div v-if="packLoading" style="text-align:center;padding:1rem;color:#9ca3af;">加载中...</div>
      <div v-for="pack in packList" :key="pack.specialty_id" class="pack-item">
        <div class="pack-header">
          <span class="pack-name">{{ pack.name || pack.specialty_id }}</span>
          <el-tag v-if="pack.status === 'installed'" type="success" size="small">已安装 v{{ pack.local_version }}</el-tag>
          <el-tag v-else-if="pack.status === 'downloading'" type="warning" size="small">安装中</el-tag>
          <el-tag v-else-if="pack.status === 'update_available'" type="" size="small">有更新 v{{ pack.remote_version }}</el-tag>
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
        <div class="pack-actions">
          <el-button
            v-if="pack.status === 'not_installed' || pack.status === 'update_available'"
            type="primary" size="small"
            :loading="downloadingPack?.specialty_id === pack.specialty_id && !['done','error'].includes(downloadingPack?.status || '')"
            @click="installPack(pack)"
          >
            {{ pack.status === 'update_available' ? '更新' : '安装' }}
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 绘图扩展包管理 -->
    <el-card v-if="isElectronEnv" class="settings-card">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <span>绘图扩展包（MedPic）</span>
          <div style="display:flex;gap:8px;">
            <el-button size="small" text type="primary" @click="importLocalPack">从本地导入</el-button>
            <el-button size="small" text type="primary" @click="goPortalSpecialties">前往门户选购</el-button>
          </div>
        </div>
      </template>
      <div v-if="!drawingPackList.length && !packLoading" class="pack-empty">
        <p style="color:#9ca3af;">暂无绘图扩展包。基础绘图功能已内置，进阶模型与工作流可在门户选购或从本地导入。</p>
      </div>
      <div v-for="pack in drawingPackList" :key="pack.specialty_id" class="pack-item">
        <div class="pack-header">
          <span class="pack-name">{{ pack.name || pack.specialty_id }}</span>
          <el-tag v-if="pack.status === 'installed'" type="success" size="small">已安装 v{{ pack.local_version }}</el-tag>
          <el-tag v-else-if="pack.status === 'downloading'" type="warning" size="small">安装中</el-tag>
          <el-tag v-else-if="pack.status === 'update_available'" type="" size="small">有更新 v{{ pack.remote_version }}</el-tag>
          <el-tag v-else type="info" size="small">未安装</el-tag>
        </div>
        <div v-if="pack.description" class="pack-stats" style="color:#6b7280;">
          {{ pack.description }}
        </div>
        <div v-if="downloadingPack?.specialty_id === pack.specialty_id" class="pack-progress">
          <el-progress
            :percentage="downloadingPack.percent"
            :status="downloadingPack.status === 'done' ? 'success' : downloadingPack.status === 'error' ? 'exception' : undefined"
            :stroke-width="6"
          />
          <span class="pack-progress-detail">{{ downloadingPack.detail }}</span>
        </div>
        <div class="pack-actions">
          <el-button
            v-if="pack.status === 'not_installed' || pack.status === 'update_available'"
            type="primary" size="small"
            :loading="downloadingPack?.specialty_id === pack.specialty_id && !['done','error'].includes(downloadingPack?.status || '')"
            @click="installPack(pack)"
          >
            {{ pack.status === 'update_available' ? '更新' : '安装' }}
          </el-button>
        </div>
      </div>
    </el-card>

    <el-card class="settings-card">
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

        <div class="api-group-title">生图生成</div>
        <el-form-item label="通义万相 API Key">
          <el-input v-model="dashscopeKey" type="password" placeholder="DashScope / 通义万相 Key" show-password />
          <a class="apply-link" href="https://bailian.console.aliyun.com/?apiKey=1" target="_blank">申请 ↗</a>
        </el-form-item>
        <el-form-item label="文心图像 API Key">
          <el-input v-model="baiduKey" type="password" placeholder="baidu key" show-password />
          <a class="apply-link" href="https://console.bce.baidu.com/iam/#/iam/apikey/list" target="_blank">申请 ↗</a>
        </el-form-item>
        <el-form-item label="文心图像 Secret Key">
          <el-input v-model="baiduSecretKey" type="password" placeholder="baidu secret" show-password />
        </el-form-item>
        <el-form-item label="Pollinations API Key">
          <el-input v-model="pollinationsKey" type="password" placeholder="sk_xxx（enter.pollinations.ai 申请）" show-password />
          <a class="apply-link" href="https://enter.pollinations.ai/" target="_blank">申请 ↗</a>
        </el-form-item>
        <el-form-item label="Comfy Cloud API Key">
          <el-input v-model="comfyCloudKey" type="password" placeholder="platform.comfy.org 生成的 Key" show-password />
          <a class="apply-link" href="https://platform.comfy.org" target="_blank">注册 / 申请 ↗</a>
        </el-form-item>

        <div class="api-group-note">
          注：OpenAI / 硅基流动 API Key 已在“文本生成”分组中配置，同样会用于生图。Pollinations 为免费兜底，需配置 Key 方可使用。
        </div>

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
    <el-card class="settings-card">
      <template #header>模型配置</template>
      <el-form label-width="140px">
        <el-form-item label="默认模型">
          <div class="model-select-row">
            <el-select v-model="selectedLlmProvider" placeholder="先选 Provider" style="width: 180px">
              <el-option v-for="p in llmProviders" :key="p" :label="p" :value="p" />
            </el-select>
            <el-select v-model="selectedDefaultModel" placeholder="再选模型" style="width: 320px">
              <el-option v-for="m in filteredModelsByProvider" :key="m.id" :label="m.name" :value="m.id" />
            </el-select>
          </div>
          <span class="model-hint">所有文章生成均使用该模型，修改后即时生效。</span>
        </el-form-item>
        <el-form-item label="生图提供商优先">
          <div class="image-provider-field">
            <el-select
              v-model="selectedImageProvider"
              placeholder="自动选择"
              style="width: min(100%, 380px)"
              :fit-input-width="false"
              popper-class="medcomm-image-provider-dropdown"
            >
              <el-option-group label="常用 API 生图">
                <el-option label="自动选择（推荐）" value="auto" />
                <el-option label="OpenAI DALL·E 3" value="openai" />
                <el-option label="硅基流动" value="siliconflow" />
                <el-option label="通义万相" value="wanx" />
                <el-option label="文心一格" value="wenxin" />
                <el-option label="Pollinations（免费兜底）" value="pollinations" />
              </el-option-group>
              <el-option-group label="ComfyUI（工作流见下方）">
                <el-option label="自动：有 Comfy Cloud Key 走云端，否则本地 8188" value="comfyui" />
                <el-option label="仅本地 HTTP（127.0.0.1:8188）" value="comfyui_local" />
                <el-option label="仅 Comfy Cloud（X-API-Key）" value="comfyui_cloud" />
              </el-option-group>
            </el-select>
            <p class="image-provider-hint">
              ComfyUI 三项在分组「ComfyUI（工作流见下方）」内；选项较多时请在展开的下拉面板内向下滚动查看。<code>npm run electron:dev</code> 会同时启动 Vite 热更新；若需验证打包效果可 <code>npm run build</code> 后使用 <code>npm run electron:dev:dist</code>。
            </p>
          </div>
        </el-form-item>
        <el-form-item label="硅基流动生图模型">
          <el-input v-model="siliconflowImageModel" placeholder="如：Kwai-Kolors/Kolors" style="width: 320px" />
          <span class="model-hint">仅在选择硅基流动或自动降级到硅基流动时生效。</span>
        </el-form-item>
        <el-form-item label="ComfyUI 工作流 JSON">
          <el-input v-model="comfyWorkflowPath" placeholder="本机 API 格式工作流文件绝对路径" style="width: 420px" />
          <span class="model-hint">在 ComfyUI 中 Save (API Format)；正提示词节点默认写入节点 ID 下的 text/string。</span>
        </el-form-item>
        <el-form-item label="ComfyUI 服务地址">
          <el-input v-model="comfyBaseUrl" placeholder="留空：本地 http://127.0.0.1:8188，云端 https://cloud.comfy.org" style="width: 420px" />
        </el-form-item>
        <el-form-item label="正提示词节点 ID">
          <el-input v-model="comfyPromptNodeId" placeholder="如 6" style="width: 120px" />
          <span class="model-hint" style="margin-left: 0.5rem;">输入键名</span>
          <el-input v-model="comfyPromptInputKey" placeholder="text" style="width: 100px; margin-left: 0.5rem;" />
        </el-form-item>
        <el-form-item label="负提示词节点 ID">
          <el-input v-model="comfyNegativeNodeId" placeholder="可选，如 7" style="width: 120px" />
          <span class="model-hint" style="margin-left: 0.5rem;">输入键名</span>
          <el-input v-model="comfyNegativeInputKey" placeholder="text" style="width: 100px; margin-left: 0.5rem;" />
        </el-form-item>
        <el-form-item label="KSampler 节点 ID">
          <el-input v-model="comfyKsamplerNodeId" placeholder="可选，用于覆盖 seed / steps / cfg / sampler" style="width: 320px" />
        </el-form-item>
      </el-form>
    </el-card>
    <el-card class="settings-card">
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
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useSettingsStore } from '@/stores/settings'
import { useAuthStore } from '@/stores/auth'
import { useMedcommLicenseStore } from '@/stores/medcommLicense'

const router = useRouter()
const settingsStore = useSettingsStore()
const comfyWorkflowPath = computed({
  get: () => settingsStore.comfyWorkflowPath,
  set: (v: string) => settingsStore.setComfyWorkflowPath(v),
})
const comfyBaseUrl = computed({
  get: () => settingsStore.comfyBaseUrl,
  set: (v: string) => settingsStore.setComfyBaseUrl(v),
})
const comfyPromptNodeId = computed({
  get: () => settingsStore.comfyPromptNodeId,
  set: (v: string) => settingsStore.setComfyPromptNodeId(v),
})
const comfyPromptInputKey = computed({
  get: () => settingsStore.comfyPromptInputKey,
  set: (v: string) => settingsStore.setComfyPromptInputKey(v),
})
const comfyNegativeNodeId = computed({
  get: () => settingsStore.comfyNegativeNodeId,
  set: (v: string) => settingsStore.setComfyNegativeNodeId(v),
})
const comfyNegativeInputKey = computed({
  get: () => settingsStore.comfyNegativeInputKey,
  set: (v: string) => settingsStore.setComfyNegativeInputKey(v),
})
const comfyKsamplerNodeId = computed({
  get: () => settingsStore.comfyKsamplerNodeId,
  set: (v: string) => settingsStore.setComfyKsamplerNodeId(v),
})
const contentStats = ref({ terms: 0, examples: 0, docs: 0 })
const authStore = useAuthStore()
const licenseStore = useMedcommLicenseStore()

const portalEmail = ref('')
const portalEmailInput = ref('')
const portalPasswordInput = ref('')
const portalLoginLoading = ref(false)
const portalLoginError = ref('')
const isElectronEnv = typeof window !== 'undefined' && !!window.electronAPI?.isElectron
const appVersion = ref('0.0.0')
if (isElectronEnv && window.electronAPI?.getAppVersion) {
  window.electronAPI.getAppVersion().then((v: string) => { appVersion.value = v }).catch(() => {})
}

// MedPic 硬件档位
const TIER_STORAGE_KEY = 'medpic_hardware_tier'
const medpicTier = ref<string | null>(null)
const comfyBundleVersion = ref<string | null>(null)

const tierDescMap: Record<string, string> = {
  low: 'SD 1.5 · 基础画质',
  standard: 'SDXL · 良好画质',
  high: 'SDXL / Flux · 优秀画质',
}
const medpicTierDesc = computed(() => tierDescMap[medpicTier.value || ''] || '')

try {
  const saved = localStorage.getItem(TIER_STORAGE_KEY)
  if (saved) medpicTier.value = saved
} catch { /* noop */ }

function saveMedpicTier(v: string) {
  medpicTier.value = v
  try { localStorage.setItem(TIER_STORAGE_KEY, v) } catch { /* noop */ }
}

if (isElectronEnv && window.electronAPI?.getComfyUIBundleInfo) {
  window.electronAPI.getComfyUIBundleInfo().then((info: any) => {
    if (info?.version) comfyBundleVersion.value = info.version
  }).catch(() => {})
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
interface DrawingPackItem extends PackItem {
  description?: string
  category?: string
}
const packList = ref<PackItem[]>([])
const drawingPackList = ref<DrawingPackItem[]>([])
const packLoading = ref(false)
const downloadingPack = ref<DownloadProgress | null>(null)

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

async function portalLogin() {
  const email = portalEmailInput.value.trim()
  const pwd = portalPasswordInput.value
  if (!email || !pwd) {
    portalLoginError.value = '请输入邮箱和密码'
    return
  }
  portalLoginLoading.value = true
  portalLoginError.value = ''
  try {
    const eApi = window.electronAPI
    if (!eApi?.portalLogin) {
      portalLoginError.value = '当前环境不支持门户登录'
      return
    }
    const res = await eApi.portalLogin(email, pwd)
    if (res.ok) {
      portalEmail.value = res.email || email
      portalPasswordInput.value = ''
      ElMessage.success(`已绑定门户账号：${portalEmail.value}`)
    } else {
      portalLoginError.value = res.error || '登录失败'
    }
  } catch (e: any) {
    portalLoginError.value = e?.message || '网络错误'
  } finally {
    portalLoginLoading.value = false
  }
}

function openMedcommSite() {
  window.electronAPI?.openExternal?.('https://medcomm.linscio.com.cn')
}

function openContact() {
  window.electronAPI?.openExternal?.('https://medcomm.linscio.com.cn/contact')
}

async function goPortal() {
  const eApi = window.electronAPI
  if (!eApi?.getPortalActivateUrl || !eApi?.openExternal) return
  const url = await eApi.getPortalActivateUrl()
  if (url) await eApi.openExternal(url)
}

async function deactivateLicense() {
  try {
    await ElMessageBox.confirm(
      '将清除本机授权信息，需要重新激活才能恢复。确认解除？',
      '解除授权绑定',
      { confirmButtonText: '解除', cancelButtonText: '取消', type: 'warning' }
    )
    const eApi = window.electronAPI
    if (!eApi?.deactivateLicense) return
    const res = await eApi.deactivateLicense()
    if (res?.ok) {
      licenseStore.$reset()
      ElMessage.success('已解除授权，请重新激活')
    } else {
      ElMessage.error(res?.error || '解除失败')
    }
  } catch {
    // 用户取消
  }
}

async function loadPackStatus() {
  const eApi = window.electronAPI
  if (!eApi?.getPackStatus) return
  packLoading.value = true
  try {
    const list: any[] = (await eApi.getPackStatus()) || []

    const specialtyItems: PackItem[] = []
    const drawingItems: DrawingPackItem[] = []

    for (const item of list) {
      const isDrawing = item.category === 'drawing' || (item.specialty_id || '').startsWith('medpic-')
      if (isDrawing) {
        drawingItems.push(item)
      } else {
        specialtyItems.push(item)
      }
    }

    packList.value = specialtyItems
    drawingPackList.value = drawingItems

    for (const sp of licenseStore.specialties) {
      const isDrawing = sp.id.startsWith('medpic-')
      const targetList = isDrawing ? drawingPackList.value : packList.value
      if (!targetList.find(p => p.specialty_id === sp.id)) {
        targetList.push({
          specialty_id: sp.id,
          name: sp.name,
          local_version: sp.local_version,
          remote_version: sp.remote_version,
          status: sp.local_version ? 'installed' : 'not_installed',
          knowledge_docs: 0, terms: 0, examples: 0,
        })
      } else {
        const existing = targetList.find(p => p.specialty_id === sp.id)!
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

async function installPack(pack: PackItem) {
  const eApi = window.electronAPI
  if (!eApi?.downloadSpecialty) {
    ElMessage.error('当前环境不支持学科包安装')
    return
  }
  downloadingPack.value = {
    specialty_id: pack.specialty_id, name: pack.name,
    percent: 0, status: 'requesting', detail: '准备中...',
  }
  try {
    const version = pack.remote_version || pack.local_version || '1.0.0'
    const fromVersion = pack.status === 'update_available' ? (pack.local_version || undefined) : undefined
    const res = await eApi.downloadSpecialty(pack.specialty_id, pack.name, version, fromVersion)
    if (res?.ok) {
      ElMessage.success(`${pack.name || pack.specialty_id} 安装完成`)
      await loadPackStatus()
    } else {
      ElMessage.error(res?.error || '安装失败')
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '安装失败')
  }
}

function goPortalSpecialties() {
  window.electronAPI?.openExternal?.('https://portal.linscio.com.cn/medcomm/specialties')
}

async function importLocalPack() {
  const eApi = window.electronAPI
  if (!eApi?.importLocalPack) {
    ElMessage.info('当前环境不支持本地导入')
    return
  }
  try {
    const res = await eApi.importLocalPack()
    if (res?.ok) {
      ElMessage.success('扩展包导入成功')
      await loadPackStatus()
    } else if (res?.error !== 'cancelled') {
      ElMessage.error(res?.error || '导入失败')
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '导入失败')
  }
}

const openaiKey = ref('')
const dashscopeKey = ref('')
const siliconflowKey = ref('')
const deepseekKey = ref('')
const zhipuKey = ref('')
const moonshotKey = ref('')
const baiduKey = ref('')
const baiduSecretKey = ref('')
const openrouterKey = ref('')
const qiniuMaasKey = ref('')
const anthropicKey = ref('')
const pollinationsKey = ref('')
const comfyCloudKey = ref('')
const deeplKey = ref('')
const googleTranslateKey = ref('')
const azureTranslateKey = ref('')
const azureTranslateRegion = ref('')
const llmModels = ref<Array<{ id: string; name: string; provider: string }>>([])
const selectedDefaultModel = ref(settingsStore.defaultModel)
const selectedLlmProvider = ref('openai')
const selectedImageProvider = ref(settingsStore.preferredImageProvider)
const siliconflowImageModel = ref(settingsStore.siliconflowImageModel)
const llmProviders = computed(() => Array.from(new Set(llmModels.value.map((m) => m.provider))))
const filteredModelsByProvider = computed(() =>
  llmModels.value.filter((m) => m.provider === selectedLlmProvider.value)
)
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

function buildLocalModels() {
  const local: Array<{ id: string; name: string; provider: string }> = []
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
      { id: 'claude-3-5-sonnet-20241022', name: 'Claude 3.5 Sonnet', provider: 'anthropic' },
      { id: 'claude-3-5-haiku-20241022', name: 'Claude 3.5 Haiku', provider: 'anthropic' }
    )
  }
  if (openrouterKey.value) {
    local.push(
      { id: 'openrouter/openai/gpt-4o-mini', name: 'openai/gpt-4o-mini', provider: 'openrouter' },
      { id: 'openrouter/openai/gpt-4o', name: 'openai/gpt-4o', provider: 'openrouter' },
      { id: 'openrouter/anthropic/claude-3.5-sonnet', name: 'anthropic/claude-3.5-sonnet', provider: 'openrouter' },
      { id: 'openrouter/anthropic/claude-3.7-sonnet', name: 'anthropic/claude-3.7-sonnet', provider: 'openrouter' },
      { id: 'openrouter/anthropic/claude-3.7-sonnet:thinking', name: 'anthropic/claude-3.7-sonnet:thinking', provider: 'openrouter' },
      { id: 'openrouter/anthropic/claude-3.5-haiku', name: 'anthropic/claude-3.5-haiku', provider: 'openrouter' },
      { id: 'openrouter/google/gemini-2.0-flash-001', name: 'google/gemini-2.0-flash-001', provider: 'openrouter' },
      { id: 'openrouter/google/gemini-2.5-flash', name: 'google/gemini-2.5-flash', provider: 'openrouter' },
      { id: 'openrouter/google/gemini-2.5-pro', name: 'google/gemini-2.5-pro', provider: 'openrouter' },
      { id: 'openrouter/google/gemini-1.5-pro', name: 'google/gemini-1.5-pro', provider: 'openrouter' },
      { id: 'openrouter/google/gemini-1.5-flash', name: 'google/gemini-1.5-flash', provider: 'openrouter' },
      { id: 'openrouter/meta-llama/llama-3.1-70b-instruct', name: 'meta-llama/llama-3.1-70b-instruct', provider: 'openrouter' },
      { id: 'openrouter/meta-llama/llama-3.1-405b-instruct', name: 'meta-llama/llama-3.1-405b-instruct', provider: 'openrouter' },
      { id: 'openrouter/deepseek/deepseek-r1', name: 'deepseek/deepseek-r1', provider: 'openrouter' },
      { id: 'openrouter/deepseek/deepseek-v3', name: 'deepseek/deepseek-v3', provider: 'openrouter' }
    )
  }
  if (siliconflowKey.value) {
    local.push(
      { id: 'Qwen/Qwen2.5-7B-Instruct', name: 'Qwen2.5-7B-Instruct', provider: 'siliconflow' },
      { id: 'Qwen/Qwen2.5-32B-Instruct', name: 'Qwen2.5-32B-Instruct', provider: 'siliconflow' },
      { id: 'Qwen/Qwen2.5-72B-Instruct', name: 'Qwen2.5-72B-Instruct', provider: 'siliconflow' },
      { id: 'deepseek-ai/DeepSeek-V2.5', name: 'DeepSeek-V2.5', provider: 'siliconflow' },
      { id: 'deepseek-ai/DeepSeek-V3', name: 'DeepSeek-V3', provider: 'siliconflow' },
      { id: 'deepseek-ai/DeepSeek-R1', name: 'DeepSeek-R1', provider: 'siliconflow' },
      { id: 'THUDM/glm-4-9b-chat', name: 'GLM-4-9B-Chat', provider: 'siliconflow' },
      { id: 'THUDM/glm-4-plus', name: 'GLM-4-Plus', provider: 'siliconflow' }
    )
  }
  if (deepseekKey.value) {
    local.push(
      { id: 'deepseek-chat', name: 'DeepSeek Chat', provider: 'deepseek' },
      { id: 'deepseek-coder', name: 'DeepSeek Coder', provider: 'deepseek' },
      { id: 'deepseek-reasoner', name: 'DeepSeek Reasoner', provider: 'deepseek' }
    )
  }
  if (zhipuKey.value) {
    local.push(
      { id: 'glm-4', name: 'GLM-4', provider: 'zhipu' },
      { id: 'glm-4-flash', name: 'GLM-4-Flash', provider: 'zhipu' },
      { id: 'glm-4-plus', name: 'GLM-4-Plus', provider: 'zhipu' },
      { id: 'glm-4-air', name: 'GLM-4-Air', provider: 'zhipu' },
      { id: 'glm-3-turbo', name: 'GLM-3-Turbo', provider: 'zhipu' }
    )
  }
  if (moonshotKey.value) {
    local.push(
      { id: 'moonshot-v1-8k', name: 'Moonshot v1 8k', provider: 'moonshot' },
      { id: 'moonshot-v1-32k', name: 'Moonshot v1 32k', provider: 'moonshot' },
      { id: 'moonshot-v1-128k', name: 'Moonshot v1 128k', provider: 'moonshot' }
    )
  }
  if (dashscopeKey.value) {
    local.push(
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
  return local
}

onMounted(async () => {
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
  window.electronAPI?.onNewSpecialtiesAvailable?.(async (payload) => {
    await loadPackStatus()
    const newIds = payload.ids || []
    if (newIds.length > 0) {
      const names = newIds.join('、')
      try {
        await ElMessageBox.confirm(
          `您已购买新学科包：${names}，是否立即安装？`,
          '新学科包可用',
          { confirmButtonText: '立即安装', cancelButtonText: '稍后', type: 'info' }
        )
        for (const id of newIds) {
          const pack = packList.value.find(p => p.specialty_id === id)
          if (pack && pack.status !== 'installed') {
            await installPack(pack)
          }
        }
      } catch {
        // 用户选择稍后
      }
    }
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
    const [openai, dashscope, siliconflow, deepseek, zhipu, moonshot, baidu, baiduSecret, openrouter, qiniuMaas, anthropic, pollinations, comfyCloud, deepl, googleTrans, azureTrans, azureTransRegion] = await Promise.all([
      api.getApiKey('openai'),
      api.getApiKey('dashscope'),
      api.getApiKey('siliconflow'),
      api.getApiKey('deepseek'),
      api.getApiKey('zhipu'),
      api.getApiKey('moonshot'),
      api.getApiKey('baidu'),
      api.getApiKey('baidu_secret'),
      api.getApiKey('openrouter'),
      api.getApiKey('qiniu_maas'),
      api.getApiKey('anthropic'),
      api.getApiKey('pollinations'),
      api.getApiKey('comfy_cloud'),
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
    if (baidu) baiduKey.value = baidu
    if (baiduSecret) baiduSecretKey.value = baiduSecret
    if (openrouter) openrouterKey.value = openrouter
    if (qiniuMaas) qiniuMaasKey.value = qiniuMaas
    if (anthropic) anthropicKey.value = anthropic
    if (pollinations) pollinationsKey.value = pollinations
    if (comfyCloud) comfyCloudKey.value = comfyCloud
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
  // 兼容旧版本遗留值：default 不是实际模型 ID
  if (selectedDefaultModel.value === 'default') {
    const preferred =
      llmModels.value.find((m) => m.provider === 'openrouter') ||
      llmModels.value.find((m) => m.provider === 'openai') ||
      llmModels.value[0]
    if (preferred?.id) {
      selectedDefaultModel.value = preferred.id
      settingsStore.setDefaultModel(preferred.id)
    }
  }
  if (!llmModels.value.some((m) => m.id === selectedDefaultModel.value)) {
    const fallback =
      llmModels.value.find((m) => m.provider === 'openrouter') ||
      llmModels.value.find((m) => m.provider === 'openai') ||
      llmModels.value[0]
    if (fallback?.id) {
      selectedDefaultModel.value = fallback.id
      settingsStore.setDefaultModel(fallback.id)
    } else {
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

async function loginLocalUser() {
  try {
    const { value } = await ElMessageBox.prompt('请输入用户名（本地数据隔离用）', '登录本地用户', {
      confirmButtonText: '登录',
      cancelButtonText: '取消',
      inputPlaceholder: '例如：张三',
    })
    const name = String(value || '').trim()
    if (!name) return
    await authStore.switchUser(name)
    ElMessage.success(`已登录为：${authStore.user?.display_name || name}`)
    router.push('/').catch(() => {})
  } catch (e: any) {
    if (e === 'cancel' || e === 'close') return
    ElMessage.error('登录失败')
  }
}

async function switchUser() {
  try {
    const { value } = await ElMessageBox.prompt('输入用户名（用于区分不同用户配置）', '切换用户', {
      confirmButtonText: '登录/切换',
      cancelButtonText: '取消',
      inputPlaceholder: '例如：张三',
    })
    const name = String(value || '').trim()
    if (!name) return
    await authStore.switchUser(name)
    ElMessage.success(`已切换为：${authStore.user?.display_name || name}`)
    router.push('/').catch(() => {})
  } catch (e: any) {
    if (e === 'cancel' || e === 'close') return
    ElMessage.error('切换失败')
  }
}

async function logout() {
  try {
    await ElMessageBox.confirm('将清空本地会话 token，下次请求会重新登录。', '退出登录', {
      confirmButtonText: '退出',
      cancelButtonText: '取消',
      type: 'warning',
    })
    authStore.logout()
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
watch(selectedImageProvider, (v) => {
  settingsStore.setPreferredImageProvider(v)
})
watch(siliconflowImageModel, (v) => {
  settingsStore.setSiliconflowImageModel(v)
})
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
      { account: 'dashscope', label: '通义万相 API Key', value: dashscopeKey.value.trim() },
      { account: 'siliconflow', label: '硅基流动 API Key', value: siliconflowKey.value.trim() },
      { account: 'deepseek', label: 'DeepSeek API Key', value: deepseekKey.value.trim() },
      { account: 'zhipu', label: '智谱 API Key', value: zhipuKey.value.trim() },
      { account: 'moonshot', label: 'Moonshot API Key', value: moonshotKey.value.trim() },
      { account: 'baidu', label: '文心图像 API Key', value: baiduKey.value.trim() },
      { account: 'baidu_secret', label: '文心图像 Secret Key', value: baiduSecretKey.value.trim() },
      { account: 'openrouter', label: 'OpenRouter API Key', value: openrouterKey.value.trim() },
      { account: 'qiniu_maas', label: '七牛 MaaS API Key', value: qiniuMaasKey.value.trim() },
      { account: 'anthropic', label: 'Anthropic API Key', value: anthropicKey.value.trim() },
      { account: 'pollinations', label: 'Pollinations API Key', value: pollinationsKey.value.trim() },
      { account: 'comfy_cloud', label: 'Comfy Cloud API Key', value: comfyCloudKey.value.trim() },
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
.model-hint { margin-left: 0.75rem; color: #6b7280; font-size: 0.85rem; }
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
.image-provider-field { max-width: 100%; }
.image-provider-hint {
  margin: 0.35rem 0 0;
  max-width: 520px;
  font-size: 0.8rem;
  color: #6b7280;
  line-height: 1.45;
}
.image-provider-hint code {
  font-size: 0.78rem;
  padding: 0.1em 0.35em;
  background: #f3f4f6;
  border-radius: 4px;
}
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
</style>

<!-- 下拉挂载在 body，需非 scoped 样式 -->
<style>
.medcomm-image-provider-dropdown {
  min-width: 400px !important;
  max-width: min(96vw, 560px);
  max-height: min(70vh, 520px) !important;
}
.medcomm-image-provider-dropdown .el-select-dropdown__item {
  white-space: normal;
  line-height: 1.35;
  min-height: 36px;
  height: auto;
  padding-top: 8px;
  padding-bottom: 8px;
  align-items: flex-start;
}
</style>
