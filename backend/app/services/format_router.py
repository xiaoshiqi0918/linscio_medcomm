"""
形式路由器 - 17 种科普形式 × 7 种平台
集中管理 Agent 群、章节结构、导出器、字段可见性
"""

# 形式 → Agent / 导出器 / 图像风格
FORMAT_CONFIG = {
    "article": {"agent": "ArticleAgents", "exporter": "HtmlDocxExporter"},
    "story": {"agent": "StoryAgents", "exporter": "HtmlDocxExporter"},
    "debunk": {"agent": "DebunkAgents", "exporter": "HtmlDocxExporter"},
    "qa_article": {"agent": "QAAgents", "exporter": "HtmlDocxExporter"},
    "research_read": {"agent": "ResearchAgents", "exporter": "HtmlDocxExporter"},
    "oral_script": {"agent": "OralAgents", "exporter": "ScriptExporter"},
    "drama_script": {"agent": "DramaAgents", "exporter": "ScriptExporter"},
    "storyboard": {"agent": "StoryboardAgents", "exporter": "StoryboardExporter"},
    "audio_script": {"agent": "AudioAgents", "exporter": "ScriptExporter"},
    "comic_strip": {"agent": "ComicAgents", "exporter": "ComicExporter", "image_style": "comic"},
    "card_series": {"agent": "CardAgents", "exporter": "CardExporter", "image_style": "flat_design"},
    "poster": {"agent": "PosterAgents", "exporter": "PdfExporter", "image_style": "medical_illustration"},
    "picture_book": {"agent": "PictureBookAgents", "exporter": "PdfExporter", "image_style": "picture_book"},
    "long_image": {"agent": "LongImageAgents", "exporter": "LongImageExporter"},
    "patient_handbook": {"agent": "HandbookAgents", "exporter": "PdfExporter"},
    "quiz_article": {"agent": "QuizAgents", "exporter": "HtmlDocxExporter"},
    "h5_outline": {"agent": "H5Agents", "exporter": "TxtExporter"},
}

# 形式 × 平台推荐矩阵  3=强推荐 2=推荐 0=不推荐
FORMAT_PLATFORM_MATRIX = {
    "article": {"wechat": 3, "xiaohongshu": 2, "journal": 3, "universal": 3},
    "story": {"wechat": 3, "xiaohongshu": 2, "journal": 2, "universal": 3},
    "debunk": {"wechat": 3, "xiaohongshu": 2, "universal": 3},
    "qa_article": {"wechat": 3, "xiaohongshu": 3, "offline": 2, "universal": 3},
    "research_read": {"wechat": 2, "bilibili": 3, "journal": 3, "universal": 2},
    "oral_script": {"douyin": 3, "bilibili": 2},
    "drama_script": {"douyin": 3, "bilibili": 2},
    "storyboard": {"douyin": 2, "bilibili": 3},
    "audio_script": {"wechat": 2, "bilibili": 3},
    "comic_strip": {"wechat": 3, "douyin": 2, "xiaohongshu": 3},
    "card_series": {"wechat": 2, "xiaohongshu": 3, "offline": 2, "universal": 2},
    "poster": {"wechat": 2, "xiaohongshu": 3, "offline": 3, "universal": 2},
    "picture_book": {"wechat": 2, "xiaohongshu": 2, "journal": 2, "offline": 3, "universal": 2},
    "long_image": {"wechat": 3, "xiaohongshu": 3},
    "patient_handbook": {"offline": 3, "universal": 3},
    "quiz_article": {"wechat": 3, "xiaohongshu": 3, "universal": 2},
    "h5_outline": {"wechat": 3},
}

# 各形式字段可见性（False=隐藏，不校验必填）
FIELD_VISIBILITY = {
    "oral_script": {"reading_level": False},
    "drama_script": {"reading_level": False},
    "storyboard": {"reading_level": False, "target_audience": False},
    "audio_script": {"reading_level": False},
    "comic_strip": {"reading_level": False},
    "card_series": {"reading_level": False},
    "poster": {"reading_level": False, "target_audience": False},
    "long_image": {"reading_level": False},
    "h5_outline": {"reading_level": False},
    "picture_book": {"target_audience": False},
}

# 各形式 section_type 枚举
SECTION_TYPES_BY_FORMAT = {
    "article": ["intro", "body", "case", "qa", "summary"],
    "story": ["opening", "development", "climax", "resolution", "lesson"],
    "debunk": ["myth_intro", "myth_1", "myth_2", "myth_3", "action_guide"],
    "qa_article": ["qa_intro", "qa_1", "qa_2", "qa_3", "qa_summary"],
    "research_read": ["background", "finding", "implication", "caution"],
    "oral_script": ["hook", "body_1", "body_2", "body_3", "summary", "cta"],
    "drama_script": ["scene_setup", "scene_1", "scene_2", "scene_3", "ending"],
    "storyboard": ["planner", "frame_1", "frame_2", "frame_3", "frame_4", "frame_5", "frame_6"],
    "audio_script": ["opening", "topic_intro", "deep_dive", "extension", "closing"],
    "comic_strip": ["planner", "panel_1", "panel_2", "panel_3", "panel_4", "panel_5", "panel_6"],
    "card_series": ["card_1", "card_2", "card_3", "card_4", "card_5"],
    "poster": ["headline", "core_message", "data_points", "cta", "visual_desc"],
    "picture_book": ["planner", "page_1", "page_2", "page_3", "page_4", "page_5"],
    "long_image": ["planner", "cover", "section_1", "section_2", "section_3", "footer"],
    "patient_handbook": ["cover_copy", "disease_intro", "symptoms", "treatment", "daily_care", "visit_tips"],
    "quiz_article": ["quiz_intro", "q_1", "q_2", "q_3", "q_4", "q_5", "summary"],
    "h5_outline": ["page_cover", "page_1", "page_2", "page_3", "page_end"],
}

# 字数统计口径：各形式参与统计的字段（v6.0）
WORD_COUNT_FIELDS = {
    "article": ["content_text"],
    "story": ["content_text"],
    "debunk": ["content_text"],
    "qa_article": ["content_text"],
    "research_read": ["content_text"],
    "oral_script": ["dialogue"],
    "drama_script": ["dialogue"],
    "storyboard": ["voiceover"],
    "audio_script": ["dialogue"],
    "comic_strip": ["dialogue", "narration"],
    "card_series": ["content_text"],
    "poster": ["content_text"],
    "picture_book": ["page_text"],
    "long_image": ["content_text"],
    "patient_handbook": ["content_text"],
    "quiz_article": ["content_text", "explanation"],
    "h5_outline": ["content_text"],
}


# 平台 / 受众 / 专科中文映射（用于示例类型头部）
PLATFORM_NAMES = {
    "wechat": "微信公众号",
    "douyin": "抖音",
    "xiaohongshu": "小红书",
    "bilibili": "B站",
    "journal": "期刊",
    "offline": "线下",
    "universal": "通用",
}
AUDIENCE_NAMES = {
    "public": "面向大众",
    "patient": "患者受众",
    "student": "学生",
    "professional": "专业读者",
    "children": "儿童",
}
SPECIALTY_NAMES = {
    "endocrine": "内分泌科",
    "cardiology": "心内科",
    "respiratory": "呼吸科",
    "neurology": "神经科",
    "pediatrics": "儿科",
}

# 形式名称映射
FORMAT_NAMES = {
    "article": "图文文章",
    "story": "科普故事",
    "debunk": "辟谣文",
    "qa_article": "问答科普",
    "research_read": "研究速读",
    "oral_script": "口播脚本",
    "drama_script": "情景剧本",
    "storyboard": "动画分镜",
    "audio_script": "播客脚本",
    "comic_strip": "条漫",
    "card_series": "知识卡片系列",
    "poster": "科普海报",
    "picture_book": "科普绘本",
    "long_image": "竖版长图",
    "patient_handbook": "患者教育手册",
    "quiz_article": "自测科普",
    "h5_outline": "H5 互动大纲",
}


def get_all_formats() -> list[dict]:
    """返回所有形式定义"""
    return [
        {
            "id": fid,
            "name": FORMAT_NAMES.get(fid, fid),
            "platform_matrix": FORMAT_PLATFORM_MATRIX.get(fid, {}),
            "field_visibility": FIELD_VISIBILITY.get(fid, {}),
        }
        for fid in FORMAT_CONFIG
    ]


# 章节类型 → 中文标题
SECTION_TITLES: dict[str, dict[str, str]] = {
    "article": {"intro": "引言", "body": "正文", "case": "案例", "qa": "Q&A", "summary": "小结"},
    "story": {"opening": "开篇", "development": "发展", "climax": "转折", "resolution": "收尾", "lesson": "知识点提炼"},
    "debunk": {"myth_intro": "引入误区", "myth_1": "误区1", "myth_2": "误区2", "myth_3": "误区3", "action_guide": "行动建议"},
    "qa_article": {"qa_intro": "问题引入", "qa_1": "问题1", "qa_2": "问题2", "qa_3": "问题3", "qa_summary": "总结"},
    "research_read": {"background": "研究背景", "finding": "关键发现", "implication": "对你意味着什么", "caution": "注意事项"},
    "oral_script": {"hook": "钩子（开场）", "body_1": "正文1", "body_2": "正文2", "body_3": "正文3", "summary": "总结", "cta": "行动号召"},
    "drama_script": {"scene_setup": "场景设定", "scene_1": "场景1", "scene_2": "场景2", "scene_3": "场景3", "ending": "结尾"},
    "storyboard": {"planner": "分镜规划"} | {f"frame_{i}": f"镜头{i}" for i in range(1, 7)},
    "audio_script": {"opening": "开场", "topic_intro": "话题引入", "deep_dive": "深入讲解", "extension": "延伸", "closing": "收尾"},
    "comic_strip": {"planner": "分格规划"} | {f"panel_{i}": f"分格{i}" for i in range(1, 7)},
    "card_series": {f"card_{i}": f"卡片{i}" for i in range(1, 6)},
    "poster": {"headline": "标题", "core_message": "核心信息", "data_points": "数据点", "cta": "行动号召", "visual_desc": "视觉描述"},
    "picture_book": {"planner": "绘本规划"} | {f"page_{i}": f"第{i}页" for i in range(1, 6)},
    "long_image": {"planner": "整体规划", "cover": "封面", "section_1": "板块1", "section_2": "板块2", "section_3": "板块3", "footer": "页脚"},
    "patient_handbook": {"cover_copy": "封面文案", "disease_intro": "疾病介绍", "symptoms": "症状识别", "treatment": "治疗方案", "daily_care": "日常注意事项", "visit_tips": "就诊提示"},
    "quiz_article": {"quiz_intro": "自测引入", "q_1": "题目1", "q_2": "题目2", "q_3": "题目3", "q_4": "题目4", "q_5": "题目5", "summary": "总结"},
    "h5_outline": {"page_cover": "封面页", "page_1": "第1页", "page_2": "第2页", "page_3": "第3页", "page_end": "结束页"},
}


def get_format_sections(format_id: str) -> list | None:
    """返回某形式的章节结构（section_type + 中文 title）"""
    sections = SECTION_TYPES_BY_FORMAT.get(format_id)
    if sections is None:
        return None
    titles = SECTION_TITLES.get(format_id, {})
    return [
        {"section_type": s, "title": titles.get(s, s), "order": i + 1}
        for i, s in enumerate(sections)
    ]
