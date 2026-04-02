<template>
  <div class="editor-toolbar" v-if="editor">
    <el-button-group size="small">
      <el-button @click="editor.chain().focus().toggleBold().run()" :type="editor.isActive('bold') ? 'primary' : ''">
        粗体
      </el-button>
      <el-button @click="editor.chain().focus().toggleItalic().run()" :type="editor.isActive('italic') ? 'primary' : ''">
        斜体
      </el-button>
    </el-button-group>
    <el-divider direction="vertical" />
    <el-dropdown v-if="formatInsertActions.length" trigger="click">
      <el-button size="small">插入块</el-button>
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
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Editor } from '@tiptap/core'

const props = defineProps<{
  editor: Editor | null
  contentFormat?: string
}>()

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
  gap: 0.5rem;
  padding: 0.5rem;
  border-bottom: 1px solid #e5e7eb;
  background: #fafafa;
}
</style>
