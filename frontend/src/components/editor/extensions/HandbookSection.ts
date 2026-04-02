import { Node, mergeAttributes } from '@tiptap/core'

export const HandbookSection = Node.create({
  name: 'handbookSection',
  group: 'block',
  content: 'block+',
  addAttributes() {
    return {
      sectionStyle: { default: 'normal' }, // normal | warning | tip | caution
    }
  },
  parseHTML() {
    return [{ tag: 'div[data-type="handbook-section"]' }]
  },
  renderHTML({ HTMLAttributes, node }) {
    const style = node?.attrs?.sectionStyle || 'normal'
    const labels: Record<string, string> = {
      normal: '正文',
      warning: '⚠️ 警示',
      tip: '💡 提示',
      caution: '📋 注意',
    }
    return [
      'div',
      mergeAttributes({ 'data-type': 'handbook-section', class: `handbook-${style}` }, HTMLAttributes),
      ['div', { class: 'handbook-label' }, labels[style]],
      ['div', { class: 'handbook-content' }, 0],
    ]
  },
})
