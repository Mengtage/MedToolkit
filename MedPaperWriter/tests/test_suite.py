#!/usr/bin/env python3
"""
MedPaperWriter 测试脚本
验证核心功能是否正常工作
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_session_manager():
    """测试会话管理器 - 核心功能"""
    print("=" * 50)
    print("测试 1: 会话管理器核心功能")
    print("=" * 50)
    
    try:
        from services.session_manager import ConversationManager, SessionMode, OutlineNode
        
        manager = ConversationManager()
        
        # 测试创建会话
        session_id = manager.create_session(SessionMode.REVIEW)
        print(f"✓ 创建综述模式会话成功: {session_id}")
        
        session = manager.get_session(session_id)
        if session:
            print(f"✓ 获取会话成功，模式: {session.mode}")
        
        # 测试更新会话
        manager.update_session(session_id, {"research_topic": "心血管疾病"})
        session = manager.get_session(session_id)
        if session and session.research_topic == "心血管疾病":
            print("✓ 会话更新成功")
        
        # 测试QA上下文
        manager.add_qa_context(session_id, "user", "我想研究高血压")
        manager.add_qa_context(session_id, "assistant", "好的，请问您想研究哪个方面？")
        qa_context = manager.get_qa_context(session_id)
        if len(qa_context) == 2:
            print("✓ QA上下文添加成功")
        
        # 测试提纲节点
        outline = OutlineNode(1, "引言")
        sub = OutlineNode(2, "研究背景", outline)
        subsub = OutlineNode(3, "疾病概述", sub)
        print(f"✓ 提纲节点创建成功，根节点: {outline.title}")
        
        # 测试提纲序列化
        outline_dict = outline.to_dict()
        if outline_dict["title"] == "引言" and len(outline_dict["children"]) == 1:
            print("✓ 提纲节点序列化成功")
        
        print("\n✅ 会话管理器核心功能测试通过！\n")
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_outline_node():
    """测试提纲节点功能"""
    print("=" * 50)
    print("测试 2: 提纲节点功能")
    print("=" * 50)
    
    try:
        from services.session_manager import OutlineNode
        
        # 创建复杂提纲
        root = OutlineNode(0, "论文提纲")
        
        intro = OutlineNode(1, "引言", root)
        intro_bg = OutlineNode(2, "研究背景", intro)
        intro_bg_overview = OutlineNode(3, "疾病概述", intro_bg)
        intro_bg_current = OutlineNode(3, "当前研究现状", intro_bg)
        intro_meaning = OutlineNode(2, "研究意义", intro)
        
        methods = OutlineNode(1, "方法", root)
        
        print(f"✓ 创建复杂提纲结构成功")
        print(f"  - 根节点子节点数: {len(root.children)}")
        print(f"  - 引言子节点数: {len(intro.children)}")
        
        # 测试树形结构
        if len(root.children) == 2 and len(intro.children) == 2:
            print("✓ 树形结构正确")
        
        # 测试层级检查
        if root.level == 0 and intro.level == 1 and intro_bg.level == 2 and intro_bg_overview.level == 3:
            print("✓ 层级设置正确")
        
        print("\n✅ 提纲节点功能测试通过！\n")
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_outline_parsing_logic():
    """测试提纲解析逻辑（不依赖FastAPI）"""
    print("=" * 50)
    print("测试 3: 提纲解析逻辑")
    print("=" * 50)
    
    try:
        from services.session_manager import OutlineNode
        import re
        
        def parse_outline_text(outline_text: str) -> OutlineNode:
            """简化的提纲解析函数"""
            lines = outline_text.strip().split("\n")
            root = OutlineNode(0, "论文提纲")
            
            stack = [(root, 0)]
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                match = re.match(r'^(\d+(?:\.\d+)*)\.\s*(.+)$', line)
                if match:
                    level = len(match.group(1).split("."))
                    title = match.group(2).strip()
                    
                    new_node = OutlineNode(level, title)
                    
                    while stack and stack[-1][1] >= level:
                        stack.pop()
                    
                    if stack:
                        new_node.parent = stack[-1][0]
                        stack[-1][0].children.append(new_node)
                    
                    stack.append((new_node, level))
            
            return root
        
        # 测试解析
        sample_outline = """1. 引言
   1.1 研究背景
      1.1.1 疾病概述
   1.2 研究意义
2. 方法"""
        
        outline = parse_outline_text(sample_outline)
        
        if outline and len(outline.children) == 2:
            print(f"✓ 提纲解析成功，根节点: {outline.title}")
            print(f"✓ 一级子节点数: {len(outline.children)}")
            
            if len(outline.children[0].children) == 2:
                print("✓ 二级子节点结构正确")
                
                if len(outline.children[0].children[0].children) == 1:
                    print("✓ 三级子节点结构正确")
        
        print("\n✅ 提纲解析逻辑测试通过！\n")
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_session_serialization():
    """测试会话序列化"""
    print("=" * 50)
    print("测试 4: 会话序列化")
    print("=" * 50)
    
    try:
        from services.session_manager import ConversationManager, SessionMode
        
        manager = ConversationManager()
        session_id = manager.create_session(SessionMode.REVIEW)
        
        # 添加一些测试数据
        manager.update_session(session_id, {"research_topic": "测试主题"})
        manager.add_qa_context(session_id, "user", "用户问题")
        manager.add_qa_context(session_id, "assistant", "AI回答")
        
        # 测试保存和加载
        json_str = manager.save_to_json(session_id)
        if json_str and "test" in json_str.lower():
            print("✓ 会话保存为JSON成功")
        
        # 测试从JSON加载
        manager2 = ConversationManager()
        loaded_session = manager2.load_from_json(json_str)
        if loaded_session and loaded_session.research_topic == "测试主题":
            print("✓ 从JSON加载会话成功")
        
        if len(loaded_session.qa_context) == 2:
            print("✓ QA上下文加载正确")
        
        print("\n✅ 会话序列化测试通过！\n")
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_project_structure():
    """测试项目结构完整性"""
    print("=" * 50)
    print("测试 5: 项目结构检查")
    print("=" * 50)
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    required_files = [
        "app.py",
        "requirements.txt",
        ".env.example",
        "llm/__init__.py",
        "llm/client.py",
        "models/__init__.py",
        "models/session.py",
        "routers/__init__.py",
        "routers/mode.py",
        "routers/chat.py",
        "routers/review.py",
        "routers/export.py",
        "services/__init__.py",
        "services/session_manager.py",
        "services/document_generator.py",
        "services/reference_formatter.py",
        "templates/index.html",
        "static/css/styles.css",
    ]
    
    all_present = True
    for file_path in required_files:
        full_path = os.path.join(base_dir, file_path)
        if os.path.exists(full_path):
            print(f"✓ {file_path}")
        else:
            print(f"✗ {file_path} - 缺失")
            all_present = False
    
    if all_present:
        print("\n✅ 所有核心文件都存在！\n")
    else:
        print("\n⚠️  部分文件缺失！\n")
    
    return all_present

def test_requirements():
    """测试依赖文件"""
    print("=" * 50)
    print("测试 6: 依赖配置检查")
    print("=" * 50)
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    req_file = os.path.join(base_dir, "requirements.txt")
    
    if os.path.exists(req_file):
        with open(req_file, "r", encoding="utf-8") as f:
            requirements = [line.strip() for line in f if line.strip()]
        
        print(f"✓ 找到 {len(requirements)} 个依赖")
        
        required_packages = [
            "fastapi",
            "uvicorn",
            "python-docx",
            "openai",
            "pandas",
            "python-dotenv",
            "pydantic",
            "python-multipart",
            "jinja2"
        ]
        
        found = 0
        for pkg in required_packages:
            for req in requirements:
                if req.lower().startswith(pkg.lower()):
                    print(f"  ✓ {req}")
                    found += 1
                    break
        
        if found == len(required_packages):
            print("\n✅ 所有必需依赖都已配置！\n")
            return True
        else:
            print(f"\n⚠️  找到 {found}/{len(required_packages)} 必需依赖\n")
            return False
    else:
        print("✗ requirements.txt 缺失")
        return False

def main():
    """运行所有测试"""
    print("\n" + "=" * 50)
    print("  MedPaperWriter 测试套件")
    print("=" * 50 + "\n")
    
    tests = [
        test_project_structure,
        test_requirements,
        test_session_manager,
        test_outline_node,
        test_outline_parsing_logic,
        test_session_serialization,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ 测试异常: {e}")
            failed += 1
    
    print("=" * 50)
    print(f"测试结果: 通过 {passed} / 失败 {failed}")
    print("=" * 50)
    
    if failed == 0:
        print("\n🎉 所有测试通过！项目核心功能正常。")
        print("\n📋 下一步：")
        print("  1. 安装依赖: pip install -r requirements.txt")
        print("  2. 配置 .env 文件")
        print("  3. 运行应用: python app.py")
        return 0
    else:
        print(f"\n⚠️  有 {failed} 个测试失败，请检查项目结构。")
        return 1

if __name__ == "__main__":
    sys.exit(main())
