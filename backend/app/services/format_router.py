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
    "story": ["hook", "development", "turning_point", "science_core", "resolution", "action_list", "closing_quote"],
    "debunk": ["rumor_present", "verdict", "debunk_1", "debunk_2", "debunk_3", "correct_practice", "anti_fraud"],
    "qa_article": ["qa_intro", "qa_1", "qa_2", "qa_3", "qa_4", "qa_5", "qa_summary"],
    "research_read": ["one_liner", "study_card", "why_matters", "methods", "findings", "implication", "limitation"],
    "oral_script": ["script_plan", "golden_hook", "problem_setup", "core_knowledge", "practical_tips", "closing_hook", "extras"],
    "drama_script": ["drama_plan", "cast_table", "act_1", "act_2", "act_3", "act_4", "act_5", "finale", "filming_notes"],
    "storyboard": ["anim_plan", "char_design", "reel_1", "reel_2", "reel_3", "reel_4", "reel_5", "prod_notes"],
    "audio_script": ["opening", "topic_intro", "deep_dive", "extension", "closing"],
    "comic_strip": ["planner", "panel_1", "panel_2", "panel_3", "panel_4", "panel_5", "panel_6", "panel_7", "panel_8", "panel_9", "panel_10", "panel_11", "panel_12"],
    "card_series": ["series_plan", "cover_card", "card_1", "card_2", "card_3", "card_4", "card_5", "card_6", "card_7", "ending_card"],
    "poster": ["poster_brief", "headline", "body_visual", "cta_footer", "design_spec"],
    "picture_book": ["book_plan", "cover", "spread_1", "spread_2", "spread_3", "spread_4", "spread_5", "spread_6", "spread_7", "back_cover"],
    "long_image": ["image_plan", "title_block", "intro_block", "core_1", "core_2", "core_3", "core_4", "tips_block", "warning_block", "summary_cta", "footer_info"],
    "patient_handbook": ["handbook_plan", "cover", "disease_know", "treatment", "daily_care", "followup", "emergency", "faq", "back_cover"],
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
    "story": {"hook": "引子", "development": "发展", "turning_point": "转折·就医", "science_core": "科普核心", "resolution": "结局", "action_list": "行动清单", "closing_quote": "结尾金句"},
    "debunk": {"rumor_present": "谣言还原", "verdict": "真相判定", "debunk_1": "逐条拆解·漏洞1", "debunk_2": "逐条拆解·漏洞2", "debunk_3": "逐条拆解·漏洞3", "correct_practice": "正确做法", "anti_fraud": "防骗指南"},
    "qa_article": {"qa_intro": "问题引入", "qa_1": "问答1·入门", "qa_2": "问答2·入门", "qa_3": "问答3·进阶", "qa_4": "问答4·实操", "qa_5": "问答5·特殊", "qa_summary": "总结"},
    "research_read": {"one_liner": "一句话摘要", "study_card": "研究信息卡", "why_matters": "为什么值得关注", "methods": "研究怎么做的", "findings": "核心发现", "implication": "对普通人意味着什么", "limitation": "注意事项·研究局限"},
    "oral_script": {"script_plan": "脚本规划", "golden_hook": "黄金开头(0-5s)", "problem_setup": "问题铺垫(5-20s)", "core_knowledge": "核心科普(20-50s)", "practical_tips": "实用建议(50-65s)", "closing_hook": "收尾钩子(最后10s)", "extras": "附加信息"},
    "drama_script": {"drama_plan": "剧本概况", "cast_table": "角色表", "act_1": "第一场·日常建立", "act_2": "第二场·冲突触发", "act_3": "第三场·错误应对", "act_4": "第四场·专业介入", "act_5": "第五场·结局升华", "finale": "终场·字幕总结", "filming_notes": "拍摄备注"},
    "storyboard": {"anim_plan": "动画概况", "char_design": "角色/元素设定", "reel_1": "第一幕·引入", "reel_2": "第二幕·问题呈现", "reel_3": "第三幕·机制解释", "reel_4": "第四幕·正确做法", "reel_5": "第五幕·总结收尾", "prod_notes": "制作备注"},
    "audio_script": {"opening": "开场", "topic_intro": "话题引入", "deep_dive": "深入讲解", "extension": "延伸", "closing": "收尾"},
    "comic_strip": {"planner": "条漫规划"} | {f"panel_{i}": f"第{i}格" for i in range(1, 13)},
    "card_series": {"series_plan": "系列规划", "cover_card": "封面卡", **{f"card_{i}": f"内容卡{i}" for i in range(1, 8)}, "ending_card": "结尾卡"},
    "poster": {"poster_brief": "海报概要", "headline": "标题区", "body_visual": "主体·视觉", "cta_footer": "行动号召·底部", "design_spec": "设计规格"},
    "picture_book": {"book_plan": "绘本规划", "cover": "封面P1", "spread_1": "跨页1·开场P2-3", "spread_2": "跨页2·问题P4-5", "spread_3": "跨页3·展开P6-7", "spread_4": "跨页4·深入P8-9", "spread_5": "跨页5·知识核心P10-11", "spread_6": "跨页6·转折P12-13", "spread_7": "跨页7·结局P14-15", "back_cover": "封底·家长指南P16"},
    "long_image": {"image_plan": "长图规划", "title_block": "封面标题区", "intro_block": "引入区", "core_1": "核心内容1", "core_2": "核心内容2", "core_3": "核心内容3", "core_4": "核心内容4", "tips_block": "实用建议区", "warning_block": "特别提醒区", "summary_cta": "总结/CTA区", "footer_info": "尾部信息区"},
    "patient_handbook": {"handbook_plan": "手册信息", "cover": "封面", "disease_know": "认识疾病", "treatment": "治疗方案", "daily_care": "日常管理", "followup": "复诊与随访", "emergency": "紧急情况", "faq": "常见问题", "back_cover": "封底"},
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
