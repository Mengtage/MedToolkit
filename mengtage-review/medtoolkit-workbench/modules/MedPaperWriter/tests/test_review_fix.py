#!/usr/bin/env python3
"""
测试 review 路由修复
"""
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from services.session_manager import manager, SessionMode, OutlineNode, SectionStatus
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_review_routes():
    """测试审核路由"""
    print("=== 测试审核路由 ===")
    
    # 1. 创建会话
    print("\n1. 创建测试会话...")
    response = client.post(
        "/api/mode/select",
        data={"mode": "review", "research_topic": "测试主题"}
    )
    print(f"   响应状态: {response.status_code}")
    assert response.status_code == 200, f"创建会话失败: {response.text}"
    data = response.json()
    assert data["success"], f"创建会话失败: {data}"
    session_id = data["session_id"]
    print(f"   会话ID: {session_id}")
    
    # 2. 生成测试 outline
    print("\n2. 创建测试 outline...")
    session = manager.get_session(session_id)
    root = OutlineNode(0, "论文提纲")
    chapter1 = OutlineNode(1, "第一章 测试", root)
    section1 = OutlineNode(2, "1.1 测试小节", chapter1)
    section1.id = "test-section-1"
    section1.status = SectionStatus.PENDING
    section1.content_zh = "这是测试内容"
    
    # 3. 测试 approve 路由
    print("\n3. 测试 /api/review/approve 路由...")
    response = client.post(
        "/api/review/approve",
        data={"session_id": session_id, "section_id": "test-section-1"}
    )
    print(f"   响应状态: {response.status_code}")
    print(f"   响应内容: {response.text}")
    assert response.status_code == 200, f"审核通过路由失败: {response.text}"
    
    # 4. 测试 revision 路由
    print("\n4. 测试 /api/review/revision 路由...")
    response = client.post(
        "/api/review/revision",
        data={
            "session_id": session_id,
            "section_id": "test-section-1",
            "feedback": "这里需要修改"
        }
    )
    print(f"   响应状态: {response.status_code}")
    print(f"   响应内容: {response.text}")
    assert response.status_code == 200, f"修订请求路由失败: {response.text}"
    
    # 5. 测试进度查询
    print("\n5. 测试 /api/review/progress 路由...")
    response = client.get(f"/api/review/progress?session_id={session_id}")
    print(f"   响应状态: {response.status_code}")
    print(f"   响应内容: {response.text}")
    assert response.status_code == 200, f"进度查询路由失败: {response.text}"
    
    print("\n✅ 所有测试通过！")

if __name__ == "__main__":
    test_review_routes()
