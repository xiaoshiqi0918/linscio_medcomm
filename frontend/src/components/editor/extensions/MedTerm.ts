import { Mark, mergeAttributes } from '@tiptap/core'

/** 专业术语 - 蓝色下划线 */
export const MedTerm = Mark.create({
  name: 'medTerm',
  addAttributes() {
    return {
      term: { default: '' },
      explain: { default: '' },
    }
  },
  parseHTML() {
    return [{ tag: 'span[data-med-term]' }]
  },
  renderHTML({ HTMLAttributes }) {
    return ['span', mergeAttributes({ 'data-med-term': '', class: 'med-term' }, HTMLAttributes), 0]
  },
})
