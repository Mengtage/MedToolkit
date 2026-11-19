#!/usr/bin/env python3
"""
MedStats-Automate 性能测试脚本
测试各模块在不同数据规模下的性能表现
"""

import time
import psutil
import pandas as pd
import numpy as np
import sys
import os
from pathlib import Path

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python'))

def generate_test_data(n_samples, n_numeric=20, n_categorical=10, missing_rate=0.1):
    """生成模拟医学数据集"""
    np.random.seed(42)
    
    data = {}
    
    # 生成连续变量（模拟实验室检查指标）
    numeric_names = ['WBC', 'RBC', 'Hb', 'Plt', 'ALT', 'AST', 'Cr', 'BUN', 
                     'Glu', 'TC', 'TG', 'HDL', 'LDL', 'Age', 'BMI', 
                     'SBP', 'DBP', 'HR', 'RR', 'Temp']
    
    for i in range(min(n_numeric, len(numeric_names))):
        data[numeric_names[i]] = np.random.normal(100, 15, n_samples)
    
    # 生成分类变量
    categorical_names = ['Gender', 'Group', 'Smoking', 'Diabetes', 'Hypertension',
                         'CVD', 'COPD', 'Cancer', 'Surgery', 'ICU']
    
    for i in range(min(n_categorical, len(categorical_names))):
        if i == 1:  # Group变量用于分组
            data[categorical_names[i]] = np.random.choice(['Control', 'Treatment'], n_samples)
        else:
            data[categorical_names[i]] = np.random.choice([0, 1], n_samples)
    
    df = pd.DataFrame(data)
    
    # 添加缺失值
    for col in df.columns:
        mask = np.random.random(n_samples) < missing_rate
        df.loc[mask, col] = np.nan
    
    return df

def measure_memory():
    """获取当前内存使用（MB）"""
    process = psutil.Process()
    return process.memory_info().rss / 1024 / 1024

def test_data_import(n_samples):
    """测试数据导入性能"""
    print(f"\n{'='*60}")
    print(f"测试数据导入 (n={n_samples})")
    print('='*60)
    
    from data_import import import_data
    
    # 生成测试数据
    test_file = f'/tmp/test_data_{n_samples}.csv'
    df = generate_test_data(n_samples)
    df.to_csv(test_file, index=False)
    
    # 测试导入时间
    start_mem = measure_memory()
    start_time = time.time()
    
    imported_data = import_data(test_file)
    
    end_time = time.time()
    end_mem = measure_memory()
    
    elapsed = end_time - start_time
    mem_used = end_mem - start_mem
    
    print(f"✓ 导入完成: {elapsed:.3f}秒, 内存增加: {mem_used:.2f}MB")
    print(f"  数据形状: {imported_data.shape}")
    
    # 清理
    os.remove(test_file)
    
    return {'time': elapsed, 'memory_mb': mem_used}

def test_quality_control(df):
    """测试质量控制性能"""
    print(f"\n{'='*60}")
    print(f"测试质量控制 (数据规模: {df.shape})")
    print('='*60)
    
    from quality_control import quality_control
    
    start_mem = measure_memory()
    start_time = time.time()
    
    results = quality_control(df, verbose=False)
    
    end_time = time.time()
    end_mem = measure_memory()
    
    elapsed = end_time - start_time
    mem_used = end_mem - start_mem
    
    print(f"✓ 质量控制完成: {elapsed:.3f}秒, 内存增加: {mem_used:.2f}MB")
    
    return {'time': elapsed, 'memory_mb': mem_used}

def test_mice_imputation(df):
    """测试MICE插补性能"""
    print(f"\n{'='*60}")
    print(f"测试MICE插补 (数据规模: {df.shape})")
    print('='*60)
    
    from mice_imputation import mice_imputation
    
    # 只对前5列进行插补以加快测试
    test_cols = df.columns[:5].tolist()
    df_test = df[test_cols].copy()
    
    start_mem = measure_memory()
    start_time = time.time()
    
    results = mice_imputation(df_test, m=3, maxit=5, verbose=False)
    
    end_time = time.time()
    end_mem = measure_memory()
    
    elapsed = end_time - start_time
    mem_used = end_mem - start_mem
    
    print(f"✓ MICE插补完成: {elapsed:.3f}秒, 内存增加: {mem_used:.2f}MB")
    
    return {'time': elapsed, 'memory_mb': mem_used}

def test_tableone(df):
    """测试TableOne生成性能"""
    print(f"\n{'='*60}")
    print(f"测试TableOne生成 (数据规模: {df.shape})")
    print('='*60)
    
    from tableone import generate_tableone
    
    start_mem = measure_memory()
    start_time = time.time()
    
    results = generate_tableone(df, strata='Group', verbose=False)
    
    end_time = time.time()
    end_mem = measure_memory()
    
    elapsed = end_time - start_time
    mem_used = end_mem - start_mem
    
    print(f"✓ TableOne生成完成: {elapsed:.3f}秒, 内存增加: {mem_used:.2f}MB")
    
    return {'time': elapsed, 'memory_mb': mem_used}

def test_effect_size(df):
    """测试效应量计算性能"""
    print(f"\n{'='*60}")
    print(f"测试效应量计算 (数据规模: {df.shape})")
    print('='*60)
    
    from effect_size import calculate_effect_size
    
    start_mem = measure_memory()
    start_time = time.time()
    
    results = calculate_effect_size(df, strata='Group', verbose=False)
    
    end_time = time.time()
    end_mem = measure_memory()
    
    elapsed = end_time - start_time
    mem_used = end_mem - start_mem
    
    print(f"✓ 效应量计算完成: {elapsed:.3f}秒, 内存增加: {mem_used:.2f}MB")
    
    return {'time': elapsed, 'memory_mb': mem_used}

def test_roc_analysis(df):
    """测试ROC分析性能"""
    print(f"\n{'='*60}")
    print(f"测试ROC分析 (数据规模: {df.shape})")
    print('='*60)
    
    from roc_analysis import roc_analysis
    
    # 创建模拟的二分类结局
    df['Outcome'] = (np.random.random(len(df)) > 0.5).astype(int)
    
    start_mem = measure_memory()
    start_time = time.time()
    
    results = roc_analysis(df, predictor='Age', outcome='Outcome', verbose=False)
    
    end_time = time.time()
    end_mem = measure_memory()
    
    elapsed = end_time - start_time
    mem_used = end_mem - start_mem
    
    print(f"✓ ROC分析完成: {elapsed:.3f}秒, 内存增加: {mem_used:.2f}MB")
    
    return {'time': elapsed, 'memory_mb': mem_used}

def run_performance_tests():
    """运行完整性能测试"""
    print("\n" + "="*70)
    print("MedStats-Automate 性能测试")
    print("="*70)
    print(f"Python版本: {sys.version.split()[0]}")
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"初始内存: {measure_memory():.2f}MB")
    
    # 测试不同数据规模
    test_sizes = [100, 500, 1000]
    all_results = []
    
    for n in test_sizes:
        print(f"\n\n{'#'*70}")
        print(f"## 测试规模: {n} 样本")
        print(f"{'#'*70}")
        
        # 生成测试数据
        df = generate_test_data(n)
        
        results = {
            'n_samples': n,
            'data_import': test_data_import(n),
            'quality_control': test_quality_control(df),
            'tableone': test_tableone(df),
            'effect_size': test_effect_size(df),
            'mice': test_mice_imputation(df),
            'roc': test_roc_analysis(df)
        }
        
        all_results.append(results)
        
        # 清理内存
        del df
        import gc
        gc.collect()
    
    # 生成性能报告
    generate_performance_report(all_results)

def generate_performance_report(results):
    """生成性能测试报告"""
    print("\n\n" + "="*70)
    print("性能测试报告摘要")
    print("="*70)
    
    print("\n| 指标 | 100样本 | 500样本 | 1000样本 |")
    print("|------|---------|---------|----------|")
    
    modules = ['data_import', 'quality_control', 'tableone', 'effect_size', 'mice', 'roc']
    
    for module in modules:
        times = [r[module]['time'] for r in results]
        print(f"| {module:20s} | {times[0]:7.3f}s | {times[1]:7.3f}s | {times[2]:8.3f}s |")
    
    print("\n内存使用 (MB):")
    print("| 指标 | 100样本 | 500样本 | 1000样本 |")
    print("|------|---------|---------|----------|")
    
    for module in modules:
        mems = [r[module]['memory_mb'] for r in results]
        print(f"| {module:20s} | {mems[0]:7.2f}MB | {mems[1]:7.2f}MB | {mems[2]:8.2f}MB |")
    
    # 性能扩展性分析
    print("\n性能扩展性 (时间增长率):")
    print("| 指标 | 100→500 (5x) | 500→1000 (2x) |")
    print("|------|---------------|----------------|")
    
    for module in modules:
        t1 = results[0][module]['time']
        t2 = results[1][module]['time']
        t3 = results[2][module]['time']
        
        rate_1 = t2 / t1 if t1 > 0 else 0
        rate_2 = t3 / t2 if t2 > 0 else 0
        
        ideal_1 = 5.0
        ideal_2 = 2.0
        
        status_1 = "✓" if rate_1 < ideal_1 * 1.5 else "⚠"
        status_2 = "✓" if rate_2 < ideal_2 * 1.5 else "⚠"
        
        print(f"| {module:20s} | {rate_1:6.2f}x {status_1}    | {rate_2:6.2f}x {status_2}     |")
    
    print("\n" + "="*70)
    print("测试完成！")
    print("="*70)

if __name__ == '__main__':
    run_performance_tests()
