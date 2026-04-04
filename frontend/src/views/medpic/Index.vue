<template>
  <div class="medpic" :class="{ 'medpic--fullscreen': step === 'comfyui' }">
    <div v-if="step !== 'comfyui'" class="medpic-header">
      <h2>MedPic 医学绘图</h2>
      <p class="subtitle">选择场景，填写内容，一键生成专业医学科普图像</p>
    </div>

    <!-- 首次使用：硬件档位选择 -->
    <div v-if="!hardwareTier" class="tier-select">
      <h3>请选择您的电脑配置</h3>
      <p class="tier-hint">
        这将帮助系统匹配最佳画质与速度，后续可在高级参数中修改。
        <a class="tier-help-link" href="javascript:void(0)" @click="showConfigHelp = true">如何查看我的配置？</a>
      </p>
      <div class="tier-grid">
        <div
          v-for="tier in tierOptions"
          :key="tier.id"
          class="tier-card"
          @click="selectTier(tier.id)"
        >
          <div class="tier-icon">{{ tier.icon }}</div>
          <div class="tier-name">{{ tier.name }}</div>
          <div class="tier-desc">{{ tier.description }}</div>
          <div class="tier-spec">{{ tier.spec }}</div>
        </div>
      </div>
    </div>

    <!-- 场景选择 -->
    <div v-else-if="!selectedScene && !directComfyMode" class="scene-select-page">
      <!-- 直接打开 ComfyUI 编辑器入口 -->
      <div v-if="comfyStatus.running || comfyStatus.available" class="comfy-quick-launch" @click="enterDirectComfyMode">
        <div class="comfy-quick-launch-icon">&#x1F3A8;</div>
        <div class="comfy-quick-launch-body">
          <div class="comfy-quick-launch-title">直接打开 ComfyUI 工作流编辑器</div>
          <div class="comfy-quick-launch-desc">
            跳过场景选择，直接进入 ComfyUI 可视化编辑器，自由搭建或编辑工作流
          </div>
          <el-tag v-if="comfyStatus.running" size="small" type="success">已就绪</el-tag>
          <el-tag v-else size="small" type="warning">启动中...</el-tag>
        </div>
        <div class="comfy-quick-launch-arrow">&#x2192;</div>
      </div>

      <h3 v-if="scenes.length" class="scene-section-title">或选择预设场景</h3>

      <div class="scene-grid">
        <div
          v-for="scene in scenes"
          :key="scene.id"
          class="scene-card"
          @click="selectScene(scene)"
        >
          <div class="scene-icon">{{ scene.icon }}</div>
          <div class="scene-info">
            <div class="scene-name">{{ scene.name }}</div>
            <div class="scene-desc">{{ scene.description }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 工作流变体选择 -->
    <div v-else-if="selectedScene && !selectedVariant && !directComfyMode" class="variant-select">
      <div class="variant-header">
        <el-button text @click="selectedScene = null">← 返回场景选择</el-button>
        <span class="current-scene">{{ selectedScene.icon }} {{ selectedScene.name }}</span>
        <el-tag size="small" type="info" style="margin-left:auto;">{{ tierLabel }}</el-tag>
      </div>
      <h3 class="variant-title">选择工作流类型</h3>
      <p class="variant-hint">不同工作流针对不同用途预设了最优的风格、画幅与构图策略</p>
      <div v-if="variantsLoading" class="variant-loading">
        <el-icon class="is-loading"><i class="el-icon-loading" /></el-icon> 加载中...
      </div>
      <div v-else class="variant-grid">
        <div
          v-for="v in sceneVariants"
          :key="v.id"
          class="variant-card"
          :class="{ disabled: !v.available }"
          @click="v.available && pickVariant(v)"
        >
          <div class="variant-id">{{ v.id }}</div>
          <div class="variant-name">{{ v.name }}</div>
          <div class="variant-desc">{{ v.description }}</div>
          <div class="variant-meta">
            <el-tag v-for="a in v.aspects" :key="a" size="small" type="info" style="margin-right:4px;">{{ a }}</el-tag>
            <el-tag v-if="v.special" size="small" type="warning" style="margin-left:4px;">{{ specialLabel(v.special) }}</el-tag>
          </div>
          <div v-if="!v.available" class="variant-unavailable">
            当前硬件档位不支持
          </div>
        </div>
      </div>
    </div>

    <!-- 生成面板 -->
    <div v-else class="gen-panel">
      <div class="gen-panel-header">
        <el-button text @click="goBack">
          ← {{ directComfyMode && step === 'comfyui' ? '返回场景选择' : step === 'compose' ? '返回生成结果' : '返回工作流选择' }}
        </el-button>
        <span v-if="directComfyMode && !selectedScene" class="current-scene">&#x1F3A8; ComfyUI 工作流编辑器</span>
        <span v-else-if="selectedScene" class="current-scene">{{ selectedScene.icon }} {{ selectedScene.name }}</span>
        <el-tag v-if="selectedVariant" size="small" style="margin-left:8px;">{{ selectedVariant.id }} {{ selectedVariant.name }}</el-tag>
        <el-tag size="small" type="info" style="margin-left:auto;">{{ tierLabel }}</el-tag>
        <el-tag v-if="comfyStatus.running" size="small" type="success" style="margin-left:4px;">ComfyUI</el-tag>
        <el-tag v-else-if="comfyStatus.available" size="small" type="warning" style="margin-left:4px;">ComfyUI 未就绪</el-tag>
      </div>

      <!-- ComfyUI 工作流编辑器（主模式） -->
      <template v-if="step === 'comfyui'">
        <div class="comfyui-workspace">
          <!-- 智能参数面板 -->
          <div class="comfy-sidebar">
            <el-form label-position="top" size="small">
              <!-- AI 提示词生成 -->
              <div class="sidebar-section">
                <h4 class="sidebar-title">AI 智能提示词</h4>
                <el-form-item label="科室">
                  <el-select v-model="form.specialty" filterable placeholder="选择科室" style="width:100%;" clearable>
                    <el-option v-for="s in specialties" :key="s" :label="s" :value="s" />
                  </el-select>
                </el-form-item>
                <el-form-item label="图像描述" required>
                  <el-input
                    v-model="aiDescription"
                    type="textarea"
                    :rows="3"
                    placeholder="用中文或英文描述想要的图像内容，如：糖尿病患者的健康饮食指南插图"
                  />
                </el-form-item>
                <el-button
                  type="primary"
                  size="small"
                  :loading="aiGenerating"
                  :disabled="!aiDescription.trim()"
                  @click="generateAIPrompt"
                  style="width:100%;"
                >
                  {{ aiPositive ? '重新生成提示词' : '生成提示词' }}
                </el-button>
              </div>

              <!-- 可编辑提示词 -->
              <div v-if="aiPositive || aiNegative" class="sidebar-section">
                <h4 class="sidebar-title">
                  提示词
                  <span v-if="aiExplanation" class="ai-explanation">{{ aiExplanation }}</span>
                </h4>
                <el-form-item label="正向提示词 (Positive)">
                  <el-input v-model="aiPositive" type="textarea" :rows="4" />
                </el-form-item>
                <el-form-item label="反向提示词 (Negative)">
                  <el-input v-model="aiNegative" type="textarea" :rows="3" />
                </el-form-item>

                <!-- 快捷优化按钮 -->
                <div class="refine-shortcuts">
                  <el-button v-for="r in refineShortcuts" :key="r.label" size="small" :loading="aiRefining" @click="quickRefine(r.instruction)" round>
                    {{ r.label }}
                  </el-button>
                </div>

                <!-- 自定义优化 -->
                <div class="refine-custom">
                  <el-input v-model="refineInput" size="small" placeholder="输入调整需求，如：加入听诊器元素" @keyup.enter="customRefine">
                    <template #append>
                      <el-button :loading="aiRefining" @click="customRefine">优化</el-button>
                    </template>
                  </el-input>
                </div>
              </div>

              <!-- 推荐参数 -->
              <div v-if="aiPositive" class="sidebar-section">
                <h4 class="sidebar-title">参数配置</h4>
                <el-form-item v-if="directComfyMode" label="场景">
                  <el-select v-model="directScene" style="width:100%;" clearable>
                    <el-option v-for="s in scenes" :key="s.id" :label="s.name" :value="s.id" />
                  </el-select>
                </el-form-item>
                <el-form-item label="风格">
                  <el-select v-model="form.style" style="width:100%;">
                    <el-option label="医学插画" value="medical_illustration" />
                    <el-option label="扁平设计" value="flat_design" />
                    <el-option label="3D 渲染" value="3d_render" />
                    <el-option label="漫画" value="comic" />
                    <el-option label="绘本风" value="picture_book" />
                  </el-select>
                </el-form-item>
                <el-form-item label="画幅">
                  <el-select v-model="form.aspectKey" style="width:100%;">
                    <el-option label="1:1 方形" value="1:1" />
                    <el-option label="4:3 横版" value="4:3" />
                    <el-option label="3:4 竖版" value="3:4" />
                    <el-option label="16:9 宽屏" value="16:9" />
                    <el-option label="9:16 竖屏" value="9:16" />
                  </el-select>
                </el-form-item>
                <el-form-item label="受众">
                  <el-select v-model="form.targetAudience" style="width:100%;">
                    <el-option label="患者及家属" value="public" />
                    <el-option label="医护人员" value="professional" />
                    <el-option label="儿童" value="children" />
                  </el-select>
                </el-form-item>
              </div>

              <!-- 执行按钮 -->
              <div v-if="aiPositive" class="sidebar-section">
                <el-button
                  v-if="comfyStatus.running"
                  size="small"
                  :loading="comfyInjecting"
                  :disabled="!aiPositive.trim()"
                  @click="injectParamsToComfy"
                  style="width:100%;"
                >
                  同步参数到工作流
                </el-button>
                <el-button
                  v-if="comfyStatus.running"
                  type="primary"
                  size="small"
                  :loading="comfyQueueing"
                  :disabled="!aiPositive.trim()"
                  style="width:100%;margin-top:8px;margin-left:0;"
                  @click="queuePromptInComfy"
                >
                  执行生成
                </el-button>
                <div v-if="pendingComfyPrompt" class="sync-status">
                  <span class="sync-ok">参数已就绪</span>
                  <span v-if="lastSyncInfo" class="sync-detail">{{ lastSyncInfo }}</span>
                </div>
              </div>
            </el-form>

            <!-- 生成结果 -->
            <div v-if="comfyListening || results.length" class="sidebar-section comfy-result-section">
              <h4 class="sidebar-title">生成结果</h4>
              <div v-if="comfyListening" class="comfy-listening">
                <el-icon class="is-loading"><i class="el-icon-loading" /></el-icon>
                监听中...
              </div>
              <div v-if="results.length" class="comfy-results-mini">
                <div v-for="(img, idx) in results" :key="idx" class="comfy-result-thumb" @click="enterCompose(idx)">
                  <img :src="img.serveUrl" />
                </div>
                <el-button size="small" type="primary" @click="enterCompose(0)" style="width:100%;margin-top:8px;">
                  下一步：排版叠字
                </el-button>
              </div>
            </div>
          </div>

          <!-- ComfyUI WebView -->
          <div class="comfy-main">
            <div v-if="!comfyStatus.running" class="comfy-not-ready">
              <div class="comfy-not-ready-icon">&#x26A0;</div>
              <h3>ComfyUI 未就绪</h3>
              <p v-if="comfyStatus.available">ComfyUI 正在启动中，请稍候...</p>
              <p v-else>未检测到 ComfyUI 安装。请配置 ComfyUI 路径或安装 ComfyUI。</p>
              <el-button v-if="comfyStatus.available" :loading="comfyPolling" @click="pollComfyReady">
                重新检测
              </el-button>
              <el-button v-else @click="step = 'generate'">
                使用内置生成模式
              </el-button>
            </div>
            <iframe
              v-else
              ref="comfyWebviewRef"
              :src="comfyUrl"
              class="comfy-webview"
              @load="onComfyWebviewReady"
            />
          </div>
        </div>
      </template>

      <!-- 内置生成模式（ComfyUI 不可用时的降级） -->
      <template v-if="step === 'generate'">
        <el-form label-position="top" class="gen-form">
          <el-form-item label="科室/专科" required>
            <el-select v-model="form.specialty" filterable placeholder="选择科室（必填）" style="width:100%;">
              <el-option v-for="s in specialties" :key="s" :label="s" :value="s" />
            </el-select>
          </el-form-item>

          <el-form-item label="图像主题" required>
            <el-input
              v-model="form.topic"
              placeholder="例如：高血压的危害、儿童疫苗接种流程、糖尿病饮食管理"
            />
          </el-form-item>

          <el-form-item label="目标受众">
            <el-radio-group v-model="form.targetAudience">
              <el-radio value="public">患者及家属</el-radio>
              <el-radio value="professional">医护人员</el-radio>
              <el-radio value="children">儿童</el-radio>
            </el-radio-group>
          </el-form-item>

          <!-- 角色一致性（B-2 / E-1/2/3） -->
          <div v-if="isCharacterConsistency" class="special-section">
            <el-form-item label="角色参考图">
              <div class="ref-image-area">
                <div v-if="referenceImage" class="ref-preview">
                  <img :src="referenceImage.serve_url" class="ref-img" />
                  <el-button size="small" text type="danger" @click="referenceImage = null; selectedPresetId = ''">移除</el-button>
                </div>
                <div v-else class="ref-upload">
                  <div v-if="presetCharacters.length" class="preset-characters">
                    <span class="preset-label">预置角色：</span>
                    <div class="preset-grid">
                      <div
                        v-for="pc in presetCharacters"
                        :key="pc.id"
                        class="preset-char-card"
                        @click="selectPresetCharacter(pc)"
                      >
                        <img :src="pc.thumbnail_url" :alt="pc.name" class="preset-char-img" />
                        <span class="preset-char-name">{{ pc.name }}</span>
                      </div>
                    </div>
                  </div>
                  <el-divider v-if="presetCharacters.length" content-position="center">或</el-divider>
                  <el-upload
                    :auto-upload="false"
                    accept="image/*"
                    :show-file-list="false"
                    @change="handleRefUpload"
                  >
                    <el-button size="small">上传自定义角色图</el-button>
                  </el-upload>
                  <span class="field-hint">
                    {{ selectedVariant?.special === 'character_consistency'
                      ? 'IP-Adapter 将保持各格角色一致（一致性约 70–80%）'
                      : '可选：上传角色图保持绘本全书角色一致' }}
                  </span>
                </div>
              </div>
            </el-form-item>
            <el-form-item v-if="referenceImage" label="角色一致性强度">
              <el-slider
                v-model="ipadapterWeight"
                :min="0.3"
                :max="0.9"
                :step="0.05"
                :format-tooltip="(v: number) => v.toFixed(2)"
                style="width:240px;"
              />
              <span class="field-hint">
                {{ ipadapterWeight >= 0.7 ? '高一致性（角色更像参考图，构图自由度低）' :
                   ipadapterWeight >= 0.5 ? '中一致性（推荐，平衡角色相似与构图自由）' :
                   '低一致性（保留角色特征但构图更自由）' }}
              </span>
            </el-form-item>
          </div>

          <!-- F-* 分段生成 -->
          <div v-if="isSegmented" class="special-section">
            <el-form-item label="段落数量">
              <el-input-number v-model="segmentCount" :min="2" :max="8" />
              <span class="field-hint">每段生成一张 1024x1024 图像，最终竖向拼接</span>
            </el-form-item>
          </div>

          <div class="gen-actions">
            <el-button
              type="primary"
              size="large"
              :loading="generating"
              :disabled="!form.topic.trim() || !form.specialty"
              @click="isSegmented ? generateSegmented() : generate()"
            >
              {{ isSegmented ? `生成 ${segmentCount} 段长图` : '生成底图' }}
            </el-button>
            <el-button
              v-if="comfyStatus.running"
              size="large"
              @click="step = 'comfyui'"
            >
              切换到 ComfyUI 编辑器
            </el-button>
          </div>

          <!-- 高级参数 -->
          <el-collapse v-model="advancedOpen" class="advanced-collapse">
            <el-collapse-item name="advanced" title="高级参数（可选）">
              <el-form-item label="画面主体描述">
                <el-input
                  v-model="form.subject"
                  placeholder="例如：一位老年男性，手握血压计（留空则由系统自动构图）"
                />
              </el-form-item>
              <div class="form-row">
                <el-form-item label="图像风格" class="form-item-half">
                  <el-select v-model="form.style">
                    <el-option label="写实插画（默认）" value="medical_illustration" />
                    <el-option label="扁平设计" value="flat_design" />
                    <el-option label="3D 渲染" value="3d_render" />
                    <el-option label="卡通" value="comic" />
                    <el-option label="绘本风" value="picture_book" />
                  </el-select>
                </el-form-item>
                <el-form-item label="色调偏好" class="form-item-half">
                  <el-select v-model="form.colorTone">
                    <el-option label="中性色（默认）" value="neutral" />
                    <el-option label="暖色系" value="warm" />
                    <el-option label="冷色系" value="cool" />
                  </el-select>
                </el-form-item>
              </div>
              <div class="form-row">
                <el-form-item label="画幅" class="form-item-half">
                  <el-select v-model="form.aspectKey">
                    <el-option
                      v-for="a in currentAspectPresets"
                      :key="a.key"
                      :label="a.label"
                      :value="a.key"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="生成张数" class="form-item-half">
                  <el-input-number v-model="form.batchCount" :min="1" :max="4" />
                </el-form-item>
              </div>
              <div class="form-row">
                <el-form-item label="出图种子" class="form-item-half">
                  <el-radio-group v-model="form.seedMode" size="small" style="margin-bottom:6px;">
                    <el-radio-button value="recommended">推荐种子</el-radio-button>
                    <el-radio-button value="random">随机探索</el-radio-button>
                    <el-radio-button value="custom">手动输入</el-radio-button>
                  </el-radio-group>
                  <el-input-number
                    v-if="form.seedMode === 'custom'"
                    v-model="form.seed"
                    :min="0"
                    controls-position="right"
                    style="width:100%;"
                    placeholder="输入种子值"
                  />
                  <span v-if="form.seedMode === 'recommended'" class="field-hint">
                    使用 LinScio 调优种子库，保证稳定出图质量
                  </span>
                  <span v-else-if="form.seedMode === 'random'" class="field-hint">
                    每次生成使用随机种子，探索更多可能性
                  </span>
                </el-form-item>
                <el-form-item label="硬件档位" class="form-item-half">
                  <el-select v-model="hardwareTier">
                    <el-option v-for="t in tierOptions" :key="t.id" :label="t.name" :value="t.id" />
                  </el-select>
                </el-form-item>
              </div>
              <el-form-item label="附加要求">
                <el-input
                  v-model="form.extraPrompt"
                  type="textarea"
                  :rows="2"
                  placeholder="自由描述额外要求（留空即可）"
                />
              </el-form-item>

              <!-- §8.2 LoRA 权重调节 -->
              <el-form-item v-if="availableLoras.length" label="LoRA 风格增强">
                <div class="lora-controls">
                  <div v-for="lora in availableLoras" :key="lora.id" class="lora-item">
                    <el-checkbox
                      :model-value="isLoraEnabled(lora.id)"
                      @change="(val: boolean) => toggleLora(lora.id, val)"
                    >
                      {{ lora.name }}
                      <span class="lora-category-tag">{{ loraCategoryLabel(lora.category) }}</span>
                    </el-checkbox>
                    <el-slider
                      v-if="isLoraEnabled(lora.id)"
                      :model-value="getLoraStrength(lora.id)"
                      :min="lora.weight_range[0]"
                      :max="lora.weight_range[1]"
                      :step="0.05"
                      :format-tooltip="(v: number) => v.toFixed(2)"
                      style="width:160px;margin-left:12px;"
                      @input="(val: number) => setLoraStrength(lora.id, val)"
                    />
                  </div>
                  <span class="field-hint">系统根据场景/风格自动推荐，可手动调节权重或关闭</span>
                </div>
              </el-form-item>
            </el-collapse-item>
          </el-collapse>
        </el-form>

        <!-- 长图拼接结果 -->
        <div v-if="isSegmented && segmentResults.length" class="results">
          <h3>段落生成结果</h3>
          <div class="result-grid">
            <div v-for="(img, idx) in segmentResults" :key="idx" class="result-item">
              <img :src="img.serveUrl" :alt="`段落 ${idx + 1}`" />
              <div class="result-label">段落 {{ idx + 1 }}</div>
            </div>
          </div>
          <div class="gen-actions" style="margin-top:1rem;">
            <el-button type="primary" :loading="stitching" @click="doStitch">
              拼接为长图
            </el-button>
          </div>
          <div v-if="stitchedResult" class="stitch-result">
            <h4>拼接完成</h4>
            <img :src="stitchedResult.stitched_url" class="stitched-preview" />
            <div class="gen-actions" style="margin-top:0.75rem;">
              <el-button type="primary" @click="downloadImage(stitchedResult.stitched_url, 0)">
                下载长图
              </el-button>
              <el-button v-if="stitchedResult.slices.length > 1" @click="downloadSlices">
                下载微信切片（{{ stitchedResult.slices.length }} 张）
              </el-button>
            </div>
          </div>
        </div>

        <!-- LoRA 使用信息 -->
        <div v-if="lastUsedLoras.length && (results.length || segmentResults.length)" class="lora-info">
          <strong>LoRA 增强：</strong>
          <span v-for="l in lastUsedLoras" :key="l.id" class="lora-info-tag">
            {{ l.name }} ({{ l.strength.toFixed(2) }})
          </span>
        </div>

        <!-- 普通生成结果 -->
        <div v-if="!isSegmented && results.length" class="results">
          <h3>生成结果（点击选择底图进行排版）</h3>
          <div class="result-grid">
            <div
              v-for="(img, idx) in results"
              :key="idx"
              class="result-item"
              :class="{ selected: selectedResultIdx === idx }"
              @click="selectResult(idx)"
            >
              <img :src="img.serveUrl" :alt="`底图 ${idx + 1}`" />
              <div class="result-actions">
                <el-button size="small" type="primary" @click.stop="enterCompose(idx)">
                  添加文字
                </el-button>
                <el-button v-if="isHighDpi" size="small" type="warning" :loading="upscaling" @click.stop="doUpscale(idx)">
                  放大为印刷版
                </el-button>
                <el-button v-if="isCharacterConsistency" size="small" @click.stop="setAsReference(idx)">
                  设为参考角色
                </el-button>
                <el-button size="small" @click.stop="downloadImage(img.serveUrl, idx)">
                  直接下载
                </el-button>
              </div>
            </div>
          </div>

          <!-- D-2 放大结果 -->
          <div v-if="upscaleResult" class="stitch-result">
            <h4>印刷级高分辨率图（{{ upscaleResult.width }}x{{ upscaleResult.height }}，{{ upscaleResult.method }}）</h4>
            <img :src="upscaleResult.serve_url" class="stitched-preview" />
            <div class="gen-actions" style="margin-top:0.75rem;">
              <el-button type="primary" @click="downloadImage(upscaleResult.serve_url, 0)">
                下载高分辨率图
              </el-button>
            </div>
          </div>
        </div>

        <div v-if="genError" class="gen-error">
          <el-alert :title="genError" type="error" show-icon />
        </div>
      </template>

      <!-- 步骤：排版叠字 -->
      <template v-if="step === 'compose'">
        <div class="compose-panel">
          <div class="compose-layout">
            <div class="compose-preview">
              <img
                :src="composedPreviewUrl || results[selectedResultIdx]?.serveUrl"
                class="preview-img"
              />
              <div v-if="composing" class="compose-loading">
                <el-icon class="is-loading"><i class="el-icon-loading" /></el-icon>
                合成中...
              </div>
            </div>
            <div class="compose-form">
              <h3>文字排版</h3>
              <p class="compose-hint">
                填写文字内容，系统将按「{{ selectedScene.name }}」场景模板自动排版
              </p>
              <el-form label-position="top">
                <el-form-item label="标题" v-if="currentZones.includes('title')">
                  <el-input
                    v-model="composeTexts.title"
                    :placeholder="form.topic || '输入标题'"
                  />
                </el-form-item>
                <el-form-item label="副标题" v-if="currentZones.includes('subtitle')">
                  <el-input
                    v-model="composeTexts.subtitle"
                    placeholder="例如：了解疾病，守护健康"
                  />
                </el-form-item>
                <el-form-item label="正文" v-if="currentZones.includes('body')">
                  <el-input
                    v-model="composeTexts.body"
                    type="textarea"
                    :rows="3"
                    placeholder="输入正文内容"
                  />
                </el-form-item>
                <el-form-item label="落款 / 来源" v-if="currentZones.includes('footer')">
                  <el-input
                    v-model="composeTexts.footer"
                    placeholder="例如：XX医院心内科"
                  />
                </el-form-item>
              </el-form>
              <div class="compose-actions">
                <el-button
                  type="primary"
                  :loading="composing"
                  :disabled="!hasComposeText"
                  @click="doCompose"
                >
                  合成图像
                </el-button>
                <el-button @click="fillDefaultTexts">
                  填入默认文案
                </el-button>
              </div>

              <div v-if="composedPreviewUrl" class="composed-done">
                <el-alert title="合成完成" type="success" :closable="false" show-icon />
                <div class="composed-download">
                  <el-button type="primary" @click="downloadImage(composedPreviewUrl, 0)">
                    下载成品图
                  </el-button>
                </div>
              </div>

              <div v-if="composeError" class="gen-error" style="margin-top:1rem;">
                <el-alert :title="composeError" type="error" show-icon />
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- 图片预览 -->
    <el-dialog v-model="previewVisible" width="80%" :show-close="true" append-to-body>
      <img :src="previewUrl" style="width:100%;" />
    </el-dialog>

    <!-- 配置查看引导 -->
    <el-dialog v-model="showConfigHelp" title="如何查看我的电脑配置" width="520px">
      <div class="config-help">
        <h4>Windows 用户</h4>
        <ol>
          <li>右键点击「此电脑」→「属性」→ 查看内存大小</li>
          <li>按 <kbd>Win + R</kbd> 输入 <code>dxdiag</code> → 切换到「显示」选项卡 → 查看显存大小</li>
          <li>或打开「任务管理器」→「性能」→「GPU」查看专用 GPU 内存</li>
        </ol>
        <h4>Mac 用户</h4>
        <ol>
          <li>点击左上角  → 「关于本机」→ 查看「内存」（即统一内存）</li>
          <li>M1/M2/M3 系列芯片的「统一内存」即为 GPU 可用内存</li>
        </ol>
        <h4>选择建议</h4>
        <ul>
          <li><strong>8GB 内存/显存</strong> → 选择「普通办公电脑」</li>
          <li><strong>12–16GB 内存/显存</strong> → 选择「游戏本 / 主流台式机」</li>
          <li><strong>24GB 及以上</strong> → 选择「专业工作站」</li>
        </ul>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, reactive, toRaw } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/api'

// ─── 硬件档位 ───

interface TierOption {
  id: string
  icon: string
  name: string
  description: string
  spec: string
}

const tierOptions: TierOption[] = [
  {
    id: 'low', icon: '💻', name: '普通办公电脑 / 轻薄本',
    description: '集成显卡 / 8GB 显存 / 8GB 统一内存',
    spec: 'SD 1.5 · 基础画质',
  },
  {
    id: 'standard', icon: '🖥', name: '游戏本 / 主流台式机',
    description: '12–16GB 显存 / 16GB 统一内存',
    spec: 'SDXL · 良好画质',
  },
  {
    id: 'high', icon: '⚡', name: '专业工作站 / 高性能主机',
    description: '24GB+ 显存 / 24GB+ 统一内存',
    spec: 'SDXL / Flux · 优秀画质',
  },
]

const TIER_STORAGE_KEY = 'medpic_hardware_tier'
const hardwareTier = ref<string | null>(null)
const showConfigHelp = ref(false)

function selectTier(id: string) {
  hardwareTier.value = id
  try { localStorage.setItem(TIER_STORAGE_KEY, id) } catch { /* noop */ }
}

const tierLabel = computed(() => {
  const t = tierOptions.find(o => o.id === hardwareTier.value)
  return t ? t.spec : ''
})

onMounted(async () => {
  try {
    const saved = localStorage.getItem(TIER_STORAGE_KEY)
    if (saved && tierOptions.some(t => t.id === saved)) {
      hardwareTier.value = saved
    }
  } catch { /* noop */ }
  loadLoraRegistry()
  loadPresetCharacters()
  await refreshComfyStatus()
  if (comfyStatus.available && !comfyStatus.running) {
    comfyPollTimer = setInterval(async () => {
      await refreshComfyStatus()
      if (comfyStatus.running && comfyPollTimer) {
        clearInterval(comfyPollTimer)
        comfyPollTimer = null
      }
    }, 5000)
  }
})

// ─── 场景定义 ───

interface Scene {
  id: string
  icon: string
  name: string
  description: string
  defaultAspect: string
  defaultStyle: string
  zones: string[]
}

const scenes: Scene[] = [
  {
    id: 'article', icon: '📰', name: '科普文章插图',
    description: '公众号/院刊文章配图、患者教育手册插图',
    defaultAspect: '1:1', defaultStyle: 'medical_illustration',
    zones: ['title', 'subtitle'],
  },
  {
    id: 'comic', icon: '📖', name: '条漫科普',
    description: '微信公众号条漫、健康教育长图',
    defaultAspect: '1:1', defaultStyle: 'comic',
    zones: ['title', 'subtitle'],
  },
  {
    id: 'card', icon: '🃏', name: '知识卡片',
    description: '朋友圈分享、小红书、微博、科室公告栏',
    defaultAspect: '1:1', defaultStyle: 'flat_design',
    zones: ['title', 'body', 'footer'],
  },
  {
    id: 'poster', icon: '🖼', name: '科普海报',
    description: '院内张贴、线上推广、活动宣传',
    defaultAspect: '9:16', defaultStyle: 'medical_illustration',
    zones: ['title', 'subtitle', 'footer'],
  },
  {
    id: 'picturebook', icon: '📚', name: '科普绘本',
    description: '儿童健康教育绘本、亲子科普读物',
    defaultAspect: '3:4', defaultStyle: 'picture_book',
    zones: ['title', 'subtitle'],
  },
  {
    id: 'longimage', icon: '📜', name: '竖版长图',
    description: '微信公众号一图流、健康知识长图',
    defaultAspect: '1:1', defaultStyle: 'flat_design',
    zones: ['title', 'body'],
  },
  {
    id: 'ppt', icon: '📊', name: 'PPT 展示图',
    description: '医学演讲 PPT、教学课件、学术汇报',
    defaultAspect: '16:9', defaultStyle: 'medical_illustration',
    zones: ['title', 'subtitle', 'footer'],
  },
]

const aspectPresetMap: Record<string, Array<{ key: string; label: string }>> = {
  article:     [{ key: '1:1', label: '1:1 方形' }, { key: '4:3', label: '4:3 横版' }],
  comic:       [{ key: '1:1', label: '1:1 单格' }, { key: '3:4', label: '3:4 竖版段' }],
  card:        [{ key: '1:1', label: '1:1 方形' }, { key: '3:4', label: '3:4 竖版' }, { key: '16:9', label: '16:9 横版' }],
  poster:      [{ key: '9:16', label: '9:16 手机海报' }, { key: '16:9', label: '16:9 横版宣传' }],
  picturebook: [{ key: '3:4', label: '3:4 封面' }, { key: '4:3', label: '4:3 内页' }, { key: '2:1', label: '2:1 跨页' }],
  longimage:   [{ key: '1:1', label: '1:1 段落' }],
  ppt:         [{ key: '16:9', label: '16:9 宽屏' }, { key: '4:3', label: '4:3 传统' }],
}

const specialties = [
  '心内科', '呼吸内科', '消化内科', '神经内科', '内分泌科',
  '普外科', '骨科', '泌尿外科', '心外科', '神经外科',
  '妇产科', '儿科', '眼科', '耳鼻喉科', '口腔科',
  '皮肤科', '肿瘤科', '急诊科', '重症医学科', '康复科',
  '影像科', '检验科', '病理科', '药学部', '护理部',
  '中医科', '全科医学', '精神科', '感染科', '老年医学科',
]

// ─── 变体 ───

interface VariantInfo {
  id: string
  scene: string
  name: string
  description: string
  style: string
  aspects: string[]
  available: boolean
  tier_exclude: string[]
  special: string | null
}

const sceneVariants = ref<VariantInfo[]>([])
const variantsLoading = ref(false)
const selectedVariant = ref<VariantInfo | null>(null)

async function loadVariants(sceneId: string) {
  variantsLoading.value = true
  try {
    const res = await api.medpic.getVariants({
      scene: sceneId,
      hardware_tier: hardwareTier.value || 'standard',
    })
    sceneVariants.value = res.data?.variants || []
  } catch {
    sceneVariants.value = []
  } finally {
    variantsLoading.value = false
  }
}

function pickVariant(v: VariantInfo) {
  selectedVariant.value = v
  form.value.style = v.style
  form.value.aspectKey = v.aspects[0] || '1:1'
  if (selectedScene.value?.id === 'picturebook') form.value.targetAudience = 'children'
  results.value = []
  genError.value = ''
  pendingComfyPrompt.value = null
  if (comfyStatus.running) {
    step.value = 'comfyui'
  } else {
    step.value = 'generate'
  }
}

function specialLabel(s: string | null): string {
  if (!s) return ''
  const map: Record<string, string> = {
    character_consistency: '角色一致性',
    high_dpi: '高分辨率',
    segmented: '分段拼接',
  }
  return map[s] || s
}

// ─── 表单 ───

const selectedScene = ref<Scene | null>(null)
const advancedOpen = ref<string[]>([])
const step = ref<'generate' | 'compose' | 'comfyui'>('generate')
const directComfyMode = ref(false)
const directScene = ref('')

function enterDirectComfyMode() {
  directComfyMode.value = true
  step.value = 'comfyui'
  results.value = []
  pendingComfyPrompt.value = null
  if (!comfyStatus.running) pollComfyReady()
}

const form = ref({
  specialty: '',
  targetAudience: 'public',
  topic: '',
  subject: '',
  style: 'medical_illustration',
  colorTone: 'neutral',
  aspectKey: '1:1',
  batchCount: 1,
  extraPrompt: '',
  seedMode: 'recommended' as 'recommended' | 'random' | 'custom',
  seed: 42,
})

const generating = ref(false)
const genError = ref('')

interface ResultImage {
  rawPath: string
  serveUrl: string
}
const results = ref<ResultImage[]>([])
const selectedResultIdx = ref(0)

const previewVisible = ref(false)
const previewUrl = ref('')

// §8.2 LoRA 管理
interface LoraInfo {
  id: string
  name: string
  category: string
  filename: string
  arch: string
  weight_range: [number, number]
  default_weight: number
  tiers: string[]
  auto_select_styles: string[]
  auto_select_scenes: string[]
  is_base_pack: boolean
  notes: string
}
const allLoras = ref<LoraInfo[]>([])
const loraOverrides = ref<Map<string, number>>(new Map())
const lastUsedLoras = ref<Array<{ id: string; name: string; category: string; strength: number }>>([])
const lastSavedHistoryId = ref<number | null>(null)
const lastPromptData = ref<Record<string, unknown> | null>(null)

const availableLoras = computed(() => {
  const tier = hardwareTier.value || 'standard'
  return allLoras.value.filter(l => l.tiers.includes(tier))
})

function isLoraEnabled(id: string): boolean {
  return loraOverrides.value.has(id)
}
function getLoraStrength(id: string): number {
  return loraOverrides.value.get(id) ?? 0
}
function toggleLora(id: string, enabled: boolean) {
  const map = new Map(loraOverrides.value)
  if (enabled) {
    const lora = allLoras.value.find(l => l.id === id)
    map.set(id, lora?.default_weight ?? 0.5)
  } else {
    map.delete(id)
  }
  loraOverrides.value = map
}
function setLoraStrength(id: string, val: number) {
  const map = new Map(loraOverrides.value)
  map.set(id, val)
  loraOverrides.value = map
}
function loraCategoryLabel(cat: string): string {
  return { style: '风格', subject: '题材', kids: '儿向', character: '角色' }[cat] || cat
}

async function loadLoraRegistry() {
  try {
    const res = await api.medpic.getLoraRegistry()
    allLoras.value = (res.data?.loras ?? []) as LoraInfo[]
  } catch { /* ignore */ }
}

const ASPECT_LABELS: Record<string, string> = {
  '1:1': '1:1 方形',
  '4:3': '4:3 横版',
  '3:4': '3:4 竖版',
  '16:9': '16:9 宽屏',
  '9:16': '9:16 竖屏',
  '2:1': '2:1 跨页',
}

const currentAspectPresets = computed(() => {
  if (selectedVariant.value) {
    return selectedVariant.value.aspects.map(a => ({
      key: a,
      label: ASPECT_LABELS[a] || a,
    }))
  }
  if (!selectedScene.value) return []
  return aspectPresetMap[selectedScene.value.id] || []
})

function selectScene(scene: Scene) {
  selectedScene.value = scene
  selectedVariant.value = null
  form.value.aspectKey = scene.defaultAspect
  form.value.style = scene.defaultStyle
  loadVariants(scene.id)
}

function goBack() {
  if (step.value === 'compose') {
    step.value = comfyStatus.running ? 'comfyui' : 'generate'
    composedPreviewUrl.value = ''
    composeError.value = ''
  } else if (directComfyMode.value && step.value === 'comfyui') {
    cleanupComfyWs()
    directComfyMode.value = false
    directScene.value = ''
    step.value = 'generate'
  } else if (step.value === 'comfyui' || step.value === 'generate') {
    cleanupComfyWs()
    selectedVariant.value = null
  }
}

// ─── 特殊能力状态 ───

const isCharacterConsistency = computed(() =>
  selectedVariant.value?.supports_character === true
  || selectedVariant.value?.special === 'character_consistency'
)
const isHighDpi = computed(() => selectedVariant.value?.special === 'high_dpi')
const isSegmented = computed(() => selectedVariant.value?.special === 'segmented')

const referenceImage = ref<{ path: string; serve_url: string } | null>(null)
const ipadapterWeight = ref(0.7)

// §9.3 预置角色库
interface PresetCharacter {
  id: string
  name: string
  description: string
  thumbnail_url: string
  reference_path: string
  scenes: string[]
}
const presetCharacters = ref<PresetCharacter[]>([])

async function loadPresetCharacters() {
  try {
    const res = await api.medpic.getPresetCharacters()
    presetCharacters.value = (res.data?.characters ?? []) as PresetCharacter[]
  } catch { /* ignore — preset library may not exist yet */ }
}

const selectedPresetId = ref('')

function selectPresetCharacter(pc: PresetCharacter) {
  referenceImage.value = {
    path: pc.reference_path,
    serve_url: pc.thumbnail_url,
  }
  selectedPresetId.value = pc.id
  ElMessage.success(`已选择预置角色：${pc.name}`)
}

const segmentCount = ref(4)
const segmentResults = ref<ResultImage[]>([])
const stitching = ref(false)
const stitchedResult = ref<{
  stitched_path: string
  stitched_url: string
  slices: Array<{ path: string; serve_url: string }>
} | null>(null)
const upscaling = ref(false)
const upscaleResult = ref<{
  path: string
  serve_url: string
  method: string
  width: number
  height: number
} | null>(null)

async function handleRefUpload(uploadFile: any) {
  const file = uploadFile?.raw || uploadFile
  if (!file) return
  try {
    const res = await api.medpic.uploadReferenceImage(file)
    if (res.data) {
      referenceImage.value = res.data
      ElMessage.success('参考角色图已上传')
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '上传失败')
  }
}

async function setAsReference(idx: number) {
  const img = results.value[idx]
  if (!img) return
  try {
    const res = await api.medpic.referenceFromGenerated(img.rawPath)
    if (res.data) {
      referenceImage.value = res.data
      ElMessage.success('已设为参考角色图')
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '设置失败')
  }
}

async function doUpscale(idx: number) {
  const img = results.value[idx]
  if (!img) return
  upscaling.value = true
  upscaleResult.value = null
  try {
    const res = await api.medpic.upscale({
      image_path: img.rawPath,
      print_size: 'A3',
      aspect: form.value.aspectKey,
    })
    if (res.data) {
      upscaleResult.value = res.data
      ElMessage.success(`放大完成（${res.data.method}）`)
      if (lastSavedHistoryId.value && res.data.path) {
        api.medpic.updateHistory(lastSavedHistoryId.value, { upscaled_image_path: res.data.path }).catch(() => {})
      }
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '放大失败')
  } finally {
    upscaling.value = false
  }
}

async function generateSegmented() {
  if (!form.value.specialty) {
    ElMessage.warning('请选择科室/专科')
    return
  }
  if (!form.value.topic.trim()) {
    ElMessage.warning('请输入图像主题')
    return
  }
  generating.value = true
  genError.value = ''
  segmentResults.value = []
  stitchedResult.value = null

  try {
    const segLoraOverrideList = loraOverrides.value.size > 0
      ? Array.from(loraOverrides.value.entries()).map(([id, strength]) => ({ id, strength }))
      : undefined

    for (let i = 0; i < segmentCount.value; i++) {
      const promptRes = await api.medpic.buildPrompt({
        scene: selectedScene.value!.id,
        topic: form.value.topic,
        variant: selectedVariant.value?.id,
        specialty: form.value.specialty,
        target_audience: form.value.targetAudience,
        style: form.value.style,
        color_tone: form.value.colorTone,
        subject: form.value.subject,
        extra_prompt: form.value.extraPrompt,
        hardware_tier: hardwareTier.value || 'standard',
        aspect: form.value.aspectKey,
        segment_index: i,
        segment_count: segmentCount.value,
        seed_mode: form.value.seedMode,
        lora_overrides: segLoraOverrideList,
        reference_image: referenceImage.value?.path || undefined,
        ipadapter_weight: referenceImage.value ? ipadapterWeight.value : undefined,
        character_preset: selectedPresetId.value || undefined,
      })
      const pp = promptRes.data!
      if (i === 0) lastUsedLoras.value = pp.loras ?? []

      let segSeed: number | undefined
      if (form.value.seedMode === 'recommended' && pp.recommended_seed != null) {
        segSeed = pp.recommended_seed + i
      } else if (form.value.seedMode === 'custom') {
        segSeed = form.value.seed + i
      }

      const segLorasForComfy = pp.loras?.map(l => [l.filename, l.strength]) ?? []

      const res = await api.imagegen.generate({
        prompt: form.value.topic,
        user_positive_prompt: pp.positive_prompt,
        user_negative_prompt: pp.negative_prompt,
        style: form.value.style,
        width: pp.width,
        height: pp.height,
        batch_count: 1,
        seed: segSeed,
        steps: pp.steps,
        cfg_scale: pp.cfg_scale,
        sampler_name: pp.sampler_name,
        specialty: form.value.specialty,
        target_audience: form.value.targetAudience,
        image_type: selectedScene.value?.id,
        comfy_workflow_path: pp.workflow_path,
        loras: segLorasForComfy,
      })
      const urls: string[] = res.data?.urls || []
      if (urls.length) {
        const u = urls[0]
        const rel = u.startsWith('medcomm-image://') ? u.slice('medcomm-image://'.length) : u
        segmentResults.value.push({
          rawPath: rel,
          serveUrl: `/api/v1/imagegen/serve?path=${encodeURIComponent(rel)}`,
        })
      }
    }
    if (!segmentResults.value.length) {
      genError.value = '未生成任何段落图像'
    }
  } catch (e: any) {
    genError.value = e?.response?.data?.detail || e?.message || '生成失败'
  } finally {
    generating.value = false
  }
}

async function doStitch() {
  if (segmentResults.value.length < 2) return
  stitching.value = true
  stitchedResult.value = null
  try {
    const res = await api.medpic.stitch({
      segment_paths: segmentResults.value.map(s => s.rawPath),
      variant_id: selectedVariant.value?.id || 'F-1',
    })
    if (res.data) {
      stitchedResult.value = res.data
      ElMessage.success('拼接完成')
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '拼接失败')
  } finally {
    stitching.value = false
  }
}

function downloadSlices() {
  if (!stitchedResult.value?.slices.length) return
  for (const [idx, slice] of stitchedResult.value.slices.entries()) {
    const a = document.createElement('a')
    a.href = slice.serve_url
    a.download = `medpic-wechat-slice-${idx + 1}.png`
    a.click()
  }
}

// ─── 生成（调用后端 build-prompt） ───

async function generate() {
  if (!form.value.specialty) {
    ElMessage.warning('请选择科室/专科')
    return
  }
  if (!form.value.topic.trim()) {
    ElMessage.warning('请输入图像主题')
    return
  }

  generating.value = true
  genError.value = ''
  results.value = []

  try {
    const loraOverrideList = loraOverrides.value.size > 0
      ? Array.from(loraOverrides.value.entries()).map(([id, strength]) => ({ id, strength }))
      : undefined

    const promptRes = await api.medpic.buildPrompt({
      scene: selectedScene.value!.id,
      topic: form.value.topic,
      variant: selectedVariant.value?.id,
      specialty: form.value.specialty,
      target_audience: form.value.targetAudience,
      style: form.value.style,
      color_tone: form.value.colorTone,
      subject: form.value.subject,
      extra_prompt: form.value.extraPrompt,
      hardware_tier: hardwareTier.value || 'standard',
      aspect: form.value.aspectKey,
      seed_mode: form.value.seedMode,
      lora_overrides: loraOverrideList,
      reference_image: referenceImage.value?.path || undefined,
      ipadapter_weight: referenceImage.value ? ipadapterWeight.value : undefined,
      character_preset: selectedPresetId.value || undefined,
    })

    const pp = promptRes.data!
    lastUsedLoras.value = pp.loras ?? []

    let effectiveSeed: number | undefined
    if (form.value.seedMode === 'recommended' && pp.recommended_seed != null) {
      effectiveSeed = pp.recommended_seed
    } else if (form.value.seedMode === 'custom') {
      effectiveSeed = form.value.seed
    }

    const lorasForComfy = pp.loras?.map(l => [l.filename, l.strength]) ?? []

    const res = await api.imagegen.generate({
      prompt: form.value.topic,
      user_positive_prompt: pp.positive_prompt,
      user_negative_prompt: pp.negative_prompt,
      style: form.value.style,
      width: pp.width,
      height: pp.height,
      batch_count: form.value.batchCount,
      seed: effectiveSeed,
      steps: pp.steps,
      cfg_scale: pp.cfg_scale,
      sampler_name: pp.sampler_name,
      specialty: form.value.specialty,
      target_audience: form.value.targetAudience,
      image_type: selectedScene.value?.id,
      preferred_provider: comfyStatus.running ? 'comfyui_local' : undefined,
      comfy_workflow_path: pp.workflow_path,
      loras: lorasForComfy,
    })

    const urls: string[] = res.data?.urls || []
    if (urls.length) {
      let items = urls.map(u => {
        const rel = u.startsWith('medcomm-image://') ? u.slice('medcomm-image://'.length) : u
        return { rawPath: rel, serveUrl: `/api/v1/imagegen/serve?path=${encodeURIComponent(rel)}` }
      })

      if (pp.process_mode === 'upscale' && pp.output_width && pp.output_height) {
        const finalized: ResultImage[] = []
        for (const item of items) {
          try {
            const fr = await api.medpic.finalize({
              image_path: item.rawPath,
              target_width: pp.output_width,
              target_height: pp.output_height,
              hardware_tier: hardwareTier.value || 'standard',
            })
            if (fr.data) {
              finalized.push({
                rawPath: fr.data.path,
                serveUrl: fr.data.serve_url,
              })
            } else {
              finalized.push(item)
            }
          } catch {
            finalized.push(item)
          }
        }
        items = finalized
      }

      results.value = items
      lastPromptData.value = pp as Record<string, unknown>

      // 自动保存首张结果到生成历史
      if (items.length > 0) {
        try {
          const hRes = await api.medpic.saveHistory({
            variant_id: selectedVariant.value?.id,
            scene: selectedScene.value!.id,
            style: form.value.style,
            hardware_tier: hardwareTier.value || 'standard',
            topic: form.value.topic,
            specialty: form.value.specialty || undefined,
            positive_prompt: pp.positive_prompt,
            negative_prompt: pp.negative_prompt,
            seed: effectiveSeed,
            seed_mode: form.value.seedMode,
            model_id: pp.model_id,
            loras: pp.loras,
            width: pp.width,
            height: pp.height,
            output_width: pp.output_width,
            output_height: pp.output_height,
            base_image_path: items[0].rawPath,
            ipadapter_weight: referenceImage.value ? ipadapterWeight.value : undefined,
            character_preset: selectedPresetId.value || undefined,
            reference_image_path: referenceImage.value?.path || undefined,
          })
          lastSavedHistoryId.value = hRes.data?.id ?? null
        } catch { /* 历史保存失败不影响主流程 */ }
      }
    } else {
      genError.value = '未返回图像结果，请检查配置或稍后重试'
    }
  } catch (e: any) {
    genError.value = e?.response?.data?.detail || e?.message || '生成失败'
  } finally {
    generating.value = false
  }
}

function selectResult(idx: number) {
  selectedResultIdx.value = idx
}

function enterCompose(idx: number) {
  selectedResultIdx.value = idx
  step.value = 'compose'
  composedPreviewUrl.value = ''
  composeError.value = ''
  composeTexts.title = form.value.topic
  composeTexts.subtitle = ''
  composeTexts.body = ''
  composeTexts.footer = ''
}

// ─── 排版叠字 ───

const composeTexts = reactive({
  title: '',
  subtitle: '',
  body: '',
  footer: '',
})

const composing = ref(false)
const composeError = ref('')
const composedPreviewUrl = ref('')

const currentZones = computed(() => selectedScene.value?.zones || [])

const hasComposeText = computed(() =>
  Object.values(composeTexts).some(v => v.trim())
)

function fillDefaultTexts() {
  composeTexts.title = form.value.topic || '标题'
  if (currentZones.value.includes('subtitle')) {
    composeTexts.subtitle = form.value.specialty
      ? `${form.value.specialty} · 健康科普`
      : '健康科普知识'
  }
  if (currentZones.value.includes('footer')) {
    composeTexts.footer = 'LinScio MedPic 出品'
  }
}

async function doCompose() {
  const img = results.value[selectedResultIdx.value]
  if (!img) return

  composing.value = true
  composeError.value = ''

  const texts: Record<string, string> = {}
  for (const [k, v] of Object.entries(composeTexts)) {
    if (v.trim()) texts[k] = v.trim()
  }

  try {
    const res = await api.medpic.compose({
      image_path: img.rawPath,
      scene: selectedScene.value!.id,
      texts,
    })
    composedPreviewUrl.value = res.data!.serve_url
    if (lastSavedHistoryId.value && res.data?.composed_path) {
      const composed = res.data.composed_path.replace(/^medcomm-image:\/\//, '')
      api.medpic.updateHistory(lastSavedHistoryId.value, { composed_image_path: composed }).catch(() => {})
    }
  } catch (e: any) {
    composeError.value = e?.response?.data?.detail || e?.message || '合成失败'
  } finally {
    composing.value = false
  }
}

// ─── AI 智能提示词 ───

const aiDescription = ref('')
const aiPositive = ref('')
const aiNegative = ref('')
const aiExplanation = ref('')
const aiGenerating = ref(false)
const aiRefining = ref(false)
const refineInput = ref('')

const refineShortcuts = [
  { label: '更通俗', instruction: '更通俗，面向普通患者' },
  { label: '更专业', instruction: '更专业，面向医护人员' },
  { label: '更儿向', instruction: '更适合儿童，可爱温和' },
  { label: '去文字', instruction: '去掉文字元素，纯图像' },
  { label: '更简洁', instruction: '更简洁，扁平化设计' },
]

function applyAIParams(params: Record<string, string>) {
  if (params.scene && directComfyMode.value) directScene.value = params.scene
  if (params.style) form.value.style = params.style
  if (params.aspect) form.value.aspectKey = params.aspect
  if (params.audience) form.value.targetAudience = params.audience
  if (params.color_tone) form.value.colorTone = params.color_tone
}

async function generateAIPrompt() {
  if (!aiDescription.value.trim()) return
  aiGenerating.value = true
  try {
    const res = await api.medpic.aiPrompt({
      description: aiDescription.value,
      specialty: form.value.specialty,
    })
    const data = res.data!
    aiPositive.value = data.positive
    aiNegative.value = data.negative
    aiExplanation.value = data.explanation || ''
    if (data.params) applyAIParams(data.params as Record<string, string>)
    form.value.topic = aiDescription.value
    ElMessage.success('提示词已生成')
  } catch (e: any) {
    ElMessage.error('生成失败: ' + (e?.response?.data?.detail || e?.message || '未知错误'))
  } finally {
    aiGenerating.value = false
  }
}

async function quickRefine(instruction: string) {
  if (!aiPositive.value) return
  aiRefining.value = true
  try {
    const res = await api.medpic.aiPromptRefine({
      current_positive: aiPositive.value,
      current_negative: aiNegative.value,
      current_params: {
        scene: directScene.value || selectedScene.value?.id || 'article',
        style: form.value.style,
        aspect: form.value.aspectKey,
        audience: form.value.targetAudience,
        color_tone: form.value.colorTone,
      },
      instruction,
    })
    const data = res.data!
    aiPositive.value = data.positive
    aiNegative.value = data.negative
    aiExplanation.value = data.explanation || ''
    if (data.params) applyAIParams(data.params as Record<string, string>)
    ElMessage.success('提示词已优化')
  } catch (e: any) {
    ElMessage.error('优化失败: ' + (e?.response?.data?.detail || e?.message || '未知错误'))
  } finally {
    aiRefining.value = false
  }
}

function customRefine() {
  if (!refineInput.value.trim()) return
  quickRefine(refineInput.value)
  refineInput.value = ''
}

// ─── ComfyUI 嵌入式集成 ───

const comfyStatus = reactive({ running: false, port: 8188, pid: null as number | null, dir: null as string | null, available: false })
const comfyUrl = ref('http://127.0.0.1:8188')
const comfyWebviewRef = ref<HTMLIFrameElement | null>(null)
const comfyInjecting = ref(false)
const comfyQueueing = ref(false)
const comfyListening = ref(false)
const comfyPolling = ref(false)
let comfyWs: WebSocket | null = null
let comfyPollTimer: ReturnType<typeof setInterval> | null = null
const pendingComfyPrompt = ref<Record<string, unknown> | null>(null)
const lastSyncInfo = ref('')

function getComfyProxyBase(): string {
  if (window.electronAPI) return `http://127.0.0.1:${comfyStatus.port}`
  return '/comfyui-proxy'
}

function getComfyWsUrl(): string {
  if (window.electronAPI) return `ws://127.0.0.1:${comfyStatus.port}/ws?clientId=medpic`
  const loc = window.location
  const protocol = loc.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${loc.host}/comfyui-proxy/ws?clientId=medpic`
}

async function refreshComfyStatus() {
  if (window.electronAPI?.getComfyUIStatus) {
    try {
      const s = await window.electronAPI.getComfyUIStatus()
      Object.assign(comfyStatus, s)
      if (s.port) comfyUrl.value = `http://127.0.0.1:${s.port}`
    } catch { /* not in Electron */ }
  } else {
    try {
      const res = await fetch(`${getComfyProxyBase()}/system_stats`, { signal: AbortSignal.timeout(2000) })
      comfyStatus.running = res.ok
      comfyStatus.available = true
      comfyStatus.port = 8188
      comfyUrl.value = 'http://127.0.0.1:8188'
    } catch {
      comfyStatus.running = false
    }
  }
}

async function pollComfyReady() {
  comfyPolling.value = true
  let attempts = 0
  while (attempts < 20) {
    await refreshComfyStatus()
    if (comfyStatus.running) break
    await new Promise(r => setTimeout(r, 2000))
    attempts++
  }
  comfyPolling.value = false
}

function connectComfyWs(): Promise<void> {
  if (comfyWs && comfyWs.readyState === WebSocket.OPEN) return Promise.resolve()
  if (comfyWs) { comfyWs.close(); comfyWs = null }
  return new Promise((resolve) => {
    const url = getComfyWsUrl()
    console.log('[MedPic] Connecting WebSocket:', url)
    comfyWs = new WebSocket(url)
    comfyWs.onopen = () => {
      comfyListening.value = true
      console.log('[MedPic] WebSocket connected')
      resolve()
    }
    comfyWs.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data)
        console.log('[MedPic] WS message:', msg.type, msg.data?.node, msg.data?.prompt_id)
        if (msg.type === 'executed' && msg.data?.output?.images) {
          handleComfyExecuted(msg.data.output.images)
        }
        if (msg.type === 'executing' && msg.data?.node === null) {
          console.log('[MedPic] Queue finished')
        }
      } catch { /* non-JSON frames (e.g. binary previews) */ }
    }
    comfyWs.onclose = () => {
      console.log('[MedPic] WebSocket closed')
      comfyWs = null
      comfyListening.value = false
    }
    comfyWs.onerror = (e) => {
      console.warn('[MedPic] WebSocket error:', e)
      comfyWs?.close()
      comfyWs = null
      comfyListening.value = false
      resolve()
    }
    setTimeout(resolve, 3000)
  })
}

function cleanupComfyWs() {
  if (comfyWs) {
    comfyWs.close()
    comfyWs = null
  }
  comfyListening.value = false
}

async function pollComfyHistory(promptId: string, base: string) {
  for (let i = 0; i < 60; i++) {
    await new Promise(r => setTimeout(r, 3000))
    try {
      const res = await fetch(`${base}/history/${promptId}`)
      if (!res.ok) continue
      const data = await res.json()
      const entry = data[promptId]
      if (!entry || !entry.outputs) continue
      for (const nodeOut of Object.values(entry.outputs) as any[]) {
        if (nodeOut?.images?.length) {
          const alreadyHas = results.value.length > 0
          if (!alreadyHas) {
            handleComfyExecuted(nodeOut.images)
          }
          return
        }
      }
    } catch { /* retry */ }
  }
}

async function handleComfyExecuted(images: Array<{ filename: string; subfolder: string; type: string }>) {
  const base = getComfyProxyBase()
  for (const img of images) {
    const imgUrl = `${base}/view?filename=${encodeURIComponent(img.filename)}&subfolder=${encodeURIComponent(img.subfolder || '')}&type=${img.type || 'output'}`
    results.value.push({
      rawPath: img.filename,
      serveUrl: imgUrl,
    })
  }
  if (results.value.length) {
    ElMessage.success(`ComfyUI 生成完成，共 ${results.value.length} 张图像`)
  }
}

const comfyBridgeReady = ref(false)

function onComfyWebviewReady() {
  connectComfyWs()
}

function handleComfyBridgeMessage(event: MessageEvent) {
  if (event.data?.type === 'medcomm:comfyReady') {
    comfyBridgeReady.value = true
  }
}

onMounted(() => {
  window.addEventListener('message', handleComfyBridgeMessage)
})

function syncWorkflowToIframe(workflow: Record<string, any> | undefined) {
  const iframe = comfyWebviewRef.value
  if (!iframe?.contentWindow || !workflow || typeof workflow !== 'object') return
  let plain: Record<string, unknown>
  try {
    plain = JSON.parse(JSON.stringify(toRaw(workflow))) as Record<string, unknown>
  } catch {
    return
  }
  try {
    iframe.contentWindow.postMessage(
      { type: 'medcomm:updateWidgets', workflow: plain },
      '*',
    )
  } catch (e) {
    console.warn('[MedPic] postMessage to ComfyUI iframe failed:', e)
  }
}

async function buildComfyPrompt(): Promise<boolean> {
  const hasAIPrompt = aiPositive.value.trim().length > 0
  if (!hasAIPrompt && !form.value.topic.trim()) return false
  const scene = selectedScene.value?.id || directScene.value || 'article'
  try {
    const res = await api.medpic.comfyuiPrompt({
      scene,
      topic: hasAIPrompt ? aiPositive.value : form.value.topic,
      variant: selectedVariant.value?.id,
      specialty: form.value.specialty,
      target_audience: form.value.targetAudience,
      style: form.value.style,
      hardware_tier: hardwareTier.value || 'standard',
      aspect: form.value.aspectKey,
      seed: form.value.seedMode === 'custom' ? form.value.seed : null,
      seed_mode: form.value.seedMode,
    })
    pendingComfyPrompt.value = res.data as unknown as Record<string, unknown>
    if (hasAIPrompt && pendingComfyPrompt.value?.prompt) {
      const wf = pendingComfyPrompt.value.prompt as Record<string, any>
      const negClipIds = new Set<string>()
      const posClipIds = new Set<string>()
      for (const node of Object.values(wf) as any[]) {
        if (node?.class_type === 'KSampler' || node?.class_type === 'KSamplerAdvanced') {
          const posRef = node.inputs?.positive
          const negRef = node.inputs?.negative
          if (Array.isArray(posRef)) posClipIds.add(String(posRef[0]))
          if (Array.isArray(negRef)) negClipIds.add(String(negRef[0]))
        }
      }
      for (const nodeId of Object.keys(wf)) {
        const node = wf[nodeId]
        if (node?.class_type === 'CLIPTextEncode' && node?.inputs && 'text' in node.inputs) {
          if (negClipIds.has(nodeId)) {
            node.inputs.text = aiNegative.value
          } else if (posClipIds.has(nodeId)) {
            node.inputs.text = aiPositive.value
          }
        }
      }
    }
    syncWorkflowToIframe(pendingComfyPrompt.value.prompt as Record<string, any>)
    const params = (res.data as any).params_used
    lastSyncInfo.value = `${params.width}×${params.height} · seed ${params.seed}`
    return true
  } catch (e: any) {
    ElMessage.error('构建参数失败: ' + (e?.response?.data?.detail || e?.message || '未知错误'))
    return false
  }
}

async function injectParamsToComfy() {
  comfyInjecting.value = true
  try {
    const ok = await buildComfyPrompt()
    if (ok && pendingComfyPrompt.value) {
      ElMessage.success(lastSyncInfo.value ? `已同步到工作流（${lastSyncInfo.value}）` : '已同步参数到工作流')
    }
  } finally {
    comfyInjecting.value = false
  }
}

async function queuePromptInComfy() {
  comfyQueueing.value = true
  try {
    if (!pendingComfyPrompt.value) {
      const ok = await buildComfyPrompt()
      if (!ok || !pendingComfyPrompt.value) {
        ElMessage.warning('请先生成提示词，或先同步参数到工作流')
        return
      }
    }
    await connectComfyWs()
    const base = getComfyProxyBase()
    const resp = await fetch(`${base}/prompt`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(pendingComfyPrompt.value),
    })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}))
      throw new Error(err.error || `HTTP ${resp.status}`)
    }
    const respJson = await resp.json().catch(() => ({}))
    const promptId = respJson.prompt_id
    ElMessage.info('已提交生成任务，请等待...')
    if (promptId) {
      pollComfyHistory(promptId, base)
    }
  } catch (e: any) {
    ElMessage.error('提交生成失败: ' + (e?.message || '未知错误'))
  } finally {
    comfyQueueing.value = false
  }
}

onBeforeUnmount(() => {
  cleanupComfyWs()
  window.removeEventListener('message', handleComfyBridgeMessage)
  if (comfyPollTimer) { clearInterval(comfyPollTimer); comfyPollTimer = null }
})

function downloadImage(url: string, idx: number) {
  const a = document.createElement('a')
  a.href = url
  a.download = `medpic-${selectedScene.value?.id || 'image'}-${idx + 1}.png`
  a.click()
}
</script>

<style scoped>
.lora-controls {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.lora-item {
  display: flex;
  align-items: center;
  gap: 8px;
}
.lora-category-tag {
  display: inline-block;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--el-color-primary-light-8);
  color: var(--el-color-primary);
  margin-left: 4px;
}
.lora-info {
  margin-top: 0.75rem;
  padding: 8px 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
  font-size: 13px;
}
.lora-info-tag {
  display: inline-block;
  margin-right: 8px;
  margin-bottom: 4px;
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--el-color-primary-light-9);
  font-size: 12px;
}

.preset-characters {
  margin-bottom: 8px;
}
.preset-label {
  display: block;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-bottom: 6px;
}
.preset-grid {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.preset-char-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 72px;
  cursor: pointer;
  border: 2px solid transparent;
  border-radius: 8px;
  padding: 4px;
  transition: border-color 0.2s;
}
.preset-char-card:hover {
  border-color: var(--el-color-primary);
  background: var(--el-fill-color-lighter);
}
.preset-char-img {
  width: 56px;
  height: 56px;
  object-fit: cover;
  border-radius: 6px;
  background: var(--el-fill-color);
}
.preset-char-name {
  font-size: 11px;
  margin-top: 3px;
  text-align: center;
  line-height: 1.2;
}

.medpic {
  max-width: 1000px;
  margin: 0 auto;
  padding: 2rem 1.5rem;
}

.medpic--fullscreen {
  max-width: none;
  padding: 0;
  height: 100%;
  min-height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #fff;
}

.medpic-header {
  margin-bottom: 1.5rem;
}

.medpic-header h2 {
  margin: 0 0 0.25rem;
  font-size: 1.5rem;
}

.subtitle {
  color: #6b7280;
  font-size: 0.9rem;
  margin: 0;
}

/* 硬件档位 */
.tier-select { text-align: center; }
.tier-select h3 { margin: 0 0 0.5rem; }
.tier-hint { color: #6b7280; font-size: 0.85rem; margin: 0 0 1.5rem; }

.tier-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
  max-width: 720px;
  margin: 0 auto;
}

.tier-card {
  padding: 1.5rem 1rem;
  border: 2px solid #e5e7eb;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  text-align: center;
}

.tier-card:hover {
  border-color: #3b82f6;
  box-shadow: 0 2px 12px rgba(59, 130, 246, 0.12);
}

.tier-help-link {
  color: #3b82f6;
  text-decoration: underline;
  cursor: pointer;
  font-size: 0.85rem;
}

.config-help h4 { margin: 1rem 0 0.5rem; font-size: 0.95rem; }
.config-help h4:first-child { margin-top: 0; }
.config-help ol, .config-help ul { padding-left: 1.5rem; margin: 0 0 0.5rem; }
.config-help li { margin-bottom: 0.3rem; font-size: 0.9rem; line-height: 1.5; }
.config-help kbd {
  background: #f3f4f6; border: 1px solid #d1d5db;
  border-radius: 3px; padding: 1px 5px; font-size: 0.85rem;
}
.config-help code {
  background: #f3f4f6; border-radius: 3px;
  padding: 1px 5px; font-size: 0.85rem;
}

.tier-icon { font-size: 2.5rem; margin-bottom: 0.75rem; }
.tier-name { font-weight: 600; font-size: 0.95rem; margin-bottom: 0.25rem; }
.tier-desc { color: #6b7280; font-size: 0.8rem; line-height: 1.4; margin-bottom: 0.5rem; }
.tier-spec { color: #3b82f6; font-size: 0.8rem; font-weight: 500; }

/* 变体选择 */
.variant-select {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 1.5rem;
}

.variant-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid #f3f4f6;
}

.variant-title { margin: 0 0 0.25rem; font-size: 1.15rem; }
.variant-hint { color: #6b7280; font-size: 0.85rem; margin: 0 0 1.5rem; }
.variant-loading { text-align: center; padding: 2rem; color: #6b7280; }

.variant-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 1rem;
}

.variant-card {
  position: relative;
  padding: 1.25rem;
  border: 2px solid #e5e7eb;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  background: #fff;
}

.variant-card:hover:not(.disabled) {
  border-color: #3b82f6;
  box-shadow: 0 2px 12px rgba(59, 130, 246, 0.1);
  transform: translateY(-1px);
}

.variant-card.disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background: #f9fafb;
}

.variant-id {
  display: inline-block;
  background: #eff6ff;
  color: #3b82f6;
  font-weight: 700;
  font-size: 0.8rem;
  padding: 2px 8px;
  border-radius: 4px;
  margin-bottom: 0.5rem;
}

.variant-name { font-weight: 600; font-size: 1rem; margin-bottom: 0.25rem; }
.variant-desc { color: #6b7280; font-size: 0.85rem; line-height: 1.4; margin-bottom: 0.75rem; }
.variant-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; }

.variant-unavailable {
  margin-top: 0.5rem;
  color: #ef4444;
  font-size: 0.8rem;
  font-weight: 500;
}

/* 快捷启动 ComfyUI */
.scene-select-page {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.scene-section-title {
  margin: 0.5rem 0 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--el-text-color-regular, #606266);
}

.comfy-quick-launch {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1.25rem 1.5rem;
  border: 2px solid #3b82f6;
  border-radius: 14px;
  cursor: pointer;
  transition: all 0.25s;
  background: linear-gradient(135deg, #eff6ff 0%, #f0f9ff 100%);
}
.comfy-quick-launch:hover {
  border-color: #2563eb;
  box-shadow: 0 4px 20px rgba(59, 130, 246, 0.18);
  transform: translateY(-2px);
}
.comfy-quick-launch-icon {
  font-size: 2.5rem;
  flex-shrink: 0;
  line-height: 1;
}
.comfy-quick-launch-body {
  flex: 1;
}
.comfy-quick-launch-title {
  font-weight: 700;
  font-size: 1.1rem;
  margin-bottom: 0.3rem;
  color: #1e40af;
}
.comfy-quick-launch-desc {
  font-size: 0.85rem;
  color: #6b7280;
  line-height: 1.4;
  margin-bottom: 0.4rem;
}
.comfy-quick-launch-arrow {
  font-size: 1.5rem;
  color: #3b82f6;
  flex-shrink: 0;
}

/* 场景卡片 */
.scene-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
}

.scene-card {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  padding: 1.25rem;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  background: #fff;
}

.scene-card:hover {
  border-color: #3b82f6;
  box-shadow: 0 2px 12px rgba(59, 130, 246, 0.1);
  transform: translateY(-1px);
}

.scene-icon { font-size: 2rem; flex-shrink: 0; }
.scene-name { font-weight: 600; font-size: 1rem; margin-bottom: 0.25rem; }
.scene-desc { color: #6b7280; font-size: 0.85rem; line-height: 1.4; }

/* 生成面板 */
.gen-panel {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 1.5rem;
}

.medpic--fullscreen .gen-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  border: none;
  border-radius: 0;
  padding: 0;
  overflow: hidden;
}

.gen-panel-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid #f3f4f6;
}

.medpic--fullscreen .gen-panel-header {
  margin: 0;
  padding: 0.5rem 1rem;
  border-bottom: 1px solid #e5e7eb;
  background: #fafbfc;
  flex-shrink: 0;
}

.current-scene { font-weight: 600; font-size: 1.1rem; }
.gen-form { max-width: 640px; }

.form-row { display: flex; gap: 1rem; }
.form-item-half { flex: 1; }
.field-hint { color: #9ca3af; font-size: 0.8rem; margin-left: 8px; }

.advanced-collapse { margin-top: 1rem; }
.gen-actions { margin-top: 1.5rem; margin-bottom: 0.5rem; }

/* 结果 */
.results {
  margin-top: 2rem;
  padding-top: 1.5rem;
  border-top: 1px solid #f3f4f6;
}

.results h3 { margin: 0 0 1rem; font-size: 1.1rem; }

.result-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 1rem;
}

.result-item {
  border: 2px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
  transition: border-color 0.2s;
  cursor: pointer;
}

.result-item:hover { border-color: #93c5fd; }
.result-item.selected { border-color: #3b82f6; }

.result-item img {
  width: 100%;
  display: block;
}

.result-actions {
  padding: 0.5rem;
  display: flex;
  gap: 0.5rem;
  justify-content: center;
}

.gen-error { margin-top: 1rem; }

/* 排版叠字面板 */
.compose-layout {
  display: flex;
  gap: 1.5rem;
}

.compose-preview {
  flex: 1;
  position: relative;
  min-width: 0;
}

.preview-img {
  width: 100%;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
}

.compose-loading {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.7);
  border-radius: 8px;
  font-size: 1rem;
  color: #3b82f6;
  gap: 0.5rem;
}

.compose-form {
  flex: 0 0 320px;
  min-width: 280px;
}

.compose-form h3 { margin: 0 0 0.25rem; font-size: 1.1rem; }
.compose-hint { color: #6b7280; font-size: 0.85rem; margin: 0 0 1rem; }

.compose-actions {
  display: flex;
  gap: 0.75rem;
  margin-top: 1rem;
}

.composed-done { margin-top: 1rem; }
.composed-download { margin-top: 0.75rem; }

/* 特殊能力区域 */
.special-section {
  background: #f8fafc;
  border: 1px dashed #d1d5db;
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 1rem;
}

.ref-image-area { display: flex; align-items: center; gap: 1rem; }
.ref-preview { display: flex; align-items: center; gap: 0.75rem; }
.ref-img { width: 80px; height: 80px; object-fit: cover; border-radius: 8px; border: 1px solid #e5e7eb; }
.ref-upload { display: flex; align-items: center; gap: 0.75rem; }

.result-label {
  text-align: center;
  font-size: 0.8rem;
  color: #6b7280;
  padding: 4px 0;
}

.stitch-result {
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid #f3f4f6;
}

.stitch-result h4 { margin: 0 0 0.75rem; font-size: 1rem; }

.stitched-preview {
  max-width: 100%;
  max-height: 600px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  object-fit: contain;
}

/* ComfyUI 嵌入式工作区 */
.comfyui-workspace {
  display: flex;
  gap: 0;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.comfy-sidebar {
  flex: 0 0 320px;
  padding: 0.75rem;
  border-right: 1px solid #e5e7eb;
  overflow-y: auto;
  background: #fafbfc;
}

.sidebar-section {
  margin-bottom: 0.75rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid #f0f0f0;
}
.sidebar-section:last-child {
  border-bottom: none;
  margin-bottom: 0;
}

.sidebar-title {
  margin: 0 0 0.5rem;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--el-text-color-primary, #303133);
}

.ai-explanation {
  display: block;
  font-weight: 400;
  font-size: 0.75rem;
  color: var(--el-text-color-secondary, #909399);
  margin-top: 0.25rem;
  line-height: 1.3;
}

.refine-shortcuts {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 0.5rem;
}

.refine-custom {
  margin-top: 0.5rem;
}

.sync-status {
  margin-top: 6px;
  text-align: center;
  font-size: 12px;
  color: #67c23a;
}
.sync-ok {
  font-weight: 600;
}
.sync-detail {
  display: block;
  color: #909399;
  margin-top: 2px;
}

.comfy-main {
  flex: 1;
  min-width: 0;
  position: relative;
}

.comfy-webview {
  width: 100%;
  height: 100%;
  border: none;
}

.comfy-not-ready {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  padding: 2rem;
  color: #6b7280;
}

.comfy-not-ready-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
}

.comfy-not-ready h3 {
  margin: 0 0 0.5rem;
  color: #374151;
}

.comfy-not-ready p {
  margin: 0 0 1.5rem;
  font-size: 0.9rem;
}

.comfy-listening {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: #3b82f6;
  font-size: 0.85rem;
  padding: 0.5rem 0;
}

.comfy-results-mini {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.comfy-result-thumb {
  width: 80px;
  height: 80px;
  border-radius: 6px;
  overflow: hidden;
  cursor: pointer;
  border: 2px solid transparent;
  transition: border-color 0.2s;
}

.comfy-result-thumb:hover {
  border-color: #3b82f6;
}

.comfy-result-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.comfy-result-section h4 {
  margin: 0 0 0.5rem;
  font-size: 0.9rem;
}

@media (max-width: 768px) {
  .compose-layout { flex-direction: column; }
  .compose-form { flex: none; width: 100%; }
  .tier-grid { grid-template-columns: 1fr; }
  .medpic--fullscreen { height: auto; overflow: auto; }
  .comfyui-workspace { flex-direction: column; flex: none; height: auto; }
  .comfy-sidebar { flex: none; border-right: none; border-bottom: 1px solid #e5e7eb; }
}
</style>
