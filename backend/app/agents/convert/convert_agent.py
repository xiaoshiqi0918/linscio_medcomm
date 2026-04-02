"""
ContentFormatConvertor - 多形式内容转换 Agent（v2.2）
v2.2 升级：children 受众拦截 + 扩展转换矩阵
"""
from app.agents.base import BaseAgent
from app.agents.prompts.convert_prompts import get_conversion_prompt


class ContentFormatConvertor(BaseAgent):
    """
    内容转换路由器
    v2.2：children 受众转换拦截 + 扩展转换矩阵（quiz_article/picture_book）
    """

    module = "convert"

    def get_base_prompt(self, state: dict) -> str:
        return get_conversion_prompt(
            source_format=state.get("source_format", "article"),
            target_format=state.get("target_format", "oral_script"),
            source_content=state.get("source_content", ""),
            target_audience=state.get("target_audience", "public"),
            platform=state.get("platform", "universal"),
        )
