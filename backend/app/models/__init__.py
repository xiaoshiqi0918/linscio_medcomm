from sqlalchemy.orm import declarative_base

Base = declarative_base()

from app.models.user import User
from app.models.user_setting import UserSetting
from app.models.article import Article, ArticleSection, ArticleContent, ArticleLiteratureBinding, ArticleExternalReference
from app.models.image import GeneratedImage
from app.models.image_prompt_template import ImagePromptTemplate
from app.models.template import ContentTemplate
from app.models.knowledge import KnowledgeDoc, KnowledgeChunk
from app.models.example import WritingExample
from app.models.term import MedicalTerm
from app.models.polish import PolishSession, PolishChange
from app.models.paper import PaperChunk
from app.models.literature import (
    LiteraturePaper, LiteratureTag, LiteratureCollection,
    LiteraturePaperTag, LiteratureAttachment, LiteratureAnnotation,
)
from app.models.specialty_package import SpecialtyPackage
from app.models.article_snapshot import ArticleSnapshot
from app.models.personal_corpus import PersonalCorpusEntry
from app.models.medpic_generation import MedPicGeneration
from app.models.contest import ContestPack, ContestRule, UserContestRule
from app.models.painting_intent import StylePreset, PaintingIntentExample, NegativeWordSet
from app.models.article_image_slot import ArticleImageSlot
from app.models.article_visual_anchor import ArticleVisualAnchor

# SaaS 独有模型 — 桌面端打包时这些文件会被排除，条件导入避免 ImportError
try:
    from app.models.billing import (
        UsageLog, RechargeLog, UserBalanceSnapshot, CompensationVoucher,
        PaymentOrder, RefundRecord, ReconciliationLog, LicenseCode, DownloadLog,
        TaskRecord, StreamingSession,
        AdminAuditLog, LlmCallLog, ContentModerationLog,
        ModelPrice, BillingSession,
    )
    from app.models.referral import ReferralLog, WithdrawalLog
except ImportError:
    pass

__all__ = [
    "Base", "User", "UserSetting", "Article", "ArticleSection", "ArticleContent", "ArticleLiteratureBinding", "ArticleExternalReference",
    "GeneratedImage", "ImagePromptTemplate", "ContentTemplate", "KnowledgeDoc", "KnowledgeChunk",
    "WritingExample", "MedicalTerm", "PolishSession", "PolishChange",
    "PaperChunk", "LiteraturePaper", "LiteratureTag", "LiteratureCollection",
    "LiteraturePaperTag", "LiteratureAttachment", "LiteratureAnnotation",
    "SpecialtyPackage",
    "ArticleSnapshot",
    "PersonalCorpusEntry",
    "MedPicGeneration",
    "ContestPack", "ContestRule", "UserContestRule",
    "StylePreset", "PaintingIntentExample", "NegativeWordSet",
    "ArticleImageSlot",
    "ArticleVisualAnchor",
]
