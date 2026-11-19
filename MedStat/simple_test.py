"""简单诊断脚本"""
import requests
import pandas as pd
import numpy as np
import io

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
data.loc[np.random.choice(n, 10), 'Age'] = np.nan

csv_buffer = io.StringIO()
data.to_csv(csv_buffer, index=False)
csv_buffer.seek(0)

print('【1】上传数据')
r = s.post(f'{base_url}/api/upload', files={'file': ('test.csv', csv_buffer.read(), 'text/csv')})
print(f'状态码: {r.status_code}')
result = r.json()
print(f'success: {result.get("success")}')
print(f'变量类型: {result.get("variable_types")}')

print('\n【2】缺失值分析')
r = s.post(f'{base_url}/api/missing-analysis')
print(f'状态码: {r.status_code}')
if r.status_code != 200:
    print(f'错误: {r.text[:300]}')

print('\n【3】分布诊断')
r = s.post(f'{base_url}/api/distribution-diagnostics')
print(f'状态码: {r.status_code}')
if r.status_code != 200:
    print(f'错误: {r.text[:300]}')

print('\n【4】MICE插补')
r = s.post(f'{base_url}/api/mice-impute', json={})
print(f'状态码: {r.status_code}')
if r.status_code != 200:
    print(f'错误: {r.text[:300]}')

print('\n【5】TableOne')
r = s.post(f'{base_url}/api/tableone', json={'group_var': 'Treatment'})
print(f'状态码: {r.status_code}')
if r.status_code == 200:
    result = r.json()
    print(f'success: {result.get("success")}')
    if result.get('rows'):
        print(f'第一行: {result["rows"][0]}')
else:
    print(f'错误: {r.text[:300]}')