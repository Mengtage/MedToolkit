"""
会话状态管理模块
负责管理MedToolkit的会话状态和上下文
"""

import secrets
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
import json


class SessionMode(str, Enum):
    """会话模式枚举"""
    REVIEW = "review"  # 综述模式
    RCT = "rct"  # RCT模式


class SectionStatus(str, Enum):
    """章节状态枚举"""
    PENDING = "pending"  # 待撰写
    WRITING = "writing"  # 撰写中
    PENDING_REVIEW = "pending_review"  # 待审核
    APPROVED = "approved"  # 已通过
    REVISION = "revision"  # 需要修订


class OutlineNode:
    """提纲节点"""

    def __init__(self, level: int, title: str, parent: Optional['OutlineNode'] = None):
        self.id = secrets.token_urlsafe(8)
        self.level = level  # 1, 2, 3级标题
        self.title = title
        self.parent = parent
        self.children: List['OutlineNode'] = []
        self.content_zh: str = ""
        self.content_en: str = ""
        self.status: SectionStatus = SectionStatus.PENDING

        if parent:
            parent.children.append(self)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "level": self.level,
            "title": self.title,
            "content_zh": self.content_zh,
            "content_en": self.content_en,
            "status": self.status.value,
            "children": [child.to_dict() for child in self.children]
        }

    @classmethod
    def from_dict(cls, data: dict, parent: Optional['OutlineNode'] = None) -> 'OutlineNode':
        """从字典创建"""
        node = cls(data["level"], data["title"], parent)
        node.id = data.get("id", node.id)
        node.content_zh = data.get("content_zh", "")
        node.content_en = data.get("content_en", "")
        node.status = SectionStatus(data.get("status", "pending"))

        for child_data in data.get("children", []):
            cls.from_dict(child_data, node)

        return node


class Session:
    """会话对象"""

    def __init__(self, mode: SessionMode, user_id: Optional[str] = None):
        self.session_id: str = secrets.token_urlsafe(32)
        self.mode: SessionMode = mode
        self.status: str = "in_progress"  # in_progress, paused, completed
        self.created_at: str = datetime.now().isoformat()
        self.updated_at: str = datetime.now().isoformat()
        self.user_id: Optional[str] = user_id

        # 综述模式相关
        self.research_topic: str = ""  # 研究主题
        self.research_question: str = ""  # 确定的研究问题
        self.qa_context: List[Dict[str, str]] = []  # 追问对话上下文
        self.outline_confirmed: bool = False
        self.outline: Optional[OutlineNode] = None

        # RCT模式相关
        self.protocol_text: str = ""  # 研究方案文本
        self.analysis_text: str = ""  # 统计分析报告
        self.framework_confirmed: bool = False
        self.current_chapter: str = ""  # 当前撰写的章节

        # 章节内容
        self.sections: List[Dict[str, Any]] = []

        # Token使用
        self.total_tokens: int = 0
        self.estimated_total: int = 0

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "session_id": self.session_id,
            "mode": self.mode.value,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "research_topic": self.research_topic,
            "research_question": self.research_question,
            "qa_context": self.qa_context,
            "outline_confirmed": self.outline_confirmed,
            "outline": self.outline.to_dict() if self.outline else None,
            "protocol_text": self.protocol_text,
            "analysis_text": self.analysis_text,
            "framework_confirmed": self.framework_confirmed,
            "current_chapter": self.current_chapter,
            "sections": self.sections,
            "total_tokens": self.total_tokens,
            "estimated_total": self.estimated_total
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Session':
        """从字典创建"""
        session = cls(SessionMode(data["mode"]), data.get("user_id"))
        session.session_id = data.get("session_id", session.session_id)
        session.status = data.get("status", "in_progress")
        session.created_at = data.get("created_at", session.created_at)
        session.updated_at = data.get("updated_at", session.updated_at)
        session.research_topic = data.get("research_topic", "")
        session.research_question = data.get("research_question", "")
        session.qa_context = data.get("qa_context", [])
        session.outline_confirmed = data.get("outline_confirmed", False)

        if data.get("outline"):
            session.outline = OutlineNode.from_dict(data["outline"])

        session.protocol_text = data.get("protocol_text", "")
        session.analysis_text = data.get("analysis_text", "")
        session.framework_confirmed = data.get("framework_confirmed", False)
        session.current_chapter = data.get("current_chapter", "")
        session.sections = data.get("sections", [])
        session.total_tokens = data.get("total_tokens", 0)
        session.estimated_total = data.get("estimated_total", 0)

        return session


class ConversationManager:
    """会话状态管理器"""

    def __init__(self):
        self.sessions: Dict[str, Session] = {}
        self.active_session_id: Optional[str] = None

    def create_session(self, mode: SessionMode, user_id: Optional[str] = None) -> str:
        """创建新会话"""
        session = Session(mode, user_id)
        self.sessions[session.session_id] = session
        self.active_session_id = session.session_id
        return session.session_id

    def get_session(self, session_id: str) -> Optional[Session]:
        """获取会话"""
        return self.sessions.get(session_id)

    def get_active_session(self) -> Optional[Session]:
        """获取当前活跃会话"""
        if self.active_session_id:
            return self.sessions.get(self.active_session_id)
        return None

    def set_active_session(self, session_id: str):
        """设置活跃会话"""
        if session_id in self.sessions:
            self.active_session_id = session_id

    def update_session(self, session_id: str, updates: dict):
        """更新会话"""
        session = self.sessions.get(session_id)
        if session:
            for key, value in updates.items():
                if hasattr(session, key):
                    setattr(session, key, value)
            session.updated_at = datetime.now().isoformat()

    def pause_session(self, session_id: str):
        """暂停会话"""
        session = self.sessions.get(session_id)
        if session:
            session.status = "paused"
            session.updated_at = datetime.now().isoformat()

    def resume_session(self, session_id: str):
        """恢复会话"""
        session = self.sessions.get(session_id)
        if session:
            session.status = "in_progress"
            session.updated_at = datetime.now().isoformat()

    def complete_session(self, session_id: str):
        """完成会话"""
        session = self.sessions.get(session_id)
        if session:
            session.status = "completed"
            session.updated_at = datetime.now().isoformat()

    def add_qa_context(self, session_id: str, role: str, content: str):
        """添加追问上下文"""
        session = self.sessions.get(session_id)
        if session:
            session.qa_context.append({
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat()
            })

    def get_qa_context(self, session_id: str) -> List[Dict[str, str]]:
        """获取追问上下文"""
        session = self.sessions.get(session_id)
        if session:
            return session.qa_context
        return []

    def set_research_question(self, session_id: str, question: str):
        """设置研究问题"""
        session = self.sessions.get(session_id)
        if session:
            session.research_question = question

    def set_outline(self, session_id: str, outline: OutlineNode):
        """设置提纲"""
        session = self.sessions.get(session_id)
        if session:
            session.outline = outline

    def confirm_outline(self, session_id: str):
        """确认提纲"""
        session = self.sessions.get(session_id)
        if session:
            session.outline_confirmed = True

    def update_token_usage(self, session_id: str, tokens: int):
        """更新Token使用"""
        session = self.sessions.get(session_id)
        if session:
            session.total_tokens += tokens

    def save_to_json(self, session_id: str) -> str:
        """保存会话为JSON字符串"""
        session = self.sessions.get(session_id)
        if session:
            return json.dumps(session.to_dict(), ensure_ascii=False, indent=2)
        return "{}"

    def load_from_json(self, json_str: str) -> Optional[Session]:
        """从JSON加载会话"""
        try:
            data = json.loads(json_str)
            session = Session.from_dict(data)
            self.sessions[session.session_id] = session
            return session
        except Exception as e:
            print(f"Failed to load session: {e}")
            return None


# 全局会话管理器实例
manager = ConversationManager()
