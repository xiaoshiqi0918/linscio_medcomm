import { Mark, mergeAttributes } from '@tiptap/core'

/** 阅读难度标记 - 用于展示术语密度或难度提示 */
export const ReadingLevel = Mark.create({
  name: 'readingLevel',
  addAttributes() {
    return {
      level: { default: 'normal' },
      hint: { default: '' },
    }
  },
  parseHTML() {
    return [{ tag: 'span[data-reading-level]' }]
  },
  renderHTML({ HTMLAttributes }) {
    return [
      'span',
      mergeAttributes({ 'data-reading-level': '', class: 'reading-level' }, HTMLAttributes),
      0,
    ]
  },
})
