import { Node, mergeAttributes } from '@tiptap/core'
import { VueNodeViewRenderer } from '@tiptap/vue-3'
import StoryboardFrameView from '@/components/editor/StoryboardFrameView.vue'

export const StoryboardFrame = Node.create({
  name: 'storyboardFrame',
  group: 'block',
  content: 'block+',
  addNodeView() {
    return VueNodeViewRenderer(StoryboardFrameView)
  },
  addAttributes() {
    return {
      frameIndex: { default: 1 },
      duration: { default: '' },
      sceneDesc: { default: '' },
      voiceover: { default: '' },
      cameraNote: { default: '' },
      imageId: { default: null },
      imagePath: { default: null },
    }
  },
  parseHTML() {
    return [{ tag: 'div[data-type="storyboard-frame"]' }]
  },
  renderHTML({ HTMLAttributes, node }) {
    const attrs = node?.attrs || {}
    return [
      'div',
      mergeAttributes({ 'data-type': 'storyboard-frame' }, HTMLAttributes),
      ['div', { class: 'frame-meta' }, `分镜 ${attrs.frameIndex ?? 1} · ${attrs.duration || '—'}s`],
      ['div', { class: 'frame-content' }, 0],
    ]
  },
})
