import { Mark, mergeAttributes } from '@tiptap/core'

/** 医学声明已核实 - 绿色高亮；可挂文献/chunk 依据供点击核对 */
export const MedClaim = Mark.create({
  name: 'medClaim',
  addAttributes() {
    return {
      source: { default: '' },
      paperId: { default: null as number | null },
      evidenceSnippet: { default: '' },
      evidenceSource: { default: '' },
      chunkId: { default: null as string | null },
    }
  },
  parseHTML() {
    return [
      {
        tag: 'span[data-med-claim]',
        getAttrs: (el) => {
          const e = el as HTMLElement
          const pid = e.getAttribute('data-paper-id')
          return {
            source: e.getAttribute('data-source') || '',
            paperId: pid && /^\d+$/.test(pid) ? Number(pid) : null,
            evidenceSnippet: (() => {
              const raw = e.getAttribute('data-evidence-snippet')
              if (!raw) return ''
              try {
                return decodeURIComponent(raw)
              } catch {
                return raw
              }
            })(),
            evidenceSource: e.getAttribute('data-evidence-source') || '',
            chunkId: e.getAttribute('data-chunk-id'),
          }
        },
      },
    ]
  },
  renderHTML({ HTMLAttributes }) {
    const paperId = HTMLAttributes.paperId
    const chunkId = HTMLAttributes.chunkId
    const snippet = HTMLAttributes.evidenceSnippet as string | undefined
    const src = HTMLAttributes.evidenceSource as string | undefined
    const legacySource = HTMLAttributes.source as string | undefined
    const attrs: Record<string, string> = {
      'data-med-claim': '',
      class: 'med-claim',
    }
    if (paperId != null && paperId !== '') attrs['data-paper-id'] = String(paperId)
    if (chunkId) attrs['data-chunk-id'] = String(chunkId)
    if (legacySource) attrs['data-source'] = String(legacySource)
    if (src) attrs['data-evidence-source'] = String(src).slice(0, 500)
    if (snippet) {
      const enc = encodeURIComponent(String(snippet).slice(0, 400))
      attrs['data-evidence-snippet'] = enc
    }
    const { paperId: _p, chunkId: _c, evidenceSnippet: _e, evidenceSource: _es, source: _s, ...rest } =
      HTMLAttributes
    return ['span', mergeAttributes(attrs, rest), 0]
  },
})
