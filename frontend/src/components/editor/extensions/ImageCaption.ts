import { Node, mergeAttributes } from '@tiptap/core'

/** 图片说明节点 */
export const ImageCaption = Node.create({
  name: 'imageCaption',
  group: 'block',
  content: 'inline*',
  parseHTML() {
    return [{ tag: 'figcaption[data-image-caption]' }]
  },
  renderHTML({ HTMLAttributes }) {
    return ['figcaption', mergeAttributes({ 'data-image-caption': '', class: 'image-caption' }, HTMLAttributes), 0]
  },
})
