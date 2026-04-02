import { Mark, mergeAttributes } from '@tiptap/core'

/** 引用标记：[1] 可点击跳转文献详情 */
export const CitationRef = Mark.create({
  name: 'citationRef',
  inclusive: false,
  addAttributes() {
    return {
      paperId: { default: null },
      externalRefId: { default: null },
      articleId: { default: null },
      sectionId: { default: null },
      index: { default: null },
      title: { default: '' },
    }
  },
  parseHTML() {
    return [{ tag: 'a[data-citation-ref]' }]
  },
  renderHTML({ HTMLAttributes }) {
    const pid = HTMLAttributes.paperId ?? ''
    const xid = HTMLAttributes.externalRefId ?? ''
    const aid = HTMLAttributes.articleId ?? ''
    const sid = HTMLAttributes.sectionId ?? ''
    return [
      'a',
      mergeAttributes(
        {
          'data-citation-ref': '1',
          'data-paper-id': String(pid),
          'data-external-ref-id': String(xid),
          'data-article-id': String(aid),
          'data-section-id': String(sid),
          class: 'citation-ref',
          href: '#',
          title: (HTMLAttributes.title as string) || '查看引用文献',
        },
        HTMLAttributes
      ),
      0,
    ]
  },
})
