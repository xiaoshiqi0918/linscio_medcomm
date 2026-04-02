import { Mark, mergeAttributes } from '@tiptap/core'

/** 数据占位符/绝对化表述 - 橙色高亮 */
export const FactWarning = Mark.create({
  name: 'factWarning',
  addAttributes() {
    return {
      message: { default: '' },
    }
  },
  parseHTML() {
    return [{ tag: 'span[data-fact-warning]' }]
  },
  renderHTML({ HTMLAttributes }) {
    return ['span', mergeAttributes({ 'data-fact-warning': '', class: 'fact-warning' }, HTMLAttributes), 0]
  },
})
