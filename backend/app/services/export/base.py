"""导出器基类 - 按形式路由"""
from abc import ABC, abstractmethod
from typing import Any


class BaseExporter(ABC):
    """导出器基类"""

    def __init__(self, article_id: int, platform: str = "wechat", db: Any = None):
        self.article_id = article_id
        self.platform = platform
        self._db = db

    @abstractmethod
    async def export(self, fmt: str = "html") -> tuple[bytes, str, str]:
        """
        执行导出
        返回 (content_bytes, media_type, filename)
        """
        pass
