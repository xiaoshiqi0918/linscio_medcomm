<template>
  <div class="editor-toolbar" v-if="editor">
    <!-- 撤销 / 重做 -->
    <el-button-group size="small">
      <el-tooltip content="撤销 (⌘Z)" placement="bottom" :show-after="350">
        <el-button class="tb-btn" :disabled="!canUndo" @click="run((c) => c.undo())">↶</el-button>
      </el-tooltip>
      <el-tooltip content="重做 (⇧⌘Z)" placement="bottom" :show-after="350">
        <el-button class="tb-btn" :disabled="!canRedo" @click="run((c) => c.redo())">↷</el-button>
      </el-tooltip>
    </el-button-group>

    <el-divider direction="vertical" />

    <!-- 段落样式（正文 / H1-H3 / 引用） -->
    <el-select
      class="tb-select tb-select--block"
      :model-value="currentBlockType"
      placeholder="段落样式"
      size="small"
      @change="setBlockType"
    >
      <el-option label="正文" value="paragraph" />
      <el-option label="标题 1" value="h1" />
      <el-option label="标题 2" value="h2" />
      <el-option label="标题 3" value="h3" />
      <el-option label="引用块" value="blockquote" />
    </el-select>

    <!-- 字体 -->
    <el-select
      class="tb-select tb-select--font"
      :model-value="currentFontFamily"
      placeholder="字体"
      size="small"
      filterable
      allow-create
      @change="setFontFamily"
    >
      <el-option v-for="f in FONT_FAMILIES" :key="f.value" :label="f.label" :value="f.value">
        <span :style="{ fontFamily: f.value || 'inherit' }">{{ f.label }}</span>
      </el-option>
    </el-select>

    <!-- 字号 -->
    <el-select
      class="tb-select tb-select--size"
      :model-value="currentFontSize"
      placeholder="字号"
      size="small"
      filterable
      allow-create
      @change="setFontSize"
    >
      <el-option v-for="s in FONT_SIZES" :key="s.value" :label="s.label" :value="s.value" />
    </el-select>

    <el-divider direction="vertical" />

    <!-- B / I / U / S -->
    <el-button-group size="small">
      <el-tooltip content="加粗 (⌘B)" placement="bottom" :show-after="350">
        <el-button
          class="tb-btn tb-btn--mark"
          :type="editor.isActive('bold') ? 'primary' : ''"
          @click="run((c) => c.toggleBold())"
        ><b>B</b></el-button>
      </el-tooltip>
      <el-tooltip content="斜体 (⌘I)" placement="bottom" :show-after="350">
        <el-button
          class="tb-btn tb-btn--mark"
          :type="editor.isActive('italic') ? 'primary' : ''"
          @click="run((c) => c.toggleItalic())"
        ><i>I</i></el-button>
      </el-tooltip>
      <el-tooltip content="下划线 (⌘U)" placement="bottom" :show-after="350">
        <el-button
          class="tb-btn tb-btn--mark"
          :type="editor.isActive('underline') ? 'primary' : ''"
          @click="run((c) => c.toggleUnderline())"
        ><u>U</u></el-button>
      </el-tooltip>
      <el-tooltip content="删除线" placement="bottom" :show-after="350">
        <el-button
          class="tb-btn tb-btn--mark"
          :type="editor.isActive('strike') ? 'primary' : ''"
          @click="run((c) => c.toggleStrike())"
        ><s>S</s></el-button>
      </el-tooltip>
    </el-button-group>

    <el-divider direction="vertical" />

    <!-- 对齐 -->
    <el-button-group size="small">
      <el-tooltip content="左对齐" placement="bottom" :show-after="350">
        <el-button
          class="tb-btn tb-btn--icon"
          :type="alignActive('left') ? 'primary' : ''"
          @click="setAlign('left')"
        >☰<span class="tb-align-hint">L</span></el-button>
      </el-tooltip>
      <el-tooltip content="居中" placement="bottom" :show-after="350">
        <el-button
          class="tb-btn tb-btn--icon"
          :type="alignActive('center') ? 'primary' : ''"
          @click="setAlign('center')"
        >≡<span class="tb-align-hint">C</span></el-button>
      </el-tooltip>
      <el-tooltip content="右对齐" placement="bottom" :show-after="350">
        <el-button
          class="tb-btn tb-btn--icon"
          :type="alignActive('right') ? 'primary' : ''"
          @click="setAlign('right')"
        >☰<span class="tb-align-hint">R</span></el-button>
      </el-tooltip>
      <el-tooltip content="两端对齐" placement="bottom" :show-after="350">
        <el-button
          class="tb-btn tb-btn--icon"
          :type="alignActive('justify') ? 'primary' : ''"
          @click="setAlign('justify')"
        >☰<span class="tb-align-hint">J</span></el-button>
      </el-tooltip>
    </el-button-group>

    <el-divider direction="vertical" />

    <!-- 首行缩进 -->
    <el-tooltip content="首行缩进 2 字符" placement="bottom" :show-after="350">
      <el-button
        class="tb-btn tb-btn--icon"
        size="small"
        :type="editor.isActive('paragraph', { indent: true }) || editor.isActive('heading', { indent: true }) ? 'primary' : ''"
        @click="toggleIndent"
      >→¶</el-button>
    </el-tooltip>

    <el-divider direction="vertical" />

    <!-- 列表 -->
    <el-button-group size="small">
      <el-tooltip content="项目符号" placement="bottom" :show-after="350">
        <el-button
          class="tb-btn tb-btn--icon"
          :type="editor.isActive('bulletList') ? 'primary' : ''"
          @click="run((c) => c.toggleBulletList())"
        >• 列表</el-button>
      </el-tooltip>
      <el-tooltip content="编号列表" placement="bottom" :show-after="350">
        <el-button
          class="tb-btn tb-btn--icon"
          :type="editor.isActive('orderedList') ? 'primary' : ''"
          @click="run((c) => c.toggleOrderedList())"
        >1. 列表</el-button>
      </el-tooltip>
    </el-button-group>

    <!-- 插入块（保留旧行为） -->
    <template v-if="formatInsertActions.length">
      <el-divider direction="vertical" />
      <el-dropdown trigger="click">
        <el-button size="small" class="tb-btn">插入块 ▾</el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item
              v-for="act in formatInsertActions"
              :key="act.name"
              @click="act.insert(editor)"
            >
              {{ act.label }}
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, watchEffect, ref } from 'vue'
import type { Editor } from '@tiptap/core'

const props = defineProps<{
  editor: Editor | null
  contentFormat?: string
}>()

const FONT_FAMILIES: Array<{ label: string; value: string }> = [
  { label: '默认字体', value: '' },
  { label: '宋体', value: '"SimSun", "宋体", serif' },
  { label: '仿宋', value: '"FangSong", "仿宋", serif' },
  { label: '楷体', value: '"KaiTi", "楷体", serif' },
  { label: '黑体', value: '"SimHei", "黑体", sans-serif' },
  { label: '微软雅黑', value: '"Microsoft YaHei", "微软雅黑", sans-serif' },
  { label: '苹方', value: '"PingFang SC", sans-serif' },
  { label: 'Times New Roman', value: '"Times New Roman", serif' },
  { label: 'Arial', value: 'Arial, sans-serif' },
  { label: 'Helvetica', value: 'Helvetica, Arial, sans-serif' },
  { label: 'Georgia', value: 'Georgia, serif' },
]

const FONT_SIZES = [
  { label: '12px', value: '12px' },
  { label: '13px', value: '13px' },
  { label: '14px', value: '14px' },
  { label: '15px', value: '15px' },
  { label: '16px', value: '16px' },
  { label: '18px', value: '18px' },
  { label: '20px', value: '20px' },
  { label: '22px', value: '22px' },
  { label: '24px', value: '24px' },
  { label: '28px', value: '28px' },
  { label: '32px', value: '32px' },
]

/** 通过订阅 selectionUpdate / transaction 强制刷新 active state（el-button 不会自动 re-render） */
const tick = ref(0)

watchEffect((onCleanup) => {
  const ed = props.editor
  if (!ed) return
  const refresh = () => {
    tick.value++
  }
  ed.on('selectionUpdate', refresh)
  ed.on('transaction', refresh)
  ed.on('update', refresh)
  onCleanup(() => {
    ed.off('selectionUpdate', refresh)
    ed.off('transaction', refresh)
    ed.off('update', refresh)
  })
})

onBeforeUnmount(() => {
  // ensure editor's listeners we attached above get released by watchEffect's onCleanup
})

function run(fn: (chain: ReturnType<Editor['chain']>) => ReturnType<Editor['chain']>) {
  const ed = props.editor
  if (!ed) return
  fn(ed.chain().focus()).run()
}

const canUndo = computed(() => {
  void tick.value
  return !!props.editor?.can?.().undo?.()
})
const canRedo = computed(() => {
  void tick.value
  return !!props.editor?.can?.().redo?.()
})

const currentBlockType = computed<string>(() => {
  void tick.value
  const ed = props.editor
  if (!ed) return 'paragraph'
  if (ed.isActive('heading', { level: 1 })) return 'h1'
  if (ed.isActive('heading', { level: 2 })) return 'h2'
  if (ed.isActive('heading', { level: 3 })) return 'h3'
  if (ed.isActive('blockquote')) return 'blockquote'
  return 'paragraph'
})

function setBlockType(val: string) {
  const ed = props.editor
  if (!ed) return
  const c = ed.chain().focus()
  if (val === 'paragraph') c.setParagraph().run()
  else if (val === 'h1') c.toggleHeading({ level: 1 }).run()
  else if (val === 'h2') c.toggleHeading({ level: 2 }).run()
  else if (val === 'h3') c.toggleHeading({ level: 3 }).run()
  else if (val === 'blockquote') c.toggleBlockquote().run()
}

const currentFontFamily = computed<string>(() => {
  void tick.value
  return (props.editor?.getAttributes('textStyle')?.fontFamily as string) || ''
})

function setFontFamily(value: string) {
  const ed = props.editor
  if (!ed) return
  if (!value) ed.chain().focus().unsetFontFamily?.().run()
  else ed.chain().focus().setFontFamily(value).run()
}

const currentFontSize = computed<string>(() => {
  void tick.value
  return (props.editor?.getAttributes('textStyle')?.fontSize as string) || ''
})

function setFontSize(value: string) {
  const ed = props.editor
  if (!ed) return
  if (!value) (ed.chain().focus() as any).unsetFontSize?.().run()
  else (ed.chain().focus() as any).setFontSize(value).run()
}

function alignActive(align: 'left' | 'center' | 'right' | 'justify') {
  void tick.value
  const ed = props.editor
  if (!ed) return false
  return ed.isActive({ textAlign: align })
}

function setAlign(align: 'left' | 'center' | 'right' | 'justify') {
  const ed = props.editor
  if (!ed) return
  ed.chain().focus().setTextAlign(align).run()
}

function toggleIndent() {
  const ed = props.editor
  if (!ed) return
  ;(ed.chain().focus() as any).toggleParagraphIndent?.().run()
}

const formatInsertActions = computed(() => {
  const fmt = props.contentFormat
  const ed = props.editor
  if (!ed) return []

  const actions: { name: string; label: string; insert: (e: Editor) => void }[] = []

  if (fmt === 'comic_strip') {
    actions.push({
      name: 'comicPanel',
      label: '漫画格',
      insert: (e) => e.chain().focus().insertContent({ type: 'comicPanel', attrs: { panelIndex: 1 }, content: [{ type: 'paragraph' }] }).run(),
    })
  }
  if (fmt === 'oral_script' || fmt === 'drama_script' || fmt === 'audio_script') {
    actions.push({
      name: 'scriptLine',
      label: '脚本行',
      insert: (e) => e.chain().focus().insertContent({ type: 'scriptLine', attrs: { timestamp: '00:00', role: '旁白' }, content: [{ type: 'paragraph' }] }).run(),
    })
  }
  if (fmt === 'storyboard') {
    actions.push({
      name: 'storyboardFrame',
      label: '分镜帧',
      insert: (e) => e.chain().focus().insertContent({ type: 'storyboardFrame', attrs: { frameIndex: 1, duration: '3' }, content: [{ type: 'paragraph' }] }).run(),
    })
  }
  if (fmt === 'card_series') {
    actions.push({
      name: 'cardBlock',
      label: '知识卡片',
      insert: (e) => e.chain().focus().insertContent({ type: 'cardBlock', attrs: { cardIndex: 1, cardTitle: '标题' }, content: [{ type: 'paragraph' }] }).run(),
    })
  }
  if (fmt === 'patient_handbook') {
    actions.push({
      name: 'handbookSection',
      label: '警示框',
      insert: (e) => e.chain().focus().insertContent({ type: 'handbookSection', attrs: { sectionStyle: 'warning' }, content: [{ type: 'paragraph' }] }).run(),
    })
    actions.push({
      name: 'handbookTip',
      label: '提示框',
      insert: (e) => e.chain().focus().insertContent({ type: 'handbookSection', attrs: { sectionStyle: 'tip' }, content: [{ type: 'paragraph' }] }).run(),
    })
  }
  if (fmt === 'quiz_article') {
    actions.push({
      name: 'quizBlock',
      label: '自测题',
      insert: (e) => e.chain().focus().insertContent({ type: 'quizBlock', attrs: { questionIndex: 1 }, content: [{ type: 'paragraph' }] }).run(),
    })
  }

  return actions
})
</script>

<style scoped>
.editor-toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.35rem;
  padding: 0.4rem 0.55rem;
  border-bottom: 1px solid #e5e7eb;
  background: #fafafa;
  position: sticky;
  top: 0;
  z-index: 4;
}

.editor-toolbar :deep(.el-divider--vertical) {
  margin: 0 0.15rem;
  height: 18px;
}

.tb-btn {
  min-width: 30px;
  padding-left: 8px;
  padding-right: 8px;
}
.tb-btn--mark { font-family: serif; }
.tb-btn--mark b { font-weight: 700; }
.tb-btn--mark i { font-style: italic; font-family: Georgia, serif; }
.tb-btn--mark u { text-decoration: underline; text-underline-offset: 2px; }
.tb-btn--mark s { text-decoration: line-through; }

.tb-btn--icon {
  font-size: 13px;
}
.tb-align-hint {
  display: inline-block;
  margin-left: 2px;
  font-size: 10px;
  color: #6b7280;
}
.el-button.is-primary .tb-align-hint { color: #fff; opacity: 0.9; }

.tb-select {
  min-width: 88px;
}
.tb-select--block { width: 96px; }
.tb-select--font { width: 132px; }
.tb-select--size { width: 86px; }
</style>
