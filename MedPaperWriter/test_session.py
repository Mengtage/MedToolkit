#!/usr/bin/env python3
"""检查会话数据结构"""
import requests

BASE_URL = 'http://localhost:8001/api'

# 创建会话
print("1. 创建会话...")
create_response = requests.post(f'{BASE_URL}/mode/select', data={
    'mode': 'rct',
    'paper_title': 'Test RCT Study'
})
session_id = create_response.json()['session_id']
print(f'   会话ID: {session_id}')

# 写入章节
print("\n2. 写入章节...")
write_response = requests.post(f'{BASE_URL}/chat/rct/write', data={
    'session_id': session_id,
    'chapter': 'Introduction',
    'language': '中文'
})
print(f'   写入响应: {write_response.status_code}')

# 获取会话信息
print("\n3. 获取会话信息...")
info_response = requests.get(f'{BASE_URL}/mode/info/{session_id}')
info = info_response.json()
print(f'   响应状态: {info_response.status_code}')
print(f'   会话sections数量: {len(info.get("sections", []))}')

if info.get('sections'):
    for i, sec in enumerate(info['sections']):
        print(f'\n   章节{i}:')
        print(f'     chapter: {sec.get("chapter")}')
        print(f'     content_zh长度: {len(sec.get("content_zh", ""))}')
        print(f'     content长度: {len(sec.get("content", ""))}')
        print(f'     content_en长度: {len(sec.get("content_en", ""))}')
        print(f'     所有键: {list(sec.keys())}')