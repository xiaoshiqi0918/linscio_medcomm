<template>
  <div class="visual-anchor-panel">
    <div class="vap-header" @click="collapsed = !collapsed">
      <div class="vap-header__title">
        <span class="vap-icon">🎭</span>
        <span>视觉锚点</span>
        <el-tag v-if="anchor?.is_configured" size="small" type="success" effect="plain">
          已配置
          <span v-if="anchor.characters?.length"> · {{ anchor.characters.length }} 角色</span>
        </el-tag>
        <el-tag v-else size="small" type="info" effect="plain">未配置</el-tag>
      </div>
      <div class="vap-header__hint">
        <span v-if="!anchor?.is_configured" class="vap-hint">保证全文角色与画风一致 · 推荐配置后再批量生图</span>
        <span v-else class="vap-hint">应用中：注入到所有未生成章节的 prompt</span>
        <el-icon class="vap-arrow" :class="{ 'vap-arrow--up': !collapsed }"><ArrowDown /></el-icon>
      </div>
    </div>

    <div v-if="!collapsed" class="vap-body">
      <!-- 风格锁 -->
      <div class="vap-section">
        <div class="vap-section__title">风格锁</div>
        <div class="vap-style-grid">
          <el-input
            v-model="localStyle.color_palette"
            size="small"
            placeholder="配色：暖橙 + 浅蓝 + 米白"
            maxlength="80"
            @blur="saveStyleLock"
          >
            <template #prepend>配色</template>
          </el-input>
          <el-input
            v-model="localStyle.lighting"
            size="small"
            placeholder="光影：左上 45° 暖光，柔和阴影"
            maxlength="80"
            @blur="saveStyleLock"
          >
            <template #prepend>光影</template>
          </el-input>
          <el-input
            v-model="localStyle.art_style_extra"
            size="small"
            placeholder="画风：现代医学扁平插画，圆角设计"
            maxlength="120"
            @blur="saveStyleLock"
          >
            <template #prepend>画风</template>
          </el-input>
        </div>
      </div>

      <!-- 角色卡 -->
      <div class="vap-section">
        <div class="vap-section__title">
          <span>核心角色（按重要度排序，最多 5 个）</span>
          <div class="vap-extract-group">
            <el-tooltip
              content="读全文文字，让 AI 推断角色与画风（适合文章已生成正文的情况）"
              placement="top"
              :show-after="300"
            >
              <el-button
                v-if="!extractLoading"
                text
                size="small"
                class="vap-extract-btn"
                @click="onExtract"
              >
                <span class="vap-sparkle">✨</span>
                {{ anchor?.is_configured ? '从全文重抽' : '从全文抽取' }}
                <span class="vap-extract-cost">0.6 积分</span>
              </el-button>
            </el-tooltip>

            <el-tooltip
              :content="extractFromImageTooltip"
              placement="top"
              :show-after="300"
            >
              <el-dropdown
                v-if="!extractLoading"
                trigger="click"
                placement="bottom-end"
                :disabled="!hasAnchorImage"
                @command="onExtractFromImageCommand"
              >
                <el-button
                  text
                  size="small"
                  class="vap-extract-btn vap-extract-btn--img"
                  :disabled="!hasAnchorImage"
                >
                  <span class="vap-extract-icon">🖼</span>
                  从首图识别
                  <span class="vap-extract-cost">0.6 积分</span>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="replace">
                      <span class="dd-icon">🔄</span>
                      替换为图中识别的角色
                      <span class="dd-hint">完全用图说了算</span>
                    </el-dropdown-item>
                    <el-dropdown-item
                      command="append"
                      :disabled="!localCharacters.length"
                    >
                      <span class="dd-icon">➕</span>
                      追加到现有角色
                      <span class="dd-hint">保留旧角色，按 role 去重</span>
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </el-tooltip>
          </div>

          <el-button v-if="extractLoading" text size="small" :loading="true">
            {{ extractLoadingMode === 'image' ? '看图识别中…' : '抽取中…' }}
          </el-button>
        </div>

        <div v-if="!localCharacters.length && !extractLoading" class="vap-empty">
          暂未配置角色。可选：
          <span class="vap-empty__sep">·</span>
          点「<b>从全文抽取</b>」让 AI 读正文识别角色
          <span class="vap-empty__sep">·</span>
          点「<b>从首图识别</b>」让 AI 看图（gpt-4o vision）识别角色
          <span class="vap-empty__sep">·</span>
          手动添加
        </div>

        <div v-else class="vap-character-list">
          <div
            v-for="(ch, idx) in localCharacters"
            :key="ch.id"
            class="vap-character"
            :class="{ 'vap-character--editing': editingIdx === idx }"
          >
            <div class="vap-character__head">
              <span class="vap-character__id">{{ ch.id }}</span>
              <el-input
                v-model="ch.role"
                size="small"
                placeholder="角色身份（如：主治医生 / 老年患者 / 家属）"
                maxlength="30"
                class="vap-character__role"
                @blur="saveCharacters"
              />
              <el-tooltip content="重要度（生图时按重要度顺序注入 prompt 顶部）" placement="top">
                <el-rate
                  v-model="ch.importance"
                  :max="5"
                  size="small"
                  @change="saveCharacters"
                />
              </el-tooltip>
              <el-button
                text
                size="small"
                type="danger"
                :icon="Delete"
                @click="removeCharacter(idx)"
              />
            </div>
            <el-input
              v-model="ch.description"
              type="textarea"
              :rows="2"
              size="small"
              placeholder="统一视觉描述（年龄/性别/外貌/服装/姿态/标志物）"
              maxlength="300"
              show-word-limit
              @blur="saveCharacters"
            />
          </div>
          <el-button
            v-if="localCharacters.length < 5"
            text
            size="small"
            class="vap-add-btn"
            :icon="Plus"
            @click="addCharacter"
          >
            添加角色
          </el-button>
        </div>
      </div>

      <!-- Seed 锁 -->
      <div class="vap-section vap-section--seed">
        <div class="vap-section__title">Base Seed</div>
        <div class="vap-seed-row">
          <el-input
            v-model.number="localSeed"
            size="small"
            type="number"
            placeholder="种子（即梦/Flux/MJ 支持）"
            class="vap-seed-input"
            @blur="saveSeed"
          />
          <el-button size="small" :icon="Refresh" @click="rerollSeed">重摇</el-button>
          <span class="vap-seed-hint">
            同 seed + 同 prompt → 相似人物。DALL·E 不支持，自动忽略。
          </span>
        </div>
      </div>

      <!-- 锚点图 -->
      <div class="vap-section">
        <div class="vap-section__title">锚点参考图</div>
        <el-radio-group
          v-model="localAnchorSource"
          size="small"
          @change="saveAnchorSource"
        >
          <el-radio-button value="auto_first">使用首张已生成图（推荐）</el-radio-button>
          <el-radio-button value="manual_pick">手动选指定图</el-radio-button>
          <el-radio-button value="disabled">不使用</el-radio-button>
        </el-radio-group>
        <div v-if="anchor?.anchor_image_path" class="vap-anchor-image">
          <img
            :src="anchorImageUrl"
            alt="锚点图"
            class="vap-anchor-image__thumb"
          />
          <div class="vap-anchor-image__meta">
            <div class="vap-anchor-image__caption">
              当前锚点图（i2i 类 provider 自动作为参考）
            </div>
            <div class="vap-anchor-image__hint">
              支持的 provider：可灵 ✓ &nbsp; 即梦 i2i ✓ &nbsp; MJ --cref ✓ &nbsp; DALL·E ✗
            </div>
            <div class="vap-anchor-image__actions">
              <el-button
                v-if="localAnchorSource === 'manual_pick'"
                text
                size="small"
                @click="emit('pickAnchor')"
              >
                📷 重新选择
              </el-button>
              <el-button
                v-if="localAnchorSource !== 'disabled'"
                text
                size="small"
                type="danger"
                @click="clearAnchorImage"
              >
                清除锚点图
              </el-button>
            </div>
          </div>
        </div>
        <div v-else class="vap-anchor-empty">
          <template v-if="localAnchorSource === 'auto_first'">
            <span>首张图生成后将自动锁定为锚点图</span>
          </template>
          <template v-else-if="localAnchorSource === 'manual_pick'">
            <span>从已生成的章节图中挑一张作为锚点（每节卡片 ⋯ 菜单也可设置）</span>
            <el-button
              size="small"
              type="primary"
              text
              class="vap-anchor-pick-btn"
              @click="emit('pickAnchor')"
            >
              📷 从已生成图选择
            </el-button>
          </template>
          <template v-else>
            <span>已禁用锚点图，仅靠角色卡 + Seed 维持一致性</span>
          </template>
        </div>
      </div>

      <!-- 危险区：清除全部配置（已配置时显示） -->
      <div v-if="anchor?.is_configured" class="vap-danger">
        <div class="vap-danger__hint">
          清除会移除全部角色卡、风格锁与锚点图，回到"未配置"状态；Base Seed 保留。
        </div>
        <el-button
          text
          size="small"
          type="danger"
          :icon="Delete"
          :loading="clearing"
          class="vap-danger__btn"
          @click="onClearAll"
        >
          清除全部配置
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown, Plus, Delete, Refresh } from '@element-plus/icons-vue'
import { api, type VisualAnchor, type VisualAnchorCharacter, type VisualAnchorStyleLock } from '@/api'

const props = defineProps<{
  articleId: number
  anchor: VisualAnchor | null
}>()

const emit = defineEmits<{
  updated: [anchor: VisualAnchor]
  /** 用户在「手动选指定图」模式下请求打开图片选择器（由父级 ContestImageOverview 弹窗实现） */
  pickAnchor: []
}>()

const collapsed = ref<boolean>(true)
const extractLoading = ref(false)
const extractLoadingMode = ref<'text' | 'image'>('text')
const editingIdx = ref<number>(-1)
const clearing = ref(false)

const localCharacters = ref<VisualAnchorCharacter[]>([])
const localStyle = reactive<VisualAnchorStyleLock>({ color_palette: '', lighting: '', art_style_extra: '' })
const localSeed = ref<number | null>(null)
const localAnchorSource = ref<VisualAnchor['anchor_source']>('auto_first')

watch(
  () => props.anchor,
  (a) => {
    if (!a) return
    localCharacters.value = (a.characters || []).map(c => ({ ...c }))
    localStyle.color_palette = a.style_lock?.color_palette || ''
    localStyle.lighting = a.style_lock?.lighting || ''
    localStyle.art_style_extra = a.style_lock?.art_style_extra || ''
    localSeed.value = a.base_seed ?? null
    localAnchorSource.value = a.anchor_source || 'auto_first'
  },
  { immediate: true, deep: false },
)

const anchorImageUrl = computed(() => {
  let p = props.anchor?.anchor_image_path as string | undefined
  if (!p) return ''
  if (p.startsWith('/')) {
    const m = p.match(/(?:^|\/)(images\/.+)$/)
    p = m ? m[1] : ''
  }
  if (!p) return ''
  return `/api/v1/imagegen/serve?path=${encodeURIComponent(p)}`
})

const hasAnchorImage = computed(() => !!props.anchor?.anchor_image_path)

const extractFromImageTooltip = computed(() => {
  if (!hasAnchorImage.value) {
    return '尚无锚点图：请先在「全章配图概览」生成至少一张图，首图会自动锁定为锚点图'
  }
  return '让 GPT-4o vision 看锚点图识别人物外貌、服装、画风，作为"图说了算"的角色卡（适合文章字数太少 / 用户已对首图非常满意的场景）'
})

async function onExtract() {
  try {
    if (props.anchor?.is_configured) {
      await ElMessageBox.confirm(
        '将重新抽取角色卡与风格锁，覆盖你已编辑的内容（24h 内同篇文章免费）。是否继续？',
        'AI 重新抽取',
        { confirmButtonText: '继续抽取', cancelButtonText: '取消', type: 'warning' },
      )
    }
  } catch {
    return
  }
  extractLoading.value = true
  extractLoadingMode.value = 'text'
  try {
    const res = await api.imageIntent.extractVisualAnchor(props.articleId)
    const data = res.data
    if (data.status !== 'ok') {
      ElMessage.warning(data.reason || 'AI 抽取失败')
      return
    }
    if (data.from_cache) {
      ElMessage.success('命中缓存，未扣积分')
    } else {
      ElMessage.success(`AI 已识别 ${data.characters.length} 个角色（扣 ${data.cost ?? 0.6} 积分）`)
    }
    emit('updated', data.anchor)
  } catch (e: any) {
    const detail = e?.response?.data?.detail || e?.message || '抽取失败'
    if (e?.response?.status === 402) {
      ElMessage.error('积分不足，请充值')
    } else {
      ElMessage.error(detail)
    }
  } finally {
    extractLoading.value = false
  }
}

async function onExtractFromImageCommand(cmd: string) {
  const mode: 'replace' | 'append' = cmd === 'append' ? 'append' : 'replace'
  if (!hasAnchorImage.value) {
    ElMessage.warning('尚无锚点图，请先生成首张配图')
    return
  }
  if (mode === 'replace' && localCharacters.value.length > 0) {
    try {
      await ElMessageBox.confirm(
        '将用"图中识别的角色"覆盖现有所有角色卡（重要：服装/画风一并覆盖）。是否继续？',
        '从首图识别 · 替换',
        { confirmButtonText: '替换', cancelButtonText: '取消', type: 'warning' },
      )
    } catch {
      return
    }
  }
  extractLoading.value = true
  extractLoadingMode.value = 'image'
  try {
    const res = await api.imageIntent.extractVisualAnchorFromImage(props.articleId, {
      merge_mode: mode,
    })
    const data = res.data
    if (data.status !== 'ok') {
      ElMessage.warning(data.reason || 'vision 识别失败')
      return
    }
    const n = data.characters?.length || 0
    const verb = mode === 'append' ? '已追加' : '已识别'
    ElMessage.success(`${verb} ${n} 个角色（看图识别，扣 ${data.cost ?? 0.6} 积分）`)
    emit('updated', data.anchor)
  } catch (e: any) {
    const detail = e?.response?.data?.detail || e?.message || '识别失败'
    if (e?.response?.status === 402) {
      ElMessage.error('积分不足，请充值')
    } else {
      ElMessage.error(detail)
    }
  } finally {
    extractLoading.value = false
  }
}

async function _save(payload: Record<string, any>) {
  try {
    const res = await api.imageIntent.updateVisualAnchor(props.articleId, payload)
    emit('updated', res.data)
  } catch (e: any) {
    const detail = e?.response?.data?.detail || e?.message || '保存失败'
    ElMessage.error(detail)
  }
}

function saveCharacters() {
  void _save({ characters: localCharacters.value })
}

function saveStyleLock() {
  void _save({ style_lock: { ...localStyle } })
}

function saveSeed() {
  void _save({ base_seed: localSeed.value || null })
}

function saveAnchorSource() {
  void _save({ anchor_source: localAnchorSource.value })
}

function rerollSeed() {
  // 32-bit unsigned 范围内，但避免 0
  localSeed.value = Math.floor(Math.random() * 2_147_483_646) + 1
  saveSeed()
}

function addCharacter() {
  const usedIds = new Set(localCharacters.value.map(c => c.id))
  let nextId = ''
  for (const c of 'ABCDEFGH') {
    if (!usedIds.has(c)) { nextId = c; break }
  }
  if (!nextId) nextId = 'X'
  localCharacters.value.push({
    id: nextId,
    role: '',
    description: '',
    importance: 3,
  })
  editingIdx.value = localCharacters.value.length - 1
}

function removeCharacter(idx: number) {
  localCharacters.value.splice(idx, 1)
  if (editingIdx.value === idx) editingIdx.value = -1
  saveCharacters()
}

function clearAnchorImage() {
  void _save({ anchor_image_path: '' })
}

async function onClearAll() {
  try {
    await ElMessageBox.confirm(
      '将清除本文章的全部视觉锚点配置（角色卡、风格锁、锚点图），回到"未配置"状态。Base Seed 保留以便后续重新配置。\n\n此操作不影响已生成的图片，仅影响后续未生成章节的 prompt 注入。',
      '清除视觉锚点配置',
      {
        confirmButtonText: '清除',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger',
      },
    )
  } catch {
    return
  }
  clearing.value = true
  try {
    const res = await api.imageIntent.updateVisualAnchor(props.articleId, {
      characters: [],
      style_lock: { color_palette: '', lighting: '', art_style_extra: '' },
      anchor_image_path: '',
      anchor_source: 'auto_first',
    })
    emit('updated', res.data)
    // 同步清空本地输入态（watch 在 props.anchor 变化后也会做，这里立即生效）
    localCharacters.value = []
    localStyle.color_palette = ''
    localStyle.lighting = ''
    localStyle.art_style_extra = ''
    localAnchorSource.value = 'auto_first'
    ElMessage.success('已清除视觉锚点配置')
  } catch (e: any) {
    const detail = e?.response?.data?.detail || e?.message || '清除失败'
    ElMessage.error(detail)
  } finally {
    clearing.value = false
  }
}

defineExpose({
  /** 外部触发：如全文生成完成时自动展开并 AI 抽取 */
  expandAndExtract() {
    collapsed.value = false
    void onExtract()
  },
})
</script>

<style scoped>
.visual-anchor-panel {
  margin-bottom: 1em;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: linear-gradient(180deg, #fafbff 0%, #ffffff 100%);
}
.vap-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.6em 0.9em;
  cursor: pointer;
  user-select: none;
}
.vap-header:hover {
  background: rgba(99, 102, 241, 0.04);
}
.vap-header__title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.95em;
  font-weight: 600;
  color: #111827;
}
.vap-icon { font-size: 1.05em; }
.vap-header__hint {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #6b7280;
  font-size: 12px;
}
.vap-arrow {
  transition: transform 0.2s;
}
.vap-arrow--up {
  transform: rotate(180deg);
}
.vap-body {
  border-top: 1px solid #e5e7eb;
  padding: 0.9em 1em 1em;
  display: flex;
  flex-direction: column;
  gap: 1em;
}
.vap-section__title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
  font-size: 0.9em;
  color: #374151;
  margin-bottom: 0.5em;
}
.vap-extract-btn {
  background: linear-gradient(90deg, rgba(99, 102, 241, 0.08), rgba(236, 72, 153, 0.08));
  border-radius: 4px;
  padding: 0 8px;
  height: 24px;
}
.vap-extract-btn:hover:not(:disabled) {
  background: linear-gradient(90deg, rgba(99, 102, 241, 0.18), rgba(236, 72, 153, 0.18));
}
.vap-sparkle {
  background: linear-gradient(90deg, #6366f1, #ec4899);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  font-weight: 700;
  margin-right: 4px;
}
.vap-extract-cost {
  font-size: 11px;
  color: #9ca3af;
  margin-left: 4px;
  font-weight: 400;
}
.vap-extract-group {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.vap-extract-icon {
  margin-right: 4px;
}
.vap-extract-btn--img {
  background: linear-gradient(90deg, rgba(34, 197, 94, 0.08), rgba(14, 165, 233, 0.08));
}
.vap-extract-btn--img:hover:not(:disabled) {
  background: linear-gradient(90deg, rgba(34, 197, 94, 0.18), rgba(14, 165, 233, 0.18));
}
.vap-extract-btn--img:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.dd-icon {
  display: inline-block;
  margin-right: 4px;
}
.dd-hint {
  margin-left: 8px;
  font-size: 11px;
  color: #9ca3af;
}
.vap-empty__sep {
  margin: 0 0.4em;
  color: #d1d5db;
}
.vap-style-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5em;
}
.vap-style-grid > .el-input:nth-child(3) {
  grid-column: span 2;
}
@media (max-width: 768px) {
  .vap-style-grid {
    grid-template-columns: 1fr;
  }
  .vap-style-grid > .el-input:nth-child(3) {
    grid-column: 1;
  }
}
.vap-empty {
  padding: 0.8em;
  text-align: center;
  color: #9ca3af;
  font-size: 12px;
  background: #f9fafb;
  border-radius: 4px;
}
.vap-character-list {
  display: flex;
  flex-direction: column;
  gap: 0.6em;
}
.vap-character {
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 0.5em 0.6em;
  background: #fff;
}
.vap-character--editing {
  border-color: #6366f1;
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.1);
}
.vap-character__head {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 0.4em;
}
.vap-character__id {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: linear-gradient(135deg, #6366f1, #ec4899);
  color: #fff;
  font-weight: 700;
  font-size: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.vap-character__role {
  flex: 1;
}
.vap-add-btn {
  align-self: flex-start;
  color: #6366f1;
}
.vap-section--seed .vap-seed-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.vap-seed-input {
  width: 220px;
}
.vap-seed-hint {
  font-size: 12px;
  color: #6b7280;
}
.vap-anchor-image {
  margin-top: 0.6em;
  display: flex;
  gap: 0.8em;
  align-items: flex-start;
}
.vap-anchor-image__thumb {
  width: 96px;
  height: 96px;
  object-fit: cover;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
}
.vap-anchor-image__meta {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.vap-anchor-image__caption {
  font-weight: 600;
  font-size: 13px;
  color: #111827;
}
.vap-anchor-image__hint {
  font-size: 12px;
  color: #6b7280;
}
.vap-anchor-empty {
  margin-top: 0.5em;
  padding: 0.6em;
  background: #f9fafb;
  border-radius: 4px;
  font-size: 12px;
  color: #6b7280;
  display: flex;
  align-items: center;
  gap: 0.6em;
  flex-wrap: wrap;
}
.vap-anchor-pick-btn {
  margin-left: auto;
}
.vap-anchor-image__actions {
  display: flex;
  gap: 0.4em;
  margin-top: 0.3em;
  flex-wrap: wrap;
}
.vap-hint {
  font-size: 12px;
}

/* ── 危险区：清除全部配置 ── */
.vap-danger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6em;
  padding: 0.55em 0.7em;
  margin-top: 0.4em;
  background: rgba(239, 68, 68, 0.04);
  border: 1px dashed rgba(239, 68, 68, 0.35);
  border-radius: 6px;
}
.vap-danger__hint {
  flex: 1;
  font-size: 12px;
  color: #b91c1c;
  line-height: 1.5;
}
.vap-danger__btn {
  flex-shrink: 0;
}
</style>
