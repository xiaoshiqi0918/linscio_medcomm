<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    :title="isEdit ? '编辑模板' : '新建模板'"
    width="780px"
    :close-on-click-modal="false"
    destroy-on-close
  >
    <el-form :model="form" label-width="100px" class="template-form">
      <el-form-item label="模板名称" required>
        <el-input v-model="form.name" placeholder="如：微信公众号科普长文" />
      </el-form-item>

      <el-form-item label="内容形式" required>
        <el-select v-model="form.content_format" placeholder="选择形式" @change="onFormatChange">
          <el-option
            v-for="f in FORMAT_OPTIONS"
            :key="f.value"
            :label="f.label"
            :value="f.value"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="平台">
        <el-select v-model="form.platform" placeholder="选择平台" clearable>
          <el-option label="微信公众号" value="wechat" />
          <el-option label="小红书" value="xiaohongshu" />
          <el-option label="抖音" value="douyin" />
          <el-option label="B站" value="bilibili" />
          <el-option label="期刊" value="journal" />
          <el-option label="线下" value="offline" />
          <el-option label="通用" value="universal" />
        </el-select>
      </el-form-item>

      <el-form-item label="专科">
        <el-select v-model="form.specialty" placeholder="选择专科" clearable>
          <el-option
            v-for="s in SPECIALTY_OPTIONS"
            :key="s.value"
            :label="s.label"
            :value="s.value"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="目标字数">
        <el-radio-group v-model="wordCountMode">
          <el-radio-button value="800">短篇 (~800)</el-radio-button>
          <el-radio-button value="1200">中篇 (~1200)</el-radio-button>
          <el-radio-button value="2000">长篇 (~2000)</el-radio-button>
          <el-radio-button value="3000">投稿 (~3000)</el-radio-button>
          <el-radio-button value="custom">自定义</el-radio-button>
        </el-radio-group>
        <el-input-number
          v-if="wordCountMode === 'custom'"
          v-model="customWordCount"
          :min="200"
          :max="8000"
          :step="100"
          style="width: 140px; margin-left: 8px;"
        />
      </el-form-item>

      <el-form-item label="目标受众">
        <el-select v-model="form.target_audience" placeholder="选择受众" clearable>
          <el-option label="公众" value="public" />
          <el-option label="患者" value="patient" />
          <el-option label="学生" value="student" />
          <el-option label="专业人士" value="professional" />
          <el-option label="儿童" value="children" />
        </el-select>
      </el-form-item>

      <el-form-item label="阅读难度">
        <el-select v-model="form.reading_level" placeholder="选择难度" clearable>
          <el-option label="通俗" value="layman" />
          <el-option label="专业" value="professional" />
        </el-select>
      </el-form-item>

      <el-form-item label="章节结构">
        <div class="section-editor">
          <div class="section-available">
            <div class="section-editor-label">可用章节（勾选添加）</div>
            <div
              v-for="sec in availableSections"
              :key="sec.value"
              class="section-check-item"
            >
              <el-checkbox
                :model-value="isSectionSelected(sec.value)"
                :disabled="sec.required"
                @change="(v: boolean) => toggleSection(sec.value, sec.label, v)"
              >{{ sec.label }}</el-checkbox>
              <el-tag v-if="sec.required" size="small" type="info" effect="plain">必选</el-tag>
            </div>
            <el-empty v-if="!availableSections.length" description="选择形式后显示" :image-size="48" />
          </div>

          <div class="section-selected">
            <div class="section-editor-label">已选章节（拖拽排序）</div>
            <div
              v-for="(sec, idx) in selectedSections"
              :key="sec.section_type"
              class="section-drag-item"
              draggable="true"
              @dragstart="onDragStart(idx, $event)"
              @dragover.prevent="onDragOver(idx, $event)"
              @drop="onDrop(idx)"
              @dragend="dragIdx = -1"
              :class="{ 'drag-over': dragOverIdx === idx && dragIdx !== idx }"
            >
              <span class="drag-handle">&#x2630;</span>
              <span class="section-name">{{ sec.title }}</span>
              <el-tag v-if="isRequired(sec.section_type)" size="small" type="info" effect="plain">必选</el-tag>
              <el-icon
                v-else
                class="remove-btn"
                @click="removeSection(idx)"
              ><Close /></el-icon>
            </div>
            <el-empty v-if="!selectedSections.length" description="从左侧添加章节" :image-size="48" />
          </div>
        </div>
      </el-form-item>

      <el-form-item label="描述">
        <el-input v-model="form.description" type="textarea" :rows="3" placeholder="模板说明（可选）" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="$emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSave">
        {{ isEdit ? '保存' : '创建' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { Close } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { api } from '@/api'
import { SPECIALTY_OPTIONS } from '@/constants/specialties'

const props = defineProps<{
  visible: boolean
  templateData?: any
}>()

const emit = defineEmits<{
  'update:visible': [val: boolean]
  saved: []
}>()

const isEdit = computed(() => !!props.templateData?.id)
const saving = ref(false)

const FORMAT_OPTIONS = [
  { value: 'article', label: '图文文章' },
  { value: 'story', label: '科普故事' },
  { value: 'debunk', label: '辟谣文' },
  { value: 'qa_article', label: '问答科普' },
  { value: 'research_read', label: '研究速读' },
  { value: 'oral_script', label: '口播脚本' },
  { value: 'drama_script', label: '情景剧本' },
  { value: 'storyboard', label: '动画分镜' },
  { value: 'audio_script', label: '播客脚本' },
  { value: 'comic_strip', label: '条漫' },
  { value: 'card_series', label: '知识卡片系列' },
  { value: 'poster', label: '科普海报' },
  { value: 'picture_book', label: '科普绘本' },
  { value: 'long_image', label: '竖版长图' },
  { value: 'patient_handbook', label: '患者教育手册' },
  { value: 'quiz_article', label: '自测科普' },
  { value: 'h5_outline', label: 'H5 互动大纲' },
]

const SECTION_CONFIGS: Record<string, { value: string; label: string; required: boolean }[]> = {
  article: [
    { value: 'body', label: '正文', required: true },
    { value: 'case', label: '案例', required: false },
    { value: 'qa', label: 'Q&A', required: false },
    { value: 'summary', label: '小结', required: true },
  ],
  story: [
    { value: 'hook', label: '引子', required: true },
    { value: 'development', label: '发展', required: true },
    { value: 'turning_point', label: '转折·就医', required: true },
    { value: 'science_core', label: '科普核心', required: true },
    { value: 'resolution', label: '结局', required: true },
    { value: 'action_list', label: '行动清单', required: false },
    { value: 'closing_quote', label: '结尾金句', required: false },
  ],
  debunk: [
    { value: 'rumor_present', label: '谣言还原', required: true },
    { value: 'verdict', label: '真相判定', required: true },
    { value: 'debunk_1', label: '拆解·漏洞1', required: true },
    { value: 'debunk_2', label: '拆解·漏洞2', required: true },
    { value: 'debunk_3', label: '拆解·漏洞3', required: false },
    { value: 'correct_practice', label: '正确做法', required: true },
    { value: 'anti_fraud', label: '防骗指南', required: true },
  ],
  qa_article: [
    { value: 'qa_intro', label: '问题引入', required: true },
    { value: 'qa_1', label: '问答1·入门', required: true },
    { value: 'qa_2', label: '问答2·入门', required: true },
    { value: 'qa_3', label: '问答3·进阶', required: true },
    { value: 'qa_4', label: '问答4·实操', required: false },
    { value: 'qa_5', label: '问答5·特殊', required: false },
    { value: 'qa_summary', label: '总结', required: true },
  ],
  research_read: [
    { value: 'one_liner', label: '一句话摘要', required: true },
    { value: 'study_card', label: '研究信息卡', required: true },
    { value: 'why_matters', label: '为什么值得关注', required: true },
    { value: 'methods', label: '研究怎么做的', required: true },
    { value: 'findings', label: '核心发现', required: true },
    { value: 'implication', label: '对普通人意味着什么', required: true },
    { value: 'limitation', label: '注意事项·研究局限', required: true },
  ],
  oral_script: [
    { value: 'script_plan', label: '脚本规划', required: true },
    { value: 'golden_hook', label: '黄金开头(0-5s)', required: true },
    { value: 'problem_setup', label: '问题铺垫(5-20s)', required: true },
    { value: 'core_knowledge', label: '核心科普(20-50s)', required: true },
    { value: 'practical_tips', label: '实用建议(50-65s)', required: true },
    { value: 'closing_hook', label: '收尾钩子(最后10s)', required: true },
    { value: 'extras', label: '附加信息', required: true },
  ],
  drama_script: [
    { value: 'drama_plan', label: '剧本概况', required: true },
    { value: 'cast_table', label: '角色表', required: true },
    { value: 'act_1', label: '第一场·日常建立', required: true },
    { value: 'act_2', label: '第二场·冲突触发', required: true },
    { value: 'act_3', label: '第三场·错误应对', required: true },
    { value: 'act_4', label: '第四场·专业介入', required: true },
    { value: 'act_5', label: '第五场·结局升华', required: true },
    { value: 'finale', label: '终场·字幕总结', required: true },
    { value: 'filming_notes', label: '拍摄备注', required: true },
  ],
  storyboard: [
    { value: 'anim_plan', label: '动画概况', required: true },
    { value: 'char_design', label: '角色/元素设定', required: true },
    { value: 'reel_1', label: '第一幕·引入', required: true },
    { value: 'reel_2', label: '第二幕·问题呈现', required: true },
    { value: 'reel_3', label: '第三幕·机制解释', required: true },
    { value: 'reel_4', label: '第四幕·正确做法', required: true },
    { value: 'reel_5', label: '第五幕·总结收尾', required: true },
    { value: 'prod_notes', label: '制作备注', required: true },
  ],
  audio_script: [
    { value: 'opening', label: '开场', required: true },
    { value: 'topic_intro', label: '话题引入', required: true },
    { value: 'deep_dive', label: '深入讲解', required: true },
    { value: 'extension', label: '延伸', required: true },
    { value: 'closing', label: '收尾', required: true },
  ],
  comic_strip: [
    { value: 'planner', label: '条漫规划', required: true },
    ...Array.from({ length: 12 }, (_, i) => ({
      value: `panel_${i + 1}`,
      label: `第${i + 1}格`,
      required: i < 9,
    })),
  ],
  card_series: [
    { value: 'series_plan', label: '系列规划', required: true },
    { value: 'cover_card', label: '封面卡', required: true },
    ...Array.from({ length: 7 }, (_, i) => ({
      value: `card_${i + 1}`,
      label: `内容卡${i + 1}`,
      required: i < 5,
    })),
    { value: 'ending_card', label: '结尾卡', required: true },
  ],
  poster: [
    { value: 'poster_brief', label: '海报概要', required: true },
    { value: 'headline', label: '标题区', required: true },
    { value: 'body_visual', label: '主体·视觉', required: true },
    { value: 'cta_footer', label: '行动号召·底部', required: true },
    { value: 'design_spec', label: '设计规格', required: true },
  ],
  picture_book: [
    { value: 'book_plan', label: '绘本规划', required: true },
    { value: 'cover', label: '封面P1', required: true },
    ...Array.from({ length: 7 }, (_, i) => ({
      value: `spread_${i + 1}`,
      label: `跨页${i + 1}`,
      required: i < 5,
    })),
    { value: 'back_cover', label: '封底·家长指南P16', required: true },
  ],
  long_image: [
    { value: 'image_plan', label: '长图规划', required: true },
    { value: 'title_block', label: '封面标题区', required: true },
    { value: 'intro_block', label: '引入区', required: true },
    { value: 'core_1', label: '核心内容1', required: true },
    { value: 'core_2', label: '核心内容2', required: true },
    { value: 'core_3', label: '核心内容3', required: true },
    { value: 'core_4', label: '核心内容4', required: false },
    { value: 'tips_block', label: '实用建议区', required: true },
    { value: 'warning_block', label: '特别提醒区', required: false },
    { value: 'summary_cta', label: '总结/CTA区', required: true },
    { value: 'footer_info', label: '尾部信息区', required: true },
  ],
  patient_handbook: [
    { value: 'handbook_plan', label: '手册信息', required: true },
    { value: 'cover', label: '封面', required: true },
    { value: 'disease_know', label: '认识疾病', required: true },
    { value: 'treatment', label: '治疗方案', required: true },
    { value: 'daily_care', label: '日常管理', required: true },
    { value: 'followup', label: '复诊与随访', required: true },
    { value: 'emergency', label: '紧急情况', required: true },
    { value: 'faq', label: '常见问题', required: true },
    { value: 'back_cover', label: '封底', required: true },
  ],
  quiz_article: [
    { value: 'quiz_intro', label: '自测引入', required: true },
    ...Array.from({ length: 5 }, (_, i) => ({
      value: `q_${i + 1}`,
      label: `题目${i + 1}`,
      required: i < 3,
    })),
    { value: 'summary', label: '总结', required: true },
  ],
  h5_outline: [
    { value: 'page_cover', label: '封面页', required: true },
    { value: 'page_1', label: '第1页', required: true },
    { value: 'page_2', label: '第2页', required: true },
    { value: 'page_3', label: '第3页', required: true },
    { value: 'page_end', label: '结束页', required: true },
  ],
}

const form = reactive({
  name: '',
  content_format: 'article',
  platform: null as string | null,
  specialty: null as string | null,
  target_audience: null as string | null,
  reading_level: null as string | null,
  description: null as string | null,
})

const wordCountMode = ref<string>('1200')
const customWordCount = ref(1500)

const selectedSections = ref<{ section_type: string; title: string; order: number }[]>([])

const availableSections = computed(() => {
  return SECTION_CONFIGS[form.content_format] || []
})

const requiredSet = computed(() => {
  const cfg = SECTION_CONFIGS[form.content_format] || []
  return new Set(cfg.filter(s => s.required).map(s => s.value))
})

function isRequired(sectionType: string) {
  return requiredSet.value.has(sectionType)
}

function isSectionSelected(sectionType: string) {
  return selectedSections.value.some(s => s.section_type === sectionType)
}

function toggleSection(sectionType: string, label: string, checked: boolean) {
  if (checked) {
    if (!isSectionSelected(sectionType)) {
      selectedSections.value.push({
        section_type: sectionType,
        title: label,
        order: selectedSections.value.length + 1,
      })
    }
  } else {
    selectedSections.value = selectedSections.value.filter(s => s.section_type !== sectionType)
  }
}

function removeSection(idx: number) {
  selectedSections.value.splice(idx, 1)
}

function onFormatChange() {
  resetSections()
}

function resetSections() {
  const cfg = SECTION_CONFIGS[form.content_format] || []
  selectedSections.value = cfg
    .filter(s => s.required)
    .map((s, i) => ({ section_type: s.value, title: s.label, order: i + 1 }))
}

// Drag and drop
const dragIdx = ref(-1)
const dragOverIdx = ref(-1)

function onDragStart(idx: number, e: DragEvent) {
  dragIdx.value = idx
  if (e.dataTransfer) {
    e.dataTransfer.effectAllowed = 'move'
  }
}

function onDragOver(idx: number, _e: DragEvent) {
  dragOverIdx.value = idx
}

function onDrop(targetIdx: number) {
  const fromIdx = dragIdx.value
  if (fromIdx < 0 || fromIdx === targetIdx) return
  const arr = [...selectedSections.value]
  const [item] = arr.splice(fromIdx, 1)
  arr.splice(targetIdx, 0, item)
  selectedSections.value = arr
  dragIdx.value = -1
  dragOverIdx.value = -1
}

// Init from props
watch(() => props.visible, (v) => {
  if (!v) return
  const data = props.templateData
  if (data?.id) {
    form.name = data.name || ''
    form.content_format = data.content_format || 'article'
    form.platform = data.platform || null
    form.specialty = data.specialty || null
    form.target_audience = data.target_audience || null
    form.reading_level = data.reading_level || null
    form.description = data.description || null

    const wc = data.target_word_count
    if (!wc) {
      wordCountMode.value = '1200'
    } else if ([800, 1200, 2000, 3000].includes(wc)) {
      wordCountMode.value = String(wc)
    } else {
      wordCountMode.value = 'custom'
      customWordCount.value = wc
    }

    if (Array.isArray(data.structure) && data.structure.length) {
      selectedSections.value = data.structure.map((s: any, i: number) => ({
        section_type: typeof s === 'string' ? s : s.section_type || s.id || s,
        title: typeof s === 'string' ? s : s.title || s.section_type || s,
        order: i + 1,
      }))
    } else {
      resetSections()
    }
  } else {
    form.name = ''
    form.content_format = 'article'
    form.platform = null
    form.specialty = null
    form.target_audience = null
    form.reading_level = null
    form.description = null
    wordCountMode.value = '1200'
    resetSections()
  }
}, { immediate: true })

async function handleSave() {
  if (!form.name?.trim()) {
    ElMessage.warning('请填写模板名称')
    return
  }

  const twc = wordCountMode.value === 'custom'
    ? customWordCount.value
    : wordCountMode.value ? Number(wordCountMode.value) : null

  const structure = selectedSections.value.map((s, i) => ({
    section_type: s.section_type,
    title: s.title,
    order: i + 1,
  }))

  const allTypes = new Set((SECTION_CONFIGS[form.content_format] || []).map(s => s.value))
  const selectedTypes = new Set(selectedSections.value.map(s => s.section_type))
  const skip = [...allTypes].filter(t => !selectedTypes.has(t))

  const payload: Record<string, any> = {
    name: form.name,
    content_format: form.content_format,
    platform: form.platform,
    specialty: form.specialty,
    target_audience: form.target_audience,
    reading_level: form.reading_level,
    description: form.description,
    target_word_count: twc,
    structure,
    skip_sections: skip.length ? skip : null,
  }

  saving.value = true
  try {
    if (isEdit.value) {
      await api.templates.updateTemplate(props.templateData.id, payload)
      ElMessage.success('模板已更新')
    } else {
      await api.templates.createTemplate(payload)
      ElMessage.success('模板已创建')
    }
    emit('saved')
    emit('update:visible', false)
  } catch (e: any) {
    const msg = e?.response?.data?.detail || '操作失败'
    ElMessage.error(msg)
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.template-form {
  max-height: 65vh;
  overflow-y: auto;
  padding-right: 8px;
}

.section-editor {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  width: 100%;
}

.section-available,
.section-selected {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 12px;
  min-height: 180px;
  max-height: 320px;
  overflow-y: auto;
}

.section-editor-label {
  font-size: 13px;
  font-weight: 600;
  color: #909399;
  margin-bottom: 8px;
}

.section-check-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
}

.section-drag-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  margin-bottom: 4px;
  background: #fff;
  cursor: grab;
  transition: box-shadow 0.15s, border-color 0.15s;
}

.section-drag-item:active {
  cursor: grabbing;
}

.section-drag-item.drag-over {
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.15);
}

.drag-handle {
  color: #c0c4cc;
  cursor: grab;
  font-size: 14px;
  user-select: none;
}

.section-name {
  flex: 1;
  font-size: 13px;
}

.remove-btn {
  color: #c0c4cc;
  cursor: pointer;
  font-size: 14px;
}

.remove-btn:hover {
  color: #f56c6c;
}
</style>
