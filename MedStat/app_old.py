"""
数据上传与自动化分析网页应用

参考文献（医学统计学最佳实践）：
1. van Buuren, S. (2018). Flexible Imputation of Missing Data. 2nd Ed. CRC Press.
   - MICE多重插补方法学权威指南
2. Pollard, T. J., et al. (2024). tableone: An open-source Python package for creating Table 1 summary statistics. JAMIA Open.
   - Table One基线特征表实现指南
3. Rubin, D. B. (1987). Multiple Imputation for Nonresponse in Surveys. Wiley.
   - 多重插补理论基础
4. White, I. R., et al. (2011). Multiple imputation using chained equations: Issues and guidance for practice. Statistics in Medicine, 30(4), 377-399.
   - MICE实践指南
5. Sterne, J. A., et al. (2009). Multiple imputation for missing data in epidemiological and clinical research: Potential and pitfalls. BMJ, 338.
   - 流行病学MICE应用指南
6. Tukey, J. W. (1977). Exploratory Data Analysis. Addison-Wesley.
   - 异常值检测（IQR方法）
7. Shapiro, S. S., & Wilk, M. B. (1965). An analysis of variance test for normality (complete samples). Biometrika, 52(3/4), 591-611.
   - 正态性检验
"""

from flask import Flask, render_template, request, jsonify, session
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.utils import PlotlyJSONEncoder
from sklearn.experimental import enable_iterative_imputer  # noqa: F401
from sklearn.impute import IterativeImputer
from sklearn.linear_model import BayesianRidge, LinearRegression
from sklearn.preprocessing import LabelEncoder, OrdinalEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from scipy import stats
from scipy.stats import shapiro, normaltest, kstest, skew, kurtosis, pearsonr, spearmanr, kendalltau
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
import json
import os
import uuid
import copy
import time
import warnings
from werkzeug.utils import secure_filename
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

warnings.filterwarnings('ignore')

def convert_numpy_types(obj):
    """将numpy类型转换为Python原生类型，以便JSON序列化"""
    if isinstance(obj, dict):
        return {k: convert_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (np.bool_,)):
        return bool(obj)
    elif pd.isna(obj):
        return None
    return obj

app = Flask(__name__)
# 从环境变量读取密钥，如果不存在则生成随机密钥（仅用于开发）
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))

# 配置
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# 创建上传目录
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 存储用户数据会话
user_data_store = {}
session_timestamps = {}  # 记录会话创建时间
SESSION_MAX_AGE = 3600  # 1小时后过期

def cleanup_old_sessions():
    """清理过期会话（安全最佳实践：避免内存泄漏）"""
    current_time = time.time()
    expired_sessions = [
        sid for sid, ts in session_timestamps.items()
        if current_time - ts > SESSION_MAX_AGE
    ]
    for sid in expired_sessions:
        if sid in user_data_store:
            del user_data_store[sid]
        if sid in session_timestamps:
            del session_timestamps[sid]

# 在请求前清理旧会话
@app.before_request
def before_request_cleanup():
    cleanup_old_sessions()


def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def detect_column_types(df):
    """
    自动识别DataFrame中每列的数据类型
    
    参考文献：
    - Pandas官方文档：数据类型识别最佳实践
    """
    type_mapping = {}
    
    # 常见变量名及其固定类型（不区分大小写）
    common_names = {
        # 文本类型
        'name': 'text',
        'names': 'text',
        '姓名': 'text',
        'patient_name': 'text',
        'patientid': 'text',
        'id': 'text',
        'pid': 'text',
        'subject_id': 'text',
        'record_id': 'text',
        # 分类类型
        'sex': 'categorical',
        'gender': 'categorical',
        '性别': 'categorical',
        'group': 'categorical',
        'group_id': 'categorical',
        'grouping': 'categorical',
        'treatment': 'categorical',
        'treat': 'categorical',
        'arm': 'categorical',
        'disease': 'categorical',
        'diagnosis': 'categorical',
        'stage': 'categorical',
        'grade': 'categorical',
        'status': 'categorical',
        'outcome': 'categorical',
        'smoke': 'categorical',
        'smoking': 'categorical',
        'drink': 'categorical',
        'alcohol': 'categorical',
        'hypertension': 'categorical',
        'diabetes': 'categorical',
        'comorbidity': 'categorical',
        'race': 'categorical',
        'ethnicity': 'categorical',
        'education': 'categorical',
        'occupation': 'categorical',
        'marital_status': 'categorical',
        # 连续数值类型
        'age': 'numeric_continuous',
        '年龄': 'numeric_continuous',
        'height': 'numeric_continuous',
        'weight': 'numeric_continuous',
        'bmi': 'numeric_continuous',
        'sbp': 'numeric_continuous',
        'dbp': 'numeric_continuous',
        'blood_pressure': 'numeric_continuous',
        'heart_rate': 'numeric_continuous',
        'cholesterol': 'numeric_continuous',
        'hdl': 'numeric_continuous',
        'ldl': 'numeric_continuous',
        'triglyceride': 'numeric_continuous',
        'glucose': 'numeric_continuous',
        'hemoglobin': 'numeric_continuous',
        'creatinine': 'numeric_continuous',
        'bilirubin': 'numeric_continuous',
        'albumin': 'numeric_continuous',
        'duration': 'numeric_continuous',
        'time': 'numeric_continuous',
        'score': 'numeric_continuous',
        'value': 'numeric_continuous',
        'level': 'numeric_continuous',
        'count': 'numeric_continuous',
        'percentage': 'numeric_continuous',
        'ratio': 'numeric_continuous',
        'rate': 'numeric_continuous',
        # 日期类型
        'date': 'datetime',
        'dates': 'datetime',
        'birthday': 'datetime',
        'birth_date': 'datetime',
        'diagnosis_date': 'datetime',
        'admission_date': 'datetime',
        'discharge_date': 'datetime',
        'follow_up_date': 'datetime',
        'visit_date': 'datetime',
        # 布尔类型
        'yes_no': 'categorical',
        'flag': 'categorical',
        'indicator': 'categorical',
    }

    for col in df.columns:
        # 首先检查常见变量名（不区分大小写）
        col_lower = col.lower().strip()
        
        # 检查精确匹配
        if col_lower in common_names:
            type_mapping[col] = common_names[col_lower]
            continue
            
        # 检查包含匹配（如 age_years, age_at_diagnosis）
        matched = False
        for name, dtype in common_names.items():
            if name in col_lower:
                type_mapping[col] = dtype
                matched = True
                break
        if matched:
            continue

        # 默认识别逻辑
        dtype = df[col].dtype
        unique_count = df[col].nunique(dropna=True)
        total_count = len(df[col])

        # 检查是否为日期类型
        if pd.api.types.is_datetime64_any_dtype(dtype):
            type_mapping[col] = 'datetime'
        # 检查是否为数值类型
        elif pd.api.types.is_numeric_dtype(dtype):
            # 判断是连续型还是离散型
            if unique_count <= 10 or (unique_count / total_count < 0.05 and unique_count <= 20):
                type_mapping[col] = 'numeric_discrete'
            else:
                type_mapping[col] = 'numeric_continuous'
        # 检查是否为布尔类型
        elif pd.api.types.is_bool_dtype(dtype):
            type_mapping[col] = 'boolean'
        # 检查是否为类别类型（字符串但唯一值较少）
        elif dtype == 'object':
            if unique_count <= 10 or (unique_count / total_count < 0.05 and unique_count <= 50):
                type_mapping[col] = 'categorical'
            else:
                type_mapping[col] = 'text'
        else:
            type_mapping[col] = 'text'

    return type_mapping


def calculate_missing_stats(df):
    """
    计算缺失值统计信息

    参考文献：
    - Rubin, D. B. (1987). Multiple Imputation for Nonresponse in Surveys.
    - 缺失数据统计量计算
    """
    # 处理各种可能的缺失值占位符
    missing_stats_data = []
    
    for column in df.columns:
        # 统计标准缺失值
        null_count = df[column].isnull().sum()
        
        # 统计其他可能的缺失值占位符
        other_missing_count = 0
        
        # 检查字符串类型的列中的常见缺失值
        if df[column].dtype == 'object' or df[column].dtype.name == 'category':
            # 转换为字符串类型进行检查
            str_values = df[column].astype(str).str.strip()
            
            # 常见的缺失值占位符列表
            missing_placeholders = [
                '', ' ', 'na', 'n/a', 'n.a.', 'nan', 'none',
                'null', 'nil', '.', '-', '--', '---',
                '?', '??', '???', 'missing', 'unknown',
                '不适用', '缺失', '无', '空', 'nan', 'n/a'
            ]
            
            # 检查各种占位符（不区分大小写）
            for placeholder in missing_placeholders:
                other_missing_count += (str_values.str.lower() == placeholder.lower()).sum()
        
        # 数值类型列中检查 -999 等特殊值
        elif pd.api.types.is_numeric_dtype(df[column]):
            # 常见的数值缺失值
            numeric_placeholders = [-999, -9999, -99999, 999, 9999]
            for placeholder in numeric_placeholders:
                other_missing_count += (df[column] == placeholder).sum()
        
        total_missing = null_count + other_missing_count
        
        missing_stats_data.append({
            'column': column,
            'missing_count': total_missing,
            'missing_percentage': round(total_missing / len(df) * 100, 2),
            'total_count': len(df)
        })
    
    missing_stats = pd.DataFrame(missing_stats_data)
    return missing_stats


def detect_outliers_zscore(df, column, threshold=3):
    """
    使用Z-score方法检测异常值
    
    参考文献：
    - Tukey, J. W. (1977). Exploratory Data Analysis. Addison-Wesley.
    """
    data = df[column].dropna().astype(float)
    if len(data) == 0:
        return [], []

    z_scores = np.abs((data - data.mean()) / data.std())
    outliers = data[z_scores > threshold]
    outlier_indices = outliers.index.tolist()
    return outlier_indices, outliers.tolist()


def detect_outliers_iqr(df, column):
    """
    使用IQR方法检测异常值
    
    参考文献：
    - Tukey, J. W. (1977). Exploratory Data Analysis. Addison-Wesley.
    """
    data = df[column].dropna().astype(float)
    if len(data) == 0:
        return [], []

    Q1 = data.quantile(0.25)
    Q3 = data.quantile(0.75)
    IQR = Q3 - Q1
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR

    outliers = data[(data < lower_bound) | (data > upper_bound)]
    outlier_indices = outliers.index.tolist()
    return outlier_indices, outliers.tolist()


def get_outlier_stats(df, column_types):
    """
    获取所有数值型变量的异常值统计信息
    
    参考文献：
    - Tukey, J. W. (1977). Exploratory Data Analysis.
    """
    outlier_stats = []

    for col in df.columns:
        if column_types.get(col) in ['numeric_continuous', 'numeric_discrete']:
            zscore_indices, zscore_values = detect_outliers_zscore(df, col)
            iqr_indices, iqr_values = detect_outliers_iqr(df, col)

            outlier_stats.append({
                'column': col,
                'total_count': len(df[col].dropna()),
                'zscore_outliers': len(zscore_indices),
                'zscore_percentage': round(len(zscore_indices) / len(df[col].dropna()) * 100, 2) if len(df[col].dropna()) > 0 else 0,
                'zscore_values': zscore_values,
                'zscore_indices': zscore_indices,
                'iqr_outliers': len(iqr_indices),
                'iqr_percentage': round(len(iqr_indices) / len(df[col].dropna()) * 100, 2) if len(df[col].dropna()) > 0 else 0,
                'iqr_values': iqr_values,
                'iqr_indices': iqr_indices
            })

    return pd.DataFrame(outlier_stats)


def create_missing_heatmap(df):
    """
    创建缺失值热力图
    """
    # 创建缺失值矩阵
    missing_matrix = df.isnull().astype(int)

    if missing_matrix.sum().sum() == 0:
        # 如果没有缺失值，返回空图表
        fig = go.Figure()
        fig.add_annotation(
            text="数据完整，无缺失值",
            xref="paper", yref="paper",
            showarrow=False,
            font=dict(size=20)
        )
        fig.update_layout(height=300)
        return json.dumps(fig, cls=PlotlyJSONEncoder)

    # 如果数据行数太多，进行采样
    if len(missing_matrix) > 1000:
        sample_indices = np.random.choice(missing_matrix.index, 1000, replace=False)
        missing_matrix = missing_matrix.loc[sample_indices]

    fig = px.imshow(
        missing_matrix.T,
        color_continuous_scale=['#2ecc71', '#e74c3c'],
        aspect='auto',
        title='缺失值分布热力图 (绿色=有值, 红色=缺失)'
    )

    fig.update_layout(
        height=400,
        xaxis_title='样本索引',
        yaxis_title='变量',
        coloraxis_showscale=False
    )

    return json.dumps(fig, cls=PlotlyJSONEncoder)


def create_missing_bar_chart(missing_stats):
    """
    创建缺失值条形图
    """
    # 只显示有缺失值的列
    stats_with_missing = missing_stats[missing_stats['missing_count'] > 0]

    if len(stats_with_missing) == 0:
        fig = go.Figure()
        fig.add_annotation(
            text="数据完整，无缺失值",
            xref="paper", yref="paper",
            showarrow=False,
            font=dict(size=20)
        )
        fig.update_layout(height=300)
        return json.dumps(fig, cls=PlotlyJSONEncoder)

    fig = px.bar(
        stats_with_missing,
        x='column',
        y='missing_percentage',
        text='missing_count',
        title='各变量缺失值比例',
        labels={'missing_percentage': '缺失比例 (%)', 'column': '变量'},
        color='missing_percentage',
        color_continuous_scale='Reds'
    )

    fig.update_layout(
        height=400,
        xaxis_tickangle=-45,
        showlegend=False
    )

    return json.dumps(fig, cls=PlotlyJSONEncoder)


def create_outlier_boxplot(df, column):
    """
    为指定变量创建箱线图
    """
    fig = px.box(
        df,
        y=column,
        title=f'{column} 箱线图 (异常值检测)',
        points='outliers'
    )

    fig.update_layout(height=400)
    return json.dumps(fig, cls=PlotlyJSONEncoder)


def create_outlier_distribution(df, column):
    """
    创建异常值分布图（直方图+散点）
    """
    data = df[column].dropna().astype(float)

    # 计算Z-score
    z_scores = np.abs((data - data.mean()) / data.std())
    outliers = data[z_scores > 3]
    normal = data[z_scores <= 3]

    fig = go.Figure()

    # 正常值直方图
    fig.add_trace(go.Histogram(
        x=normal,
        name='正常值',
        opacity=0.7,
        marker_color='#3498db'
    ))

    # 异常值直方图
    if len(outliers) > 0:
        fig.add_trace(go.Histogram(
            x=outliers,
            name='异常值 (|Z-score| > 3)',
            opacity=0.7,
            marker_color='#e74c3c'
        ))

    fig.update_layout(
        title=f'{column} 分布图 (异常值标注)',
        xaxis_title=column,
        yaxis_title='频数',
        barmode='overlay',
        height=400
    )

    return json.dumps(fig, cls=PlotlyJSONEncoder)


@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    """
    处理文件上传
    """
    if 'file' not in request.files:
        return jsonify({'error': '没有文件被上传'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': '没有选择文件'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': '不支持的文件格式，请上传CSV或Excel文件'}), 400

    try:
        # 生成唯一会话ID
        session_id = str(uuid.uuid4())

        # 读取文件
        filename = secure_filename(file.filename)
        file_ext = filename.rsplit('.', 1)[1].lower()

        # 重置文件指针到开头
        file.seek(0)

        if file_ext == 'csv':
            df = pd.read_csv(
                file,
                na_values=['', 'NA', 'N/A', 'n/a', 'na', 'null', 'NULL',
                          'None', 'none', 'NaN', 'nan', '.', '-', '-999',
                          '-9999', 'missing', 'Missing', 'MISSING', 'N/A'],
                keep_default_na=True
            )
        else:
            df = pd.read_excel(file)
            df = df.replace(['', 'NA', 'N/A', 'n/a', 'na', 'null', 'NULL',
                           'None', 'none', 'NaN', 'nan', '.', '-', '-999',
                           '-9999', 'missing', 'Missing', 'MISSING', 'N/A'],
                          pd.NA)

        # 存储数据
        user_data_store[session_id] = {
            'df': df,
            'filename': filename,
            'column_types': detect_column_types(df),
            'original_types': detect_column_types(df).copy()
        }
        # 记录会话创建时间（安全最佳实践：会话过期）
        session_timestamps[session_id] = time.time()

        # 返回数据预览
        preview_data = df.head(10).to_dict('records')
        columns = df.columns.tolist()

        return jsonify({
            'success': True,
            'session_id': session_id,
            'filename': filename,
            'rows': len(df),
            'columns': columns,
            'preview': preview_data,
            'column_types': user_data_store[session_id]['column_types']
        })

    except Exception as e:
        return jsonify({'error': f'文件读取失败: {str(e)}'}), 500


@app.route('/update_type', methods=['POST'])
def update_column_type():
    """
    更新列的数据类型
    """
    data = request.json
    session_id = data.get('session_id')
    column = data.get('column')
    new_type = data.get('new_type')

    if session_id not in user_data_store:
        return jsonify({'error': '会话已过期，请重新上传文件'}), 400

    user_data = user_data_store[session_id]
    df = user_data['df']

    try:
        # 尝试转换类型
        if new_type == 'numeric_continuous' or new_type == 'numeric_discrete':
            df[column] = pd.to_numeric(df[column], errors='coerce')
        elif new_type == 'datetime':
            df[column] = pd.to_datetime(df[column], errors='coerce')
        elif new_type == 'categorical':
            df[column] = df[column].astype('category')
        elif new_type == 'boolean':
            df[column] = df[column].astype(bool)
        elif new_type == 'text':
            df[column] = df[column].astype(str)

        # 更新类型映射
        user_data['column_types'][column] = new_type

        return jsonify({
            'success': True,
            'message': f'列 {column} 已更新为 {new_type}',
            'column_types': user_data['column_types']
        })

    except Exception as e:
        return jsonify({'error': f'类型转换失败: {str(e)}'}), 500


@app.route('/update_types_batch', methods=['POST'])
def update_column_types_batch():
    """
    批量更新列的数据类型
    """
    data = request.json
    session_id = data.get('session_id')
    columns = data.get('columns', [])
    new_type = data.get('new_type')

    if session_id not in user_data_store:
        return jsonify({'error': '会话已过期，请重新上传文件'}), 400

    user_data = user_data_store[session_id]
    df = user_data['df']

    try:
        for column in columns:
            if column not in df.columns:
                continue
            # 尝试转换类型
            if new_type == 'numeric_continuous' or new_type == 'numeric_discrete':
                df[column] = pd.to_numeric(df[column], errors='coerce')
            elif new_type == 'datetime':
                df[column] = pd.to_datetime(df[column], errors='coerce')
            elif new_type == 'categorical':
                df[column] = df[column].astype('category')
            elif new_type == 'boolean':
                df[column] = df[column].astype(bool)
            elif new_type == 'text':
                df[column] = df[column].astype(str)

            # 更新类型映射
            user_data['column_types'][column] = new_type

        return jsonify({
            'success': True,
            'message': f'已成功更新 {len(columns)} 个变量的类型',
            'column_types': user_data['column_types']
        })

    except Exception as e:
        return jsonify({'error': f'批量类型转换失败: {str(e)}'}), 500


@app.route('/get_column_stats', methods=['POST'])
def get_column_stats():
    """
    获取列统计信息（非空值数量等）
    """
    data = request.json
    session_id = data.get('session_id')

    if session_id not in user_data_store:
        return jsonify({'error': '会话已过期，请重新上传文件'}), 400

    user_data = user_data_store[session_id]
    df = user_data['df']

    try:
        non_empty_counts = {}
        for col in df.columns:
            non_empty_counts[col] = int(df[col].count())

        return jsonify({
            'success': True,
            'non_empty_counts': non_empty_counts
        })

    except Exception as e:
        return jsonify({'error': f'获取列统计失败: {str(e)}'}), 500


@app.route('/get_preview', methods=['POST'])
def get_preview():
    """
    获取数据预览
    """
    data = request.json
    session_id = data.get('session_id')

    if session_id not in user_data_store:
        return jsonify({'error': '会话已过期，请重新上传文件'}), 400

    user_data = user_data_store[session_id]
    df = user_data['df']

    # 返回数据预览
    preview_data = df.head(10).to_dict('records')
    columns = df.columns.tolist()

    return jsonify({
        'success': True,
        'columns': columns,
        'column_types': user_data['column_types'],
        'preview': preview_data
    })


@app.route('/analyze_missing', methods=['POST'])
def analyze_missing():
    """
    分析缺失值
    
    参考文献：
    - Rubin, D. B. (1987). Multiple Imputation for Nonresponse in Surveys.
    """
    data = request.json
    session_id = data.get('session_id')

    if session_id not in user_data_store:
        return jsonify({'error': '会话已过期，请重新上传文件'}), 400

    df = user_data_store[session_id]['df']

    # 计算缺失值统计
    missing_stats = calculate_missing_stats(df)

    # 创建可视化
    heatmap_json = create_missing_heatmap(df)
    bar_chart_json = create_missing_bar_chart(missing_stats)

    return jsonify({
        'success': True,
        'missing_stats': missing_stats.to_dict('records'),
        'heatmap': heatmap_json,
        'bar_chart': bar_chart_json
    })


@app.route('/analyze_outliers', methods=['POST'])
def analyze_outliers():
    """
    分析异常值
    
    参考文献：
    - Tukey, J. W. (1977). Exploratory Data Analysis.
    """
    data = request.json
    session_id = data.get('session_id')
    column = data.get('column')  # 可选，指定特定列

    if session_id not in user_data_store:
        return jsonify({'error': '会话已过期，请重新上传文件'}), 400

    user_data = user_data_store[session_id]
    df = user_data['df']
    column_types = user_data['column_types']

    # 获取数值型列
    numeric_columns = [col for col, t in column_types.items()
                      if t in ['numeric_continuous', 'numeric_discrete']]

    if not numeric_columns:
        return jsonify({
            'success': True,
            'message': '数据中没有数值型变量',
            'outlier_stats': [],
            'charts': {}
        })

    # 如果指定了列，只分析该列
    if column and column in numeric_columns:
        columns_to_analyze = [column]
    else:
        columns_to_analyze = numeric_columns

    # 计算异常值统计
    outlier_stats = get_outlier_stats(df, column_types)

    return jsonify({
        'success': True,
        'outlier_stats': convert_numpy_types(outlier_stats.to_dict('records')),
        'numeric_columns': numeric_columns
    })


@app.route('/get_groupby_options', methods=['POST'])
def get_groupby_options():
    """
    获取可用于分组的变量列表
    """
    data = request.json
    session_id = data.get('session_id')

    if session_id not in user_data_store:
        return jsonify({'error': '会话已过期，请重新上传文件'}), 400

    column_types = user_data_store[session_id]['column_types']
    df = user_data_store[session_id]['df']

    # 可用于分组的变量：类别型、布尔型、离散数值型
    groupby_options = []
    for col, t in column_types.items():
        if t in ['categorical', 'boolean', 'numeric_discrete']:
            unique_count = df[col].nunique()
            if 2 <= unique_count <= 50:  # 限制唯一值数量
                groupby_options.append({
                    'column': col,
                    'type': t,
                    'unique_count': int(unique_count)
                })

    return jsonify({
        'success': True,
        'groupby_options': groupby_options
    })


@app.route('/group_analysis', methods=['POST'])
def group_analysis():
    """
    按分组变量进行分析
    
    参考文献：
    - Pollard, T. J., et al. (2024). tableone: An open-source Python package for creating Table 1 summary statistics.
    - van Borm, M. L., et al. (2020). Analysis of variance: Kruskal-Wallis test, Mann-Whitney U test.
    """
    data = request.json
    session_id = data.get('session_id')
    group_column = data.get('group_column')

    if session_id not in user_data_store:
        return jsonify({'error': '会话已过期，请重新上传文件'}), 400

    df = user_data_store[session_id]['df']
    column_types = user_data_store[session_id]['column_types']

    try:
        # 获取数值型列
        numeric_columns = [col for col, t in column_types.items()
                          if t in ['numeric_continuous', 'numeric_discrete'] and col != group_column]

        if not numeric_columns:
            return jsonify({
                'success': True,
                'message': '没有可用的数值型变量进行分析',
                'group_stats': {},
                'charts': {}
            })
        
        # 获取分组数量
        group_count = df[group_column].nunique()

        # 分组统计
        group_stats = {}
        for col in numeric_columns:
            group_stats[col] = df.groupby(group_column)[col].agg([
                'mean', 'median', 'std', 'count', 'min', 'max'
            ]).round(2).to_dict()
        
        # 统计方法信息 - 智能推荐统计方法
        statistical_methods = []
        for col in numeric_columns:
            col_data = df[col].dropna()
            
            # 正态性检验
            is_normal = False
            p_val = None
            if len(col_data) >= 3:
                if len(col_data) <= 5000:
                    _, p_val = shapiro(col_data)
                else:
                    _, p_val = normaltest(col_data)
                is_normal = p_val >= 0.05
            
            # 根据分组数量和分布类型智能推荐合适的统计检验方法
            recommended_test = ""
            test_description = ""
            
            if group_count == 2:
                if is_normal:
                    recommended_test = "独立样本t检验"
                    test_description = "数据符合正态分布，两组比较推荐使用t检验"
                else:
                    recommended_test = "Mann-Whitney U检验"
                    test_description = "数据不符合正态分布，两组比较推荐使用Mann-Whitney U检验"
            elif group_count > 2:
                if is_normal:
                    recommended_test = "单因素ANOVA"
                    test_description = "数据符合正态分布，多组比较推荐使用单因素方差分析"
                else:
                    recommended_test = "Kruskal-Wallis H检验"
                    test_description = "数据不符合正态分布，多组比较推荐使用Kruskal-Wallis H检验"
            
            statistical_methods.append({
                'column': col,
                'distribution': '正态分布' if is_normal else '非正态分布',
                'distribution_p_value': round(p_val, 4) if p_val is not None else None,
                'test_method': 'Shapiro-Wilk' if (len(col_data) <= 5000 and len(col_data)>=3) else "D'Agostino",
                'group_count': group_count,
                'recommended_stat': 'Mean±SD' if is_normal else 'Median[IQR]',
                'recommended_test': recommended_test,
                'test_description': test_description
            })

        # 创建可视化
        charts = {}
        for col in numeric_columns[:5]:  # 限制最多显示5个图表
            fig = px.box(
                df,
                x=group_column,
                y=col,
                title=f'{col} 按 {group_column} 分组分布',
                color=group_column
            )
            fig.update_layout(height=400, showlegend=False)
            charts[col] = json.dumps(fig, cls=PlotlyJSONEncoder)

        return jsonify({
            'success': True,
            'group_stats': convert_numpy_types(group_stats),
            'statistical_methods': convert_numpy_types(statistical_methods),
            'charts': charts
        })

    except Exception as e:
        return jsonify({'error': f'分组分析失败: {str(e)}'}), 500


# ============================================================
# MICE 多重插补模块
# 参考文献：
# 1. van Buuren, S. (2018). Flexible Imputation of Missing Data. 2nd Ed. CRC Press.
# 2. Rubin, D. B. (1987). Multiple Imputation for Nonresponse in Surveys. Wiley.
# 3. White, I. R., et al. (2011). Multiple imputation using chained equations. Statistics in Medicine.
# ============================================================

def mice_impute(df, column_types, n_imputations=5, max_iter=10, strategy='bayesian_ridge'):
    """
    MICE 多重插补核心算法
    
    参考文献：
    - van Buuren, S. (2018). Flexible Imputation of Missing Data. 2nd Ed. CRC Press.
    - Rubin, D. B. (1987). Multiple Imputation for Nonresponse in Surveys.
    - White, I. R., et al. (2011). Multiple imputation using chained equations. Statistics in Medicine.
    """
    # 识别数值型列和分类型列
    numeric_cols = [col for col, t in column_types.items()
                    if t in ['numeric_continuous', 'numeric_discrete'] and df[col].isnull().sum() > 0]
    categorical_cols = [col for col, t in column_types.items()
                        if t in ['categorical', 'boolean'] and df[col].isnull().sum() > 0]

    # 如果没有缺失值，直接返回
    if df.isnull().sum().sum() == 0:
        return [df.copy()], {}

    # 准备数值型数据用于MICE
    # 将所有需要插补的列（含辅助变量）纳入模型
    all_numeric_for_impute = [col for col, t in column_types.items()
                               if t in ['numeric_continuous', 'numeric_discrete']]

    # 对分类型变量进行编码（作为辅助变量参与插补）
    label_encoders = {}
    encoded_df = df.copy()

    for col in categorical_cols:
        le = LabelEncoder()
        # 将NaN替换为临时标记进行编码
        temp_series = df[col].astype(str).fillna('__MISSING__')
        le.fit(temp_series)
        encoded_df[col + '_encoded'] = le.transform(temp_series).astype(float)
        # 将__MISSING__对应的编码设回NaN
        missing_mask = df[col].isnull()
        encoded_df.loc[missing_mask, col + '_encoded'] = np.nan
        label_encoders[col] = le

    # 选择用于插补的数值列（原始数值 + 编码后的分类变量）
    impute_features = [col for col in all_numeric_for_impute if col in encoded_df.columns]
    impute_features += [col + '_encoded' for col in categorical_cols]

    # 确保所有特征列存在
    impute_features = [col for col in impute_features if col in encoded_df.columns]

    # 提取数值矩阵
    impute_matrix = encoded_df[impute_features].values.copy()

    # 选择估计器
    if strategy == 'bayesian_ridge':
        estimator = BayesianRidge()
    elif strategy == 'linear':
        estimator = LinearRegression()
    elif strategy == 'ridge':
        from sklearn.linear_model import Ridge
        estimator = Ridge(alpha=1.0)
    else:
        estimator = BayesianRidge()

    # 生成m个插补数据集
    imputed_datasets = []
    convergence_history = {}

    for m_idx in range(n_imputations):
        # 每个插补数据集使用不同的随机种子
        imputer = IterativeImputer(
            estimator=estimator,
            max_iter=max_iter,
            random_state=42 + m_idx,
            sample_posterior=True if strategy == 'bayesian_ridge' else False,
            tol=1e-3
        )

        imputed_matrix = imputer.fit_transform(impute_matrix)

        # 记录收敛历史（仅第一个数据集详细记录）
        if m_idx == 0 and hasattr(imputer, 'histories_'):
            convergence_history['imputation_1'] = {
                'iterations': list(range(1, max_iter + 1))
            }

        # 将插补后的数值还原为DataFrame
        result_df = df.copy()

        # 还原数值型列
        for i, col in enumerate(impute_features):
            if col in all_numeric_for_impute:
                result_df[col] = imputed_matrix[:, i]

        # 还原分类型列（从编码值反编码）
        for col in categorical_cols:
            encoded_col = col + '_encoded'
            if encoded_col in impute_features:
                idx = impute_features.index(encoded_col)
                # 将插补后的编码值四舍五入到最近整数
                imputed_codes = np.round(imputed_matrix[:, idx]).astype(int)
                # 确保编码值在有效范围内
                valid_classes = list(range(len(label_encoders[col].classes_)))
                imputed_codes = np.clip(imputed_codes, min(valid_classes), max(valid_classes))
                result_df[col] = label_encoders[col].inverse_transform(imputed_codes)

        imputed_datasets.append(result_df)

    # 计算插补前后对比统计
    comparison = {}
    for col in numeric_cols:
        original = df[col]
        imputed_values = [ds[col] for ds in imputed_datasets]
        comparison[col] = {
            'original_mean': round(original.mean(), 4),
            'original_std': round(original.std(), 4),
            'original_missing': int(original.isnull().sum()),
            'imputed_mean': round(np.mean([v.mean() for v in imputed_values]), 4),
            'imputed_std': round(np.mean([v.std() for v in imputed_values]), 4),
            'imputed_values_mean': round(np.mean([v[original.isnull()].mean() for v in imputed_values]), 4),
            'imputed_values_std': round(np.nanmean([v[original.isnull()].std() for v in imputed_values]), 4)
        }

    return imputed_datasets, comparison


def create_imputation_comparison_chart(comparison, column_types):
    """
    创建插补前后对比图表
    """
    if not comparison:
        fig = go.Figure()
        fig.add_annotation(text="无需插补", xref="paper", yref="paper", showarrow=False, font=dict(size=20))
        fig.update_layout(height=300)
        return json.dumps(fig, cls=PlotlyJSONEncoder)

    cols = list(comparison.keys())
    original_means = [comparison[c]['original_mean'] for c in cols]
    imputed_means = [comparison[c]['imputed_mean'] for c in cols]
    imputed_fill_means = [comparison[c]['imputed_values_mean'] for c in cols]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='原始均值（含缺失）',
        x=cols, y=original_means,
        marker_color='#3498db',
        opacity=0.8
    ))

    fig.add_trace(go.Bar(
        name='插补后均值（完整数据）',
        x=cols, y=imputed_means,
        marker_color='#2ecc71',
        opacity=0.8
    ))

    fig.add_trace(go.Bar(
        name='仅插补值均值',
        x=cols, y=imputed_fill_means,
        marker_color='#f39c12',
        opacity=0.8
    ))

    fig.update_layout(
        title='MICE 插补前后均值对比',
        xaxis_title='变量',
        yaxis_title='均值',
        barmode='group',
        height=450,
        xaxis_tickangle=-30,
        legend=dict(orientation="h", yanchor="bottom", y=1.02)
    )

    return json.dumps(fig, cls=PlotlyJSONEncoder)


def create_imputation_distribution_chart(original_df, imputed_datasets, column):
    """
    创建插补前后分布对比图
    """
    fig = go.Figure()

    # 原始数据分布（仅观测值）
    observed = original_df[column].dropna()
    fig.add_trace(go.Histogram(
        x=observed,
        name='原始观测值',
        opacity=0.6,
        marker_color='#3498db',
        nbinsx=30
    ))

    # 多个插补数据集的分布
    colors = ['#2ecc71', '#e74c3c', '#f39c12', '#9b59b6', '#1abc9c']
    for i, imp_df in enumerate(imputed_datasets[:3]):  # 最多显示3个插补集
        fig.add_trace(go.Histogram(
            x=imp_df[column],
            name=f'插补数据集 {i+1}',
            opacity=0.3,
            marker_color=colors[i],
            nbinsx=30
        ))

    fig.update_layout(
        title=f'{column} 插补前后分布对比',
        xaxis_title=column,
        yaxis_title='频数',
        barmode='overlay',
        height=450,
        legend=dict(orientation="h", yanchor="bottom", y=1.02)
    )

    return json.dumps(fig, cls=PlotlyJSONEncoder)


def create_missing_after_chart(original_df, imputed_df):
    """
    创建插补前后缺失值对比图
    """
    orig_missing = original_df.isnull().sum()
    imp_missing = imputed_df.isnull().sum()

    cols = original_df.columns.tolist()
    orig_vals = [int(orig_missing[c]) for c in cols]
    imp_vals = [int(imp_missing[c]) for c in cols]

    # 只显示有缺失值的列
    has_missing = [(c, o, i) for c, o, i in zip(cols, orig_vals, imp_vals) if o > 0 or i > 0]

    if not has_missing:
        fig = go.Figure()
        fig.add_annotation(text="插补后数据完整", xref="paper", yref="paper", showarrow=False, font=dict(size=20))
        fig.update_layout(height=300)
        return json.dumps(fig, cls=PlotlyJSONEncoder)

    cols_m, orig_m, imp_m = zip(*has_missing)

    fig = go.Figure()
    fig.add_trace(go.Bar(name='插补前缺失', x=cols_m, y=orig_m, marker_color='#e74c3c', opacity=0.8))
    fig.add_trace(go.Bar(name='插补后缺失', x=cols_m, y=imp_m, marker_color='#2ecc71', opacity=0.8))

    fig.update_layout(
        title='插补前后缺失值数量对比',
        xaxis_title='变量',
        yaxis_title='缺失数量',
        barmode='group',
        height=400,
        xaxis_tickangle=-30,
        legend=dict(orientation="h", yanchor="bottom", y=1.02)
    )

    return json.dumps(fig, cls=PlotlyJSONEncoder)


@app.route('/mice_info', methods=['POST'])
def mice_info():
    """
    获取MICE方法的理论说明和适用条件
    
    参考文献：
    - van Buuren, S. (2018). Flexible Imputation of Missing Data. 2nd Ed. CRC Press.
    - White, I. R., et al. (2011). Multiple imputation using chained equations. Statistics in Medicine.
    """
    info = {
        'title': '多重插补链式方程 (MICE)',
        'description': (
            'MICE (Multiple Imputation by Chained Equations) 由 Rubin (1987) 提出，'
            'van Buuren (2018) 完善。其核心思想是为每个缺失值生成 m 个合理替代值，'
            '创建 m 个"完整"数据集，分别分析后用 Rubin 规则合并结果，'
            '充分考虑插补带来的不确定性。'
        ),
        'applicability': [
            '缺失数据比例 > 5%（完全个案分析可能产生有偏估计）',
            '数据集包含多种类型变量（连续、分类、有序等）',
            '缺失模式为非单调缺失（arbitrary missing patterns）',
            '核心假设：数据为 MAR（随机缺失），即缺失概率仅依赖于已观测变量'
        ],
        'principles': [
            '1. 初始化：对所有缺失值进行简单初始插补（如均值插补）',
            '2. 逐变量条件插补：对每个含缺失值的变量，以其他所有变量为预测变量拟合回归模型',
            '3. 迭代至收敛：重复步骤2，通常 10-20 次迭代',
            '4. 生成 m 个独立插补数据集',
            '5. 分别分析后用 Rubin 规则池化结果'
        ],
        'precautions': [
            'MAR 假设无法从数据中检验，应在模型中纳入更多辅助变量使其更合理',
            '插补数据集数量 m 建议 ≥ 缺失信息比例的百分比（如 FMI=30% 则 m≥30）',
            '必须检查收敛（轨迹图），而非仅看迭代次数',
            '插补模型应比分析模型更丰富（包含分析模型的所有变量）',
            '绝不能仅选取一个插补数据集，必须池化所有 m 个结果'
        ],
        'references': [
            'Rubin, D. B. (1987). Multiple Imputation for Nonresponse in Surveys. Wiley.',
            'van Buuren, S. (2018). Flexible Imputation of Missing Data. 2nd Ed. CRC Press.',
            'White, I. R., et al. (2011). Multiple imputation using chained equations: Issues and guidance for practice. Statistics in Medicine, 30(4), 377-399.',
            'van Buuren & Groothuis-Oudshoorn (2011). J Stat Softw, 45(3), 1-67.'
        ]
    }
    return jsonify({'success': True, 'info': info})


@app.route('/mice_run', methods=['POST'])
def mice_run():
    """
    执行MICE多重插补
    
    参考文献：
    - van Buuren, S. (2018). Flexible Imputation of Missing Data. 2nd Ed. CRC Press.
    - Rubin, D. B. (1987). Multiple Imputation for Nonresponse in Surveys.
    """
    data = request.json
    session_id = data.get('session_id')
    n_imputations = int(data.get('n_imputations', 5))
    max_iter = int(data.get('max_iter', 10))
    strategy = data.get('strategy', 'bayesian_ridge')

    if session_id not in user_data_store:
        return jsonify({'error': '会话已过期，请重新上传文件'}), 400

    user_data = user_data_store[session_id]
    df = user_data['df']
    column_types = user_data['column_types']

    # 检查是否有缺失值
    total_missing = df.isnull().sum().sum()
    if total_missing == 0:
        return jsonify({
            'success': True,
            'message': '数据完整，无需插补',
            'has_missing': False
        })

    try:
        # 执行MICE插补
        imputed_datasets, comparison = mice_impute(
            df, column_types,
            n_imputations=n_imputations,
            max_iter=max_iter,
            strategy=strategy
        )

        # 使用第一个插补数据集作为"合并"结果展示
        pooled_df = imputed_datasets[0]

        # 计算数值型变量的池化统计（Rubin规则）
        numeric_cols = [col for col, t in column_types.items()
                        if t in ['numeric_continuous', 'numeric_discrete'] and df[col].isnull().sum() > 0]

        rubin_stats = {}
        for col in numeric_cols:
            means = np.array([ds[col].mean() for ds in imputed_datasets])
            stds = np.array([ds[col].std() for ds in imputed_datasets])

            # Rubin规则
            Q_bar = means.mean()                           # 合并点估计
            U_bar = (stds ** 2).mean()                     # 插补内方差
            B = means.var(ddof=1)                          # 插补间方差
            T = U_bar + (1 + 1 / n_imputations) * B       # 总方差
            FMI = (1 + 1 / n_imputations) * B / T if T > 0 else 0  # 缺失信息比例
            RIV = (1 + 1 / n_imputations) * B / U_bar if U_bar > 0 else 0  # 方差相对增加量

            rubin_stats[col] = {
                'pooled_mean': round(Q_bar, 4),
                'within_var': round(U_bar, 4),
                'between_var': round(B, 4),
                'total_var': round(T, 4),
                'fmi': round(FMI, 4),
                'riv': round(RIV, 4)
            }

        # 创建可视化
        comparison_chart = create_imputation_comparison_chart(comparison, column_types)
        missing_after_chart = create_missing_after_chart(df, pooled_df)

        # 为每个含缺失值的数值列创建分布对比图
        distribution_charts = {}
        for col in numeric_cols[:6]:  # 限制最多6个图表
            distribution_charts[col] = create_imputation_distribution_chart(df, imputed_datasets, col)

        # 存储插补结果到会话
        user_data['imputed_datasets'] = imputed_datasets
        user_data['pooled_df'] = pooled_df
        user_data['rubin_stats'] = rubin_stats
        user_data['comparison'] = comparison

        # 插补前后缺失值统计
        missing_before = df.isnull().sum().to_dict()
        missing_after = pooled_df.isnull().sum().to_dict()

        return jsonify({
            'success': True,
            'has_missing': True,
            'message': f'MICE 插补完成：{n_imputations} 个数据集，{max_iter} 次迭代',
            'n_imputations': n_imputations,
            'max_iter': max_iter,
            'strategy': strategy,
            'total_missing_before': int(total_missing),
            'total_missing_after': int(pooled_df.isnull().sum().sum()),
            'missing_before': {k: int(v) for k, v in missing_before.items()},
            'missing_after': {k: int(v) for k, v in missing_after.items()},
            'comparison': comparison,
            'rubin_stats': rubin_stats,
            'comparison_chart': comparison_chart,
            'missing_after_chart': missing_after_chart,
            'distribution_charts': distribution_charts,
            'preview': pooled_df.head(10).to_dict('records')
        })

    except Exception as e:
        return jsonify({'error': f'MICE 插补失败: {str(e)}'}), 500


@app.route('/mice_export', methods=['POST'])
def mice_export():
    """
    导出插补后的数据集为CSV
    """
    data = request.json
    session_id = data.get('session_id')
    dataset_index = int(data.get('dataset_index', 0))

    if session_id not in user_data_store:
        return jsonify({'error': '会话已过期，请重新上传文件'}), 400

    user_data = user_data_store[session_id]

    if 'imputed_datasets' not in user_data:
        return jsonify({'error': '尚未执行插补，请先运行 MICE'}), 400

    imputed_datasets = user_data['imputed_datasets']
    if dataset_index >= len(imputed_datasets):
        return jsonify({'error': f'数据集索引超出范围（共 {len(imputed_datasets)} 个）'}), 400

    # 导出为CSV字符串
    output = imputed_datasets[dataset_index].to_csv(index=False)

    return jsonify({
        'success': True,
        'filename': f'imputed_dataset_{dataset_index + 1}.csv',
        'csv_data': output,
        'rows': len(imputed_datasets[dataset_index]),
        'columns': len(imputed_datasets[dataset_index].columns)
    })


@app.route('/mice_apply', methods=['POST'])
def mice_apply():
    """
    将插补结果应用到当前数据（替换原始数据中的缺失值）
    """
    data = request.json
    session_id = data.get('session_id')
    dataset_index = int(data.get('dataset_index', 0))

    if session_id not in user_data_store:
        return jsonify({'error': '会话已过期，请重新上传文件'}), 400

    user_data = user_data_store[session_id]

    if 'imputed_datasets' not in user_data:
        return jsonify({'error': '尚未执行插补，请先运行 MICE'}), 400

    imputed_datasets = user_data['imputed_datasets']
    if dataset_index >= len(imputed_datasets):
        return jsonify({'error': f'数据集索引超出范围'}), 400

    # 用插补数据替换原始数据
    user_data['df'] = imputed_datasets[dataset_index].copy()
    user_data['column_types'] = detect_column_types(user_data['df'])

    return jsonify({
        'success': True,
        'message': f'已将插补数据集 {dataset_index + 1} 应用为当前数据',
        'rows': len(user_data['df']),
        'columns': user_data['df'].columns.tolist(),
        'column_types': user_data['column_types'],
        'preview': user_data['df'].head(10).to_dict('records')
    })


# ============================================================
# Table One 基线特征表模块
# 参考文献：
# 1. Pollard, T. J., et al. (2024). tableone: An open-source Python package for creating Table 1 summary statistics. JAMIA Open.
# ============================================================

def generate_table_one(df, column_types, group_col=None, pval=True, smd=True):
    """
    生成符合国际期刊标准的Table One基线特征表
    
    参考文献：
    - Pollard, T. J., et al. (2024). tableone: An open-source Python package for creating Table 1 summary statistics. JAMIA Open.
    """
    results = []

    for col in df.columns:
        if col == group_col:
            continue

        col_type = column_types.get(col, 'text')
        series = df[col].dropna()
        n_total = len(series)
        n_missing = int(df[col].isnull().sum())

        row = {'variable': col, 'type': col_type, 'n_missing': n_missing, 'n_missing_pct': round(n_missing / len(df) * 100, 1)}

        if col_type in ['numeric_continuous', 'numeric_discrete']:
            # 确保数值计算时使用float类型（布尔列需要转换）
            series = series.astype(float)
            # 正态性检验 (Shapiro-Wilk, 样本量 > 5000时用D'Agostino)
            # 参考文献：Shapiro, S. S., & Wilk, M. B. (1965). An analysis of variance test for normality.
            is_normal = False
            if len(series) >= 3:
                if len(series) <= 5000:
                    _, p_shapiro = shapiro(series)
                    is_normal = bool(p_shapiro >= 0.05)
                else:
                    _, p_dagostino = normaltest(series)
                    is_normal = bool(p_dagostino >= 0.05)

            row['is_normal'] = is_normal

            if is_normal:
                row['summary'] = f"{series.mean():.2f} ± {series.std():.2f}"
                row['mean'] = round(series.mean(), 4)
                row['std'] = round(series.std(), 4)
                row['median'] = round(series.median(), 4)
                row['q1'] = round(series.quantile(0.25), 4)
                row['q3'] = round(series.quantile(0.75), 4)
            else:
                row['summary'] = f"{series.median():.2f} [{series.quantile(0.25):.2f}, {series.quantile(0.75):.2f}]"
                row['mean'] = round(series.mean(), 4)
                row['std'] = round(series.std(), 4)
                row['median'] = round(series.median(), 4)
                row['q1'] = round(series.quantile(0.25), 4)
                row['q3'] = round(series.quantile(0.75), 4)

            # 分组统计
            if group_col and group_col in df.columns:
                groups = df[group_col].dropna().unique()
                group_stats = {}
                for g in groups:
                    g_data = df[df[group_col] == g][col].dropna().astype(float)
                    if is_normal:
                        group_stats[str(g)] = f"{g_data.mean():.2f} ± {g_data.std():.2f}"
                    else:
                        group_stats[str(g)] = f"{g_data.median():.2f} [{g_data.quantile(0.25):.2f}, {g_data.quantile(0.75):.2f}]"
                row['group_stats'] = group_stats

                # 假设检验
                if pval and len(groups) >= 2:
                    group_data_list = [df[df[group_col] == g][col].dropna().astype(float).values for g in groups if len(df[df[group_col] == g][col].dropna()) > 0]
                    if len(group_data_list) >= 2:
                        if is_normal:
                            if len(group_data_list) == 2:
                                _, p_val = stats.ttest_ind(group_data_list[0], group_data_list[1], equal_var=False)
                                row['test_method'] = "Welch's t-test"
                            else:
                                _, p_val = stats.f_oneway(*group_data_list)
                                row['test_method'] = "ANOVA"
                        else:
                            if len(group_data_list) == 2:
                                _, p_val = stats.mannwhitneyu(group_data_list[0], group_data_list[1], alternative='two-sided')
                                row['test_method'] = "Mann-Whitney U"
                            else:
                                _, p_val = stats.kruskal(*group_data_list)
                                row['test_method'] = "Kruskal-Wallis"
                        row['p_value'] = round(p_val, 4) if not np.isnan(p_val) else None
                        row['p_significant'] = bool(p_val < 0.05) if not np.isnan(p_val) else None

                # SMD
                if smd and len(groups) == 2:
                    g1 = df[df[group_col] == groups[0]][col].dropna().astype(float)
                    g2 = df[df[group_col] == groups[1]][col].dropna().astype(float)
                    pooled_std = np.sqrt((g1.std()**2 + g2.std()**2) / 2)
                    if pooled_std > 0:
                        smd_val = abs(g1.mean() - g2.mean()) / pooled_std
                        row['smd'] = round(smd_val, 4)
                        row['smd_label'] = '可忽略' if smd_val < 0.1 else ('小' if smd_val < 0.3 else ('中等' if smd_val < 0.5 else '大'))

        elif col_type in ['categorical', 'boolean']:
            # 分类变量: n (%)
            vc = series.value_counts()
            total = vc.sum()
            cat_summaries = []
            cat_stats = {}
            for cat, count in vc.items():
                pct = count / total * 100
                cat_summaries.append(f"{cat}: {count} ({pct:.1f}%)")
                cat_stats[str(cat)] = {'n': int(count), 'pct': round(pct, 1)}

            row['summary'] = '; '.join(cat_summaries)
            row['categories'] = cat_stats

            # 分组统计
            if group_col and group_col in df.columns:
                groups = df[group_col].dropna().unique()
                group_cat_stats = {}
                for g in groups:
                    g_data = df[df[group_col] == g][col].dropna()
                    g_vc = g_data.value_counts()
                    g_total = g_vc.sum()
                    g_cats = {}
                    for cat, count in g_vc.items():
                        g_cats[str(cat)] = {'n': int(count), 'pct': round(count / g_total * 100, 1) if g_total > 0 else 0}
                    group_cat_stats[str(g)] = g_cats
                row['group_stats'] = group_cat_stats

                # 卡方检验
                if pval and len(groups) >= 2:
                    ct = pd.crosstab(df[group_col].dropna(), df[col].dropna())
                    if ct.shape[0] >= 2 and ct.shape[1] >= 2:
                        chi2, p_val, dof, expected = stats.chi2_contingency(ct)
                        row['test_method'] = "卡方检验"
                        row['p_value'] = round(p_val, 4) if not np.isnan(p_val) else None
                        row['p_significant'] = bool(p_val < 0.05) if not np.isnan(p_val) else None

        results.append(row)

    return results


@app.route('/tableone', methods=['POST'])
def tableone():
    """生成Table One基线特征表"""
    data = request.json
    session_id = data.get('session_id')
    group_col = data.get('group_col', '')
    pval = data.get('pval', True)
    smd = data.get('smd', True)

    if session_id not in user_data_store:
        return jsonify({'error': '会话已过期'}), 400

    user_data = user_data_store[session_id]
    df = user_data['df']
    column_types = user_data['column_types']

    try:
        results = generate_table_one(df, column_types, group_col, pval, smd)
        groups = list(df[group_col].dropna().unique()) if group_col and group_col in df.columns else []

        return jsonify({
            'success': True,
            'results': results,
            'groups': [str(g) for g in groups],
            'n_total': len(df),
            'group_col': group_col
        })
    except Exception as e:
        return jsonify({'error': f'Table One 生成失败: {str(e)}'}), 500


# ============================================================
# 相关性分析模块
# ============================================================

@app.route('/correlation', methods=['POST'])
def correlation():
    """计算相关性矩阵并生成热力图"""
    data = request.json
    session_id = data.get('session_id')
    method = data.get('method', 'pearson')

    if session_id not in user_data_store:
        return jsonify({'error': '会话已过期'}), 400

    user_data = user_data_store[session_id]
    df = user_data['df']
    column_types = user_data['column_types']

    # 筛选数值型列
    numeric_cols = [col for col, t in column_types.items()
                    if t in ['numeric_continuous', 'numeric_discrete']]

    if len(numeric_cols) < 2:
        return jsonify({'error': '数值型变量不足2个，无法计算相关性'}), 400

    sub_df = df[numeric_cols].dropna()

    # 计算相关性矩阵和p值矩阵
    n = len(numeric_cols)
    corr_matrix = np.zeros((n, n))
    pval_matrix = np.ones((n, n))

    for i in range(n):
        for j in range(n):
            if i == j:
                corr_matrix[i, j] = 1.0
                pval_matrix[i, j] = 0.0
            elif method == 'pearson':
                r, p = pearsonr(sub_df.iloc[:, i], sub_df.iloc[:, j])
                corr_matrix[i, j] = r
                pval_matrix[i, j] = p
            elif method == 'spearman':
                r, p = spearmanr(sub_df.iloc[:, i], sub_df.iloc[:, j])
                corr_matrix[i, j] = r
                pval_matrix[i, j] = p
            elif method == 'kendall':
                r, p = kendalltau(sub_df.iloc[:, i], sub_df.iloc[:, j])
                corr_matrix[i, j] = r
                pval_matrix[i, j] = p

    # 构建结果表格
    corr_results = []
    for i in range(n):
        for j in range(i + 1, n):
            corr_results.append({
                'var1': numeric_cols[i],
                'var2': numeric_cols[j],
                'correlation': round(corr_matrix[i, j], 4),
                'p_value': round(pval_matrix[i, j], 6),
                'significant': bool(pval_matrix[i, j] < 0.05),
                'strength': '强' if abs(corr_matrix[i, j]) >= 0.7 else ('中等' if abs(corr_matrix[i, j]) >= 0.4 else '弱')
            })

    # Plotly热力图
    fig = go.Figure(data=go.Heatmap(
        z=corr_matrix,
        x=numeric_cols,
        y=numeric_cols,
        text=corr_matrix.round(3),
        texttemplate='%{text}',
        colorscale='RdBu_r',
        zmin=-1, zmax=1,
        colorbar=dict(title='相关系数')
    ))

    # 添加显著性标记
    annotations = []
    for i in range(n):
        for j in range(n):
            if i != j and pval_matrix[i, j] < 0.05:
                annotations.append(dict(
                    x=numeric_cols[j], y=numeric_cols[i],
                    text='*', showarrow=False,
                    font=dict(size=14, color='yellow')
                ))

    fig.update_layout(
        title=f'{method.capitalize()} 相关系数矩阵（* p<0.05, ** p<0.01, *** p<0.001）',
        height=max(500, n * 50),
        xaxis_tickangle=-45,
        annotations=annotations
    )

    # 构建SPSS风格的矩阵数据
    spss_matrix = []
    for i in range(n):
        row_data = {'variable': numeric_cols[i]}
        for j in range(n):
            # 构建单元格内容：相关系数 + 显著性星号
            corr_val = round(corr_matrix[i, j], 3)
            p_val = pval_matrix[i, j]
            
            # 显著性标记
            stars = ''
            if i != j:
                if p_val < 0.001:
                    stars = '***'
                elif p_val < 0.01:
                    stars = '**'
                elif p_val < 0.05:
                    stars = '*'
            
            cell_value = f"{corr_val}{stars}"
            row_data[numeric_cols[j]] = cell_value
            # 同时保存p值用于显示
            row_data[f"{numeric_cols[j]}_p"] = round(p_val, 4)
        spss_matrix.append(row_data)

    chart_json = json.dumps(fig, cls=PlotlyJSONEncoder)

    return jsonify({
        'success': True,
        'variables': numeric_cols,
        'corr_results': convert_numpy_types(corr_results),
        'spss_matrix': convert_numpy_types(spss_matrix),
        'chart': chart_json,
        'method': method,
        'n_used': len(sub_df)
    })


# ============================================================
# 分布诊断模块
# ============================================================

def create_qq_plot(series, column, group_name=None):
    """创建QQ图"""
    from scipy.stats import probplot
    
    fig = go.Figure()
    
    # 计算QQ图数据
    quantiles, values = probplot(series, plot=None)
    
    fig.add_trace(go.Scatter(
        x=quantiles,
        y=values,
        mode='markers',
        name=f'{column} 数据点',
        marker=dict(color='#3498db', size=6)
    ))
    
    # 添加参考线
    min_val = min(values)
    max_val = max(values)
    fig.add_trace(go.Scatter(
        x=[quantiles.min(), quantiles.max()],
        y=[min_val, max_val],
        mode='lines',
        name='参考线',
        line=dict(color='#e74c3c', dash='dash')
    ))
    
    title = f'{column} Q-Q图'
    if group_name:
        title += f' ({group_name})'
    
    fig.update_layout(
        title=title,
        xaxis_title='理论分位数',
        yaxis_title='样本分位数',
        height=400,
        showlegend=True
    )
    
    return json.dumps(fig, cls=PlotlyJSONEncoder)


def create_histogram(series, column, group_name=None):
    """创建直方图"""
    fig = go.Figure()
    
    fig.add_trace(go.Histogram(
        x=series,
        nbinsx=20,
        name=f'{column} 直方图',
        marker=dict(color='#3498db', opacity=0.7)
    ))
    
    title = f'{column} 直方图'
    if group_name:
        title += f' ({group_name})'
    
    fig.update_layout(
        title=title,
        xaxis_title=column,
        yaxis_title='频数',
        height=400
    )
    
    return json.dumps(fig, cls=PlotlyJSONEncoder)


def create_box_plot(df, column, group_column=None):
    """创建箱线图"""
    fig = go.Figure()
    
    if group_column:
        # 按分组绘制
        groups = df[group_column].dropna().unique()
        for group in sorted(groups):
            group_data = df[df[group_column] == group][column].dropna()
            fig.add_trace(go.Box(
                y=group_data,
                name=str(group),
                boxmean='sd'
            ))
    else:
        fig.add_trace(go.Box(
            y=df[column].dropna(),
            name=column,
            boxmean='sd'
        ))
    
    title = f'{column} 箱线图'
    if group_column:
        title += f' (按 {group_column} 分组)'
    
    fig.update_layout(
        title=title,
        yaxis_title=column,
        height=400
    )
    
    return json.dumps(fig, cls=PlotlyJSONEncoder)


@app.route('/distribution_diag', methods=['POST'])
def distribution_diag():
    """对数值型变量进行分布诊断"""
    data = request.json
    session_id = data.get('session_id')
    target_vars = data.get('target_vars', [])
    group_var = data.get('group_var', '')
    chart_types = data.get('chart_types', ['qq', 'histogram', 'box'])

    if session_id not in user_data_store:
        return jsonify({'error': '会话已过期'}), 400

    user_data = user_data_store[session_id]
    df = user_data['df']
    column_types = user_data['column_types']

    # 获取数值型变量
    numeric_cols = [col for col, t in column_types.items()
                    if t in ['numeric_continuous', 'numeric_discrete']]

    if not numeric_cols:
        return jsonify({'error': '无数值型变量'}), 400

    # 如果用户指定了目标变量，则使用指定的变量
    if target_vars and len(target_vars) > 0:
        target_cols = [v for v in target_vars if v in numeric_cols]
        if not target_cols:
            return jsonify({'error': '指定的目标变量不是数值型变量'}), 400
    else:
        target_cols = numeric_cols

    diag_results = {}
    charts = []

    for col in target_cols:
        series = df[col].dropna().astype(float)
        if len(series) < 3:
            continue

        result = {'variable': col, 'n': len(series)}

        # 描述统计
        result['mean'] = round(series.mean(), 4)
        result['std'] = round(series.std(), 4)
        result['median'] = round(series.median(), 4)
        result['skewness'] = round(float(skew(series)), 4)
        result['kurtosis'] = round(float(kurtosis(series)), 4)
        result['min'] = round(float(series.min()), 4)
        result['max'] = round(float(series.max()), 4)
        result['q1'] = round(float(series.quantile(0.25)), 4)
        result['q3'] = round(float(series.quantile(0.75)), 4)

        # 正态性检验
        # 参考文献：Shapiro, S. S., & Wilk, M. B. (1965).
        if len(series) <= 5000:
            stat_sw, p_sw = shapiro(series)
            result['shapiro_stat'] = round(stat_sw, 4)
            result['shapiro_p'] = round(p_sw, 6)
            result['shapiro_normal'] = bool(p_sw >= 0.05)
            result['test_method'] = 'Shapiro-Wilk'
            result['p_value'] = result['shapiro_p']
        else:
            stat_dp, p_dp = normaltest(series)
            result['dagostino_stat'] = round(stat_dp, 4)
            result['dagostino_p'] = round(p_dp, 6)
            result['dagostino_normal'] = bool(p_dp >= 0.05)
            result['test_method'] = 'D\'Agostino-Pearson'
            result['p_value'] = result['dagostino_p']

        # K-S检验
        stat_ks, p_ks = kstest(series, 'norm', args=(series.mean(), series.std()))
        result['ks_stat'] = round(stat_ks, 4)
        result['ks_p'] = round(p_ks, 6)

        # 综合判断
        is_normal = result.get('shapiro_normal', result.get('dagostino_normal', False))
        result['is_normal'] = is_normal
        result['recommendation'] = '正态分布，建议使用均值±标准差' if is_normal else '非正态分布，建议使用中位数[IQR]'

        # 偏度判断
        sk = abs(result['skewness'])
        result['skew_label'] = '对称' if sk < 0.5 else ('轻度偏态' if sk < 1 else ('中度偏态' if sk < 2 else '重度偏态'))

        diag_results[col] = result

        # 生成图表
        if group_var and group_var in df.columns:
            # 按分组生成图表
            groups = df[group_var].dropna().unique()
            for group in sorted(groups):
                group_data = df[df[group_var] == group][col].dropna()
                if len(group_data) < 3:
                    continue
                
                if 'qq' in chart_types:
                    charts.append({
                        'type': 'qq',
                        'variable': col,
                        'group': str(group),
                        'chart': create_qq_plot(group_data, col, str(group))
                    })
                
                if 'histogram' in chart_types:
                    charts.append({
                        'type': 'histogram',
                        'variable': col,
                        'group': str(group),
                        'chart': create_histogram(group_data, col, str(group))
                    })
        else:
            # 不分组生成图表
            if 'qq' in chart_types:
                charts.append({
                    'type': 'qq',
                    'variable': col,
                    'group': None,
                    'chart': create_qq_plot(series, col)
                })
            
            if 'histogram' in chart_types:
                charts.append({
                    'type': 'histogram',
                    'variable': col,
                    'group': None,
                    'chart': create_histogram(series, col)
                })
        
        # 箱线图（支持分组）
        if 'box' in chart_types:
            charts.append({
                'type': 'box',
                'variable': col,
                'group': group_var if group_var else None,
                'chart': create_box_plot(df, col, group_var)
            })

    return jsonify({
        'success': True,
        'diag_results': convert_numpy_types(diag_results),
        'charts': charts,
        'target_vars': target_cols,
        'group_var': group_var
    })


# ============================================================
# Excel导出功能
# 参考文献：
# openpyxl官方文档：Excel文件生成最佳实践
# ============================================================

@app.route('/export_excel', methods=['POST'])
def export_excel():
    """
    导出分析结果为Excel文件
    """
    data = request.json
    session_id = data.get('session_id')
    export_type = data.get('export_type', 'all')

    if session_id not in user_data_store:
        return jsonify({'error': '会话已过期，请重新上传文件'}), 400

    user_data = user_data_store[session_id]
    df = user_data['df']
    column_types = user_data['column_types']

    try:
        wb = Workbook()
        # 删除默认的工作表
        wb.remove(wb.active)
        
        # 注意：已删除原始数据sheet，避免数据泄露风险

        if export_type in ['all', 'missing']:
            # 工作表2: 缺失值分析
            ws_missing = wb.create_sheet('缺失值分析')
            missing_stats = calculate_missing_stats(df)
            for r in dataframe_to_rows(missing_stats, index=False, header=True):
                ws_missing.append(r)

        if export_type in ['all', 'outliers']:
            # 工作表3: 异常值分析
            ws_outliers = wb.create_sheet('异常值分析')
            outlier_stats = get_outlier_stats(df, column_types)
            if len(outlier_stats) > 0:
                for r in dataframe_to_rows(outlier_stats, index=False, header=True):
                    ws_outliers.append(r)

        if export_type in ['all', 'tableone']:
            # 工作表4: Table One
            ws_tableone = wb.create_sheet('TableOne')
            try:
                # 获取分组变量（如果存在）
                group_col = user_data.get('group_col', '')
                tableone_results = generate_table_one(df, column_types, group_col, pval=True, smd=True)
                
                # 获取分组列表
                groups = list(df[group_col].dropna().unique()) if group_col and group_col in df.columns else []
                groups_str = [str(g) for g in groups]
                
                # 构建表头：变量(level) | Group1 | Group2 | P值 | SMD
                headers = ['变量(level)']
                headers.extend(groups_str)
                if len(groups) >= 2:
                    headers.append('P值')
                    if len(groups) == 2:
                        headers.append('SMD')
                
                ws_tableone.append(headers)
                
                # 填充数据
                for row in tableone_results:
                    var_name = row.get('variable', '')
                    var_type = row.get('type', '')
                    categories = row.get('categories', {})
                    group_stats = row.get('group_stats', {})
                    p_value = row.get('p_value')
                    smd = row.get('smd')
                    
                    # 分类变量处理
                    if var_type in ['categorical', 'boolean'] and categories:
                        cats = list(categories.keys())
                        is_binary = len(cats) == 2
                        
                        for idx, cat in enumerate(cats):
                            # 二分类只显示第一行
                            if is_binary and idx > 0:
                                continue
                            
                            row_data = []
                            
                            # 变量名（只在第一行显示）
                            if idx == 0:
                                row_data.append(f'{var_name} ({cat})')
                            else:
                                row_data.append(f'    {cat}')  # 缩进显示
                            
                            # 各分组统计
                            for g in groups_str:
                                if g in group_stats and cat in group_stats[g]:
                                    gs = group_stats[g][cat]
                                    row_data.append(f"{gs['n']} ({gs['pct']}%)")
                                else:
                                    row_data.append('-')
                            
                            # P值（只在第一行显示）
                            if idx == 0 and len(groups) >= 2:
                                if p_value is not None:
                                    if p_value >= 0.999:
                                        row_data.append('>0.999')
                                    elif p_value < 0.001:
                                        row_data.append('<0.001')
                                    else:
                                        row_data.append(f'{p_value:.3f}')
                                else:
                                    row_data.append('-')
                                
                                # SMD（只在两组时显示）
                                if len(groups) == 2:
                                    if smd is not None:
                                        row_data.append(f'{smd:.3f}')
                                    else:
                                        row_data.append('..')
                            elif len(groups) >= 2:
                                row_data.append('')
                                if len(groups) == 2:
                                    row_data.append('')
                            
                            ws_tableone.append(row_data)
                    
                    # 数值型变量处理
                    elif var_type in ['numeric_continuous', 'numeric_discrete']:
                        row_data = [var_name]
                        
                        # 各分组统计
                        for g in groups_str:
                            if g in group_stats:
                                row_data.append(group_stats[g])
                            else:
                                row_data.append('-')
                        
                        # P值
                        if len(groups) >= 2:
                            if p_value is not None:
                                if p_value >= 0.999:
                                    row_data.append('>0.999')
                                elif p_value < 0.001:
                                    row_data.append('<0.001')
                                else:
                                    row_data.append(f'{p_value:.3f}')
                            else:
                                row_data.append('-')
                            
                            # SMD
                            if len(groups) == 2:
                                if smd is not None:
                                    row_data.append(f'{smd:.3f}')
                                else:
                                    row_data.append('..')
                        
                        ws_tableone.append(row_data)
                    
                    # 其他类型变量
                    else:
                        row_data = [var_name]
                        for g in groups_str:
                            row_data.append('-')
                        if len(groups) >= 2:
                            row_data.append('-')
                            if len(groups) == 2:
                                row_data.append('..')
                        ws_tableone.append(row_data)
                        
            except Exception as e:
                ws_tableone.append(['错误', str(e)])

        if export_type in ['all', 'correlation']:
            # 工作表5: 相关性分析
            numeric_cols = [col for col, t in column_types.items()
                           if t in ['numeric_continuous', 'numeric_discrete']]
            if len(numeric_cols) >= 2:
                ws_corr = wb.create_sheet('相关性分析')
                sub_df = df[numeric_cols].dropna()
                if len(sub_df) >= 2:
                    corr_matrix = sub_df.corr(method='pearson')
                    corr_matrix_df = pd.DataFrame(corr_matrix)
                    for r in dataframe_to_rows(corr_matrix_df, index=True, header=True):
                        ws_corr.append(r)

        # 保存到内存并返回
        import io
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        # 转换为base64以便前端下载
        import base64
        excel_data = base64.b64encode(buffer.read()).decode('utf-8')

        return jsonify({
            'success': True,
            'filename': 'data_analysis_results.xlsx',
            'excel_data': excel_data
        })

    except Exception as e:
        return jsonify({'error': f'Excel导出失败: {str(e)}'}), 500


@app.route('/export_pdf', methods=['POST'])
def export_pdf():
    """
    导出分析结果为PDF报告
    """
    data = request.json
    session_id = data.get('session_id')
    export_type = data.get('export_type', 'tableone')  # 'tableone' 或 'group'

    if session_id not in user_data_store:
        return jsonify({'error': '会话已过期，请重新上传文件'}), 400

    user_data = user_data_store[session_id]
    df = user_data['df']
    column_types = user_data['column_types']

    try:
        import io
        buffer = io.BytesIO()
        
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        # 添加标题
        title = Paragraph('数据分析报告', styles['Title'])
        story.append(title)
        story.append(Spacer(1, 12))
        
        if export_type == 'tableone':
            # 生成Table One报告
            story.append(Paragraph('Table One: 基线特征表', styles['Heading2']))
            story.append(Spacer(1, 12))
            
            try:
                tableone_results = generate_table_one(df, column_types)
                
                # 准备表格数据
                table_data = [['变量', '类型', '统计摘要', '缺失数', '缺失%']]
                for row in tableone_results:
                    table_data.append([
                        str(row.get('variable', '')),
                        str(row.get('type', '')),
                        str(row.get('summary', '')),
                        str(row.get('n_missing', 0)),
                        f"{row.get('n_missing_pct', 0)}%"
                    ])
                
                # 创建表格
                t = Table(table_data)
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                story.append(t)
            except Exception as e:
                story.append(Paragraph(f'生成Table One时出错: {str(e)}', styles['Normal']))
        
        elif export_type == 'group':
            # 生成分组分析报告
            story.append(Paragraph('分组分析报告', styles['Heading2']))
            story.append(Spacer(1, 12))
            story.append(Paragraph('需要指定分组变量以生成分组分析报告', styles['Normal']))
        
        doc.build(story)
        buffer.seek(0)
        
        # 转换为base64
        import base64
        pdf_data = base64.b64encode(buffer.read()).decode('utf-8')
        
        return jsonify({
            'success': True,
            'filename': 'analysis_report.pdf',
            'pdf_data': pdf_data
        })
        
    except Exception as e:
        return jsonify({'error': f'PDF导出失败: {str(e)}'}), 500


@app.route('/reset', methods=['POST'])
def reset_data():
    """
    重置当前会话数据
    """
    data = request.json
    session_id = data.get('session_id')

    if session_id not in user_data_store:
        return jsonify({'error': '会话不存在'}), 400

    # 清除数据
    user_data_store[session_id] = {}

    return jsonify({'success': True, 'message': '数据已重置'})


if __name__ == '__main__':
    # 添加命令行参数
    import argparse

    parser = argparse.ArgumentParser(description='数据上传与自动化分析应用')
    parser.add_argument('--port', type=int, default=5000, help='服务端口')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='服务地址')
    parser.add_argument('--debug', action='store_true', help='调试模式')

    args = parser.parse_args()

    # 打印启动信息
    print("=" * 60)
    print("数据上传与自动化分析应用")
    print("=" * 60)
    print(f"访问地址: http://{args.host}:{args.port}")
    print("=" * 60)

    app.run(host=args.host, port=args.port, debug=args.debug)