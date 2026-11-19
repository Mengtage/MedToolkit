"""
Services模块

不要把 session_manager / document_generator 在这里 eager import：
两者会反向 import services.logger，eager import 会形成包级循环依赖，
并让"仅导入会话管理器"也被迫加载 LLM 客户端（缺少 API Key 时启动失败）。
需要时通过属性懒加载。
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # 仅用于类型提示
    from services.session_manager import Session, SessionMode, ConversationManager


def __getattr__(name):
    if name in {"manager", "Session", "SessionMode", "OutlineNode", "SectionStatus", "ConversationManager"}:
        from services import session_manager as sm
        return getattr(sm, name)
    if name == "DocumentGenerator":
        from core.document_generator import DocumentGenerator
        return DocumentGenerator
    if name == "ReferenceFormatter":
        from core.reference_formatter import ReferenceFormatter
        return ReferenceFormatter
    raise AttributeError(f"module 'services' has no attribute {name!r}")


__all__ = [
    "manager",
    "Session",
    "SessionMode",
    "OutlineNode",
    "SectionStatus",
    "ConversationManager",
    "DocumentGenerator",
    "ReferenceFormatter",
]
