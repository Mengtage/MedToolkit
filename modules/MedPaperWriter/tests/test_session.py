"""
会话管理测试
"""

import pytest
from services.session_manager import manager, SessionMode, OutlineNode, Session


class TestSession:
    """会话创建和管理测试"""

    def test_create_session(self):
        """测试创建会话"""
        session_id = manager.create_session(SessionMode.REVIEW)
        assert session_id is not None
        session = manager.get_session(session_id)
        assert session is not None
        assert session.mode == SessionMode.REVIEW
        assert session.status == "in_progress"

    def test_create_rct_session(self):
        """测试创建RCT会话"""
        session_id = manager.create_session(SessionMode.RCT)
        session = manager.get_session(session_id)
        assert session.mode == SessionMode.RCT

    def test_session_token(self):
        """测试会话令牌"""
        session_id = manager.create_session(SessionMode.REVIEW)
        session = manager.get_session(session_id)
        assert session.user_token is not None
        assert len(session.user_token) > 0

    def test_session_access_validation(self):
        """测试会话访问验证"""
        session_id = manager.create_session(SessionMode.REVIEW)
        session = manager.get_session(session_id)

        # 有效令牌
        assert manager.validate_session_access(session_id, session.user_token) is True

        # 无效令牌
        assert manager.validate_session_access(session_id, "invalid_token") is False

    def test_update_session(self):
        """测试更新会话"""
        session_id = manager.create_session(SessionMode.REVIEW)
        manager.update_session(session_id, {"research_topic": "Test Topic"})
        session = manager.get_session(session_id)
        assert session.research_topic == "Test Topic"

    def test_pause_resume_session(self):
        """测试暂停和恢复会话"""
        session_id = manager.create_session(SessionMode.REVIEW)
        manager.pause_session(session_id)
        assert manager.get_session(session_id).status == "paused"
        manager.resume_session(session_id)
        assert manager.get_session(session_id).status == "in_progress"

    def test_complete_session(self):
        """测试完成会话"""
        session_id = manager.create_session(SessionMode.REVIEW)
        manager.complete_session(session_id)
        assert manager.get_session(session_id).status == "completed"

    def test_qa_context(self):
        """测试QA上下文"""
        session_id = manager.create_session(SessionMode.REVIEW)
        manager.add_qa_context(session_id, "user", "Hello")
        manager.add_qa_context(session_id, "assistant", "Hi")
        context = manager.get_qa_context(session_id)
        assert len(context) == 2
        assert context[0]["role"] == "user"
        assert context[1]["role"] == "assistant"

    def test_research_question(self):
        """测试研究问题"""
        session_id = manager.create_session(SessionMode.REVIEW)
        manager.set_research_question(session_id, "What is the effect?")
        session = manager.get_session(session_id)
        assert session.research_question == "What is the effect?"

    def test_token_usage(self):
        """测试Token使用"""
        session_id = manager.create_session(SessionMode.REVIEW)
        manager.update_token_usage(session_id, 100)
        manager.update_token_usage(session_id, 50)
        session = manager.get_session(session_id)
        assert session.total_tokens == 150


class TestOutlineNode:
    """提纲节点测试"""

    def test_create_node(self):
        """测试创建节点"""
        node = OutlineNode(1, "Introduction")
        assert node.level == 1
        assert node.title == "Introduction"
        assert node.id is not None

    def test_node_hierarchy(self):
        """测试节点层级"""
        root = OutlineNode(0, "Root")
        child1 = OutlineNode(1, "Chapter 1", root)
        child2 = OutlineNode(1, "Chapter 2", root)
        grandchild = OutlineNode(2, "Section 1.1", child1)

        assert len(root.children) == 2
        assert len(child1.children) == 1
        assert grandchild.parent == child1

    def test_node_serialization(self):
        """测试节点序列化"""
        root = OutlineNode(0, "Root")
        OutlineNode(1, "Chapter 1", root)
        OutlineNode(1, "Chapter 2", root)

        data = root.to_dict()
        assert data["title"] == "Root"
        assert len(data["children"]) == 2

        restored = OutlineNode.from_dict(data)
        assert restored.title == "Root"
        assert len(restored.children) == 2

    def test_node_status(self):
        """测试节点状态"""
        from services.session_manager import SectionStatus
        node = OutlineNode(1, "Test")
        assert node.status == SectionStatus.PENDING
        node.status = SectionStatus.APPROVED
        assert node.status == SectionStatus.APPROVED


class TestSessionSerialization:
    """会话序列化测试"""

    def test_session_to_dict(self):
        """测试会话转字典"""
        session_id = manager.create_session(SessionMode.REVIEW)
        session = manager.get_session(session_id)
        data = session.to_dict()
        assert data["session_id"] == session_id
        assert data["mode"] == "review"

    def test_session_from_dict(self):
        """测试从字典恢复会话"""
        original = Session(SessionMode.REVIEW)
        original.research_topic = "Test"
        original.total_tokens = 500

        data = original.to_dict()
        restored = Session.from_dict(data)

        assert restored.session_id == original.session_id
        assert restored.research_topic == "Test"
        assert restored.total_tokens == 500

    def test_safe_dict(self):
        """测试安全字典"""
        session_id = manager.create_session(SessionMode.REVIEW)
        session = manager.get_session(session_id)
        safe = session.to_safe_dict()
        assert "user_token" not in safe
        assert "session_id" in safe
