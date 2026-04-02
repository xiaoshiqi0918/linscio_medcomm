import { Extension } from '@tiptap/core'

/** 供条漫格等 NodeView 读取当前文章 ID，用于生图连贯性（article_id → DB 锁定文案/种子） */
export const MedCommImageContext = Extension.create({
  name: 'medCommImageContext',
  addStorage() {
    return {
      articleId: null as number | null,
    }
  },
})
