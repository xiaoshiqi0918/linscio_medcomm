"""按 content_format + section_type 生成内容的通用 Agent"""
from app.agents.base import BaseAgent
from app.agents.prompts import FORMAT_SECTION_PROMPTS, DEFAULT_PROMPT
from app.agents.prompts.task_prompts import get_task_prompt


class FormatAgent(BaseAgent):
    """根据形式与章节类型动态生成提示词"""
    module = "medcomm"

    def __init__(self, content_format: str, section_type: str):
        self.content_format = content_format
        self.section_type = section_type

    def get_base_prompt(self, state: dict) -> str:
        cf = self.content_format
        st = self.section_type
        # 优先使用 Layer 3 详细任务提示词
        task = get_task_prompt(cf, st, state)
        if task:
            return task
        # fallback 到简版模板
        prompt = FORMAT_SECTION_PROMPTS.get(cf, {}).get(st) or DEFAULT_PROMPT
        return f"""
{prompt}

主题：{state.get('topic', '')}
目标读者：{state.get('target_audience', 'public')}
平台：{state.get('platform', 'wechat')}
专科：{state.get('specialty', '')}

要求：语言通俗，不给出具体医学建议或剂量。
"""
