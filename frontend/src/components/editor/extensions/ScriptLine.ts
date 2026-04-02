import { Node, mergeAttributes } from '@tiptap/core'

export const ScriptLine = Node.create({
  name: 'scriptLine',
  group: 'block',
  content: 'block+',
  addAttributes() {
    return {
      timestamp: { default: '' },
      role: { default: '' },
      lineType: { default: 'narration' }, // narration | dialogue | action | note
    }
  },
  parseHTML() {
    return [{ tag: 'div[data-type="script-line"]' }]
  },
  renderHTML({ HTMLAttributes, node }) {
    const attrs = node?.attrs || {}
    return [
      'div',
      mergeAttributes({ 'data-type': 'script-line' }, HTMLAttributes),
      ['span', { class: 'script-timestamp' }, attrs.timestamp || ''],
      ['span', { class: 'script-role' }, attrs.role || ''],
      ['span', { class: 'script-text' }, 0],
    ]
  },
})
