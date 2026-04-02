/**
 * 形式感知编辑器 - 按 content_format 返回对应 Tiptap 扩展配置
 */
import type { Extension } from '@tiptap/core'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'

import { ComicPanel } from '@/components/editor/extensions/ComicPanel'
import { ScriptLine } from '@/components/editor/extensions/ScriptLine'
import { StoryboardFrame } from '@/components/editor/extensions/StoryboardFrame'
import { CardBlock } from '@/components/editor/extensions/CardBlock'
import { HandbookSection } from '@/components/editor/extensions/HandbookSection'
import { QuizBlock } from '@/components/editor/extensions/QuizBlock'
import { MedClaim } from '@/components/editor/extensions/MedClaim'
import { PendingClaim } from '@/components/editor/extensions/PendingClaim'
import { FactWarning } from '@/components/editor/extensions/FactWarning'
import { MedTerm } from '@/components/editor/extensions/MedTerm'
import { MedImage } from '@/components/editor/extensions/MedImage'
import { ImageCaption } from '@/components/editor/extensions/ImageCaption'
import { ReadingLevel } from '@/components/editor/extensions/ReadingLevel'
import { LocateHit } from '@/components/editor/extensions/LocateHit'
import { CitationRef } from '@/components/editor/extensions/CitationRef'

const narrativeExt = [
  StarterKit.configure({ heading: { levels: [1, 2, 3] } }),
  Placeholder.configure({ placeholder: '开始撰写医学科普内容...' }),
  MedClaim,
  PendingClaim,
  FactWarning,
  MedTerm,
  MedImage,
  ImageCaption,
  ReadingLevel,
  LocateHit,
  CitationRef,
]

const baseExtensions: Extension[] = [
  StarterKit.configure({ heading: { levels: [1, 2, 3] } }),
  Placeholder.configure({ placeholder: '开始撰写医学科普内容...' }),
  MedImage,
  ImageCaption,
  LocateHit,
  CitationRef,
]

const FORMAT_EXTENSIONS: Record<string, Extension[]> = {
  article: narrativeExt,
  story: narrativeExt,
  debunk: narrativeExt,
  qa_article: narrativeExt,
  research_read: narrativeExt,
  oral_script: [StarterKit.configure({ heading: false }), Placeholder.configure({ placeholder: '口播脚本...' }), ScriptLine, LocateHit, CitationRef],
  drama_script: [StarterKit.configure({ heading: false }), Placeholder.configure({ placeholder: '情景剧本...' }), ScriptLine, LocateHit, CitationRef],
  storyboard: [StarterKit.configure({ heading: false }), Placeholder.configure({ placeholder: '动画分镜...' }), StoryboardFrame, LocateHit, CitationRef],
  audio_script: [StarterKit.configure({ heading: false }), Placeholder.configure({ placeholder: '播客脚本...' }), ScriptLine, LocateHit, CitationRef],
  comic_strip: [StarterKit.configure({ heading: false }), Placeholder.configure({ placeholder: '条漫分格...' }), ComicPanel, LocateHit, CitationRef],
  card_series: [StarterKit.configure({ heading: { levels: [1, 2] } }), Placeholder.configure({ placeholder: '知识卡片...' }), CardBlock, LocateHit, CitationRef],
  poster: baseExtensions,
  picture_book: baseExtensions,
  long_image: baseExtensions,
  patient_handbook: [StarterKit.configure({ heading: { levels: [1, 2, 3] } }), Placeholder.configure({ placeholder: '患者手册...' }), HandbookSection, MedClaim, PendingClaim, FactWarning, MedTerm, LocateHit, CitationRef],
  quiz_article: [StarterKit.configure({ heading: { levels: [1, 2] } }), Placeholder.configure({ placeholder: '自测科普...' }), QuizBlock, MedClaim, PendingClaim, FactWarning, MedTerm, LocateHit, CitationRef],
  h5_outline: baseExtensions,
}

export function useFormatEditor(contentFormat?: string): Extension[] {
  if (!contentFormat || !FORMAT_EXTENSIONS[contentFormat]) {
    return baseExtensions
  }
  return FORMAT_EXTENSIONS[contentFormat]
}

export { FORMAT_EXTENSIONS }
