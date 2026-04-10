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
]
