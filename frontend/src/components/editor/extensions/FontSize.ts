/**
 * FontSize - 在 TextStyle 上扩展一个 fontSize 属性
 *
 * 用法：
 *   editor.chain().focus().setMark('textStyle', { fontSize: '16px' }).run()
 *   editor.chain().focus().setFontSize('16px').run()
 *   editor.chain().focus().unsetFontSize().run()
 */
import { Extension } from '@tiptap/core'

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    fontSize: {
      setFontSize: (size: string) => ReturnType
      unsetFontSize: () => ReturnType
    }
  }
}

export const FontSize = Extension.create({
  name: 'fontSize',
  addOptions() {
    return { types: ['textStyle'] as string[] }
  },
  addGlobalAttributes() {
    return [
      {
        types: this.options.types,
        attributes: {
          fontSize: {
            default: null as string | null,
            parseHTML: (element: HTMLElement) => element.style.fontSize || null,
            renderHTML: (attrs: Record<string, unknown>) => {
              const v = attrs.fontSize
              if (!v) return {}
              return { style: `font-size: ${v}` }
            },
          },
        },
      },
    ]
  },
  addCommands() {
    return {
      setFontSize:
        (size: string) =>
        ({ chain }) => chain().setMark('textStyle', { fontSize: size }).run(),
      unsetFontSize:
        () =>
        ({ chain }) =>
          chain().setMark('textStyle', { fontSize: null }).removeEmptyTextStyle().run(),
    }
  },
})

export default FontSize
