<template>
  <el-dialog
    v-model="visibleProxy"
    title="AI 智能扩写画意 · 对比"
    width="92%"
    :style="{ maxWidth: '1100px' }"
    align-center
    destroy-on-close
    @opened="onOpen"
  >
    <div class="enrich-dialog">
      <!-- 顶部状态条 -->
      <div v-if="loading" class="enrich-status enrich-status--loading">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>AI 正在扩写中，预计 5-15 秒…</span>
      </div>
      <div v-else-if="rejected" class="enrich-status enrich-status--reject">
        <el-icon><WarningFilled /></el-icon>
        <span>{{ rejectReason || '当前画意涉及合规风险，无法扩写' }}</span>
      </div>
      <div v-else-if="errorMsg" class="enrich-status enrich-status--error">
        <el-icon><CircleCloseFilled /></el-icon>
        <span>{{ errorMsg }}</span>
      </div>
      <div v-else-if="enriched && fromCache" class="enrich-status enrich-status--cache">
        <el-icon><CollectionTag /></el-icon>
        <span>命中 24h 缓存（不扣积分）</span>
      </div>
      <div v-else-if="enriched" class="enrich-status enrich-status--ok">
        <el-icon><CircleCheckFilled /></el-icon>
        <span>扩写完成 · 已扣 {{ costUsed }} 积分（{{ originalLength }} 字 → {{ enrichedLength }} 字）</span>
      </div>

      <!-- 双栏对比 -->
      <div class="enrich-columns">
        <div class="enrich-col enrich-col--original">
          <div class="enrich-col__title">
            <span>原画意</span>
            <span class="enrich-col__hint">可编辑</span>
          </div>
          <el-input
            v-model="originalText"
            type="textarea"
            :rows="13"
            placeholder="原始画意"
          />
          <div class="enrich-col__counter">{{ originalText.length }} 字</div>
        </div>
        <div class="enrich-col enrich-col--enriched">
          <div class="enrich-col__title">
            <span><span class="sparkle">✨</span> AI 扩写版</span>
            <span class="enrich-col__hint">可编辑</span>
          </div>
          <el-input
            v-model="enrichedText"
            type="textarea"
            :rows="13"
            placeholder="点击右下「重新扩写」开始"
            :disabled="loading"
          />
          <div class="enrich-col__counter">{{ enrichedText.length }} 字</div>
        </div>
      </div>

      <!-- AI 总结 -->
      <div v-if="hintsAdded.length || preserved.length" class="enrich-summary">
        <div v-if="hintsAdded.length" class="enrich-summary__block">
          <div class="enrich-summary__title">
            <span class="sparkle">✨</span> AI 主要补充了这些细节
          </div>
          <ul class="enrich-summary__list">
            <li v-for="(h, idx) in hintsAdded" :key="`h-${idx}`">{{ h }}</li>
          </ul>
        </div>
        <div v-if="preserved.length" class="enrich-summary__block enrich-summary__block--preserved">
          <div class="enrich-summary__title">
            <el-icon><Lock /></el-icon> AI 保留未改的事项
          </div>
          <ul class="enrich-summary__list">
            <li v-for="(p, idx) in preserved" :key="`p-${idx}`">{{ p }}</li>
          </ul>
        </div>
      </div>

      <!-- 提示信息 -->
      <div class="enrich-tips">
        <div>提示：</div>
        <ul>
          <li>扩写不会改变你的医学事实，只补充画面细节（环境/角色/光影/道具/文字）</li>
          <li>你可以直接编辑扩写版后再保存为画意</li>
          <li>「重新扩写」会再花 0.6 积分尝试不同方向（同一画意 24h 内复用缓存不扣分）</li>
        </ul>
      </div>
    </div>

    <template #footer>
      <span class="enrich-footer">
        <el-button @click="onCancel">取消</el-button>
        <el-button
          :disabled="loading"
          @click="onUseOriginal"
        >
          使用原版
        </el-button>
        <el-button
          :loading="loading"
          :disabled="!enrichedText"
          @click="onRequestEnrich"
        >
          {{ enriched ? '🔄 重新扩写' : '开始扩写' }}
        </el-button>
        <el-button
          type="primary"
          :disabled="!enrichedText || loading"
          @click="onUseEnriched"
        >
          ✨ 使用扩写版
        </el-button>
      </span>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Loading, WarningFilled, CircleCloseFilled, CircleCheckFilled,
  CollectionTag, Lock,
} from '@element-plus/icons-vue'
import { api } from '@/api'

const props = defineProps<{
  modelValue: boolean
  initialIntent: string
  styleName?: string
  aspectRatio?: string
  sectionText?: string
  topic?: string
  sectionType?: string
  /** 是否在打开后立即触发一次扩写 */
  autoEnrich?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [v: boolean]
  /** 用户最终选定要保存的画意 */
  apply: [text: string, source: 'original' | 'enriched']
  /** 取消（关闭，不保存） */
  cancel: []
}>()

const visibleProxy = computed({
  get: () => props.modelValue,
  set: v => emit('update:modelValue', v),
})

const originalText = ref('')
const enrichedText = ref('')
const hintsAdded = ref<string[]>([])
const preserved = ref<string[]>([])
const loading = ref(false)
const rejected = ref(false)
const rejectReason = ref('')
const errorMsg = ref('')
const fromCache = ref(false)
const enriched = ref(false)
const costUsed = ref(0)
const originalLength = ref(0)
const enrichedLength = ref(0)

watch(() => props.modelValue, v => {
  if (v) {
    originalText.value = (props.initialIntent || '').trim()
    enrichedText.value = ''
    hintsAdded.value = []
    preserved.value = []
    rejected.value = false
    rejectReason.value = ''
    errorMsg.value = ''
    fromCache.value = false
    enriched.value = false
    costUsed.value = 0
  }
})

async function onOpen() {
  if (props.autoEnrich && originalText.value && !enriched.value) {
    await onRequestEnrich()
  }
}

async function onRequestEnrich() {
  if (!originalText.value || originalText.value.trim().length < 4) {
    ElMessage.warning('画意至少 4 字')
    return
  }
  loading.value = true
  rejected.value = false
  rejectReason.value = ''
  errorMsg.value = ''
  try {
    const res = await api.imageIntent.enrichIntent({
      intent_text: originalText.value.trim(),
      style_preset: props.styleName || null,
      aspect_ratio: props.aspectRatio || '16:9',
      section_text: props.sectionText || null,
      topic: props.topic || null,
      section_type: props.sectionType || null,
    })
    const data = res.data
    if (data.status === 'rejected') {
      rejected.value = true
      rejectReason.value = data.reason || ''
      enrichedText.value = ''
      hintsAdded.value = []
      preserved.value = []
      enriched.value = false
      return
    }
    if (data.status === 'error') {
      errorMsg.value = data.reason || '扩写失败'
      enriched.value = false
      return
    }
    enrichedText.value = data.enriched_intent || ''
    hintsAdded.value = data.hints_added || []
    preserved.value = data.preserved || []
    fromCache.value = !!data.from_cache
    costUsed.value = data.cost ?? 0
    originalLength.value = data.original_length || originalText.value.length
    enrichedLength.value = data.enriched_length || enrichedText.value.length
    enriched.value = true
  } catch (e: any) {
    let detail = (e?.response?.data?.detail as string) || e?.message || '扩写失败'
    if (!e?.response) {
      const m = String(e?.message || '')
      if (m === 'Network Error' || (e?.code === 'ERR_NETWORK' && !m)) {
        detail = '无法连接服务器（请确认后端已启动、Vite 代理 / 网络正常）'
      } else if (/connection|network|fetch/i.test(m) && m.length < 80) {
        detail = `请求失败：${m}。若大模型在服务端报错，可检查 HTTP(S)_PROXY 或设置 MEDCOMM_OPENAI_IGNORE_SYSTEM_PROXY=1 后重启后端。`
      }
    }
    errorMsg.value = detail
    if (e?.response?.status === 402) {
      ElMessage.error('积分不足，请充值后重试')
    }
  } finally {
    loading.value = false
  }
}

function onUseOriginal() {
  emit('apply', originalText.value.trim(), 'original')
  visibleProxy.value = false
}

function onUseEnriched() {
  if (!enrichedText.value) return
  emit('apply', enrichedText.value.trim(), 'enriched')
  visibleProxy.value = false
}

function onCancel() {
  emit('cancel')
  visibleProxy.value = false
}
</script>

<style scoped>
.enrich-dialog {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.enrich-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 6px;
  font-size: 13px;
}
.enrich-status--loading {
  background: linear-gradient(90deg, #f5f3ff 0%, #eef2ff 100%);
  color: #6366f1;
}
.enrich-status--ok {
  background: #ecfdf5;
  color: #059669;
}
.enrich-status--cache {
  background: #fef3c7;
  color: #b45309;
}
.enrich-status--reject {
  background: #fef2f2;
  color: #dc2626;
}
.enrich-status--error {
  background: #fef2f2;
  color: #dc2626;
}

.enrich-columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.enrich-col {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.enrich-col__title {
  font-weight: 600;
  font-size: 13px;
  color: #111827;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.enrich-col__hint {
  font-weight: 400;
  color: #9ca3af;
  font-size: 11px;
}
.enrich-col__counter {
  font-size: 11px;
  color: #6b7280;
  text-align: right;
}
.enrich-col--enriched .enrich-col__title {
  background: linear-gradient(90deg, #f5f3ff 0%, #fce7f3 100%);
  padding: 6px 10px;
  border-radius: 6px;
}
.sparkle {
  background: linear-gradient(90deg, #6366f1, #ec4899);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  font-weight: 700;
}

.enrich-summary {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.enrich-summary__block {
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 10px 12px;
}
.enrich-summary__block--preserved {
  background: #f0fdf4;
  border-color: #bbf7d0;
}
.enrich-summary__title {
  font-weight: 600;
  font-size: 13px;
  color: #111827;
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 4px;
}
.enrich-summary__list {
  margin: 0;
  padding-left: 1.4em;
  font-size: 12.5px;
  color: #4b5563;
  line-height: 1.6;
}
.enrich-summary__list li {
  margin: 0.2em 0;
}
.enrich-tips {
  background: #f3f4f6;
  border-radius: 6px;
  padding: 10px 14px;
  font-size: 12px;
  color: #4b5563;
}
.enrich-tips ul {
  margin: 4px 0 0;
  padding-left: 1.4em;
}
.enrich-tips li {
  margin: 2px 0;
}

.enrich-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

@media (max-width: 768px) {
  .enrich-columns,
  .enrich-summary {
    grid-template-columns: 1fr;
  }
}
</style>
