/**
 * ParagraphIndent - 给 paragraph / heading 节点加一个 indent 属性，
 * 控制是否首行缩进 2em（与 Word 的"首行缩进"按钮等价）。
 *
 * indent === true  → 强制首行缩进（覆盖默认）
 * indent === false → 强制不缩进（覆盖默认）
 * indent === null  → 由模板 / 导出端按格式决定（不写 inline style）
 */
import { Extension } from '@tiptap/core'

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    paragraphIndent: {
      setParagraphIndent: (indent: boolean) => ReturnType
      toggleParagraphIndent: () => ReturnType
      clearParagraphIndent: () => ReturnType
    }
  }
}

const TYPES = ['paragraph', 'heading']

export const ParagraphIndent = Extension.create({
  name: 'paragraphIndent',
  addOptions() {
    return { types: TYPES }
  },
  addGlobalAttributes() {
    return [
      {
        types: this.options.types,
        attributes: {
          indent: {
            default: null as boolean | null,
            keepOnSplit: true,
            parseHTML: (element: HTMLElement) => {
              const v = element.style.textIndent || element.getAttribute('data-indent')
              if (!v) return null
              if (v === 'true' || v === '2em' || v === '2rem') return true
              if (v === 'false' || v === '0' || v === '0px') return false
              return null
            },
            renderHTML: (attrs: Record<string, unknown>) => {
              const v = attrs.indent
              if (v === true) return { 'data-indent': 'true', style: 'text-indent: 2em' }
              if (v === false) return { 'data-indent': 'false', style: 'text-indent: 0' }
              return {}
            },
          },
        },
      },
    ]
  },
  addCommands() {
    return {
      setParagraphIndent:
        (indent: boolean) =>
        ({ commands }) => {
          let ok = false
          for (const t of this.options.types) {
            if (commands.updateAttributes(t, { indent })) ok = true
          }
          return ok
        },
      toggleParagraphIndent:
        () =>
        ({ editor, commands }) => {
          const cur = editor.getAttributes('paragraph')?.indent
            ?? editor.getAttributes('heading')?.indent
          const next = cur === true ? false : true
          let ok = false
          for (const t of this.options.types) {
            if (commands.updateAttributes(t, { indent: next })) ok = true
          }
          return ok
        },
      clearParagraphIndent:
        () =>
        ({ commands }) => {
          let ok = false
          for (const t of this.options.types) {
            if (commands.updateAttributes(t, { indent: null })) ok = true
          }
          return ok
        },
    }
  },
})

export default ParagraphIndent
