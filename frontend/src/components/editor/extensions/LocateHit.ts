import { Mark, mergeAttributes } from '@tiptap/core'

/** 临时定位高亮（用于导出前问题一键定位） */
export const LocateHit = Mark.create({
  name: 'locateHit',
  parseHTML() {
    return [{ tag: 'span[data-locate-hit]' }]
  },
  renderHTML({ HTMLAttributes }) {
    return ['span', mergeAttributes({ 'data-locate-hit': '', class: 'locate-hit' }, HTMLAttributes), 0]
  },
})
