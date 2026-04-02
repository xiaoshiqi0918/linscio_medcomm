/**
 * 从 Tiptap/ProseMirror JSON 抽取纯文本（用于导出前问题定位）
 */
export function extractPlainFromTiptapJson(node: unknown): string {
  if (node == null) return ''
  if (typeof node === 'string') return node
  if (typeof node !== 'object') return ''
  const o = node as { type?: string; text?: string; content?: unknown[] }
  if (o.type === 'text' && typeof o.text === 'string') return o.text
  const parts = Array.isArray(o.content) ? o.content.map(extractPlainFromTiptapJson) : []
  return parts.join('')
}

/**
 * 移除孤儿引用标记（paperId 不在 validPaperIds 中的 citationRef）
 * 保留文本，只去掉可点击的 mark，返回新 JSON（不修改原对象）
 */
export function stripOrphanCitationMarks(doc: unknown, validPaperIds: Set<number>): unknown {
  if (doc == null) return doc
  if (typeof doc !== 'object') return doc
  const o = doc as { type?: string; text?: string; marks?: Array<{ type: string; attrs?: Record<string, unknown> }>; content?: unknown[] }
  if (o.type === 'text' && typeof o.text === 'string') {
    const marks = Array.isArray(o.marks) ? o.marks : []
    const filtered = marks.filter((m) => {
      if (m?.type !== 'citationRef') return true
      const pid = Number(m?.attrs?.paperId ?? 0)
      return validPaperIds.has(pid)
    })
    if (filtered.length === marks.length) return doc
    return { ...o, marks: filtered.length ? filtered : undefined }
  }
  if (Array.isArray(o.content)) {
    const content = o.content.map((c) => stripOrphanCitationMarks(c, validPaperIds))
    return { ...o, content }
  }
  return doc
}
