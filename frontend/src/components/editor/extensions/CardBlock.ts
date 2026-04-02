import { Node, mergeAttributes } from '@tiptap/core'
import { VueNodeViewRenderer } from '@tiptap/vue-3'
import CardBlockView from '@/components/editor/CardBlockView.vue'

export const CardBlock = Node.create({
  name: 'cardBlock',
  group: 'block',
  content: 'block+',
  addNodeView() {
    return VueNodeViewRenderer(CardBlockView)
  },
  addAttributes() {
    return {
      cardIndex: { default: 1 },
      cardTitle: { default: '' },
      colorScheme: { default: 'blue' },
      imageId: { default: null },
      imagePath: { default: null },
    }
  },
  parseHTML() {
    return [{ tag: 'div[data-type="card-block"]' }]
  },
  renderHTML({ HTMLAttributes, node }) {
    const attrs = node?.attrs || {}
    return [
      'div',
      mergeAttributes({ 'data-type': 'card-block', class: `card-${attrs.colorScheme || 'blue'}` }, HTMLAttributes),
      ['div', { class: 'card-header' }, attrs.cardTitle || `卡片 ${attrs.cardIndex ?? 1}`],
      ['div', { class: 'card-body' }, 0],
    ]
  },
})
