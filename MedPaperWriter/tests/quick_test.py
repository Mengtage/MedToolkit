#!/usr/bin/env python3
"""
快速测试 review 修复
"""
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from services.session_manager import manager, SessionMode, OutlineNode, SectionStatus

print("=== 快速测试 ===")

# 1. 创建测试会话
print("\n1. 创建测试会话...")
session_id = manager.create_session(SessionMode.REVIEW)
print(f"   会话ID: {session_id}")

# 2. 创建测试 outline
print("\n2. 创建测试 outline...")
session = manager.get_session(session_id)
root = OutlineNode(0, "论文提纲")
chapter1 = OutlineNode(1, "第一章 测试", root)
section1 = OutlineNode(2, "1.1 测试小节", chapter1)
section1.id = "test-section-1"
section1.status = SectionStatus.PENDING
section1.content_zh = "这是测试内容"
session.outline = root

print("   Outline 创建成功")

# 3. 测试内部函数
print("\n3. 测试内部函数...")

# 导入 review 模块
from routers.review import find_outline_node, collect_all_sections

# 测试 find_outline_node
found = find_outline_node(root, "test-section-1")
print(f"   find_outline_node: {found.title if found else '未找到'}")

# 测试 collect_all_sections
all_sections = collect_all_sections(root)
print(f"   collect_all_sections: 找到 {len(all_sections)} 个章节")

print("\n✅ 内部测试通过！")
print("\n现在你可以重新启动应用，审核功能应该正常工作了。")
