"""
诊断前后端对接问题
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright
import requests
import pandas as pd
import numpy as np
import io

def upload_test_data():
    """上传测试数据"""
    base_url = 'http://localhost:5559'
    s = requests.Session()

    np.random.seed(42)
    n = 100

    data = pd.DataFrame({
        'Treatment': np.random.choice([0, 1], size=n),
        'Age': np.random.normal(50, 15, n),
        'Gender': np.random.choice([0, 1], size=n),
        'ASA': np.random.choice([1, 2, 3], size=n),
        'BP_Sys': np.random.normal(120, 20, n),
        'Complication': np.random.choice([0, 1], size=n)
    })

    # 添加一些缺失值
    data.loc[np.random.choice(n, 10), 'Age'] = np.nan
    data.loc[np.random.choice(n, 5), 'BP_Sys'] = np.nan

    csv_buffer = io.StringIO()
    data.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)

    response = s.post(f'{base_url}/api/upload', files={'file': ('test_data.csv', csv_buffer.read(), 'text/csv')})
    print(f"上传数据: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"  - 行数: {result.get('row_count')}")
        print(f"  - 列数: {result.get('column_count')}")
        print(f"  - 变量类型: {result.get('variable_types')}")
        return s
    else:
        print(f"  失败: {response.text}")
        return None

def test_missing_analysis(s):
    """测试缺失值分析"""
    print("\n【测试】缺失值分析")
    response = s.post('http://localhost:5559/api/missing-analysis')
    print(f"  状态码: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"  success: {result.get('success')}")
        print(f"  结果: {list(result.get('results', {}).keys())[:5]}...")
    else:
        print(f"  失败: {response.text[:200]}")

def test_distribution_diagnostics(s):
    """测试分布诊断"""
    print("\n【测试】分布诊断")
    response = s.post('http://localhost:5559/api/distribution-diagnostics')
    print(f"  状态码: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"  success: {result.get('success')}")
        print(f"  结果键: {list(result.keys())}")
    else:
        print(f"  失败: {response.text[:200]}")

def test_mice_impute(s):
    """测试MICE插补"""
    print("\n【测试】MICE插补")
    response = s.post('http://localhost:5559/api/mice-impute', json={})
    print(f"  状态码: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"  success: {result.get('success')}")
        print(f"  结果键: {list(result.keys())}")
    else:
        print(f"  失败: {response.text[:200]}")

def test_tableone(s):
    """测试TableOne"""
    print("\n【测试】TableOne")
    response = s.post('http://localhost:5559/api/tableone', json={'group_var': 'Treatment'})
    print(f"  状态码: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"  success: {result.get('success')}")
        if 'rows' in result:
            print(f"  行数: {len(result.get('rows', []))}")
            if result.get('rows'):
                print(f"  第一行字段: {list(result['rows'][0].keys())}")
                print(f"  示例行: {result['rows'][0]}")
    else:
        print(f"  失败: {response.text[:200]}")

def test_browser_console():
    """测试浏览器控制台"""
    print("\n【浏览器测试】检查前端控制台错误")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        console_messages = []
        page.on('console', lambda msg: console_messages.append(f"[{msg.type}] {msg.text}"))

        page.goto('http://localhost:5559')
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(2000)

        # 点击上传区域
        print("  1. 检查上传界面...")
        page.screenshot(path='/tmp/medstat_upload.png')
        print("     截图已保存到 /tmp/medstat_upload.png")

        # 上传文件
        print("  2. 上传测试数据...")
        page.set_input_files('input[type="file"]', '/Users/mentage/Desktop/MedToolkit/MedStat/test_advanced_features.py')
        page.wait_for_timeout(3000)

        # 检查数据预览
        print("  3. 检查数据预览...")
        content = page.content()
        if '100行' in content or 'row_count' in content.lower():
            print("     数据预览正常")
        else:
            print("     数据预览可能有问题")

        # 截图当前状态
        page.screenshot(path='/tmp/medstat_after_upload.png', full_page=True)
        print("     截图已保存到 /tmp/medstat_after_upload.png")

        # 打印控制台错误
        errors = [m for m in console_messages if m.startswith('[error]')]
        if errors:
            print(f"\n  控制台错误 ({len(errors)}个):")
            for err in errors[:10]:
                print(f"    {err[:150]}")
        else:
            print("\n  无控制台错误")

        browser.close()

def main():
    print("=" * 60)
    print("MedStat 前后端对接诊断")
    print("=" * 60)

    # 1. 上传测试数据
    s = upload_test_data()
    if not s:
        print("无法上传测试数据，请确保服务器在 http://localhost:5559 运行")
        return

    # 2. 测试各个API
    test_missing_analysis(s)
    test_distribution_diagnostics(s)
    test_mice_impute(s)
    test_tableone(s)

    # 3. 浏览器测试
    test_browser_console()

    print("\n" + "=" * 60)
    print("诊断完成")
    print("=" * 60)

if __name__ == '__main__':
    main()