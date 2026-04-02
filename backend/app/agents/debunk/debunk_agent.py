"""辟谣文 Agent - 形式族 A 叙事类"""
from app.agents.base import BaseAgent
from app.agents.prompts import FORMAT_SECTION_PROMPTS


class DebunkMythAgent(BaseAgent):
    """辟谣文单节 Agent，输出 ❌ 误区 / ✅ 真相 / 📖 解释 格式"""

    module = "debunk"

    def __init__(self, section_type: str):
        self.section_type = section_type

    def get_base_prompt(self, state: dict) -> str:
        prompt = FORMAT_SECTION_PROMPTS.get("debunk", {}).get(
            self.section_type,
            "请针对主题中的一个常见医学误区撰写辟谣内容。",
        )
        return f"""
{prompt}

主题：{state.get('topic', '')}
误区编号/类型：{state.get('section_type', '')}
目标读者：{state.get('target_audience', 'public')}
平台：{state.get('platform', 'wechat')}
专科：{state.get('specialty', '')}

要求：语言通俗，不给出具体医学建议或剂量。
"""
