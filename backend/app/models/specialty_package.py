"""
学科包状态表（设计 2.2 软件端数据库扩展）
用于 MedComm 桌面端本地 SQLite，跟踪学科包下载与安装状态
状态机：not_installed → downloading → installed
        installed → update_available → downloading → installed
        downloading → error（超时或校验失败）
        error → not_installed（用户重试）
"""
from sqlalchemy import Column, Integer, String, DateTime, Text

from app.models import Base


class SpecialtyPackage(Base):
    __tablename__ = "specialty_packages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    specialty_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    local_version = Column(String(20))  # NULL = 未安装
    remote_version = Column(String(20))
    status = Column(String(20), default='not_installed')
    download_progress = Column(Integer, default=0)  # 0-100
    download_tmp_path = Column(Text)  # 断点续传临时文件路径
    download_offset = Column(Integer, default=0)  # 已下载字节数
    download_started_at = Column(DateTime)  # 下载开始时间（崩溃检测用）
    last_checked_at = Column(DateTime)
    installed_at = Column(DateTime)
    updated_at = Column(DateTime)
