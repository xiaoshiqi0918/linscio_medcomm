"""口播脚本 Agent - 形式族 B 脚本类"""
from app.agents.base import BaseAgent
from app.agents.prompts import FORMAT_SECTION_PROMPTS


class OralScriptAgent(BaseAgent):
    """口播短视频脚本 Agent，输出带时间戳的口语化内容"""

    module = "oral_script"

    def __init__(self, section_type: str):
        self.section_type = section_type

    def get_base_prompt(self, state: dict) -> str:
        prompt = FORMAT_SECTION_PROMPTS.get("oral_script", {}).get(
            self.section_type,
            "请撰写口播脚本段落。",
        )
        return f"""
{prompt}

主题：{state.get('topic', '')}
目标平台：{state.get('platform', 'wechat')}
专科：{state.get('specialty', '')}

要求：每段标注时间戳，累计时长控制在60秒内；语言口语化，无书面语；每段不超过50字。
"""
