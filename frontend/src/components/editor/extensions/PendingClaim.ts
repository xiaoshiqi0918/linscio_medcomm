import { Mark, mergeAttributes } from '@tiptap/core'

/** 医学声明待核实 - 黄色高亮 */
export const PendingClaim = Mark.create({
  name: 'pendingClaim',
  addAttributes() {
    return {}
  },
  parseHTML() {
    return [{ tag: 'span[data-pending-claim]' }]
  },
  renderHTML({ HTMLAttributes }) {
    return ['span', mergeAttributes({ 'data-pending-claim': '', class: 'pending-claim' }, HTMLAttributes), 0]
  },
})
