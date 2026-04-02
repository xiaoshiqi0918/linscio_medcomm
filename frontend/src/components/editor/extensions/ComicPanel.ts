import { Node, mergeAttributes } from '@tiptap/core'
import { VueNodeViewRenderer } from '@tiptap/vue-3'
import ComicPanelView from '@/components/editor/ComicPanelView.vue'

export const ComicPanel = Node.create({
  name: 'comicPanel',
  group: 'block',
  content: 'block+',
  addNodeView() {
    return VueNodeViewRenderer(ComicPanelView)
  },
  addAttributes() {
    return {
      panelIndex: { default: 1 },
      sceneDesc: { default: '' },
      dialogue: { default: '' },
      narration: { default: '' },
      imageId: { default: null },
      imagePath: { default: null },
    }
  },
  parseHTML() {
    return [{ tag: 'div[data-type="comic-panel"]' }]
  },
  renderHTML({ HTMLAttributes, node }) {
    const idx = node?.attrs?.panelIndex ?? 1
    return [
      'div',
      mergeAttributes({ 'data-type': 'comic-panel' }, HTMLAttributes),
      ['div', { class: 'panel-meta' }, `第 ${idx} 格`],
      ['div', { class: 'panel-content' }, 0],
    ]
  },
})
