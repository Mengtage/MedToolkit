"""
测试新增的高级统计功能
"""

import requests
import numpy as np
import pandas as pd

def main():
    base_url = 'http://localhost:5559'
    s = requests.Session()
    
    print("=" * 60)
    print("MedStat 高级统计功能测试")
    print("=" * 60)
    
    # 创建测试数据
    np.random.seed(42)
    n = 100
    
    data = {
        'Treatment': np.random.choice([0, 1], size=n, p=[0.5, 0.5]).astype(float),
        'Outcome': np.random.choice([0, 1], size=n, p=[0.6, 0.4]).astype(float),
        'ASA': np.random.choice([1, 2, 3], size=n, p=[0.3, 0.5, 0.2]).astype(float),
        'AgeGroup': np.random.choice([1, 2, 3], size=n, p=[0.4, 0.4, 0.2]).astype(float),
        'Gender': np.random.choice([0, 1], size=n, p=[0.5, 0.5]).astype(float),
        'Age': np.random.normal(50, 15, n),
        'BMI': np.random.normal(25, 5, n)
    }
    
    # 引入一些缺失值
    for i in range(10):
        data['Outcome'][np.random.randint(0, n)] = np.nan
    
    df = pd.DataFrame(data)
    
    # 上传数据
    print("\n【1】上传数据")
    files = {'file': ('test_data.csv', df.to_csv(index=False), 'text/csv')}
    response = s.post(f'{base_url}/api/upload', files=files)
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        print("✓ 数据上传成功")
    else:
        print(f"✗ 失败: {response.text}")
        return
    
    # 测试分类变量检验
    print("\n【2】测试分类变量检验")
    response = s.post(f'{base_url}/api/categorical-test', json={
        'var_name': 'Gender',
        'group_var': 'Treatment',
        'method': 'auto'
    })
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"✓ 检验方法: {result.get('method')}")
        print(f"  P值: {result.get('p_value')}")
        print(f"  选择理由: {result.get('reason')}")
    else:
        print(f"✗ 失败: {response.text}")
    
    # 测试Mantel-Haenszel分层分析
    print("\n【3】测试Mantel-Haenszel分层分析")
    response = s.post(f'{base_url}/api/stratified-analysis', json={
        'group_var': 'Treatment',
        'outcome_var': 'Outcome',
        'strata_var': 'ASA'
    })
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"✓ 汇总OR: {result.get('pooled_or')}")
        print(f"  MH检验P值: {result.get('mh_p_value')}")
        print(f"  同质性检验P值: {result.get('homogeneity_p')}")
        print(f"  分层数: {result.get('n_strata')}")
    else:
        print(f"✗ 失败: {response.text}")
    
    # 测试敏感性分析
    print("\n【4】测试敏感性分析")
    response = s.post(f'{base_url}/api/sensitivity-analysis', json={
        'outcome_var': 'Outcome',
        'group_var': 'Treatment'
    })
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        scenarios = result.get('scenarios', {})
        tipping = result.get('tipping_point', {})
        
        print(f"✓ 观察数据OR: {scenarios.get('observed', {}).get('or')}")
        print(f"  最差情况OR: {scenarios.get('worst_case', {}).get('or')}")
        print(f"  最佳情况OR: {scenarios.get('best_case', {}).get('or')}")
        print(f"  Tipping Point: {tipping.get('is_robust')}")
    else:
        print(f"✗ 失败: {response.text}")
    
    # 测试交互作用分析
    print("\n【5】测试交互作用分析")
    response = s.post(f'{base_url}/api/interaction-analysis', json={
        'var1': 'Treatment',
        'var2': 'AgeGroup',
        'outcome_var': 'Outcome',
        'model_type': 'logistic'
    })
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"✓ 交互作用P值: {result.get('lr_p_value')}")
        print(f"  是否存在交互: {result.get('has_interaction')}")
        if 'interaction_or' in result:
            print(f"  交互效应OR: {result.get('interaction_or')}")
    else:
        print(f"✗ 失败: {response.text}")
    
    # 测试趋势检验
    print("\n【6】测试Cochran-Armitage趋势检验")
    response = s.post(f'{base_url}/api/trend-test', json={
        'group_var': 'AgeGroup',
        'outcome_var': 'Outcome'
    })
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"✓ 趋势检验Z值: {result.get('statistic')}")
        print(f"  P值: {result.get('p_value')}")
        print(f"  趋势方向: {result.get('trend_direction')}")
    else:
        print(f"✗ 失败: {response.text}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == '__main__':
    main()