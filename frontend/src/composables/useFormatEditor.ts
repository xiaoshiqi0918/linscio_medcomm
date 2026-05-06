/**
 * 形式感知编辑器 - 按 content_format 返回对应 Tiptap 扩展配置
 */
import type { Extension } from '@tiptap/core'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import Underline from '@tiptap/extension-underline'
import TextStyle from '@tiptap/extension-text-style'
import TextAlign from '@tiptap/extension-text-align'
import FontFamily from '@tiptap/extension-font-family'

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
import { AigcWarning } from '@/components/editor/extensions/AigcWarning'
import { FontSize } from '@/components/editor/extensions/FontSize'
import { ParagraphIndent } from '@/components/editor/extensions/ParagraphIndent'

/** 通用排版工具：字体、字号、下划线、对齐、首行缩进 —— 所有格式共享 */
const wordLikeExt: Extension[] = [
  Underline,
  TextStyle,
  FontFamily.configure({ types: ['textStyle'] }),
  FontSize,
  TextAlign.configure({ types: ['paragraph', 'heading'] }),
  ParagraphIndent,
]

const narrativeExt = [
  StarterKit.configure({ heading: { levels: [1, 2, 3] } }),
  Placeholder.configure({ placeholder: '开始撰写医学科普内容...' }),
  ...wordLikeExt,
  AigcWarning,
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
  ...wordLikeExt,
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
  oral_script: [StarterKit.configure({ heading: false }), Placeholder.configure({ placeholder: '口播脚本...' }), ...wordLikeExt, ScriptLine, LocateHit, CitationRef],
  drama_script: [StarterKit.configure({ heading: false }), Placeholder.configure({ placeholder: '情景剧本...' }), ...wordLikeExt, ScriptLine, LocateHit, CitationRef],
  storyboard: [StarterKit.configure({ heading: false }), Placeholder.configure({ placeholder: '动画分镜...' }), ...wordLikeExt, StoryboardFrame, LocateHit, CitationRef],
  audio_script: [StarterKit.configure({ heading: false }), Placeholder.configure({ placeholder: '播客脚本...' }), ...wordLikeExt, ScriptLine, LocateHit, CitationRef],
  comic_strip: [StarterKit.configure({ heading: false }), Placeholder.configure({ placeholder: '条漫分格...' }), ...wordLikeExt, ComicPanel, LocateHit, CitationRef],
  card_series: [StarterKit.configure({ heading: { levels: [1, 2] } }), Placeholder.configure({ placeholder: '知识卡片...' }), ...wordLikeExt, CardBlock, LocateHit, CitationRef],
  poster: baseExtensions,
  picture_book: baseExtensions,
  long_image: baseExtensions,
  patient_handbook: [StarterKit.configure({ heading: { levels: [1, 2, 3] } }), Placeholder.configure({ placeholder: '患者手册...' }), ...wordLikeExt, HandbookSection, MedClaim, PendingClaim, FactWarning, MedTerm, LocateHit, CitationRef],
  quiz_article: [StarterKit.configure({ heading: { levels: [1, 2] } }), Placeholder.configure({ placeholder: '自测科普...' }), ...wordLikeExt, QuizBlock, MedClaim, PendingClaim, FactWarning, MedTerm, LocateHit, CitationRef],
  h5_outline: baseExtensions,
  /** 与同类型 narrative 形式一致：[共识]/[[待核实]] 等语义节点与核实联动 */
  contest_article: narrativeExt,
}

export function useFormatEditor(contentFormat?: string): Extension[] {
  if (!contentFormat || !FORMAT_EXTENSIONS[contentFormat]) {
    return baseExtensions
  }
  return FORMAT_EXTENSIONS[contentFormat]
}

export { FORMAT_EXTENSIONS }
