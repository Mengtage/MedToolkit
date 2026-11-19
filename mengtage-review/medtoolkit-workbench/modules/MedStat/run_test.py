#!/usr/bin/env python3
import requests
import pandas as pd
import numpy as np
import tempfile
import os
import zipfile
from io import BytesIO

def main():
    base_url = 'http://localhost:5559'
    s = requests.Session()
    
    # 创建测试数据
    data = {
        'Age': [25, 30, 35, np.nan, 40, 45, 50, 55, np.nan, 60],
        'BMI': [22.5, 24.1, np.nan, 28.3, 25.6, 27.8, np.nan, 23.4, 26.7, 29.1],
        'Gender': ['M', 'F', 'M', 'F', 'M', 'F', 'M', 'F', 'M', 'F'],
        'Group': ['Control', 'Control', 'Control', 'Control', 'Control', 'Treatment', 'Treatment', 'Treatment', 'Treatment', 'Treatment'],
        'Score': [85, 90, 78, 92, 88, 75, 82, 88, 95, 80]
    }
    df = pd.DataFrame(data)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        df.to_csv(f, index=False)
        temp_file = f.name
    
    try:
        print('=' * 60)
        print('MEDSTAT API 测试')
        print('=' * 60)
        
        # 1. 上传数据
        print('\n【1】测试数据上传')
        with open(temp_file, 'rb') as f:
            response = s.post(base_url + '/api/upload', files={'file': ('test.csv', f, 'text/csv')})
        if response.status_code == 200:
            result = response.json()
            print('状态码:', response.status_code)
            print('成功:', result.get('row_count'), '行,', result.get('column_count'), '列')
        
        # 2. 缺失值分析
        print('\n【2】测试缺失值分析')
        response = s.post(base_url + '/api/missing-analysis', json={})
        print('状态码:', response.status_code)
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print('成功')
                print('  缺失率:', result.get('results', {}).get('missing_rate', 0))
                print('  包含热力图:', 'heatmap' in result.get('results', {}))
                print('  包含条形图:', 'bar_chart' in result.get('results', {}))
                print('  包含统计:', 'stats' in result.get('results', {}))
        
        # 3. 异常值检测
        print('\n【3】测试异常值检测')
        response = s.post(base_url + '/api/outlier-detection', json={'method': 'zscore'})
        print('状态码:', response.status_code)
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print('成功')
                print('  包含统计:', 'stats' in result)
                print('  包含图表:', 'charts' in result)
        
        # 4. 分布诊断
        print('\n【4】测试分布诊断')
        response = s.post(base_url + '/api/distribution-diagnostics', json={})
        print('状态码:', response.status_code)
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print('成功')
                print('  包含结果:', 'results' in result)
                print('  包含图表:', 'charts' in result)
        
        # 5. MICE
        print('\n【5】测试MICE多重插补')
        response = s.post(base_url + '/api/mice-impute', json={'m': 3, 'max_iter': 5})
        print('状态码:', response.status_code)
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print('成功')
                print('  插补前缺失:', result.get('before_missing'))
                print('  插补后缺失:', result.get('after_missing'))
                print('  包含均值对比图:', 'mean_comparison_chart' in result)
                print('  包含缺失图表:', 'missing_chart' in result)
                print('  包含分布图表:', 'distribution_charts' in result)
        
        # 6. TableOne
        print('\n【6】测试TableOne')
        response = s.post(base_url + '/api/tableone', json={'group_by': 'Group', 'pval': True, 'smd': True})
        print('状态码:', response.status_code)
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print('成功')
                headers = result.get('headers', [])
                print('  表头:', headers)
                if 'SMD' in headers:
                    print('  ✓ SMD列已添加')
        
        # 7. 导出
        print('\n【7】测试导出')
        response = s.post(base_url + '/api/export/all', json={})
        print('状态码:', response.status_code)
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type')
            print('Content-Type:', content_type)
            if content_type == 'application/zip':
                try:
                    with zipfile.ZipFile(BytesIO(response.content)) as zf:
                        files = zf.namelist()
                        print('zip包含文件:', files)
                        print('✓ zip文件可正常解压')
                except Exception as e:
                    print('zip解压失败:', e)
        
        print('\n' + '=' * 60)
        print('测试完成')
        print('=' * 60)
    
    finally:
        os.unlink(temp_file)

if __name__ == '__main__':
    main()