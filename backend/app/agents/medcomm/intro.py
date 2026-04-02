"""图文文章引言 Agent 示例"""
from app.agents.base import BaseAgent


class ArticleIntroAgent(BaseAgent):
    module = "medcomm"

    def get_base_prompt(self, state: dict) -> str:
        return f"""
请为医学科普图文文章撰写引言。

主题：{state.get('topic', '')}
目标读者：{state.get('target_audience', 'public')}
平台：{state.get('platform', 'wechat')}

要求：
- 吸引读者注意力，点明主题
- 语言通俗，200字以内
- 不给出具体医学建议
"""
