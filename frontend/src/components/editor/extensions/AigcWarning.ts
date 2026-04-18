import { Mark, mergeAttributes } from '@tiptap/core'

/** AIGC高风险段落高亮标记 */
export const AigcWarning = Mark.create({
  name: 'aigcWarning',
  addAttributes() {
    return {
      level: { default: 'medium' },
      tooltip: { default: '' },
    }
  },
  parseHTML() {
    return [{ tag: 'span[data-aigc-warning]' }]
  },
  renderHTML({ HTMLAttributes }) {
    const level = HTMLAttributes.level || 'medium'
    const cls = level === 'high' ? 'aigc-warning-high' : 'aigc-warning-medium'
    return [
      'span',
      mergeAttributes(
        {
          'data-aigc-warning': level,
          class: cls,
          title: HTMLAttributes.tooltip || '',
        },
        HTMLAttributes,
      ),
      0,
    ]
  },
})
