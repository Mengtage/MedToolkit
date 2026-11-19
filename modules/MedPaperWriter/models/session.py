"""
数据模型模块
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


class ModeType(str, Enum):
    """模式类型"""
    REVIEW = "review"
    RCT = "rct"


class SectionStatus(str, Enum):
    """章节状态"""
    PENDING = "pending"
    WRITING = "writing"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REVISION = "revision"


class QAContext(BaseModel):
    """问答上下文"""
    role: str
    content: str
    timestamp: str


class Section(BaseModel):
    """章节模型"""
    section_id: str
    title: str
    content_zh: str = ""
    content_en: str = ""
    status: SectionStatus = SectionStatus.PENDING
    level: int = 1
    parent_id: Optional[str] = None


class OutlineNode(BaseModel):
    """提纲节点"""
    id: str
    level: int
    title: str
    content_zh: str = ""
    content_en: str = ""
    status: SectionStatus = SectionStatus.PENDING
    children: List['OutlineNode'] = []


class SessionState(BaseModel):
    """会话状态"""
    session_id: str
    mode: ModeType
    status: str = "in_progress"
    created_at: str
    updated_at: str
    research_topic: str = ""
    research_question: str = ""
    qa_context: List[QAContext] = []
    outline_confirmed: bool = False
    sections: List[Section] = []
    total_tokens: int = 0
    estimated_total: int = 0


class ChatRequest(BaseModel):
    """对话请求"""
    session_id: str
    message: str
    clear_context: bool = False


class ChatResponse(BaseModel):
    """对话响应"""
    success: bool
    message: str = ""
    qa_context: List[QAContext] = []
    token_usage: Dict[str, int] = {}
    total_tokens: int = 0


class OutlineRequest(BaseModel):
    """提纲请求"""
    session_id: str
    study_type: str = "综述"


class OutlineResponse(BaseModel):
    """提纲响应"""
    success: bool
    outline: Dict[str, Any] = {}
    outline_text: str = ""
    token_usage: Dict[str, int] = {}


class ReviewRequest(BaseModel):
    """审核请求"""
    session_id: str
    section_id: str
    content: Optional[str] = None


class ReviewResponse(BaseModel):
    """审核响应"""
    success: bool
    message: str = ""
    section_id: str = ""


class ExportRequest(BaseModel):
    """导出请求"""
    session_id: str
    language: str = "中文"
    ref_style: str = "vancouver"


class ExportResponse(BaseModel):
    """导出响应"""
    success: bool
    message: str = ""
    file_path: str = ""
    file_name: str = ""
