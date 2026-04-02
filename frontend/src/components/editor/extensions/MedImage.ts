import { Node, mergeAttributes } from '@tiptap/core'

/** 医学图片节点 - 支持 medcomm-image:// 协议 */
export const MedImage = Node.create({
  name: 'medImage',
  group: 'block',
  draggable: true,
  addAttributes() {
    return {
      src: { default: '' },
      alt: { default: '' },
      title: { default: '' },
    }
  },
  parseHTML() {
    return [{ tag: 'img[data-med-image]' }]
  },
  renderHTML({ HTMLAttributes }) {
    return ['figure', { class: 'med-image-wrapper' }, ['img', mergeAttributes({ 'data-med-image': '', class: 'med-image' }, HTMLAttributes)]]
  },
})
