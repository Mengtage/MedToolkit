#!/usr/bin/env python3
"""测试英文导出功能"""
import requests
import json

BASE_URL = "http://localhost:8001/api"

def test_english_export():
    # 创建会话
    print("1. 创建RCT会话...")
    create_response = requests.post(f"{BASE_URL}/mode/select", data={
        "mode": "rct",
        "paper_title": "Test RCT Study"
    })
    print(f"   响应: {create_response.status_code}")
    session_data = create_response.json()
    print(f"   响应内容: {session_data}")
    session_id = session_data.get("session_id")
    print(f"   会话ID: {session_id}")
    
    if not session_id:
        print("   ❌ 创建会话失败")
        return
    
    # 添加RCT章节内容（模拟已有内容）
    print("\n2. 模拟添加RCT章节内容...")
    
    # 使用RCT章节写入API
    for chapter, content in [
        ("Introduction", "本研究旨在探讨新型药物对高血压患者的治疗效果。高血压是一种常见的心血管疾病，严重影响患者的生活质量。"),
        ("Methods", "本研究采用随机对照试验设计，将200名高血压患者随机分为实验组和对照组，每组100人。")
    ]:
        write_response = requests.post(f"{BASE_URL}/chat/rct/write", data={
            "session_id": session_id,
            "chapter": chapter,
            "language": "中文"
        })
        print(f"   写入{chapter}: {write_response.status_code}")
    
    # 测试英文导出
    print("\n3. 测试英文导出...")
    export_response = requests.get(f"{BASE_URL}/export/download/{session_id}?language=English&ref_style=vancouver")
    
    if export_response.ok:
        print(f"   ✅ 导出成功！状态码: {export_response.status_code}")
        print(f"   内容类型: {export_response.headers.get('content-type')}")
        
        # 保存测试文件
        with open("/Users/mentage/Desktop/MedToolkit/MedPaperWriter/test_output_en.docx", "wb") as f:
            f.write(export_response.content)
        print("   文件已保存: test_output_en.docx")
    else:
        print(f"   ❌ 导出失败！状态码: {export_response.status_code}")
        print(f"   错误信息: {export_response.text}")
    
    # 测试中文导出作为对比
    print("\n4. 测试中文导出（对比）...")
    export_zh_response = requests.get(f"{BASE_URL}/export/download/{session_id}?language=中文&ref_style=vancouver")
    
    if export_zh_response.ok:
        print(f"   ✅ 导出成功！状态码: {export_zh_response.status_code}")
        with open("/Users/mentage/Desktop/MedToolkit/MedPaperWriter/test_output_zh.docx", "wb") as f:
            f.write(export_zh_response.content)
        print("   文件已保存: test_output_zh.docx")
    else:
        print(f"   ❌ 导出失败！状态码: {export_zh_response.status_code}")
        print(f"   错误信息: {export_zh_response.text}")

if __name__ == "__main__":
    test_english_export()