#!/usr/bin/env python3
"""
测试路由是否正确注册
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app import app

print("=== 检查路由注册 ===")
print(f"\n总路由数: {len(app.routes)}")
print("\n所有路由列表:")
for route in app.routes:
    if hasattr(route, 'path'):
        methods = ','.join(route.methods) if hasattr(route, 'methods') else 'N/A'
        print(f"  {methods:10} {route.path}")

print("\n=== 查找 review 相关路由 ===")
review_routes = [r for r in app.routes if hasattr(r, 'path') and '/api/review' in r.path]
print(f"\n找到 {len(review_routes)} 个 review 路由:")
for route in review_routes:
    methods = ','.join(route.methods) if hasattr(route, 'methods') else 'N/A'
    print(f"  {methods:10} {route.path}")

print("\n✅ 路由检查完成！")
