<template>
  <div class="contest-image-overview">
    <div v-if="!totalSections" class="overview-empty">
      暂无可配图章节，请先生成章节正文。
    </div>

    <template v-else>
      <!-- ── 视觉锚点（折叠式，默认收起） ── -->
      <VisualAnchorPanel
        v-if="articleId"
        :article-id="articleId"
        :anchor="visualAnchor || null"
        class="overview-anchor"
        @updated="(a: any) => emit('visualAnchorUpdated', a)"
        @pick-anchor="openAnchorPicker"
      />

      <!-- ── 锚点图选择弹窗 ── -->
      <el-dialog
        v-model="anchorPickerVisible"
        title="选择锚点参考图"
        width="640px"
        :close-on-click-modal="false"
        align-center
      >
        <div v-if="!pickableCells.length" class="anchor-picker-empty">
          暂无已生成的章节图，请先用「一键生成全部图」或单节生成至少一张图。
        </div>
        <div v-else class="anchor-picker-grid">
          <div
            v-for="c in pickableCells"
            :key="c.section.id"
            class="anchor-picker-item"
            :class="{ 'anchor-picker-item--active': c.slot?.image_path === visualAnchor?.anchor_image_path }"
            @click="pickAnchorFromCell(c)"
          >
            <img :src="c.imageUrl!" :alt="`第 ${c.section.order_num || c.index + 1} 节`" />
            <div class="anchor-picker-caption">
              <span>第 {{ c.section.order_num || c.index + 1 }} 节</span>
              <span v-if="c.slot?.image_path === visualAnchor?.anchor_image_path" class="anchor-picker-badge">当前锚点</span>
            </div>
          </div>
        </div>
      </el-dialog>

      <!-- ── 批量操作栏 ── -->
      <div class="batch-bar">
        <div class="batch-bar__row">
          <el-tooltip
            content="为所有未配画意的章节自动生成画意（每节 0.3 积分；已有画意的节不重复扣费）"
            placement="top"
            :show-after="300"
          >
            <el-button
              size="small"
              :icon="Star"
              :loading="batch.suggesting"
              :disabled="batchAnyRunning"
              @click="batchSuggestIntent"
            >
              <span class="batch-btn-label">一键建议画意</span>
              <span class="batch-btn-cost">{{ pendingIntentCount }}节·~{{ (pendingIntentCount * 0.3).toFixed(1) }}积分</span>
            </el-button>
          </el-tooltip>

          <el-tooltip
            content="把所有已配画意的章节批量 AI 扩写成 300+ 字剧本式场景（每节 0.6 积分；24h 同画意命中缓存不扣分）"
            placement="top"
            :show-after="300"
          >
            <el-button
              size="small"
              :icon="MagicStick"
              :loading="batch.enriching"
              :disabled="batchAnyRunning || enrichableCount === 0"
              @click="batchEnrichIntent"
            >
              <span class="batch-btn-label">一键 AI 扩写</span>
              <span class="batch-btn-cost">{{ enrichableCount }}节·~{{ (enrichableCount * 0.6).toFixed(1) }}积分</span>
            </el-button>
          </el-tooltip>

          <el-tooltip
            content="把所有已配画意的章节批量生成中/英文双语提示词（免费，DeepSeek 兜底）"
            placement="top"
            :show-after="300"
          >
            <el-button
              size="small"
              :icon="Document"
              :loading="batch.promptGen"
              :disabled="batchAnyRunning || promptableCount === 0"
              @click="batchGeneratePrompt"
            >
              <span class="batch-btn-label">一键生成提示词</span>
              <span class="batch-btn-cost">{{ promptableCount }}节·免费</span>
            </el-button>
          </el-tooltip>

          <el-tooltip
            :content="storyboardModeTooltip"
            placement="top"
            :show-after="300"
          >
            <el-button
              type="primary"
              size="small"
              :icon="Picture"
              :loading="batch.imageGen"
              :disabled="batchAnyRunning"
              @click="emitBatchImage"
            >
              <span class="batch-btn-label">{{ storyboardMode ? '🎬 故事板生图' : '一键生成全部图' }}</span>
              <span class="batch-btn-cost">{{ totalSections }}节·{{ totalSections * 2 }}积分</span>
            </el-button>
          </el-tooltip>
        </div>

        <div class="batch-bar__row batch-bar__options">
          <el-checkbox v-model="useEnrichInBatch" :disabled="batchAnyRunning" size="small">
            <span class="opt-label"><span class="opt-icon">✨</span> 生图前先 AI 扩写画意</span>
          </el-checkbox>
          <el-checkbox v-model="storyboardMode" :disabled="batchAnyRunning" size="small">
            <span class="opt-label"><span class="opt-icon">🎬</span> 故事板模式（串行 + 锚点参考）</span>
          </el-checkbox>
          <div class="batch-style">
            <span class="batch-engine-label">风格</span>
            <el-select
              v-model="stylePresetIdLocal"
              size="small"
              style="width: 200px;"
              :disabled="batchAnyRunning || !stylePresets.length"
              :placeholder="stylePresets.length ? '继承各节默认' : '加载中…'"
              clearable
              @change="onBatchStyleChange"
            >
              <el-option
                v-for="p in stylePresets"
                :key="p.id"
                :label="p.display_name || p.name"
                :value="p.id"
              >
                <span class="batch-style-name">{{ p.display_name || p.name }}</span>
                <span v-if="p.description" class="batch-style-desc">{{ p.description }}</span>
              </el-option>
            </el-select>
          </div>
          <div class="batch-engine">
            <span class="batch-engine-label">引擎</span>
            <el-select
              v-model="engineLocal"
              size="small"
              style="width: 168px;"
              :disabled="batchAnyRunning"
              placeholder="自动选择"
              @change="(v: string) => emit('engine-change', v)"
            >
              <el-option label="自动选择" value="" />
              <el-option
                v-for="opt in engineOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </div>
        </div>

        <div v-if="batchProgress.total > 0" class="batch-bar__progress">
          <el-progress
            :percentage="Math.round(batchProgress.done / batchProgress.total * 100)"
            :status="batchProgress.fail > 0 ? 'warning' : (batchProgress.done === batchProgress.total ? 'success' : undefined)"
          />
          <div class="batch-bar__stats">
            <span>{{ batchProgress.label }}</span>
            <span>{{ batchProgress.done }}/{{ batchProgress.total }}</span>
            <span v-if="batchProgress.fail" class="stat-fail">失败 {{ batchProgress.fail }}</span>
            <span v-if="batchProgress.skip" class="stat-skip">跳过 {{ batchProgress.skip }}</span>
          </div>
        </div>
      </div>

      <!-- ── 每节配图卡片（行式，宽屏左右、窄屏上下） ── -->
      <div class="cell-list">
        <div
          v-for="cell in cells"
          :key="cell.section.id"
          class="cell"
          :class="{
            'cell--active': cell.section.id === activeSectionId,
            'cell--has-image': !!cell.imageUrl,
            'cell--no-content': !cell.section.has_content,
          }"
        >
          <!-- ── 头部 ── -->
          <div class="cell-head">
            <div class="cell-head__title" @click="$emit('navigate', cell.section.id)">
              <span class="cell-order">{{ cell.section.order_num || cell.index + 1 }}</span>
              <span class="cell-title-text">{{ cell.section.title || cell.section.section_type || `第 ${cell.index + 1} 节` }}</span>
            </div>
            <div class="cell-head__meta">
              <el-tag v-if="cell.imageUrl && cell.slot?.image_status === 'uploaded'" size="small" type="primary" effect="plain">已上传</el-tag>
              <el-tag v-else-if="cell.imageUrl" size="small" type="success" effect="plain">已生成</el-tag>
              <el-tag v-else-if="cell.slot?.prompt_zh || cell.slot?.prompt_en" size="small" type="warning" effect="plain">提示词就绪</el-tag>
              <el-tag v-else-if="cell.slot?.intent_text" size="small" type="warning" effect="plain">已配画意</el-tag>
              <el-tag v-else-if="!cell.section.has_content" size="small" type="info" effect="plain">暂无正文</el-tag>
              <el-tag v-else size="small" type="info" effect="plain">未配置</el-tag>
              <span v-if="cell.slot?.image_provider" class="cell-provider">{{ providerLabel(cell.slot.image_provider) }}</span>
            </div>
            <div class="cell-head__actions">
              <el-tooltip
                content="一键清空本节的画意 / 提示词 / 配图，并清除历史重绘记录（不影响其他节）"
                placement="top"
                :show-after="300"
              >
                <el-button
                  text
                  size="small"
                  :icon="Delete"
                  :disabled="!cell.slot || !!batchAnyRunning || !!generatingImage[cell.section.id]"
                  :loading="!!clearingMap[cell.section.id]"
                  class="cell-clear-btn"
                  @click="clearOneSection(cell)"
                >
                  清空本节
                </el-button>
              </el-tooltip>
              <el-dropdown
                trigger="click"
                placement="bottom-end"
                @command="(cmd: string) => onMoreCommand(cmd, cell)"
              >
                <el-button text size="small" :icon="More" />
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="set-anchor" :disabled="!cell.imageUrl">
                      📌 设为视觉锚点图
                    </el-dropdown-item>
                    <el-dropdown-item command="copy-intent" :disabled="!intentEdits[cell.section.id]">
                      📋 复制画意
                    </el-dropdown-item>
                    <el-dropdown-item command="clear-prompts" :disabled="!cell.slot?.prompt_zh && !cell.slot?.prompt_en">
                      🧹 清空提示词
                    </el-dropdown-item>
                    <el-dropdown-item command="delete-slot" :disabled="!cell.slot" divided>
                      <span style="color: #ef4444;">🗑 清空本节（含历史重绘）</span>
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </div>

          <!-- ── 主体（响应式：宽屏左右、窄屏上下） ── -->
          <div class="cell-body">
            <!-- 缩略图 -->
            <div class="cell-thumb">
              <img
                v-if="cell.imageUrl"
                :src="cell.imageUrl"
                :alt="intentEdits[cell.section.id] || cell.section.title || ''"
                loading="lazy"
                @click="onPreview(cell)"
                @error="onImageError"
              />
              <div v-else class="cell-thumb__placeholder">
                <span v-if="!cell.section.has_content">暂无正文</span>
                <span v-else-if="generatingImage[cell.section.id]">生成中…</span>
                <span v-else>未生成</span>
              </div>
              <div class="cell-thumb__actions" @click.stop>
                <el-upload
                  :auto-upload="false"
                  :show-file-list="false"
                  accept=".jpg,.jpeg,.png"
                  :on-change="(file: any) => onUpload(cell, file)"
                >
                  <el-button text size="small" :icon="Upload" class="thumb-btn">上传</el-button>
                </el-upload>
                <el-button
                  v-if="cell.imageUrl"
                  text
                  size="small"
                  :icon="ZoomIn"
                  class="thumb-btn"
                  @click="onPreview(cell)"
                >
                  预览
                </el-button>
              </div>
            </div>

            <!-- 编辑区 -->
            <div class="cell-editor">
              <!-- 画意 -->
              <div class="block">
                <div class="block-head">
                  <span class="block-label">画意</span>
                  <div class="block-actions">
                    <el-tooltip content="基于本节正文，AI 给 2-3 条候选画意" placement="top" :show-after="300">
                      <el-button
                        text
                        size="small"
                        :icon="Star"
                        :loading="!!suggestingMap[cell.section.id]"
                        :disabled="!cell.section.has_content || batchAnyRunning"
                        @click="suggestOne(cell)"
                      >
                        建议
                        <span class="action-cost">0.3</span>
                      </el-button>
                    </el-tooltip>
                    <el-tooltip content="把简短画意 AI 扩写成 300+ 字剧本式场景描述（24h 缓存）" placement="top" :show-after="300">
                      <el-button
                        text
                        size="small"
                        :icon="MagicStick"
                        :loading="!!enrichingMap[cell.section.id]"
                        :disabled="!intentEdits[cell.section.id] || intentEdits[cell.section.id]?.trim().length < 4 || batchAnyRunning"
                        @click="enrichOne(cell)"
                      >
                        AI 扩写
                        <span class="action-cost">0.6</span>
                      </el-button>
                    </el-tooltip>
                  </div>
                </div>
                <el-input
                  v-model="intentEdits[cell.section.id]"
                  type="textarea"
                  :rows="2"
                  :placeholder="cell.section.has_content ? '描述这张配图要传达什么（如：医生向患者讲解血压管理的温馨场景）' : '本节暂无正文，请先生成正文后再配画意'"
                  :disabled="batchAnyRunning"
                  @blur="saveIntent(cell)"
                />
                <div v-if="suggestionsMap[cell.section.id]?.length" class="suggestions">
                  <div
                    v-for="s in suggestionsMap[cell.section.id]"
                    :key="s.intent"
                    class="suggestion-item"
                    @click="applySuggestion(cell, s.intent)"
                  >
                    <span class="suggestion-text">{{ s.intent }}</span>
                    <span v-if="s.reason" class="suggestion-reason">{{ s.reason }}</span>
                  </div>
                </div>
              </div>

              <!-- 提示词 -->
              <div class="block">
                <div class="block-head">
                  <span class="block-label">
                    提示词
                    <span class="prompt-lang-tag">{{ promptLangLabel }}</span>
                  </span>
                  <div class="block-actions">
                    <el-tooltip
                      :content="`基于画意生成${promptLangShort}提示词；图生成时也会自动生成（免费）`"
                      placement="top"
                      :show-after="300"
                    >
                      <el-button
                        text
                        size="small"
                        :icon="Document"
                        :loading="!!promptingMap[cell.section.id]"
                        :disabled="!intentEdits[cell.section.id] || intentEdits[cell.section.id]?.trim().length < 4 || batchAnyRunning"
                        @click="generatePromptOne(cell)"
                      >
                        {{ promptButtonLabel }}
                      </el-button>
                    </el-tooltip>
                  </div>
                </div>
                <div
                  v-if="hasVisiblePrompt(cell)"
                  :class="showBothPromptCols(cell) ? 'prompt-cols' : 'prompt-single'"
                >
                  <div v-if="showZhCol(cell)" class="prompt-col">
                    <div class="prompt-col__head">
                      <span>中文</span>
                      <el-button text size="small" @click="copyText(promptZhEdits[cell.section.id])">复制</el-button>
                    </div>
                    <el-input
                      v-model="promptZhEdits[cell.section.id]"
                      type="textarea"
                      :rows="3"
                      :disabled="batchAnyRunning"
                      :placeholder="providerLang === 'zh' ? '点上方按钮生成中文提示词' : ''"
                      class="prompt-textarea"
                      @blur="savePromptZh(cell)"
                    />
                  </div>
                  <div v-if="showEnCol(cell)" class="prompt-col">
                    <div class="prompt-col__head">
                      <span>英文</span>
                      <el-button text size="small" @click="copyText(promptEnEdits[cell.section.id])">复制</el-button>
                    </div>
                    <el-input
                      v-model="promptEnEdits[cell.section.id]"
                      type="textarea"
                      :rows="3"
                      :disabled="batchAnyRunning"
                      :placeholder="providerLang === 'en' ? '点上方按钮生成英文提示词' : ''"
                      class="prompt-textarea"
                      @blur="savePromptEn(cell)"
                    />
                  </div>
                </div>
                <div v-else class="prompt-empty">
                  {{ promptEmptyHint }}
                </div>
              </div>

              <!-- 反向提示词（自动合并风格预设 + 全局禁词，只读 + 可复制） -->
              <div v-if="cell.slot?.negative_words && providerNeedsNegative" class="block negative-block">
                <div class="block-head block-head--toggle" @click="toggleNegative(cell.section.id)">
                  <span class="block-label">
                    反向提示词
                    <el-tooltip
                      content="自动合并自风格预设的负面词与全局禁词；图像引擎会自动避免这些元素。仅展示，不可手工编辑。"
                      placement="top"
                      :show-after="300"
                    >
                      <el-icon class="block-label-info"><InfoFilled /></el-icon>
                    </el-tooltip>
                    <el-tag size="small" type="info" effect="plain" style="margin-left: 0.4rem;">
                      {{ negativeWordCount(cell.slot.negative_words) }} 词
                    </el-tag>
                  </span>
                  <div class="block-actions" @click.stop>
                    <el-button text size="small" @click="copyText(cell.slot.negative_words)">复制</el-button>
                    <el-button text size="small" @click="toggleNegative(cell.section.id)">
                      {{ negativeOpen[cell.section.id] ? '收起' : '展开' }}
                    </el-button>
                  </div>
                </div>
                <div v-if="negativeOpen[cell.section.id]" class="negative-text">
                  {{ cell.slot.negative_words }}
                </div>
              </div>

              <!-- 画幅 + 微调 -->
              <div class="cell-tune">
                <div class="cell-tune__row cell-tune__row--aspect">
                  <span class="cell-tune__label">画幅</span>
                  <el-radio-group
                    :model-value="getCellAspectValue(cell)"
                    size="small"
                    :disabled="batchAnyRunning"
                    @update:model-value="(v: any) => setCellAspect(cell, v)"
                  >
                    <el-radio-button label="16:9" value="16:9">横版 16:9</el-radio-button>
                    <el-radio-button label="1:1" value="1:1">方形 1:1</el-radio-button>
                    <el-radio-button label="3:4" value="3:4">竖版 3:4</el-radio-button>
                    <el-radio-button label="small" value="small">小图 1:1</el-radio-button>
                  </el-radio-group>
                  <div class="aspect-preview" :title="aspectPixelText(getCellAspectValue(cell))">
                    <div
                      class="aspect-preview__box"
                      :class="`aspect-preview__box--${aspectClass(getCellAspectValue(cell))}`"
                    >
                      <span class="aspect-preview__label">{{ aspectShortLabel(getCellAspectValue(cell)) }}</span>
                    </div>
                    <span class="aspect-preview__pixels">{{ aspectPixelText(getCellAspectValue(cell)) }}</span>
                  </div>
                </div>

                <!-- 形状构图（可选）-->
                <div class="cell-tune__row">
                  <span class="cell-tune__label">形状</span>
                  <el-select
                    :model-value="adjustmentEdits[cell.section.id].shape || ''"
                    size="small"
                    style="width: 200px;"
                    :disabled="batchAnyRunning"
                    @change="(v: any) => onShapeChange(cell, v)"
                  >
                    <el-option label="不限定（矩形）" value="" />
                    <el-option label="圆形" value="circle" />
                    <el-option label="椭圆" value="ellipse" />
                    <el-option label="直角三角 · 左上" value="triangle_top_left" />
                    <el-option label="直角三角 · 右上" value="triangle_top_right" />
                    <el-option label="直角三角 · 左下" value="triangle_bottom_left" />
                    <el-option label="直角三角 · 右下" value="triangle_bottom_right" />
                  </el-select>
                  <div
                    v-if="adjustmentEdits[cell.section.id].shape"
                    class="shape-preview"
                    :title="`形状构图：${shapeLabel(adjustmentEdits[cell.section.id].shape)}`"
                  >
                    <div
                      class="shape-preview__box"
                      :class="`shape-preview__box--${adjustmentEdits[cell.section.id].shape}`"
                    ></div>
                    <span class="shape-preview__hint">画面会按此形状构图，矩形画幅不变</span>
                  </div>
                </div>

                <div class="cell-tune__row cell-tune__adjusts">
                  <span class="cell-tune__label">微调</span>
                  <div class="cell-tune__input-wrap">
                    <el-input
                      v-model="adjustmentEdits[cell.section.id].composition_zh"
                      size="small"
                      placeholder="构图（如：特写 / 中景 / 全景）"
                      class="cell-tune__input"
                      :disabled="batchAnyRunning"
                      clearable
                      @blur="onAdjustChange(cell)"
                      @clear="onAdjustChange(cell)"
                    />
                    <div class="cell-tune__quick">
                      <el-tag
                        v-for="tag in COMPOSITION_QUICK_TAGS"
                        :key="tag"
                        size="small"
                        effect="plain"
                        class="cell-tune__quick-tag"
                        @click="applyQuickCompositionTag(cell, tag)"
                      >{{ tag }}</el-tag>
                    </div>
                  </div>
                  <el-input
                    v-model="adjustmentEdits[cell.section.id].lighting_zh"
                    size="small"
                    placeholder="光线（如：自然光 / 暖光 / 冷光）"
                    class="cell-tune__input"
                    :disabled="batchAnyRunning"
                    clearable
                    @blur="onAdjustChange(cell)"
                    @clear="onAdjustChange(cell)"
                  />
                  <el-input
                    v-model="adjustmentEdits[cell.section.id].color_zh"
                    size="small"
                    placeholder="色调（如：暖色调 / 冷色调）"
                    class="cell-tune__input"
                    :disabled="batchAnyRunning"
                    clearable
                    @blur="onAdjustChange(cell)"
                    @clear="onAdjustChange(cell)"
                  />
                </div>
              </div>

              <!-- 操作 -->
              <div class="cell-cta">
                <el-button
                  type="primary"
                  size="default"
                  :icon="Picture"
                  :loading="!!generatingImage[cell.section.id]"
                  :disabled="!intentEdits[cell.section.id] || intentEdits[cell.section.id]?.trim().length < 4 || batchAnyRunning"
                  @click="generateImageOne(cell)"
                >
                  {{ cell.imageUrl ? '🔄 重新生成本节图' : '🎨 生成本节图' }}
                  <span class="cta-cost">2 积分</span>
                </el-button>
                <span v-if="cell.imageUrl" class="cta-hint">点缩略图可放大预览</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- ── AI 扩写对话框 ── -->
    <IntentEnrichDialog
      v-model="enrichDialogVisible"
      :initial-intent="enrichTargetIntent"
      :section-text="enrichTargetText"
      :topic="topic || ''"
      :section-type="enrichTargetType"
      :auto-enrich="true"
      @apply="onEnrichApply"
    />

    <!-- ── 大图预览 ── -->
    <el-dialog v-model="previewVisible" :title="previewTitle" width="780" align-center>
      <img v-if="previewUrl" :src="previewUrl" alt="预览" style="width: 100%; border-radius: 6px;" />
      <div v-if="previewIntent" class="preview-intent">{{ previewIntent }}</div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Star, MagicStick, Document, Picture, Upload, ZoomIn, More, InfoFilled, Delete,
} from '@element-plus/icons-vue'
import { api } from '@/api'
import IntentEnrichDialog from './IntentEnrichDialog.vue'
import VisualAnchorPanel from './VisualAnchorPanel.vue'

const props = defineProps<{
  articleId: number
  sections: any[]
  slots: any[]
  activeSectionId?: number | null
  preferredProvider?: string
  topic?: string
  /** 来自 Article.vue：当前文章的视觉锚点（用于"设为锚点图"操作） */
  visualAnchor?: any
  /** 来自 Article.vue：批量生图的全局进度（仅用于显示） */
  externalImageBatch?: { total: number; done: number; fail: number; skip: number; running: boolean }
  /**
   * 来自 Article.vue：编辑器中的实时合并内容（TipTap JSON）。
   * 配图管理在「合并视图」下用它做画意建议的真实数据源，
   * 而不是后端 sections[*].content_excerpt 那份"上次加载快照"。
   */
  liveContentJson?: any
}>()

const emit = defineEmits<{
  navigate: [sectionId: number]
  slotUpdated: [slot: any]
  slotRemoved: [slotId: number]
  /** 通知父组件触发批量生图（包含 storyboard / use-enrich 选项） */
  batchImage: [opts: { useEnrich: boolean; storyboard: boolean; engine: string }]
  /** 用户更新了引擎选择 */
  engineChange: [engine: string]
  /** 通知父组件刷新视觉锚点（如设为锚点图后） */
  visualAnchorRefresh: []
  /** 视觉锚点子面板更新（角色 / 风格 / 锚点图变更后由 VAP 抛出） */
  visualAnchorUpdated: [anchor: any]
}>()

// ── Provider 显示名 ──
const PROVIDER_LABELS: Record<string, string> = {
  jimeng: '即梦', kling: '可灵', midjourney: 'MJ',
  gpt_image: 'GPT Image', openai: 'DALL·E', gemini_image: 'Gemini',
  moonshot_image: 'Kimi', wanx: '通义', siliconflow: '硅基', wenxin: '文心',
  comfyui_local: 'ComfyUI', comfyui_cloud: 'ComfyUI Cloud', pollinations: 'Pollinations',
  jimeng_avatar: '即梦人像',
  manual_upload: '手动上传',
}
function providerLabel(p: string) { return PROVIDER_LABELS[p] || p }

const engineOptions = [
  { value: 'jimeng', label: '即梦 AI' },
  { value: 'kling', label: '可灵 AI' },
  { value: 'midjourney', label: 'Midjourney' },
  { value: 'gpt_image', label: 'GPT Image' },
  { value: 'openai', label: 'DALL·E 3' },
  { value: 'gemini_image', label: 'Google Gemini' },
  { value: 'moonshot_image', label: 'Kimi 图像' },
  { value: 'comfyui_local', label: 'ComfyUI（本地）' },
  { value: 'comfyui_cloud', label: 'ComfyUI Cloud' },
  { value: 'wanx', label: '通义万相' },
  { value: 'siliconflow', label: '硅基流动' },
  { value: 'wenxin', label: '文心一格' },
]

// ── 引擎本地状态（双向同步父组件 preferred-provider） ──
const engineLocal = ref(props.preferredProvider || '')
watch(() => props.preferredProvider, (v) => { if ((v || '') !== engineLocal.value) engineLocal.value = v || '' })

// ── Provider → 语言 / 是否需要负向词（与后端 prompt_engine 保持一致） ──
const PROVIDER_LANG_MAP: Record<string, 'zh' | 'en'> = {
  kling: 'zh', jimeng: 'zh', wenxin: 'zh', wanx: 'zh', tongyi: 'zh',
  moonshot_image: 'zh', gpt_image: 'zh',
  openai: 'en', dalle3: 'en', midjourney: 'en', siliconflow: 'en',
  comfyui_local: 'en', comfyui_cloud: 'en', gemini_image: 'en', pollinations: 'en',
}
const PROVIDER_NEG_MAP: Record<string, boolean> = {
  kling: false, jimeng: false, wenxin: false, wanx: false, tongyi: false,
  moonshot_image: false, gpt_image: false, openai: false, dalle3: false,
  gemini_image: false, pollinations: false,
  midjourney: true, siliconflow: true, comfyui_local: true, comfyui_cloud: true,
}
const providerLang = computed<'zh' | 'en' | 'both'>(() => {
  const p = (engineLocal.value || '').trim().toLowerCase()
  if (!p) return 'both'
  return PROVIDER_LANG_MAP[p] || 'both'
})
const providerNeedsNegative = computed<boolean>(() => {
  const p = (engineLocal.value || '').trim().toLowerCase()
  if (!p) return true
  return PROVIDER_NEG_MAP[p] !== false
})
const promptLangShort = computed(() => {
  if (providerLang.value === 'zh') return '中文'
  if (providerLang.value === 'en') return '英文'
  return '中英'
})
const promptLangLabel = computed(() => {
  if (providerLang.value === 'zh') return '中文（适配国内绘图引擎）'
  if (providerLang.value === 'en') return '英文（适配 SD / FLUX / MJ / DALL-E）'
  return '中 / 英双语'
})
const promptButtonLabel = computed(() => `生成${promptLangShort.value}`)
const promptEmptyHint = computed(() => {
  if (providerLang.value === 'zh') return '画意填好后点「生成中文」生成中文提示词；也可直接点「生成本节图」由系统自动一气呵成。'
  if (providerLang.value === 'en') return '画意填好后点「生成英文」生成英文提示词；也可直接点「生成本节图」由系统自动一气呵成。'
  return '画意填好后点「生成中英」可单独生成提示词；也可直接点「生成本节图」由系统自动一气呵成。'
})

function showZhCol(cell: any): boolean {
  if (providerLang.value === 'en') return false
  if (providerLang.value === 'zh') return true
  return !!promptZhEdits[cell.section.id]
}
function showEnCol(cell: any): boolean {
  if (providerLang.value === 'zh') return false
  if (providerLang.value === 'en') return true
  return !!promptEnEdits[cell.section.id]
}
function showBothPromptCols(cell: any): boolean {
  return showZhCol(cell) && showEnCol(cell)
}
function hasVisiblePrompt(cell: any): boolean {
  const id = cell.section.id
  if (providerLang.value === 'zh') return !!promptZhEdits[id]
  if (providerLang.value === 'en') return !!promptEnEdits[id]
  return !!(promptZhEdits[id] || promptEnEdits[id])
}

// ── slots 索引化 ──
const slotsBySection = computed(() => {
  const m: Record<number, any> = {}
  for (const s of props.slots || []) {
    if (s?.section_id != null) m[s.section_id] = s
  }
  return m
})

/**
 * 历史上传图曾写入绝对路径（如 /Users/xxx/.linscio_medcomm/images/contest/xxx.jpg），
 * 而 /api/v1/imagegen/serve 只接受相对路径并拒绝以 / 开头的入参。这里做一次兼容：
 *   - 若是相对路径直接用；
 *   - 若是绝对路径，截取出 images/... 段（含 contest 子目录或年月子目录），
 *     交给 serve_image 用 app_data_root 拼接。
 */
function _toServePath(p: string): string {
  if (!p) return ''
  if (!p.startsWith('/')) return p
  const m = p.match(/(?:^|\/)(images\/.+)$/)
  return m ? m[1] : ''
}

const cells = computed(() => {
  return (props.sections || []).map((sec, idx) => {
    const slot = slotsBySection.value[sec.id] || null
    let imageUrl = ''
    if (slot?.image_path) {
      const rel = _toServePath(String(slot.image_path))
      if (rel) {
        imageUrl = `/api/v1/imagegen/serve?path=${encodeURIComponent(rel)}&t=${slot.updated_at || ''}`
      }
    }
    return { section: sec, slot, imageUrl, index: idx }
  })
})

const totalSections = computed(() => cells.value.length)
const pendingIntentCount = computed(() =>
  cells.value.filter(c => c.section.has_content && !(intentEdits[c.section.id] || '').trim()).length,
)
const enrichableCount = computed(() =>
  cells.value.filter(c => c.section.has_content && (intentEdits[c.section.id] || '').trim().length >= 4).length,
)
const promptableCount = computed(() =>
  cells.value.filter(c =>
    c.section.has_content &&
    (intentEdits[c.section.id] || '').trim().length >= 4 &&
    !(c.slot?.prompt_zh || c.slot?.prompt_en),
  ).length,
)

// ── 本地编辑 state（按 section_id） ──
const intentEdits = reactive<Record<number, string>>({})
const promptZhEdits = reactive<Record<number, string>>({})
const promptEnEdits = reactive<Record<number, string>>({})
const aspectRatioEdits = reactive<Record<number, string>>({})
const adjustmentEdits = reactive<Record<number, {
  composition_zh: string
  lighting_zh: string
  color_zh: string
  shape: string
}>>({})

// ── 形状构图（与后端 SHAPE_COMPOSITION_HINTS 一一对应）──
const SHAPE_LABELS: Record<string, string> = {
  '': '不限定（矩形）',
  circle: '圆形',
  ellipse: '椭圆',
  triangle_top_left: '直角三角 · 左上',
  triangle_top_right: '直角三角 · 右上',
  triangle_bottom_left: '直角三角 · 左下',
  triangle_bottom_right: '直角三角 · 右下',
}
function shapeLabel(s: string | undefined): string {
  return SHAPE_LABELS[s || ''] || (s || '')
}

const COMPOSITION_QUICK_TAGS = ['特写', '中景', '全景', '俯视', '仰视'] as const
const suggestingMap = reactive<Record<number, boolean>>({})
const enrichingMap = reactive<Record<number, boolean>>({})
const promptingMap = reactive<Record<number, boolean>>({})
const generatingImage = reactive<Record<number, boolean>>({})
const suggestionsMap = reactive<Record<number, Array<{ intent: string; reason?: string }>>>({})
const negativeOpen = reactive<Record<number, boolean>>({})

function toggleNegative(sectionId: number) {
  negativeOpen[sectionId] = !negativeOpen[sectionId]
}

function negativeWordCount(text: string | null | undefined): number {
  if (!text) return 0
  return text.split(/[,，;；\s]+/).filter(Boolean).length
}

// ── 锚点图选择弹窗 ──
const anchorPickerVisible = ref(false)
const pickableCells = computed(() => cells.value.filter(c => !!c.imageUrl))

function openAnchorPicker() {
  if (!pickableCells.value.length) {
    ElMessage.warning('暂无已生成的章节图，请先生成至少一张')
    return
  }
  anchorPickerVisible.value = true
}

async function pickAnchorFromCell(cell: any) {
  if (!cell.slot?.image_path) return
  try {
    await api.imageIntent.updateVisualAnchor(props.articleId, {
      anchor_image_path: cell.slot.image_path,
      anchor_source: 'manual_pick',
    })
    ElMessage.success(`已将第 ${cell.section.order_num || cell.index + 1} 节图设为视觉锚点`)
    emit('visualAnchorRefresh')
    anchorPickerVisible.value = false
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '设置锚点失败')
  }
}

// ── 风格预设（来自后端） ──
const stylePresets = ref<any[]>([])
const stylePresetIdLocal = ref<number | null>(null)

async function loadStylePresets() {
  try {
    const res = await api.imageIntent.getStylePresets()
    stylePresets.value = res.data?.items || []
  } catch {
    stylePresets.value = []
  }
}
void loadStylePresets()

// 同步 props.slots → 本地 edits
watch(() => props.slots, (slots) => {
  for (const c of cells.value) {
    const id = c.section.id
    const slot = slotsBySection.value[id]
    // 只在本地未编辑过、或后端值更新时同步（避免覆盖用户正在敲的内容）
    if (!(id in intentEdits)) intentEdits[id] = slot?.intent_text || ''
    else if ((slot?.intent_text || '') !== intentEdits[id] && document.activeElement?.tagName !== 'TEXTAREA') {
      intentEdits[id] = slot?.intent_text || ''
    }
    if (!(id in promptZhEdits)) promptZhEdits[id] = slot?.prompt_zh || ''
    else if ((slot?.prompt_zh || '') !== promptZhEdits[id] && document.activeElement?.tagName !== 'TEXTAREA') {
      promptZhEdits[id] = slot?.prompt_zh || ''
    }
    if (!(id in promptEnEdits)) promptEnEdits[id] = slot?.prompt_en || ''
    else if ((slot?.prompt_en || '') !== promptEnEdits[id] && document.activeElement?.tagName !== 'TEXTAREA') {
      promptEnEdits[id] = slot?.prompt_en || ''
    }
    // 画幅
    if (!(id in aspectRatioEdits)) {
      aspectRatioEdits[id] = slot?.aspect_ratio || '16:9'
    } else if ((slot?.aspect_ratio || '16:9') !== aspectRatioEdits[id] && !document.activeElement?.matches?.('input,textarea')) {
      aspectRatioEdits[id] = slot?.aspect_ratio || '16:9'
    }
    // 微调
    if (!(id in adjustmentEdits)) {
      const adj = slot?.user_adjustments || {}
      adjustmentEdits[id] = {
        composition_zh: adj.composition_zh || '',
        lighting_zh: adj.lighting_zh || '',
        color_zh: adj.color_zh || '',
        shape: adj.shape || '',
      }
    } else {
      const adj = slot?.user_adjustments || {}
      const cur = adjustmentEdits[id]
      // 仅在未聚焦输入框时同步，避免打字时被覆盖
      if (!document.activeElement?.matches?.('input,textarea')) {
        if ((adj.composition_zh || '') !== cur.composition_zh) cur.composition_zh = adj.composition_zh || ''
        if ((adj.lighting_zh || '') !== cur.lighting_zh) cur.lighting_zh = adj.lighting_zh || ''
        if ((adj.color_zh || '') !== cur.color_zh) cur.color_zh = adj.color_zh || ''
        if ((adj.shape || '') !== cur.shape) cur.shape = adj.shape || ''
      }
    }
  }
  // 推断批量栏当前默认风格：如果所有 slot 风格一致，回填到下拉
  if (stylePresetIdLocal.value == null && (slots || []).length) {
    const ids = (slots || []).map((s: any) => s?.style_preset_id).filter(Boolean)
    if (ids.length && ids.every((x: number) => x === ids[0])) {
      stylePresetIdLocal.value = ids[0]
    }
  }
}, { immediate: true, deep: true })

// ── 批量状态 ──
const batch = reactive({
  suggesting: false,
  enriching: false,
  promptGen: false,
  imageGen: false,
})
const useEnrichInBatch = ref(false)
const storyboardMode = ref(false)

const batchAnyRunning = computed(() =>
  batch.suggesting || batch.enriching || batch.promptGen || batch.imageGen ||
  !!props.externalImageBatch?.running,
)

const batchProgress = computed(() => {
  // 若父组件正在跑生图批次，优先显示父组件进度
  if (props.externalImageBatch?.running || (props.externalImageBatch?.total || 0) > 0) {
    const ext = props.externalImageBatch!
    return {
      total: ext.total || 0,
      done: ext.done || 0,
      fail: ext.fail || 0,
      skip: ext.skip || 0,
      label: '🎨 生图',
    }
  }
  return localBatchProgress
})
const localBatchProgress = reactive({
  total: 0,
  done: 0,
  fail: 0,
  skip: 0,
  label: '',
})
function resetLocalBatchProgress(label = '') {
  localBatchProgress.total = 0
  localBatchProgress.done = 0
  localBatchProgress.fail = 0
  localBatchProgress.skip = 0
  localBatchProgress.label = label
}

const storyboardModeTooltip = computed(() => {
  if (!storyboardMode.value) return '一键为所有章节生成 AI 配图（每节 2 积分）'
  return '🎬 故事板：串行生图 + 第一张完成后自动作为后续所有图的视觉锚点参考。一致性最强，耗时增加 ≈ 30%。'
})

// ── 工具：建画位（不存在时新建） ──
async function _ensureSlotForSection(sec: any, intentSeed: string): Promise<any> {
  const existing = slotsBySection.value[sec.id]
  if (existing) return existing
  try {
    const res = await api.imageIntent.createImageSlot(props.articleId, {
      section_id: sec.id,
      intent_text: intentSeed || '',
      aspect_ratio: aspectRatioEdits[sec.id] || '16:9',
      style_preset_id: stylePresetIdLocal.value || null,
    })
    if (res.data) emit('slotUpdated', res.data)
    return res.data
  } catch {
    return null
  }
}

/** 把 TipTap node 抽成纯文本，块级节点之间补换行。 */
function _nodePlainText(node: any): string {
  if (!node || typeof node !== 'object') return ''
  if (node.type === 'text') return String(node.text || '')
  if (node.type === 'hardBreak') return '\n'
  const children: any[] = Array.isArray(node.content) ? node.content : []
  const inner = children.map(_nodePlainText).join('')
  if (node.type === 'paragraph' || node.type === 'heading' || node.type === 'blockquote'
      || node.type === 'listItem' || node.type === 'codeBlock') {
    return inner + '\n'
  }
  return inner
}

/** 把 TipTap doc 转成块数组（含 inner 纯文本），便于按 H2 拆分。 */
function _docToBlocks(doc: any): Array<{ type: string; level?: number; text: string }> {
  if (!doc || typeof doc !== 'object') return []
  const nodes: any[] = Array.isArray(doc.content) ? doc.content : []
  return nodes.map(n => ({
    type: String(n?.type || ''),
    level: Number((n?.attrs as any)?.level || 0) || undefined,
    text: _nodePlainText(n).trim(),
  }))
}

/** 以 H2/H3 标题为边界把合并文档切成 chunks：[{title, text}]。 */
function _splitByHeading(doc: any): Array<{ title: string; text: string }> {
  const blocks = _docToBlocks(doc)
  const chunks: Array<{ title: string; text: string }> = []
  let cur: { title: string; lines: string[] } | null = null
  for (const b of blocks) {
    if (b.type === 'heading' && (b.level === 2 || b.level === 3)) {
      if (cur) chunks.push({ title: cur.title, text: cur.lines.join('\n').trim() })
      cur = { title: b.text, lines: [] }
      continue
    }
    if (!cur) cur = { title: '', lines: [] }
    if (b.text) cur.lines.push(b.text)
  }
  if (cur) chunks.push({ title: cur.title, text: cur.lines.join('\n').trim() })
  return chunks.filter(c => c.title || c.text)
}

/** 实时全文（取自编辑器 props.liveContentJson）。当编辑器没值时退到 sections 的 content_excerpt 拼接。 */
const liveFullText = computed(() => {
  const doc = props.liveContentJson
  if (doc && typeof doc === 'object') {
    const txt = (Array.isArray(doc.content) ? doc.content : [])
      .map((n: any) => _nodePlainText(n))
      .join('\n')
      .trim()
    if (txt) return txt
  }
  // fallback：把所有 section 的 excerpt 拼起来
  const parts: string[] = []
  for (const s of props.sections || []) {
    const t = (s?.content_excerpt || s?.content_text || '').trim()
    if (t) parts.push(t)
  }
  return parts.join('\n\n').trim()
})

/** 按 H2 标题切分实时全文 → 章节标题(去除括号 / 空白后) → 文本 chunk。 */
const liveChunksByTitle = computed<Record<string, string>>(() => {
  const doc = props.liveContentJson
  if (!doc) return {}
  const chunks = _splitByHeading(doc)
  const out: Record<string, string> = {}
  for (const c of chunks) {
    const key = (c.title || '').trim()
    if (!key) continue
    out[key] = c.text
  }
  return out
})

function _normalizeTitle(s: string): string {
  return String(s || '').replace(/[\s\u3000（）()【】\[\]·、，,。]/g, '').toLowerCase()
}

/** 配图管理实时取节文本：
 *  ① 若编辑器实时内容里有 H2/H3 与本节标题匹配，用切到的那一段；
 *  ② 否则若该节自带后端 excerpt（非合并模式或后端 fallback 已注入），用后端 excerpt；
 *  ③ 兜底：用编辑器实时全文。
 *  这样在合并视图下，每节的"建议画意 / 扩写 / 提示词 / 生图"都能跟上编辑器最新内容。
 */
function _sectionPlainText(sec: any): string {
  if (!sec) return ''
  // ① 标题匹配
  const titleKey = _normalizeTitle(sec.title || '')
  if (titleKey) {
    const map = liveChunksByTitle.value
    for (const k of Object.keys(map)) {
      if (_normalizeTitle(k) === titleKey) {
        const t = (map[k] || '').trim()
        if (t) return t
      }
    }
  }
  // ② 后端 excerpt（一般是合并模式下的全文 fallback，或非合并模式下本节文本）
  if (typeof sec.content_excerpt === 'string' && sec.content_excerpt.trim()) {
    return sec.content_excerpt.trim()
  }
  if (typeof sec.content_text === 'string' && sec.content_text.trim()) {
    return sec.content_text.trim()
  }
  // ③ 编辑器实时全文兜底
  return liveFullText.value
}

// ── 单条画意：建议 ──
async function suggestOne(cell: any) {
  const sec = cell.section
  if (!sec.has_content) {
    ElMessage.warning('当前章节暂无正文，无法建议画意')
    return
  }
  const sectionText = _sectionPlainText(sec)
  if (!sectionText || sectionText.length < 30) {
    ElMessage.warning(`正文过短（${sectionText.length} 字 < 30），跳过建议`)
    return
  }
  suggestingMap[sec.id] = true
  // 已为其它章节生成的画意，作为 prior_intents 传给 LLM，让本节有意做差异化
  const priorIntents = cells.value
    .filter((c: any) => c.section.id !== sec.id)
    .map((c: any) => (intentEdits[c.section.id] || '').trim())
    .filter((x: string) => !!x)
    .slice(-6)
  try {
    const res = await api.imageIntent.suggestIntent({
      section_text: sectionText,
      topic: props.topic,
      section_type: sec.section_type,
      section_title: sec.title || sec.section_type || '',
      prior_intents: priorIntents,
    })
    const list = res.data?.suggestions || []
    if (!list.length) {
      ElMessage.info('暂无画意建议')
      suggestionsMap[sec.id] = []
    } else {
      suggestionsMap[sec.id] = list
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '建议失败')
  } finally {
    suggestingMap[sec.id] = false
  }
}

function applySuggestion(cell: any, intent: string) {
  intentEdits[cell.section.id] = intent
  suggestionsMap[cell.section.id] = []
  void saveIntent(cell)
}

// ── 单条画意：AI 扩写 ──
const enrichDialogVisible = ref(false)
const enrichTargetIntent = ref('')
const enrichTargetText = ref('')
const enrichTargetType = ref('')
const pendingEnrichCell = ref<any>(null)

async function enrichOne(cell: any) {
  const sec = cell.section
  const intent = (intentEdits[sec.id] || '').trim()
  if (intent.length < 4) {
    ElMessage.warning('请先填写画意（至少 4 字）')
    return
  }
  enrichTargetIntent.value = intent
  enrichTargetText.value = _sectionPlainText(sec)
  enrichTargetType.value = sec.section_type || ''
  pendingEnrichCell.value = cell
  enrichDialogVisible.value = true
}

async function onEnrichApply(text: string, _source: 'original' | 'enriched') {
  const cell = pendingEnrichCell.value
  pendingEnrichCell.value = null
  if (!cell) return
  intentEdits[cell.section.id] = text
  await saveIntent(cell, { clearPrompts: true })
}

// ── 单条画意：保存 ──
async function saveIntent(cell: any, opts: { clearPrompts?: boolean } = {}) {
  const sec = cell.section
  const newIntent = (intentEdits[sec.id] || '').trim()
  let slot = cell.slot
  if (!slot && newIntent) {
    slot = await _ensureSlotForSection(sec, newIntent)
    if (!slot) return
  }
  if (!slot) return
  if ((slot.intent_text || '') === newIntent && !opts.clearPrompts) return
  try {
    const payload: any = { intent_text: newIntent }
    if (opts.clearPrompts) {
      payload.prompt_zh = ''
      payload.prompt_en = ''
      promptZhEdits[sec.id] = ''
      promptEnEdits[sec.id] = ''
    }
    const upd = await api.imageIntent.updateImageSlot(slot.id, payload)
    if (upd.data) emit('slotUpdated', upd.data)
  } catch {
    /* ignore */
  }
}

// ── 单条提示词：保存 ──
async function savePromptZh(cell: any) {
  const sec = cell.section
  const slot = cell.slot
  if (!slot) return
  const v = promptZhEdits[sec.id] || ''
  if ((slot.prompt_zh || '') === v) return
  try {
    const upd = await api.imageIntent.updateImageSlot(slot.id, { prompt_zh: v })
    if (upd.data) emit('slotUpdated', upd.data)
  } catch { /* ignore */ }
}
async function savePromptEn(cell: any) {
  const sec = cell.section
  const slot = cell.slot
  if (!slot) return
  const v = promptEnEdits[sec.id] || ''
  if ((slot.prompt_en || '') === v) return
  try {
    const upd = await api.imageIntent.updateImageSlot(slot.id, { prompt_en: v })
    if (upd.data) emit('slotUpdated', upd.data)
  } catch { /* ignore */ }
}

// ── 画幅 / 微调：保存到 slot ──
async function ensureSlotForCell(cell: any) {
  let slot = cell.slot
  if (!slot) {
    try {
      const cur = (intentEdits[cell.section.id] || '').trim() || cell.section?.intent_text || ''
      const created = await api.imageIntent.createImageSlot(props.articleId, {
        section_id: cell.section.id,
        intent_text: cur,
        aspect_ratio: aspectRatioEdits[cell.section.id] || '16:9',
        style_preset_id: stylePresetIdLocal.value || null,
      })
      slot = created.data
      if (slot) emit('slotUpdated', slot)
    } catch { return null }
  }
  return slot
}

// 直接读取最稳定的画幅值（即便本地 reactive Record 还没初始化也能拿到正确值）
function getCellAspectValue(cell: any): string {
  const id = cell?.section?.id
  if (id != null && aspectRatioEdits[id]) return aspectRatioEdits[id]
  return cell?.slot?.aspect_ratio || '16:9'
}

// 与后端 contest.py 的 _ASPECT_TO_PIXELS 一一对应
const ASPECT_PIXELS: Record<string, [number, number]> = {
  '16:9':  [1792, 1024],
  '1:1':   [1024, 1024],
  '3:4':   [1024, 1792],
  'small': [512, 512],
}
function aspectClass(v: string): string {
  if (v === '16:9') return 'wide'
  if (v === '3:4')  return 'tall'
  if (v === 'small') return 'small'
  return 'square'
}
function aspectShortLabel(v: string): string {
  return v === 'small' ? '小 1:1' : v
}
function aspectPixelText(v: string): string {
  const px = ASPECT_PIXELS[v]
  return px ? `${px[0]} × ${px[1]} px` : v
}

async function setCellAspect(cell: any, v: string) {
  const aspect = String(v || '16:9')
  aspectRatioEdits[cell.section.id] = aspect
  await onAspectChange(cell)
}

async function onAspectChange(cell: any) {
  const slot = await ensureSlotForCell(cell)
  if (!slot) return
  const v = aspectRatioEdits[cell.section.id] || '16:9'
  if ((slot.aspect_ratio || '') === v) return
  try {
    const upd = await api.imageIntent.updateImageSlot(slot.id, { aspect_ratio: v })
    if (upd.data) emit('slotUpdated', upd.data)
  } catch { /* ignore */ }
}

function _adjustsEqual(a: any, b: any) {
  return (a?.composition_zh || '') === (b?.composition_zh || '') &&
    (a?.lighting_zh || '') === (b?.lighting_zh || '') &&
    (a?.color_zh || '') === (b?.color_zh || '') &&
    (a?.shape || '') === (b?.shape || '')
}

async function onAdjustChange(cell: any) {
  const slot = await ensureSlotForCell(cell)
  if (!slot) return
  const cur = adjustmentEdits[cell.section.id]
  const old = slot.user_adjustments || {}
  if (_adjustsEqual(cur, old)) return
  const merged = { ...old, ...cur }
  try {
    const upd = await api.imageIntent.updateImageSlot(slot.id, { user_adjustments: merged })
    if (upd.data) emit('slotUpdated', upd.data)
  } catch { /* ignore */ }
}

// 形状变化：保存到 user_adjustments + 清空旧 prompt（让下次生成按新形状重算）
async function onShapeChange(cell: any, shape: string) {
  adjustmentEdits[cell.section.id].shape = shape || ''
  const slot = await ensureSlotForCell(cell)
  if (!slot) return
  const old = slot.user_adjustments || {}
  const merged = { ...old, shape: shape || null }
  try {
    const upd = await api.imageIntent.updateImageSlot(slot.id, {
      user_adjustments: merged,
      prompt_zh: '',
      prompt_en: '',
    })
    if (upd.data) {
      emit('slotUpdated', upd.data)
      promptZhEdits[cell.section.id] = ''
      promptEnEdits[cell.section.id] = ''
    }
    if (shape) ElMessage.success(`已切换为${shapeLabel(shape)}构图，下次生图按新形状重算`)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存形状失败')
  }
}

function applyQuickCompositionTag(cell: any, tag: string) {
  const id = cell.section.id
  const cur = (adjustmentEdits[id]?.composition_zh || '').trim()
  adjustmentEdits[id].composition_zh = cur === tag ? '' : tag
  void onAdjustChange(cell)
}

// ── 批量栏：风格预设变更 → 应用到全部章节 ──
// 同时清空已生成的中英 prompt，让下次"生成本节图"自动重算（否则旧 prompt 里嵌着旧风格）
async function onBatchStyleChange(val: number | null) {
  const targets = cells.value.filter(c => !!c.slot)
  if (!targets.length) {
    ElMessage.info('已记录默认风格，新建图位时将自动应用')
    return
  }
  let ok = 0
  let fail = 0
  let cleared = 0
  for (const c of targets) {
    try {
      const hadPrompt = !!(c.slot.prompt_zh || c.slot.prompt_en)
      const upd = await api.imageIntent.updateImageSlot(c.slot.id, {
        style_preset_id: val ?? null,
        prompt_zh: '',
        prompt_en: '',
      })
      if (upd.data) {
        emit('slotUpdated', upd.data)
        promptZhEdits[c.section.id] = ''
        promptEnEdits[c.section.id] = ''
        if (hadPrompt) cleared++
      }
      ok++
    } catch { fail++ }
  }
  const clearedTip = cleared > 0 ? `；已清空 ${cleared} 节的旧提示词，下次生图会按新风格重算` : ''
  if (val == null) {
    ElMessage.success(`已清空风格预设（${ok} 节${clearedTip}）`)
  } else {
    const name = stylePresets.value.find(p => p.id === val)?.display_name || stylePresets.value.find(p => p.id === val)?.name || ''
    ElMessage.success(`已统一风格为「${name}」（${ok} 节${fail ? `，失败 ${fail}` : ''}${clearedTip}）`)
  }
}

// ── 单条提示词：生成 ──
async function generatePromptOne(cell: any) {
  const sec = cell.section
  const intent = (intentEdits[sec.id] || '').trim()
  if (intent.length < 4) {
    ElMessage.warning('请先填写画意（至少 4 字）')
    return
  }
  let slot = cell.slot || await _ensureSlotForSection(sec, intent)
  if (!slot) {
    ElMessage.error('建立画位失败')
    return
  }
  if ((slot.intent_text || '') !== intent) {
    try {
      const upd = await api.imageIntent.updateImageSlot(slot.id, { intent_text: intent })
      slot = upd.data || slot
      emit('slotUpdated', slot)
    } catch { /* ignore */ }
  }
  promptingMap[sec.id] = true
  try {
    const res = await api.imageIntent.generateSlotPrompt(slot.id, {
      preferred_provider: engineLocal.value || undefined,
    })
    const newSlot = res.data?.slot
    if (newSlot) {
      promptZhEdits[sec.id] = newSlot.prompt_zh || ''
      promptEnEdits[sec.id] = newSlot.prompt_en || ''
      emit('slotUpdated', newSlot)
      ElMessage.success('提示词生成完成')
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '生成提示词失败')
  } finally {
    promptingMap[sec.id] = false
  }
}

// ── 单条配图：生成 ──
async function generateImageOne(cell: any) {
  const sec = cell.section
  const intent = (intentEdits[sec.id] || '').trim()
  if (intent.length < 4) {
    ElMessage.warning('请先填写画意（至少 4 字）')
    return
  }
  if (cell.imageUrl) {
    try {
      await ElMessageBox.confirm(
        `当前章节已有配图，重新生成会覆盖。是否继续？（2 积分）`,
        '重新生成',
        { confirmButtonText: '重新生成', cancelButtonText: '取消', type: 'warning' },
      )
    } catch { return }
  }

  generatingImage[sec.id] = true
  try {
    let slot = cell.slot || await _ensureSlotForSection(sec, intent)
    if (!slot) { ElMessage.error('建立画位失败'); return }

    if ((slot.intent_text || '') !== intent) {
      try {
        const upd = await api.imageIntent.updateImageSlot(slot.id, { intent_text: intent })
        slot = upd.data || slot
        emit('slotUpdated', slot)
      } catch { /* ignore */ }
    }
    if (!slot.prompt_zh && !slot.prompt_en) {
      try {
        const pr = await api.imageIntent.generateSlotPrompt(slot.id, {
          preferred_provider: engineLocal.value || undefined,
        })
        slot = pr.data?.slot || slot
        promptZhEdits[sec.id] = slot.prompt_zh || ''
        promptEnEdits[sec.id] = slot.prompt_en || ''
        emit('slotUpdated', slot)
      } catch { /* ignore */ }
    }
    const gen = await api.imageIntent.generateSlotImage(
      slot.id,
      engineLocal.value ? { preferred_provider: engineLocal.value } : undefined,
    )
    const newSlot = gen.data?.slot
    if (newSlot) {
      emit('slotUpdated', newSlot)
      ElMessage.success(`第 ${sec.order_num || cell.index + 1} 节配图已生成`)
    }
  } catch (e: any) {
    const detail = e?.response?.data?.detail || e?.message || '生成失败'
    ElMessage.error(`生成失败：${detail}`)
  } finally {
    generatingImage[sec.id] = false
  }
}

// ── 上传 ──
async function onUpload(cell: any, fileWrap: any) {
  const file = fileWrap?.raw || fileWrap
  if (!file) return
  if (!/\.(jpe?g|png)$/i.test(file.name || '')) {
    ElMessage.warning('仅支持 JPG / PNG')
    return
  }
  try {
    const fallbackIntent = `${cell.section.title || cell.section.section_type || '配图'}（手动上传）`
    let slot = cell.slot || await _ensureSlotForSection(cell.section, fallbackIntent)
    if (!slot) { ElMessage.error('建立画位失败'); return }
    const fd = new FormData()
    fd.append('file', file)
    const res = await api.imageIntent.uploadSlotImage(slot.id, fd)
    if (res.data) {
      emit('slotUpdated', res.data)
      const updated: any = res.data
      const stillHasOldPrompt = !!(updated.prompt_zh || updated.prompt_en)
      ElMessage.success(
        stillHasOldPrompt
          ? '上传成功（原 AI 提示词保留供参考；若不再需要，可在「更多 → 清空提示词」中清除）'
          : '上传成功',
      )
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '上传失败')
  }
}

// ── 预览 ──
const previewVisible = ref(false)
const previewUrl = ref('')
const previewTitle = ref('')
const previewIntent = ref('')

function onPreview(cell: any) {
  if (!cell.imageUrl) return
  previewUrl.value = cell.imageUrl
  previewTitle.value = `第 ${cell.section.order_num || cell.index + 1} 节${cell.section.title ? ` · ${cell.section.title}` : ''}`
  previewIntent.value = intentEdits[cell.section.id] || ''
  previewVisible.value = true
}

function onImageError(_e: Event) { /* 占位符已存在 */ }

// ── 更多操作 ──
async function onMoreCommand(cmd: string, cell: any) {
  const sec = cell.section
  if (cmd === 'set-anchor') {
    if (!cell.slot?.image_path) {
      ElMessage.warning('该节尚未生成图，无法设为锚点')
      return
    }
    try {
      await api.imageIntent.updateVisualAnchor(props.articleId, {
        anchor_image_path: cell.slot.image_path,
        anchor_source: 'manual_pick',
      })
      ElMessage.success(`已将第 ${sec.order_num || cell.index + 1} 节配图设为视觉锚点`)
      emit('visualAnchorRefresh')
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.detail || '设置锚点失败')
    }
    return
  }
  if (cmd === 'copy-intent') {
    const txt = intentEdits[sec.id] || ''
    if (!txt) return
    await copyText(txt)
    return
  }
  if (cmd === 'clear-prompts') {
    if (!cell.slot) return
    try {
      const upd = await api.imageIntent.updateImageSlot(cell.slot.id, { prompt_zh: '', prompt_en: '' })
      promptZhEdits[sec.id] = ''
      promptEnEdits[sec.id] = ''
      if (upd.data) emit('slotUpdated', upd.data)
      ElMessage.success('已清空中英文提示词')
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.detail || '操作失败')
    }
    return
  }
  if (cmd === 'delete-slot') {
    await clearOneSection(cell)
    return
  }
}

// ── 清空本节（画意 / 提示词 / 当前图 / 历史重绘记录） ──
const clearingMap = reactive<Record<number, boolean>>({})

async function clearOneSection(cell: any) {
  if (!cell.slot) {
    ElMessage.info('本节暂无可清空的内容')
    return
  }
  const sec = cell.section
  const sectionLabel = sec.title || sec.section_type || `第 ${sec.order_num || cell.index + 1} 节`
  try {
    await ElMessageBox.confirm(
      `将清空「${sectionLabel}」的画意、中英文提示词、当前配图、风格 / 微调 / 画幅及历史重绘记录，操作不可撤销。`,
      '清空本节绘图',
      {
        confirmButtonText: '清空',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger',
      },
    )
  } catch { return }
  if (clearingMap[sec.id]) return
  clearingMap[sec.id] = true
  try {
    const res = await api.imageIntent.deleteImageSlot(cell.slot.id, { purge_history: true })
    intentEdits[sec.id] = ''
    promptZhEdits[sec.id] = ''
    promptEnEdits[sec.id] = ''
    if (suggestionsMap[sec.id]) suggestionsMap[sec.id] = []
    if (sec.id in aspectRatioEdits) aspectRatioEdits[sec.id] = '16:9'
    negativeOpen[sec.id] = false
    emit('slotRemoved', cell.slot.id)
    const purged = (res?.data as any)?.purged_history || 0
    ElMessage.success(
      purged > 0
        ? `已清空本节绘图（同时清理 ${purged} 条历史重绘记录）`
        : '已清空本节绘图',
    )
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '清空失败')
  } finally {
    clearingMap[sec.id] = false
  }
}

async function copyText(text: string | null | undefined) {
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制')
  } catch {
    ElMessage.error('复制失败，请手动选择')
  }
}

// ── 批量：建议画意（仅对未配画意 + 有正文 + ≥30 字） ──
async function batchSuggestIntent() {
  const targets = cells.value.filter(c =>
    c.section.has_content &&
    !(intentEdits[c.section.id] || '').trim() &&
    _sectionPlainText(c.section).length >= 30,
  )
  if (!targets.length) {
    ElMessage.info('没有需要建议画意的章节')
    return
  }
  try {
    await ElMessageBox.confirm(
      `将为 ${targets.length} 节生成画意，每节 0.3 积分（共 ~${(targets.length * 0.3).toFixed(1)} 积分）。是否继续？`,
      '一键建议画意',
      { confirmButtonText: '开始', cancelButtonText: '取消' },
    )
  } catch { return }

  batch.suggesting = true
  resetLocalBatchProgress('📌 建议画意')
  localBatchProgress.total = targets.length
  let okCount = 0
  // 累积已下发画意作为 prior_intents，让后续章节的画意刻意做差异化（场景/机制/数据）。
  const accumulatedIntents: string[] = []
  for (const cell of targets) {
    const sec = cell.section
    suggestingMap[sec.id] = true
    try {
      const sectionText = _sectionPlainText(sec)
      const res = await api.imageIntent.suggestIntent({
        section_text: sectionText,
        topic: props.topic,
        section_type: sec.section_type,
        section_title: sec.title || sec.section_type || '',
        prior_intents: accumulatedIntents.slice(-6),
      })
      const first = res.data?.suggestions?.[0]?.intent
      if (first) {
        intentEdits[sec.id] = first
        await saveIntent(cell)
        accumulatedIntents.push(String(first).trim())
        okCount++
      } else {
        localBatchProgress.skip++
      }
    } catch {
      localBatchProgress.fail++
    } finally {
      suggestingMap[sec.id] = false
      localBatchProgress.done++
    }
  }
  batch.suggesting = false
  ElMessage.success(`已为 ${okCount} 节生成画意${localBatchProgress.fail ? `，失败 ${localBatchProgress.fail}` : ''}`)
}

// ── 批量：AI 扩写 ──
async function batchEnrichIntent() {
  const targets = cells.value.filter(c =>
    c.section.has_content &&
    (intentEdits[c.section.id] || '').trim().length >= 4,
  )
  if (!targets.length) {
    ElMessage.info('没有可扩写的章节')
    return
  }
  try {
    await ElMessageBox.confirm(
      `将对 ${targets.length} 节执行 AI 扩写画意，每节 0.6 积分（共 ~${(targets.length * 0.6).toFixed(1)} 积分；24h 内同画意命中缓存不重复扣）。是否继续？`,
      '一键 AI 扩写',
      { confirmButtonText: '开始', cancelButtonText: '取消' },
    )
  } catch { return }

  batch.enriching = true
  resetLocalBatchProgress('✨ AI 扩写')
  localBatchProgress.total = targets.length
  let okCount = 0
  for (const cell of targets) {
    const sec = cell.section
    enrichingMap[sec.id] = true
    try {
      const res = await api.imageIntent.enrichIntent({
        intent_text: (intentEdits[sec.id] || '').trim(),
        section_text: _sectionPlainText(sec),
        topic: props.topic || '',
        section_type: sec.section_type || '',
      })
      if (res.data?.status === 'ok' && res.data.enriched_intent) {
        intentEdits[sec.id] = res.data.enriched_intent
        await saveIntent(cell, { clearPrompts: true })
        okCount++
      } else {
        localBatchProgress.skip++
      }
    } catch {
      localBatchProgress.fail++
    } finally {
      enrichingMap[sec.id] = false
      localBatchProgress.done++
    }
  }
  batch.enriching = false
  ElMessage.success(`已扩写 ${okCount} 节${localBatchProgress.fail ? `，失败 ${localBatchProgress.fail}` : ''}`)
}

// ── 批量：生成提示词 ──
async function batchGeneratePrompt() {
  const targets = cells.value.filter(c =>
    c.section.has_content &&
    (intentEdits[c.section.id] || '').trim().length >= 4 &&
    !(c.slot?.prompt_zh || c.slot?.prompt_en),
  )
  if (!targets.length) {
    ElMessage.info('没有需要生成提示词的章节')
    return
  }
  batch.promptGen = true
  resetLocalBatchProgress('🧠 生成提示词')
  localBatchProgress.total = targets.length
  let okCount = 0
  for (const cell of targets) {
    const sec = cell.section
    promptingMap[sec.id] = true
    try {
      const intent = (intentEdits[sec.id] || '').trim()
      let slot = cell.slot || await _ensureSlotForSection(sec, intent)
      if (!slot) { localBatchProgress.fail++; continue }
      if ((slot.intent_text || '') !== intent) {
        try {
          const upd = await api.imageIntent.updateImageSlot(slot.id, { intent_text: intent })
          slot = upd.data || slot
        } catch { /* ignore */ }
      }
      const pr = await api.imageIntent.generateSlotPrompt(slot.id, {
        preferred_provider: engineLocal.value || undefined,
      })
      const newSlot = pr.data?.slot
      if (newSlot) {
        promptZhEdits[sec.id] = newSlot.prompt_zh || ''
        promptEnEdits[sec.id] = newSlot.prompt_en || ''
        emit('slotUpdated', newSlot)
        okCount++
      }
    } catch {
      localBatchProgress.fail++
    } finally {
      promptingMap[sec.id] = false
      localBatchProgress.done++
    }
  }
  batch.promptGen = false
  ElMessage.success(`已生成 ${okCount} 节提示词${localBatchProgress.fail ? `，失败 ${localBatchProgress.fail}` : ''}`)
}

// ── 批量：生图 → 委托父组件（保持 storyboard / visual-anchor 集成） ──
function emitBatchImage() {
  emit('batchImage', {
    useEnrich: useEnrichInBatch.value,
    storyboard: storyboardMode.value,
    engine: engineLocal.value || '',
  })
}

defineExpose({})
</script>

<style scoped>
.contest-image-overview {
  margin-bottom: 1em;
}

.overview-anchor {
  margin-bottom: 0.7em;
}

/* ── 锚点图选择弹窗 ── */
.anchor-picker-empty {
  padding: 1.5em;
  text-align: center;
  color: #9ca3af;
  background: #f9fafb;
  border-radius: 6px;
}
.anchor-picker-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 0.75em;
  max-height: 60vh;
  overflow-y: auto;
}
.anchor-picker-item {
  border: 2px solid transparent;
  border-radius: 6px;
  overflow: hidden;
  cursor: pointer;
  background: #f9fafb;
  transition: all 0.15s ease;
}
.anchor-picker-item:hover {
  border-color: #93c5fd;
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}
.anchor-picker-item--active {
  border-color: #3b82f6;
  box-shadow: 0 0 0 1px #3b82f6 inset;
}
.anchor-picker-item img {
  width: 100%;
  aspect-ratio: 1 / 1;
  object-fit: cover;
  display: block;
}
.anchor-picker-caption {
  padding: 0.4em 0.5em;
  font-size: 12px;
  color: #374151;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.anchor-picker-badge {
  background: #3b82f6;
  color: #fff;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 9999px;
}
.overview-empty {
  padding: 1.5em;
  background: #f9fafb;
  border-radius: 6px;
  text-align: center;
  color: #9ca3af;
  font-size: 0.9em;
}

/* ── 批量栏 ── */
.batch-bar {
  margin-bottom: 0.85em;
  padding: 0.7em 0.9em;
  /* 不透明背景：避免下方画图队列卡片透过来造成"被遮挡"的视觉混淆 */
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 0.6em;
  /* 在滚动容器（.fold-panel__body）里钉在顶部 */
  position: sticky;
  top: 0;
  z-index: 5;
  /* 顶部分隔阴影：滚动时清晰区分批量栏与下方画图队列卡片 */
  box-shadow: 0 6px 10px -6px rgba(15, 23, 42, 0.18);
}
.batch-bar__row {
  display: flex;
  align-items: center;
  gap: 0.5em;
  flex-wrap: wrap;
}
.batch-bar__options {
  font-size: 0.86em;
  color: #6b7280;
}
.batch-style {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
}
.batch-engine {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.batch-engine-label {
  color: #6b7280;
  font-size: 12px;
}
.batch-style-name {
  font-weight: 500;
  margin-right: 8px;
}
.batch-style-desc {
  color: #9ca3af;
  font-size: 12px;
}
.batch-btn-label { font-weight: 500; }
.batch-btn-cost {
  margin-left: 6px;
  font-size: 11px;
  color: #9ca3af;
  font-weight: 400;
}
.batch-bar__progress { display: flex; flex-direction: column; gap: 4px; }
.batch-bar__stats {
  display: flex;
  gap: 8px;
  font-size: 12px;
  color: #6b7280;
}
.stat-fail { color: #ef4444; }
.stat-skip { color: #d97706; }

.opt-label {
  display: inline-flex;
  align-items: center;
  gap: 3px;
}
.opt-icon { font-size: 1em; }

/* ── 卡片列表 ── */
.cell-list {
  display: flex;
  flex-direction: column;
  gap: 0.65em;
}
.cell {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  transition: border-color 0.15s, box-shadow 0.15s;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.cell:hover { border-color: #93c5fd; }
.cell--active {
  border-color: #2563eb;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.12);
}
.cell--no-content { opacity: 0.7; }

/* 头部 */
.cell-head {
  display: flex;
  align-items: center;
  gap: 0.6em;
  padding: 0.6em 0.8em;
  border-bottom: 1px solid #f3f4f6;
  background: #fafafa;
}
.cell-head__title {
  display: flex;
  align-items: center;
  gap: 0.45em;
  cursor: pointer;
  flex: 1;
  min-width: 0;
}
.cell-order {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: linear-gradient(135deg, #6366f1, #ec4899);
  color: #fff;
  font-weight: 700;
  font-size: 12px;
  flex-shrink: 0;
}
.cell-title-text {
  font-weight: 600;
  color: #111827;
  font-size: 0.93em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cell-head__meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}
.cell-provider { color: #6b7280; font-size: 11px; }
.cell-head__actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 4px;
}
.cell-clear-btn {
  color: #ef4444;
}
.cell-clear-btn:hover:not(:disabled) {
  color: #dc2626;
  background: rgba(239, 68, 68, 0.08);
}
.cell-clear-btn.is-disabled {
  color: #d1d5db !important;
}

/* 主体：宽屏左右、窄屏上下 */
.cell-body {
  display: flex;
  gap: 0.85em;
  padding: 0.7em 0.85em 0.85em;
  align-items: flex-start;
}
@media (max-width: 720px) {
  .cell-body { flex-direction: column; }
}

/* 缩略图 */
.cell-thumb {
  flex: 0 0 240px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: stretch;
}
@media (max-width: 720px) {
  .cell-thumb { flex: 0 0 auto; width: 100%; }
}
.cell-thumb img {
  width: 100%;
  aspect-ratio: 16 / 9;
  object-fit: cover;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
  cursor: zoom-in;
  transition: transform 0.15s;
  background: #f3f4f6;
}
.cell-thumb img:hover { transform: scale(1.02); }
.cell-thumb__placeholder {
  width: 100%;
  aspect-ratio: 16 / 9;
  background: linear-gradient(135deg, #f3f4f6 0%, #e5e7eb 100%);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #9ca3af;
  font-size: 13px;
}
.cell-thumb__actions {
  display: flex;
  gap: 4px;
  justify-content: center;
}
.cell-thumb__actions :deep(.el-upload) { display: inline-flex; }
.thumb-btn { padding: 0 6px; }

/* 编辑区 */
.cell-editor {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.65em;
  min-width: 0;
}
.block { display: flex; flex-direction: column; gap: 0.35em; }
.block-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 0.85em;
}
.block-label {
  font-weight: 600;
  color: #374151;
}
.block-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}
.action-cost {
  margin-left: 4px;
  font-size: 10px;
  color: #9ca3af;
  font-weight: 400;
}

.suggestions {
  display: flex;
  flex-direction: column;
  gap: 0.3em;
  margin-top: 0.25em;
}
.suggestion-item {
  padding: 0.4em 0.6em;
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.84em;
  display: flex;
  justify-content: space-between;
  gap: 6px;
  transition: background 0.15s;
}
.suggestion-item:hover { background: #e0f2fe; }
.suggestion-text { color: #1e3a8a; flex: 1; }
.suggestion-reason { color: #6b7280; font-size: 0.8em; flex-shrink: 0; }

.prompt-cols {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5em;
}
@media (max-width: 920px) {
  .prompt-cols { grid-template-columns: 1fr; }
}
.prompt-single {
  display: flex;
  flex-direction: column;
  gap: 0.5em;
}
.prompt-lang-tag {
  margin-left: 0.5em;
  padding: 0.05em 0.5em;
  border-radius: 999px;
  background: #eef2ff;
  color: #4338ca;
  font-size: 0.7em;
  font-weight: 500;
}
.prompt-col { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.prompt-col__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 0.8em;
  font-weight: 600;
  color: #6b7280;
}
.prompt-textarea :deep(textarea) {
  font-size: 0.82em;
  line-height: 1.5;
}
.prompt-empty {
  padding: 0.6em;
  background: #f9fafb;
  border-radius: 4px;
  font-size: 0.82em;
  color: #6b7280;
  line-height: 1.5;
}

/* 反向提示词块 */
.negative-block { margin-top: 0.4em; }
.block-head--toggle { cursor: pointer; user-select: none; }
.block-head--toggle:hover .block-label { color: #2563eb; }
.block-label-info {
  margin-left: 0.25em;
  color: #9ca3af;
  vertical-align: -2px;
  font-size: 0.95em;
}
.negative-text {
  margin-top: 0.4em;
  padding: 0.55em 0.7em;
  background: #fff7ed;
  border: 1px dashed #fed7aa;
  border-radius: 4px;
  color: #9a3412;
  font-size: 0.78em;
  line-height: 1.55;
  word-break: break-word;
  white-space: pre-wrap;
}

.cell-tune {
  display: flex;
  flex-direction: column;
  gap: 0.4em;
  padding: 0.5em 0.65em;
  background: #f9fafb;
  border: 1px dashed #e5e7eb;
  border-radius: 6px;
}
.cell-tune__row {
  display: flex;
  align-items: center;
  gap: 0.6em;
  flex-wrap: wrap;
}
.cell-tune__label {
  font-size: 0.78em;
  color: #6b7280;
  font-weight: 600;
  min-width: 32px;
}
.cell-tune__adjusts { gap: 0.4em; }
.cell-tune__row--aspect { gap: 0.75em; }

/* ── 画幅预览 ── */
.aspect-preview {
  display: inline-flex;
  align-items: center;
  gap: 0.5em;
  margin-left: 0.25em;
}
.aspect-preview__box {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1.5px solid #2563eb;
  border-radius: 3px;
  background: rgba(37, 99, 235, 0.08);
  color: #1e40af;
  font-size: 0.7em;
  font-weight: 600;
  flex-shrink: 0;
  transition: width 0.2s ease, height 0.2s ease;
}
.aspect-preview__box--wide {
  width: 56px;
  height: 32px;
}
.aspect-preview__box--square {
  width: 32px;
  height: 32px;
}
.aspect-preview__box--tall {
  width: 24px;
  height: 32px;
  font-size: 0.62em;
}
.aspect-preview__box--small {
  width: 18px;
  height: 18px;
  font-size: 0.55em;
}
.aspect-preview__label {
  line-height: 1;
  white-space: nowrap;
}
.aspect-preview__pixels {
  font-size: 0.72em;
  color: #6b7280;
  white-space: nowrap;
}

/* ── 形状构图预览 ── */
.shape-preview {
  display: inline-flex;
  align-items: center;
  gap: 0.5em;
  margin-left: 0.25em;
}
.shape-preview__box {
  width: 28px;
  height: 28px;
  background: rgba(37, 99, 235, 0.18);
  border: 1.2px solid #2563eb;
  flex-shrink: 0;
}
.shape-preview__box--circle { border-radius: 50%; }
.shape-preview__box--ellipse {
  width: 36px;
  height: 22px;
  border-radius: 50%;
}
.shape-preview__box--triangle_top_left {
  background: rgba(37, 99, 235, 0.25);
  border: none;
  outline: 1.2px solid #2563eb;
  outline-offset: -1.2px;
  clip-path: polygon(0 0, 100% 0, 0 100%);
}
.shape-preview__box--triangle_top_right {
  background: rgba(37, 99, 235, 0.25);
  border: none;
  outline: 1.2px solid #2563eb;
  outline-offset: -1.2px;
  clip-path: polygon(0 0, 100% 0, 100% 100%);
}
.shape-preview__box--triangle_bottom_left {
  background: rgba(37, 99, 235, 0.25);
  border: none;
  outline: 1.2px solid #2563eb;
  outline-offset: -1.2px;
  clip-path: polygon(0 0, 0 100%, 100% 100%);
}
.shape-preview__box--triangle_bottom_right {
  background: rgba(37, 99, 235, 0.25);
  border: none;
  outline: 1.2px solid #2563eb;
  outline-offset: -1.2px;
  clip-path: polygon(100% 0, 100% 100%, 0 100%);
}
.shape-preview__hint {
  font-size: 0.7em;
  color: #6b7280;
  white-space: nowrap;
}

/* ── 构图快捷标签（特写/中景/全景/俯视/仰视）── */
.cell-tune__input-wrap {
  display: flex;
  flex-direction: column;
  gap: 0.25em;
  flex: 1 1 140px;
  min-width: 120px;
}
.cell-tune__quick {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25em;
}
.cell-tune__quick-tag {
  cursor: pointer;
  user-select: none;
}
.cell-tune__quick-tag:hover {
  background: #eef2ff !important;
  color: #4338ca !important;
}
.cell-tune__input {
  flex: 1;
  min-width: 130px;
  max-width: 220px;
}
.cell-tune :deep(.el-radio-button__inner) {
  font-size: 0.8em;
  padding: 5px 10px;
}

.cell-cta {
  display: flex;
  align-items: center;
  gap: 0.6em;
  padding-top: 0.25em;
}
.cta-cost {
  margin-left: 6px;
  font-size: 11px;
  opacity: 0.8;
  font-weight: 400;
}
.cta-hint {
  font-size: 0.78em;
  color: #9ca3af;
}

/* 预览对话框 */
.preview-intent {
  margin-top: 0.7em;
  color: #6b7280;
  font-size: 0.9em;
  line-height: 1.6;
}
</style>
