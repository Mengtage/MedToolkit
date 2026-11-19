"""
生成示例数据用于测试
"""
import pandas as pd
import numpy as np

# 设置随机种子
np.random.seed(42)

# 生成示例数据
n_samples = 200

# 创建数据
data = {
    'ID': range(1, n_samples + 1),
    '姓名': [f'用户_{i}' for i in range(1, n_samples + 1)],
    '年龄': np.random.randint(18, 65, n_samples),
    '性别': np.random.choice(['男', '女'], n_samples),
    '部门': np.random.choice(['销售', '技术', '市场', '人事', '财务'], n_samples),
    '薪资': np.random.normal(8000, 2000, n_samples).astype(int),
    '工作年限': np.random.randint(0, 30, n_samples),
    '绩效评分': np.random.uniform(60, 100, n_samples).round(1),
    '是否在职': np.random.choice([True, False], n_samples, p=[0.9, 0.1]),
    '入职日期': pd.date_range(start='2020-01-01', periods=n_samples, freq='D').tolist()
}

df = pd.DataFrame(data)

# 添加一些缺失值
missing_indices = np.random.choice(df.index, size=10, replace=False)
df.loc[missing_indices[:5], '年龄'] = np.nan
df.loc[missing_indices[5:], '薪资'] = np.nan

# 添加一些异常值
outlier_indices = np.random.choice(df.index, size=5, replace=False)
df.loc[outlier_indices[:3], '薪资'] = df['薪资'].max() * 3
df.loc[outlier_indices[3:], '绩效评分'] = 150

# 保存为CSV
df.to_csv('/workspace/data_analysis_app/sample_employee_data.csv', index=False, encoding='utf-8-sig')
print("示例数据已生成: sample_employee_data.csv")
print(f"数据形状: {df.shape}")
print(f"\n数据预览:")
print(df.head(10))
print(f"\n缺失值统计:")
print(df.isnull().sum())
