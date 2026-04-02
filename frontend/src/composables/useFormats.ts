/** 形式与平台常量，与后端 format_router 保持一致 */
export const FORMAT_NAMES: Record<string, string> = {
  article: '图文文章',
  story: '科普故事',
  debunk: '辟谣文',
  qa_article: '问答科普',
  research_read: '研究速读',
  oral_script: '口播脚本',
  drama_script: '情景剧本',
  storyboard: '动画分镜',
  audio_script: '播客脚本',
  comic_strip: '条漫',
  card_series: '知识卡片系列',
  poster: '科普海报',
  picture_book: '科普绘本',
  long_image: '竖版长图',
  patient_handbook: '患者教育手册',
  quiz_article: '自测科普',
  h5_outline: 'H5 互动大纲',
}

export const PLATFORM_NAMES: Record<string, string> = {
  wechat: '微信公众号',
  douyin: '抖音/快手',
  xiaohongshu: '小红书',
  bilibili: 'B站',
  journal: '科普期刊',
  offline: '线下印刷',
  universal: '通用',
}

export function formatLabel(formatId: string): string {
  return FORMAT_NAMES[formatId] || formatId || '未选形式'
}

export function platformLabel(platformId: string): string {
  return PLATFORM_NAMES[platformId] || platformId || '未选平台'
}
