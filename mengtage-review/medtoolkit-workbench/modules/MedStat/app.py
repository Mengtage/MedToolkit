"""
MedStat - 医学统计分析工具
Flask应用主文件
"""

from flask import Flask, render_template, request, jsonify, session, send_file
from werkzeug.utils import secure_filename
import pandas as pd
import numpy as np
import os
import uuid
import traceback
import json
import math
from io import BytesIO

# 导入我们自己的模块
from src.core import DataImporter, VariableTypeDetector
from src.analysis import (
    MissingDataAnalyzer, OutlierDetector,
    DistributionDiagnostics, MICEImputer,
    TableOne, GroupAnalyzer, CorrelationAnalyzer,
    ModelEvaluator, evaluate_model, compare_models,
    LinearRegressionAnalyzer, LogisticRegressionAnalyzer, GLMAnalyzer,
    RegressionDiagnostics, FormulaParser,
    NormalityTests, VarianceTests, CorrelationTests,
    MeanComparisonTests, ProportionTests, EffectSizeCalculator,
    MultipleComparisons
)
from src.analysis.categorical_tests import (
    CategoricalTestSelector, CochranArmitageTest, MantelHaenszelTest
)
from src.analysis.sensitivity_analysis import SensitivityAnalyzer
from src.analysis.interaction_analysis import InteractionAnalyzer
from src.utils import Visualizer, Exporter


# 初始化Flask应用
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
app.config['UPLOAD_FOLDER'] = '/tmp/medstat_uploads'
app.config['DATA_FOLDER'] = '/tmp/medstat_sessions'


# 确保目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['DATA_FOLDER'], exist_ok=True)


@app.before_request
def log_request():
    """记录所有请求的详细信息用于调试"""
    log_line = (
        f"\n{'='*60}\n"
        f"【请求日志】{request.method} {request.path}\n"
        f"时间: {pd.Timestamp.now()}\n"
        f"客户端IP: {request.remote_addr}\n"
        f"User-Agent: {request.headers.get('User-Agent', 'Unknown')}\n"
        f"Content-Type: {request.headers.get('Content-Type', 'Unknown')}\n"
        f"Referrer: {request.headers.get('Referer', 'Unknown')}\n"
        f"查询参数: {request.args}\n"
        f"表单字段: {list(request.form.keys())}\n"
        f"文件字段: {list(request.files.keys())}\n"
        f"{'='*60}"
    )
    print(log_line)
    # 日志写到应用所在目录（避免硬编码旧路径导致 FileNotFoundError→500）
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'server.log')
    with open(log_path, 'a') as f:
        f.write(log_line + '\n')


@app.after_request
def add_security_headers(response):
    """添加安全响应头"""
    # Content Security Policy - 允许必要的资源
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdn.plot.ly; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' data: https://cdn.jsdelivr.net https://*.githubusercontent.com; "
        "font-src 'self' https://cdn.jsdelivr.net; "
        "connect-src 'self' https://cdn.jsdelivr.net;"
    )
    response.headers['Content-Security-Policy'] = csp
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response


def get_session_dir(session_id):
    """获取会话目录"""
    return os.path.join(app.config['DATA_FOLDER'], session_id)


def save_data(session_id, df, variable_types, filename=None):
    """保存数据到文件系统"""
    session_dir = get_session_dir(session_id)
    os.makedirs(session_dir, exist_ok=True)
    
    # 保存DataFrame
    data_path = os.path.join(session_dir, 'data.pkl')
    df.to_pickle(data_path)
    
    # 保存变量类型
    types_path = os.path.join(session_dir, 'variable_types.json')
    with open(types_path, 'w', encoding='utf-8') as f:
        json.dump(variable_types, f, ensure_ascii=False)
    
    # 保存原始文件名
    if filename:
        meta_path = os.path.join(session_dir, 'meta.json')
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump({'filename': filename}, f, ensure_ascii=False)


def load_data(session_id):
    """从文件系统加载数据"""
    session_dir = get_session_dir(session_id)
    
    data_path = os.path.join(session_dir, 'data.pkl')
    types_path = os.path.join(session_dir, 'variable_types.json')
    
    if not os.path.exists(data_path) or not os.path.exists(types_path):
        return None, None
    
    df = pd.read_pickle(data_path)
    
    with open(types_path, 'r', encoding='utf-8') as f:
        variable_types = json.load(f)
    
    return df, variable_types


def save_result(session_id, result_name, data):
    """保存分析结果"""
    session_dir = get_session_dir(session_id)
    os.makedirs(session_dir, exist_ok=True)
    
    result_path = os.path.join(session_dir, f'result_{result_name}.json')
    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, default=str)


def load_result(session_id, result_name):
    """加载分析结果"""
    session_dir = get_session_dir(session_id)
    result_path = os.path.join(session_dir, f'result_{result_name}.json')
    
    if os.path.exists(result_path):
        with open(result_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


@app.route('/')
def index():
    """首页"""
    session.clear()
    return render_template('index.html')


@app.route('/api/health')
def health_check():
    """健康检查端点"""
    return jsonify({'status': 'ok', 'timestamp': pd.Timestamp.now().isoformat()})


@app.route('/api/upload', methods=['POST'])
def upload_file():
    """上传文件API"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '没有文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '没有选择文件'}), 400
        
        if file:
            importer = DataImporter()
            df = importer.read_file(file, file.filename)
            
            type_detector = VariableTypeDetector(df)
            variable_types = type_detector.get_types()
            
            session_id = str(uuid.uuid4())
            session['id'] = session_id
            
            # 保存到文件系统
            save_data(session_id, df, variable_types, secure_filename(file.filename))
            
            # 转换为前端期望的格式：对象数组
            # 确保所有NaN值都被替换为None
            data_list = []
            for _, row in df.iterrows():
                row_dict = {}
                for col in df.columns:
                    val = row[col]
                    # 检查NaN和Infinity
                    if pd.isna(val) or (isinstance(val, float) and (math.isnan(val) or math.isinf(val))):
                        row_dict[col] = None
                    else:
                        row_dict[col] = val
                data_list.append(row_dict)
            
            # 手动序列化并替换NaN和Infinity
            response_data = {
                'success': True,
                'data': data_list,
                'variable_types': variable_types,
                'row_count': len(df),
                'column_count': len(df.columns),
                'filename': secure_filename(file.filename)
            }
            
            # 使用json.dumps并处理NaN/Infinity
            json_str = json.dumps(response_data, 
                                default=lambda x: None if pd.isna(x) else str(x),
                                allow_nan=False)
            response = app.response_class(
                response=json_str,
                status=200,
                mimetype='application/json'
            )
            return response
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/variable-types', methods=['POST'])
def update_variable_types():
    """更新变量类型"""
    try:
        session_id = session.get('id')
        if not session_id:
            return jsonify({'error': '没有上传数据'}), 400
        
        df, _ = load_data(session_id)
        if df is None:
            return jsonify({'error': '数据加载失败'}), 400
        
        # 修复：处理Content-Type不正确的情况
        request_data = request.json if request.json else {}
        new_types = request_data.get('types', {})
        
        if not new_types:
            return jsonify({'error': '没有提供类型信息'}), 400
        
        type_detector = VariableTypeDetector(df)
        
        for col, new_type in new_types.items():
            if col in type_detector.type_mapping:
                type_detector.type_mapping[col] = new_type
        
        variable_types = type_detector.get_types()
        
        # 重新保存
        save_data(session_id, df, variable_types)
        
        return jsonify({
            'success': True,
            'variable_types': variable_types
        })
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/missing-analysis', methods=['POST'])
def missing_analysis():
    """缺失值分析"""
    try:
        session_id = session.get('id')
        if not session_id:
            return jsonify({'error': '没有上传数据'}), 400

        df, _ = load_data(session_id)
        if df is None:
            return jsonify({'error': '数据加载失败'}), 400

        request_data = request.get_json(silent=True) or {}
        policy = request_data.get('missing_codes', load_result(session_id, 'missing_policy') or {})
        analyzer = MissingDataAnalyzer(df, missing_codes=policy)
        save_result(session_id, 'missing_policy', policy)
        raw_results = analyzer.analyze()

        # 计算总体缺失率
        total_cells = df.shape[0] * df.shape[1]
        total_missing = sum(r['missing_count'] for r in raw_results)
        missing_rate = total_missing / total_cells if total_cells > 0 else 0

        # 前端期望的格式
        stats = []
        for r in raw_results:
            stats.append({
                'variable': r['variable'],
                'missing_count': r['missing_count'],
                'missing_percent': (r['missing_count'] / r['total'] * 100) if r['total'] > 0 else 0,
                'total': r['total']
            })

        # 生成热力图数据
        missing_matrix = analyzer.get_missing_matrix()
        heatmap_data = {
            'data': [{
                'z': missing_matrix.values.tolist(),
                'x': df.columns.tolist(),
                'y': [str(i) for i in range(len(df))],
                'type': 'heatmap',
                'colorscale': [[0, '#f0f0f0'], [1, '#ff6b6b']],
                'zmin': 0,
                'zmax': 1,
                'showscale': True,
                'colorbar': {
                    'tickvals': [0, 1],
                    'ticktext': ['非缺失', '缺失'],
                    'title': '状态'
                }
            }],
            'layout': {
                'title': '缺失值分布热力图',
                'xaxis': {'title': '变量'},
                'yaxis': {'title': '样本'}
            }
        }

        # 生成条形图数据
        missing_counts = [r['missing_count'] for r in raw_results]
        bar_chart_data = {
            'data': [{
                'x': [r['variable'] for r in raw_results],
                'y': missing_counts,
                'type': 'bar',
                'marker': {'color': '#4e79a7'}
            }],
            'layout': {
                'title': '各变量缺失数量',
                'xaxis': {'title': '变量'},
                'yaxis': {'title': '缺失数量'}
            }
        }

        results = {
            'missing_rate': missing_rate,
            'stats': stats,
            'heatmap': heatmap_data,
            'bar_chart': bar_chart_data
        }

        save_result(session_id, 'missing_analysis', results)

        return jsonify({
            'success': True,
            'results': results
        })
    
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/outlier-detection', methods=['POST'])
def outlier_detection():
    """异常值检测"""
    try:
        session_id = session.get('id')
        if not session_id:
            return jsonify({'error': '没有上传数据'}), 400

        df, var_types = load_data(session_id)
        if df is None or var_types is None:
            return jsonify({'error': '数据加载失败'}), 400

        detector = OutlierDetector(df, var_types)
        raw_results = detector.detect()

        # 前端期望的格式
        stats = []
        charts = []

        for r in raw_results:
            total = r.get('total', 0)
            zscore_outliers = r.get('zscore_outliers', 0)
            iqr_outliers = r.get('iqr_outliers', 0)

            stats.append({
                'variable': r['variable'],
                'total': total,
                'zscore_outliers': zscore_outliers,
                'zscore_percent': (zscore_outliers / total * 100) if total > 0 else 0,
                'iqr_outliers': iqr_outliers,
                'iqr_percent': (iqr_outliers / total * 100) if total > 0 else 0
            })

            # 生成箱线图
            col_data = df[r['variable']].dropna().values
            if len(col_data) > 0:
                charts.append({
                    'title': f'{r["variable"]} 箱线图',
                    'data': [{
                        'y': col_data.tolist(),
                        'type': 'box',
                        'name': r['variable'],
                        'boxpoints': 'outliers'
                    }],
                    'layout': {
                        'title': f'{r["variable"]} 异常值检测',
                        'yaxis': {'title': r['variable']}
                    }
                })

        results = {
            'stats': stats,
            'charts': charts
        }

        save_result(session_id, 'outlier_detection', results)

        return jsonify({
            'success': True,
            'stats': stats,
            'charts': charts
        })
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/outlier-details', methods=['POST'])
def outlier_details():
    """获取特定变量的异常值详情"""
    try:
        session_id = session.get('id')
        if not session_id:
            return jsonify({'error': '没有上传数据'}), 400
        
        df, var_types = load_data(session_id)
        if df is None or var_types is None:
            return jsonify({'error': '数据加载失败'}), 400
        
        # 修复：处理Content-Type不正确的情况
        request_data = request.json if request.json else {}
        variable = request_data.get('variable')
        
        if variable not in df.columns:
            return jsonify({'error': '变量不存在'}), 400
        
        detector = OutlierDetector(df, var_types)
        results = detector.detect()
        
        details = []
        if results:
            for res in results:
                if res['variable'] == variable and 'indices' in res:
                    for idx in res['indices']:
                        details.append({
                            'row_index': idx,
                            'value': df.iloc[idx][variable],
                            'method': res['method']
                        })
                    break
        
        return jsonify({
            'success': True,
            'details': details
        })
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/distribution-diagnostics', methods=['POST'])
def distribution_diagnostics():
    """分布诊断"""
    try:
        session_id = session.get('id')
        if not session_id:
            return jsonify({'error': '没有上传数据'}), 400

        df, var_types = load_data(session_id)
        if df is None or var_types is None:
            return jsonify({'error': '数据加载失败'}), 400

        # 修复：处理Content-Type不正确的情况
        request_data = request.json if request.json else {}
        targets = request_data.get('targets', [])
        chart_type = request_data.get('chart_type', 'all')

        diag = DistributionDiagnostics(df, var_types)

        if targets:
            raw_results = [diag.analyze_variable(t) for t in targets]
        else:
            raw_results = diag.analyze_all_numeric()

        # 前端期望的格式
        results = []
        charts = []

        for res in raw_results:
            if 'error' in res:
                continue

            # 选择一个主要的检验结果
            test_name = 'Shapiro-Wilk'
            p_value = 0.5

            if 'shapiro_wilk' in res and res['shapiro_wilk']:
                p_value = res['shapiro_wilk']['p_value']
            elif 'kolmogorov_smirnov' in res and res['kolmogorov_smirnov']:
                test_name = 'Kolmogorov-Smirnov'
                p_value = res['kolmogorov_smirnov']['p_value']
            elif 'dagostino_pearson' in res and res['dagostino_pearson']:
                test_name = 'D\'Agostino-Pearson'
                p_value = res['dagostino_pearson']['p_value']

            # 结论和建议
            conclusion = '正态' if p_value > 0.05 else '非正态'
            recommendation = '参数检验' if p_value > 0.05 else '非参数检验'

            results.append({
                'variable': res['column'],
                'n': res['n'],
                'mean': res['stats']['mean'],
                'std': res['stats']['std'],
                'skewness': res['stats']['skewness'],
                'kurtosis': res['stats']['kurtosis'],
                'test_name': test_name,
                'p_value': p_value,
                'conclusion': conclusion,
                'recommendation': recommendation
            })

            # 生成图表
            col_data = df[res['column']].dropna().values
            if len(col_data) > 0:
                if chart_type in ['all', 'qq']:
                    # QQ图
                    import scipy.stats as stats
                    sorted_data = np.sort(col_data)
                    n = len(sorted_data)
                    theoretical_quantiles = stats.norm.ppf((np.arange(1, n + 1) - 0.5) / n)
                    charts.append({
                        'data': [{
                            'x': theoretical_quantiles.tolist(),
                            'y': sorted_data.tolist(),
                            'mode': 'markers',
                            'type': 'scatter',
                            'name': res['column']
                        }],
                        'layout': {
                            'title': f'{res["column"]} Q-Q Plot',
                            'xaxis': {'title': '理论分位数'},
                            'yaxis': {'title': '样本分位数'}
                        }
                    })

                if chart_type in ['all', 'histogram']:
                    # 直方图
                    charts.append({
                        'data': [{
                            'x': col_data.tolist(),
                            'type': 'histogram',
                            'name': res['column'],
                            'nbinsx': 30
                        }],
                        'layout': {
                            'title': f'{res["column"]} 直方图',
                            'xaxis': {'title': res['column']},
                            'yaxis': {'title': '频数'}
                        }
                    })

                if chart_type in ['all', 'box']:
                    # 箱线图
                    charts.append({
                        'data': [{
                            'y': col_data.tolist(),
                            'type': 'box',
                            'name': res['column']
                        }],
                        'layout': {
                            'title': f'{res["column"]} 箱线图',
                            'yaxis': {'title': res['column']}
                        }
                    })

        save_result(session_id, 'distribution_diagnostics', {'results': results, 'charts': charts})

        return jsonify({
            'success': True,
            'results': results,
            'charts': charts
        })
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/mice-impute', methods=['POST'])
def mice_impute():
    """MICE多重插补"""
    try:
        session_id = session.get('id')
        
        if not session_id:
            return jsonify({'error': '没有上传数据'}), 400

        df, var_types = load_data(session_id)
        
        if df is None or var_types is None:
            return jsonify({'error': '数据加载失败'}), 400

        # 修复：处理Content-Type不正确的情况
        request_data = request.get_json(silent=True) or {}
        
        n_imputations = request_data.get('n_imputations', 5)
        max_iter = request_data.get('max_iter', 10)
        strategy = request_data.get('strategy', 'bayesian_ridge')

        
        policy = request_data.get('missing_codes', load_result(session_id, 'missing_policy') or {})
        df = MissingDataAnalyzer(df, missing_codes=policy).normalized_data()
        imputer = MICEImputer(df, var_types, n_imputations=n_imputations,
                             max_iter=max_iter, strategy=strategy)
        imputed_datasets = imputer.impute()
        save_result(session_id, 'missing_policy', policy)
        comparison = imputer.get_comparison()
        

        # 计算插补前后缺失数量
        before_missing = int(df.isnull().sum().sum())
        after_missing = int(imputed_datasets[0].isnull().sum().sum())
        

        # 保存插补数据集
        session_dir = get_session_dir(session_id)
        for i, ds in enumerate(imputed_datasets):
            ds_path = os.path.join(session_dir, f'imputed_{i}.pkl')
            ds.to_pickle(ds_path)

        # 构建比较表格数据（修复：检查comparison是否为None）
        comp_data = []
        if comparison is not None:
            for var, row_data in comparison.items():
                comp_data.append({
                    'variable': var,
                    'original_missing': row_data.get('original_missing', 0),
                    'original_mean': row_data.get('original_mean', 0),
                    'original_std': row_data.get('original_std', 0),
                    'imputed_mean': row_data.get('imputed_mean', 0),
                    'imputed_std': row_data.get('imputed_std', 0),
                    'imputed_values_mean': row_data.get('imputed_values_mean')
                })

        # Pool actual per-dataset estimates and variances via the shared implementation.
        rubin_stats = imputer.pooled_means()

        # 生成均值比较图表
        mean_comparison_chart = {}
        if comparison is not None:
            variables = list(comparison.keys())
            original_means = [comparison[var].get('original_mean', 0) for var in variables]
            imputed_means = [comparison[var].get('imputed_mean', 0) for var in variables]

            mean_comparison_chart = {
                'data': [
                    {'x': variables, 'y': original_means, 'name': '原始均值', 'type': 'bar'},
                    {'x': variables, 'y': imputed_means, 'name': '插补后均值', 'type': 'bar'}
                ],
                'layout': {
                    'title': '插补前后均值对比',
                    'barmode': 'group',
                    'xaxis': {'title': '变量'},
                    'yaxis': {'title': '均值'}
                }
            }

        # 生成缺失数量图表
        missing_chart = {
            'data': [{
                'x': ['插补前', '插补后'],
                'y': [before_missing, after_missing],
                'type': 'bar',
                'marker': {'color': ['#ff6b6b', '#4ecdc4']}
            }],
            'layout': {
                'title': '缺失值数量对比',
                'xaxis': {'title': '状态'},
                'yaxis': {'title': '缺失数量'}
            }
        }

        # 生成分布对比图表
        distribution_charts = []
        numeric_cols = [col for col in df.columns if var_types.get(col) in ['numeric_continuous', 'numeric_discrete']]
        for col in numeric_cols[:5]:  # 限制图表数量
            orig_data = df[col].dropna().values
            if len(orig_data) > 0:
                imputed_data = imputed_datasets[0][col].dropna().values
                if len(imputed_data) > 0:
                    distribution_charts.append({
                        'data': [
                            {'x': orig_data.tolist(), 'name': '原始', 'type': 'histogram', 'opacity': 0.7},
                            {'x': imputed_data.tolist(), 'name': '插补后', 'type': 'histogram', 'opacity': 0.7}
                        ],
                        'layout': {
                            'title': f'{col} 分布对比',
                            'barmode': 'overlay',
                            'xaxis': {'title': col},
                            'yaxis': {'title': '频数'}
                        }
                    })

        result_data = {
            'before_missing': before_missing,
            'after_missing': after_missing,
            'm': len(imputed_datasets),
            'inference_status': 'multiple_imputation' if len(imputed_datasets) > 1 else 'single_completed_dataset_no_mi_inference',
            'comparison': comp_data,
            'rubin_stats': rubin_stats,
            'mean_comparison_chart': mean_comparison_chart,
            'missing_chart': missing_chart,
            'distribution_charts': distribution_charts
        }

        save_result(session_id, 'mice_results', result_data)
        
        return jsonify({
            'success': True,
            **result_data
        })
    
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/tableone', methods=['POST'])
def generate_tableone():
    """生成TableOne基线特征表"""
    try:
        session_id = session.get('id')
        if not session_id:
            return jsonify({'error': '没有上传数据'}), 400

        df, var_types = load_data(session_id)
        if df is None or var_types is None:
            return jsonify({'error': '数据加载失败'}), 400

        # 修复：处理Content-Type不正确的情况
        request_data = request.json if request.json else {}
        strata = request_data.get('group_by', None)
        pval = request_data.get('pval', True)
        smd = request_data.get('smd', True)

        table_one = TableOne(df, var_types, strata=strata)
        result = table_one.generate()

        # 转换为前端期望的格式
        headers = ['变量']
        rows = []

        if strata:
            groups = sorted(df[strata].dropna().unique())
            headers.extend([str(g) for g in groups])
            if pval:
                headers.append('P值')
            if smd and len(groups) == 2:
                headers.append('SMD')
        else:
            headers.append('总体')

        # 计算SMD
        smd_values = {}
        if smd and strata and len(groups) == 2:
            for var in table_one.numeric_vars:
                var_data = result['table'][result['table']['variable'] == var]
                if len(var_data) >= 2:
                    try:
                        vals = {}
                        for g in groups:
                            row = var_data[var_data['group'] == str(g)]
                            if len(row) > 0:
                                vals[g] = {
                                    'mean': row['mean'].iloc[0],
                                    'std': row['sd'].iloc[0]
                                }
                        if len(vals) == 2:
                            g1, g2 = list(vals.keys())
                            mean_diff = vals[g1]['mean'] - vals[g2]['mean']
                            pooled_std = np.sqrt((vals[g1]['std']**2 + vals[g2]['std']**2) / 2)
                            if pooled_std > 0:
                                smd_values[var] = abs(mean_diff / pooled_std)
                    except:
                        pass

        # 处理数值变量
        for var in table_one.numeric_vars:
            var_data = result['table'][result['table']['variable'] == var]

            if strata:
                row_values = [f'{var}']
                for g in groups:
                    group_row = var_data[var_data['group'] == str(g)]
                    if len(group_row) > 0:
                        row_values.append(group_row['display'].iloc[0])
                    else:
                        row_values.append('-')
                if pval:
                    p_row = next((p for p in result['p_values'] if p['variable'] == var), None)
                    if p_row:
                        row_values.append(f"{p_row['p_value']:.4f}")
                    else:
                        row_values.append('-')
                if smd and len(groups) == 2:
                    smd_val = smd_values.get(var)
                    if smd_val is not None:
                        row_values.append(f"{smd_val:.4f}")
                    else:
                        row_values.append('-')
                rows.append(row_values)
            else:
                if len(var_data) > 0:
                    rows.append([var, var_data['display'].iloc[0], ''])

        # 处理分类变量
        for var in table_one.categorical_vars:
            var_data = result['table'][result['table']['variable'] == var]
            levels = sorted(var_data['level'].unique())

            for level in levels:
                level_data = var_data[var_data['level'] == str(level)]

                if strata:
                    row_values = [f'  {level}']
                    for g in groups:
                        group_row = level_data[level_data['group'] == str(g)]
                        if len(group_row) > 0:
                            row_values.append(group_row['display'].iloc[0])
                        else:
                            row_values.append('-')
                    if pval and level == levels[0]:
                        p_row = next((p for p in result['p_values'] if p['variable'] == var), None)
                        if p_row:
                            row_values.append(f"{p_row['p_value']:.4f}")
                        else:
                            row_values.append('-')
                    else:
                        if pval:
                            row_values.append('')
                    if smd and len(groups) == 2:
                        if level == levels[0]:
                            smd_val = smd_values.get(var)
                            if smd_val is not None:
                                row_values.append(f"{smd_val:.4f}")
                            else:
                                row_values.append('-')
                        else:
                            row_values.append('')
                    rows.append(row_values)
                else:
                    if len(level_data) > 0:
                        rows.append([f'{var}: {level}', level_data['display'].iloc[0], ''])

        tableone_result = {
            'headers': headers,
            'rows': rows,
            'n': len(df)
        }

        save_result(session_id, 'tableone', tableone_result)

        return jsonify({
            'success': True,
            'headers': headers,
            'rows': rows,
            'n': len(df)
        })
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/group-analysis', methods=['POST'])
def group_analysis():
    """分组分析"""
    try:
        session_id = session.get('id')
        if not session_id:
            return jsonify({'error': '没有上传数据'}), 400
        
        df, var_types = load_data(session_id)
        if df is None or var_types is None:
            return jsonify({'error': '数据加载失败'}), 400
        
        # 修复：处理Content-Type不正确的情况
        request_data = request.json if request.json else {}
        group_var = request_data.get('group_by')
        
        if not group_var:
            return jsonify({'error': '没有指定分组变量'}), 400
        
        analyzer = GroupAnalyzer(df, var_types, group_var)
        results = analyzer.analyze_all()
        
        # 转换为前端期望的格式
        methods = []
        stats_headers = ['变量']
        groups = sorted(df[group_var].dropna().unique())
        stats_headers.extend([str(g) for g in groups])
        stats_headers.append('统计量')
        stats_headers.append('方法')
        stats_rows = []
        charts = []
        
        for result in results:
            var_name = result['variable']
            
            # 确定分布和统计方法
            if result['type'] == 'numeric':
                # 使用分布诊断结果
                diag = DistributionDiagnostics(df, var_types)
                diag_result = diag.test_normality(var_name)
                is_normal = diag_result.get('is_normal_majority', False)
                distribution = '正态' if is_normal else '非正态'
                
                if len(groups) == 2:
                    if is_normal:
                        method = '独立样本 t 检验'
                        test_key = 'welch_t_test'
                    else:
                        method = 'Mann-Whitney U 检验'
                        test_key = 'mann_whitney_u'
                else:
                    if is_normal:
                        method = '单因素方差分析'
                        test_key = 'anova'
                    else:
                        method = 'Kruskal-Wallis 检验'
                        test_key = 'kruskal_wallis'
                
                statistic = '-'
                if 'tests' in result and test_key in result['tests']:
                    statistic = f"{result['tests'][test_key]['statistic']:.3f}"
                
                methods.append({
                    'variable': var_name,
                    'distribution': distribution,
                    'group_count': len(groups),
                    'statistic': statistic,
                    'method': method
                })
                
                # 构建统计表格行
                row_data = [var_name]
                for g in groups:
                    group_key = str(g)
                    if group_key in result['groups']:
                        g_data = result['groups'][group_key]
                        row_data.append(f"{g_data['mean']:.2f} ({g_data['sd']:.2f})")
                    else:
                        row_data.append('-')
                row_data.append(statistic)
                row_data.append(method)
                stats_rows.append(row_data)
                
                # 添加图表数据
                chart_data = {
                    'title': f'{var_name} 按 {group_var} 分组',
                    'data': [],
                    'layout': {
                        'title': f'{var_name} 分布',
                        'xaxis': {'title': group_var},
                        'yaxis': {'title': var_name}
                    }
                }
                
                x_values = []
                y_values = []
                for g in groups:
                    group_key = str(g)
                    if group_key in result['groups']:
                        group_vals = df[df[group_var] == g][var_name].dropna()
                        x_values.extend([str(g)] * len(group_vals))
                        y_values.extend(group_vals.tolist())
                
                chart_data['data'].append({
                    'type': 'box',
                    'x': x_values,
                    'y': y_values,
                    'name': var_name
                })
                
                charts.append(chart_data)
                
            else:
                # 分类变量
                methods.append({
                    'variable': var_name,
                    'distribution': '-',
                    'group_count': len(groups),
                    'statistic': '-',
                    'method': '卡方检验'
                })
                
                # 构建统计表格行
                row_data = [var_name]
                for g in groups:
                    group_key = str(g)
                    if group_key in result['groups']:
                        level_strs = []
                        for level, level_data in result['groups'][group_key].items():
                            level_strs.append(f"{level}: {level_data['n']} ({level_data['percent']}%)")
                        row_data.append(', '.join(level_strs))
                    else:
                        row_data.append('-')
                
                statistic = '-'
                if 'tests' in result and 'chi_square' in result['tests']:
                    statistic = f"{result['tests']['chi_square']['statistic']:.3f}"
                
                row_data.append(statistic)
                row_data.append('卡方检验')
                stats_rows.append(row_data)
                
                # 添加条形图
                chart_data = {
                    'title': f'{var_name} 按 {group_var} 分组',
                    'data': [],
                    'layout': {
                        'title': f'{var_name} 分布',
                        'barmode': 'group',
                        'xaxis': {'title': group_var},
                        'yaxis': {'title': '计数'}
                    }
                }
                
                # 获取所有分类级别
                all_levels = set()
                for g in groups:
                    group_key = str(g)
                    if group_key in result['groups']:
                        all_levels.update(result['groups'][group_key].keys())
                all_levels = sorted(all_levels)
                
                for level in all_levels:
                    x = [str(g) for g in groups]
                    y = []
                    for g in groups:
                        group_key = str(g)
                        if group_key in result['groups'] and level in result['groups'][group_key]:
                            y.append(result['groups'][group_key][level]['n'])
                        else:
                            y.append(0)
                    
                    chart_data['data'].append({
                        'type': 'bar',
                        'x': x,
                        'y': y,
                        'name': str(level)
                    })
                
                charts.append(chart_data)
        
        group_result = {
            'methods': methods,
            'stats_headers': stats_headers,
            'stats_rows': stats_rows,
            'charts': charts,
            'group_var': group_var
        }
        
        save_result(session_id, 'group_analysis', group_result)
        
        return jsonify({
            'success': True,
            'methods': methods,
            'stats_headers': stats_headers,
            'stats_rows': stats_rows,
            'charts': charts,
            'group_var': group_var
        })
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/correlation-analysis', methods=['POST'])
def correlation_analysis():
    """相关性分析"""
    try:
        session_id = session.get('id')
        if not session_id:
            return jsonify({'error': '没有上传数据'}), 400
        
        df, var_types = load_data(session_id)
        if df is None or var_types is None:
            return jsonify({'error': '数据加载失败'}), 400
        
        # 修复：处理Content-Type不正确的情况
        request_data = request.json if request.json else {}
        method = request_data.get('method', 'pearson')
        
        analyzer = CorrelationAnalyzer(df, var_types)
        results = analyzer.calculate_all(method=method)
        pairwise = analyzer.pairwise_analysis()
        
        if not results:
            return jsonify({'error': '数值变量不足，无法进行相关性分析'}), 400
        
        # 构建热力图数据
        variables = results['variables']
        corr_matrix = results['correlation_matrix']
        
        z_values = []
        for var1 in variables:
            row = []
            for var2 in variables:
                row.append(corr_matrix[var1][var2])
            z_values.append(row)
        
        heatmap = {
            'data': [{
                'type': 'heatmap',
                'x': variables,
                'y': variables,
                'z': z_values,
                'colorscale': 'RdBu',
                'zmin': -1,
                'zmax': 1,
                'text': z_values,
                'hoverongaps': False
            }],
            'layout': {
                'title': f'{method.capitalize()} 相关系数热力图',
                'xaxis': {'title': '', 'tickangle': -45},
                'yaxis': {'title': ''}
            }
        }
        
        # 构建详情表格
        details = []
        for pair in pairwise:
            var1, var2 = pair['x'], pair['y']
            corr_result = None
            
            if method == 'pearson' and pair['pearson']:
                corr_result = pair['pearson']
            elif method == 'spearman' and pair['spearman']:
                corr_result = pair['spearman']
            
            if corr_result:
                details.append({
                    'var1': var1,
                    'var2': var2,
                    'correlation': corr_result['coefficient'],
                    'p_value': corr_result['p_value'],
                    'significant': corr_result['p_value'] < 0.05
                })
        
        corr_result = {
            'heatmap': heatmap,
            'details': details,
            'method': method
        }
        
        save_result(session_id, 'correlation_analysis', corr_result)
        
        return jsonify({
            'success': True,
            'heatmap': heatmap,
            'details': details,
            'method': method
        })
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/visualize/histogram/<column>')
def visualize_histogram(column):
    """获取直方图数据"""
    try:
        session_id = session.get('id')
        if not session_id:
            return jsonify({'error': '数据不完整'}), 400
        
        df, _ = load_data(session_id)
        if df is None:
            return jsonify({'error': '数据加载失败'}), 400
        
        data = Visualizer.prepare_histogram_data(df, column)
        
        return jsonify({'success': True, 'data': data})
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/visualize/boxplot/<column>')
def visualize_boxplot(column):
    """获取箱线图数据"""
    try:
        session_id = session.get('id')
        if not session_id:
            return jsonify({'error': '数据不完整'}), 400
        
        df, _ = load_data(session_id)
        if df is None:
            return jsonify({'error': '数据加载失败'}), 400
        
        group_var = request.args.get('group_var')
        
        data = Visualizer.prepare_boxplot_data(df, column, group_var=group_var)
        
        return jsonify({'success': True, 'data': data})
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/visualize/scatter')
def visualize_scatter():
    """获取散点图数据"""
    try:
        session_id = session.get('id')
        if not session_id:
            return jsonify({'error': '数据不完整'}), 400
        
        df, _ = load_data(session_id)
        if df is None:
            return jsonify({'error': '数据加载失败'}), 400
        
        x = request.args.get('x')
        y = request.args.get('y')
        
        if not x or not y:
            return jsonify({'error': '没有指定x和y变量'}), 400
        
        data = Visualizer.prepare_scatterplot_data(df, x, y)
        
        return jsonify({'success': True, 'data': data})
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/export/all', methods=['POST'])
def export_all():
    """导出所有分析结果"""
    try:
        session_id = session.get('id')
        if not session_id:
            return jsonify({'error': '数据不完整'}), 400
        
        # 准备会话数据
        session_data = {
            'id': session_id,
            'tableone': load_result(session_id, 'tableone'),
            'group_analysis': load_result(session_id, 'group_analysis'),
            'correlation_analysis': load_result(session_id, 'correlation_analysis'),
            'missing_analysis': load_result(session_id, 'missing_analysis'),
            'outlier_detection': load_result(session_id, 'outlier_detection'),
            'distribution_diagnostics': load_result(session_id, 'distribution_diagnostics'),
            'imputation_comparison': load_result(session_id, 'imputation_comparison')
        }
        
        format = request.json.get('format', 'zip')

        sheets_dict = Exporter.prepare_export_package(session_data)

        if format == 'zip':
            output = Exporter.export_to_zip(sheets_dict)
            filename = f"medstat_results_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.zip"
            return send_file(
                output,
                mimetype='application/zip',
                as_attachment=True,
                download_name=filename
            )
        else:
            output = Exporter.export_multiple_sheets(sheets_dict, format=format)
            filename = f"medstat_results_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=filename
            )
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/export/data', methods=['POST'])
def export_data():
    """导出原始数据或插补后的数据"""
    try:
        session_id = session.get('id')
        if not session_id:
            return jsonify({'error': '数据不完整'}), 400
        
        # 修复：处理Content-Type不正确的情况
        request_data = request.json if request.json else {}
        format = request_data.get('format', 'csv')
        use_imputed = request_data.get('use_imputed', False)
        imputation_index = request_data.get('imputation_index', 0)
        
        if use_imputed:
            session_dir = get_session_dir(session_id)
            ds_path = os.path.join(session_dir, f'imputed_{imputation_index}.pkl')
            if os.path.exists(ds_path):
                df = pd.read_pickle(ds_path)
            else:
                df, _ = load_data(session_id)
        else:
            df, _ = load_data(session_id)
        
        if df is None:
            return jsonify({'error': '数据加载失败'}), 400
        
        output = Exporter.export_dataframe(df, format=format)
        
        if format == 'csv':
            mimetype = 'text/csv'
            filename = f"data_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv"
        else:
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            filename = f"data_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        return send_file(
            output,
            mimetype=mimetype,
            as_attachment=True,
            download_name=filename
        )
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/apply-mice-dataset', methods=['POST'])
def apply_mice_dataset():
    """应用选定的MICE插补数据集"""
    try:
        session_id = session.get('id')
        if not session_id:
            return jsonify({'error': '没有可用的插补数据集'}), 400
        
        # 修复：处理Content-Type不正确的情况
        request_data = request.json if request.json else {}
        dataset_index = request_data.get('dataset_index', 0)
        
        session_dir = get_session_dir(session_id)
        ds_path = os.path.join(session_dir, f'imputed_{dataset_index}.pkl')
        
        if not os.path.exists(ds_path):
            return jsonify({'error': '无效的数据集索引'}), 400
        
        df = pd.read_pickle(ds_path)
        
        # 重新保存数据
        _, var_types = load_data(session_id)
        save_data(session_id, df, var_types)
        
        # 转换为前端期望的格式：对象数组
        data_list = df.where(pd.notnull(df), None).to_dict(orient='records')
        
        return jsonify({
            'success': True,
            'data': data_list,
            'row_count': len(df),
            'column_count': len(df.columns),
            'message': '插补数据已成功应用'
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/stratified-analysis', methods=['POST'])
def stratified_analysis():
    """Mantel-Haenszel分层分析"""
    try:
        session_id = session.get('id')
        if not session_id:
            return jsonify({'error': '没有上传数据'}), 400

        df, var_types = load_data(session_id)
        if df is None or var_types is None:
            return jsonify({'error': '数据加载失败'}), 400

        # 修复：处理Content-Type不正确的情况
        request_data = request.json if request.json else {}
        group_var = request_data.get('group_var')
        outcome_var = request_data.get('outcome_var')
        strata_var = request_data.get('strata_var')

        if not all([group_var, outcome_var, strata_var]):
            return jsonify({'error': '缺少必要参数'}), 400

        result = MantelHaenszelTest.test(df, group_var, outcome_var, strata_var)
        result['forest_plot'] = MantelHaenszelTest.generate_forest_plot_data(
            result['strata'], 
            result['pooled_or'], 
            result['pooled_or_ci']
        )

        save_result(session_id, 'stratified_analysis', result)

        return jsonify({'success': True, **result})

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/sensitivity-analysis', methods=['POST'])
def sensitivity_analysis():
    """敏感性分析"""
    try:
        session_id = session.get('id')
        if not session_id:
            return jsonify({'error': '没有上传数据'}), 400

        df, var_types = load_data(session_id)
        if df is None or var_types is None:
            return jsonify({'error': '数据加载失败'}), 400

        # 修复：处理Content-Type不正确的情况
        request_data = request.json if request.json else {}
        outcome_var = request_data.get('outcome_var')
        group_var = request_data.get('group_var')
        missing_col = request_data.get('missing_col')

        if not all([outcome_var, group_var]):
            return jsonify({'error': '缺少必要参数'}), 400

        scenarios = SensitivityAnalyzer.extreme_case_analysis(
            df, outcome_var, group_var, missing_col
        )
        tipping = SensitivityAnalyzer.tipping_point_analysis(
            df, outcome_var, group_var, missing_col
        )

        result = {
            'scenarios': scenarios,
            'tipping_point': tipping,
            'sensitivity_plot': SensitivityAnalyzer.generate_sensitivity_plot(scenarios)
        }

        save_result(session_id, 'sensitivity_analysis', result)

        return jsonify({'success': True, **result})

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/interaction-analysis', methods=['POST'])
def interaction_analysis():
    """交互作用分析"""
    try:
        session_id = session.get('id')
        if not session_id:
            return jsonify({'error': '没有上传数据'}), 400

        df, var_types = load_data(session_id)
        if df is None or var_types is None:
            return jsonify({'error': '数据加载失败'}), 400

        # 修复：处理Content-Type不正确的情况
        request_data = request.json if request.json else {}
        var1 = request_data.get('var1')
        var2 = request_data.get('var2')
        outcome_var = request_data.get('outcome_var')
        model_type = request_data.get('model_type', 'logistic')

        if not all([var1, var2, outcome_var]):
            return jsonify({'error': '缺少必要参数'}), 400

        result = InteractionAnalyzer.analyze(df, var1, var2, outcome_var, model_type)
        
        if 'error' not in result:
            result['interaction_plot'] = InteractionAnalyzer.generate_interaction_plot(
                df, var1, var2, outcome_var
            )

        save_result(session_id, 'interaction_analysis', result)

        return jsonify({'success': True, **result})

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/categorical-test', methods=['POST'])
def categorical_test():
    """分类变量统计检验"""
    try:
        session_id = session.get('id')
        if not session_id:
            return jsonify({'error': '没有上传数据'}), 400

        df, var_types = load_data(session_id)
        if df is None or var_types is None:
            return jsonify({'error': '数据加载失败'}), 400

        # 修复：处理Content-Type不正确的情况
        request_data = request.json if request.json else {}
        var_name = request_data.get('var_name')
        group_var = request_data.get('group_var')
        method = request_data.get('method', 'auto')

        if not all([var_name, group_var]):
            return jsonify({'error': '缺少必要参数'}), 400

        # 构建列联表
        contingency_table = pd.crosstab(df[group_var], df[var_name])

        result = CategoricalTestSelector.select_test(contingency_table.values, method)
        result['contingency_table'] = contingency_table.values.tolist()
        result['row_labels'] = contingency_table.index.tolist()
        result['col_labels'] = contingency_table.columns.tolist()

        save_result(session_id, 'categorical_test', result)

        return jsonify({'success': True, **result})

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/trend-test', methods=['POST'])
def trend_test():
    """Cochran-Armitage趋势检验"""
    try:
        session_id = session.get('id')
        if not session_id:
            return jsonify({'error': '没有上传数据'}), 400

        df, var_types = load_data(session_id)
        if df is None or var_types is None:
            return jsonify({'error': '数据加载失败'}), 400

        # 修复：处理Content-Type不正确的情况
        request_data = request.json if request.json else {}
        group_var = request_data.get('group_var')
        outcome_var = request_data.get('outcome_var')
        order = request_data.get('order', None)

        if not all([group_var, outcome_var]):
            return jsonify({'error': '缺少必要参数'}), 400

        # 构建列联表
        contingency_table = pd.crosstab(df[group_var], df[outcome_var])
        group_labels = contingency_table.index.tolist()

        result = CochranArmitageTest.test(group_labels, contingency_table.values, order)

        save_result(session_id, 'trend_test', result)

        return jsonify({'success': True, **result})

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/model-evaluation', methods=['POST'])
def model_evaluation():
    """预测模型评估"""
    print("\n" + "="*60)
    print("【模型评估API】收到请求")
    print("="*60)
    try:
        session_id = session.get('id')
        print(f"Session ID: {session_id}")
        
        if not session_id:
            print("错误：没有上传数据")
            return jsonify({'error': '没有上传数据'}), 400

        df, var_types = load_data(session_id)
        print(f"数据加载: df={df is not None}, var_types={var_types is not None}")
        
        if df is None or var_types is None:
            print("错误：数据加载失败")
            return jsonify({'error': '数据加载失败'}), 400

        # 修复：处理Content-Type不正确的情况
        request_data = request.json if request.json else {}
        print(f"请求数据: {request_data}")
        
        outcome_var = request_data.get('outcome_var')
        prediction_var = request_data.get('prediction_var')
        threshold = request_data.get('threshold', 0.5)
        old_prediction_var = request_data.get('old_prediction_var')

        print(f"outcome_var: {outcome_var}")
        print(f"prediction_var: {prediction_var}")
        print(f"threshold: {threshold}")
        print(f"old_prediction_var: {old_prediction_var}")

        # 验证参数
        if not outcome_var or not prediction_var:
            print("错误：缺少必要参数")
            return jsonify({'error': '缺少必要参数：outcome_var 和 prediction_var'}), 400

        if outcome_var not in df.columns:
            print(f"错误：结果变量不存在 - {outcome_var}")
            return jsonify({'error': f'结果变量 {outcome_var} 不存在'}), 400

        if prediction_var not in df.columns:
            print(f"错误：预测变量不存在 - {prediction_var}")
            return jsonify({'error': f'预测变量 {prediction_var} 不存在'}), 400
        
        # 获取数据
        y_true = df[outcome_var].values
        y_scores = df[prediction_var].values
        print(f"y_true shape: {y_true.shape}, unique values: {np.unique(y_true)}")
        print(f"y_scores shape: {y_scores.shape}, unique values: {np.unique(y_scores)[:10]}...")
        
        # 验证：结果变量必须是二进制或可以转换为二进制
        unique_outcome = np.unique(y_true)
        if len(unique_outcome) != 2:
            print(f"错误：结果变量必须是二分类变量，当前有 {len(unique_outcome)} 个类别")
            return jsonify({'error': f'结果变量必须是二分类变量（只有两个类别），当前变量 {outcome_var} 有 {len(unique_outcome)} 个类别'}), 400
        
        # 将结果变量转换为0/1
        y_true_binary = (y_true == unique_outcome[1]).astype(int)
        print(f"转换后的y_true: {np.unique(y_true_binary)}")
        
        # 检查预测变量是否为概率值或分类结果
        unique_scores = np.unique(y_scores)
        is_prob_like = len(unique_scores) > 2 or (np.min(y_scores) >= 0 and np.max(y_scores) <= 1)
        
        if not is_prob_like and not np.all(np.isin(unique_scores, [0, 1])):
            print(f"错误：预测变量必须是概率值或二进制分类结果")
            return jsonify({'error': '预测变量必须是概率值（0-1之间）或二进制分类结果（0/1）'}), 400

        # 检查是否需要比较
        if old_prediction_var and old_prediction_var in df.columns:
            old_probs = df[old_prediction_var].values
            print("执行模型比较...")
            results = compare_models(y_true_binary, y_scores, old_probs, threshold)
        else:
            print("执行单模型评估...")
            results = evaluate_model(y_true_binary, y_scores, None, threshold)

        print(f"评估结果键: {results.keys() if isinstance(results, dict) else 'N/A'}")
        print("评估完成，返回成功")
        
        save_result(session_id, 'model_evaluation', results)

        return jsonify({'success': True, 'results': results})

    except Exception as e:
        print(f"错误异常: {type(e).__name__}: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/regression/ols', methods=['POST'])
def regression_ols():
    """OLS线性回归分析"""
    print("\n" + "="*60)
    print("【OLS回归API】收到请求")
    print("="*60)
    try:
        session_id = session.get('id')
        if not session_id:
            return jsonify({'error': '没有上传数据'}), 400

        df, var_types = load_data(session_id)
        if df is None or var_types is None:
            return jsonify({'error': '数据加载失败'}), 400

        request_data = request.json if request.json else {}
        print(f"请求数据: {request_data}")

        formula = request_data.get('formula')
        y_var = request_data.get('y_var')
        X_vars = request_data.get('X_vars', [])
        add_constant = request_data.get('add_constant', True)

        print(f"formula: {formula}, y_var: {y_var}, X_vars: {X_vars}")

        analyzer = LinearRegressionAnalyzer(df, var_types)

        if formula:
            results = analyzer.fit_ols(formula=formula)
        elif y_var and X_vars:
            results = analyzer.fit_ols(y_var=y_var, X_vars=X_vars, add_constant=add_constant)
        else:
            return jsonify({'error': '需要提供formula或(y_var, X_vars)'}), 400

        print(f"OLS回归完成: success={results.get('success')}")

        if results.get('success'):
            save_result(session_id, 'ols_regression', results)

        return jsonify(results)

    except Exception as e:
        print(f"OLS回归异常: {type(e).__name__}: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/regression/logit', methods=['POST'])
def regression_logit():
    """Logistic回归分析"""
    print("\n" + "="*60)
    print("【Logistic回归API】收到请求")
    print("="*60)
    try:
        session_id = session.get('id')
        if not session_id:
            return jsonify({'error': '没有上传数据'}), 400

        df, var_types = load_data(session_id)
        if df is None or var_types is None:
            return jsonify({'error': '数据加载失败'}), 400

        request_data = request.json if request.json else {}
        print(f"请求数据: {request_data}")

        formula = request_data.get('formula')
        y_var = request_data.get('y_var')
        X_vars = request_data.get('X_vars', [])
        add_constant = request_data.get('add_constant', True)

        print(f"formula: {formula}, y_var: {y_var}, X_vars: {X_vars}")

        analyzer = LogisticRegressionAnalyzer(df, var_types)

        if formula:
            results = analyzer.fit_logit(formula=formula)
        elif y_var and X_vars:
            results = analyzer.fit_logit(y_var=y_var, X_vars=X_vars, add_constant=add_constant)
        else:
            return jsonify({'error': '需要提供formula或(y_var, X_vars)'}), 400

        print(f"Logistic回归完成: success={results.get('success')}")

        if results.get('success'):
            save_result(session_id, 'logit_regression', results)

        return jsonify(results)

    except Exception as e:
        print(f"Logistic回归异常: {type(e).__name__}: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/regression/glm', methods=['POST'])
def regression_glm():
    """GLM广义线性回归"""
    print("\n" + "="*60)
    print("【GLM回归API】收到请求")
    print("="*60)
    try:
        session_id = session.get('id')
        if not session_id:
            return jsonify({'error': '没有上传数据'}), 400

        df, var_types = load_data(session_id)
        if df is None or var_types is None:
            return jsonify({'error': '数据加载失败'}), 400

        request_data = request.json if request.json else {}
        print(f"请求数据: {request_data}")

        glm_type = request_data.get('type', 'poisson')
        formula = request_data.get('formula')
        y_var = request_data.get('y_var')
        X_vars = request_data.get('X_vars', [])

        print(f"glm_type: {glm_type}, formula: {formula}")

        analyzer = GLMAnalyzer(df, var_types)

        if glm_type == 'poisson':
            if formula:
                results = analyzer.fit_poisson(formula=formula)
            elif y_var and X_vars:
                results = analyzer.fit_poisson(y_var=y_var, X_vars=X_vars)
            else:
                return jsonify({'error': '需要提供formula或(y_var, X_vars)'}), 400
        elif glm_type == 'gamma':
            if formula:
                results = analyzer.fit_gamma(formula=formula)
            elif y_var and X_vars:
                results = analyzer.fit_gamma(y_var=y_var, X_vars=X_vars)
            else:
                return jsonify({'error': '需要提供formula或(y_var, X_vars)'}), 400
        else:
            return jsonify({'error': f'不支持的GLM类型: {glm_type}'}), 400

        print(f"GLM回归完成: success={results.get('success')}")

        if results.get('success'):
            save_result(session_id, f'{glm_type}_glm', results)

        return jsonify(results)

    except Exception as e:
        print(f"GLM回归异常: {type(e).__name__}: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/regression/diagnostics', methods=['POST'])
def regression_diagnostics():
    """回归诊断"""
    print("\n" + "="*60)
    print("【回归诊断API】收到请求")
    print("="*60)
    try:
        session_id = session.get('id')
        if not session_id:
            return jsonify({'error': '没有上传数据'}), 400

        ols_result = load_result(session_id, 'ols_regression')
        print(f"OLS结果加载: {ols_result is not None}")

        if not ols_result:
            return jsonify({'error': '请先运行OLS回归分析'}), 400

        residuals = np.array(ols_result.get('residuals', []))
        fitted = np.array(ols_result.get('fittedvalues', []))

        if len(residuals) == 0 or len(fitted) == 0:
            return jsonify({'error': '回归结果数据不完整'}), 400

        diagnostics = RegressionDiagnostics(residuals, fitted)

        request_data = request.json if request.json else {}
        test_type = request_data.get('test_type', 'all')

        if test_type == 'normality' or test_type == 'all':
            normality = diagnostics.normality_tests()
        else:
            normality = None

        if test_type == 'heteroskedasticity' or test_type == 'all':
            heteroskedasticity = diagnostics.heteroskedasticity_tests()
        else:
            heteroskedasticity = None

        if test_type == 'autocorrelation' or test_type == 'all':
            autocorrelation = diagnostics.autocorrelation_tests()
        else:
            autocorrelation = None

        if test_type == 'plots':
            plots = diagnostics.residual_plots()
        else:
            plots = None

        results = {
            'success': True,
            'normality': normality,
            'heteroskedasticity': heteroskedasticity,
            'autocorrelation': autocorrelation,
            'plots': plots
        }

        print(f"诊断完成")
        return jsonify(results)

    except Exception as e:
        print(f"回归诊断异常: {type(e).__name__}: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats/normality', methods=['POST'])
def stats_normality():
    """正态性检验"""
    print("\n" + "="*60)
    print("【正态性检验API】收到请求")
    print("="*60)
    try:
        session_id = session.get('id')
        if not session_id:
            return jsonify({'error': '没有上传数据'}), 400

        df, var_types = load_data(session_id)
        if df is None:
            return jsonify({'error': '数据加载失败'}), 400

        request_data = request.json if request.json else {}
        variable = request_data.get('variable')
        test_all = request_data.get('test_all', False)

        if test_all:
            results = {}
            for col in df.columns:
                if var_types.get(col) in ['continuous', 'count']:
                    data = df[col].dropna().values
                    if len(data) >= 3:
                        results[col] = NormalityTests.all_tests(data)
            return jsonify({'success': True, 'results': results})
        elif variable:
            if variable not in df.columns:
                return jsonify({'error': f'变量 {variable} 不存在'}), 400
            data = df[variable].dropna().values
            if len(data) < 3:
                return jsonify({'error': '样本量至少需要3个'}), 400
            results = NormalityTests.all_tests(data)
            return jsonify({'success': True, 'variable': variable, 'results': results})
        else:
            return jsonify({'error': '需要提供variable或设置test_all=true'}), 400

    except Exception as e:
        print(f"正态性检验异常: {type(e).__name__}: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats/ttest', methods=['POST'])
def stats_ttest():
    """t检验"""
    print("\n" + "="*60)
    print("【t检验API】收到请求")
    print("="*60)
    try:
        session_id = session.get('id')
        if not session_id:
            return jsonify({'error': '没有上传数据'}), 400

        df, var_types = load_data(session_id)
        if df is None:
            return jsonify({'error': '数据加载失败'}), 400

        request_data = request.json if request.json else {}
        test_type = request_data.get('type', 'independent')
        group1_var = request_data.get('group1')
        group2_var = request_data.get('group2')
        continuous_var = request_data.get('continuous_var')
        pop_mean = request_data.get('pop_mean')

        if test_type == 'independent':
            if not group1_var or not group2_var or not continuous_var:
                return jsonify({'error': '需要提供group1, group2和continuous_var'}), 400

            group1_data = df[continuous_var][df[group1_var] == 1].dropna().values
            group2_data = df[continuous_var][df[group2_var] == 1].dropna().values

            if len(group1_data) < 2 or len(group2_data) < 2:
                return jsonify({'error': '每组样本量至少需要2个'}), 400

            results = MeanComparisonTests.ttest_independent(group1_data, group2_data)

        elif test_type == 'paired':
            if not group1_var or not group2_var:
                return jsonify({'error': '需要提供group1和group2'}), 400

            paired1 = df[group1_var].dropna().values
            paired2 = df[group2_var].dropna().values

            min_len = min(len(paired1), len(paired2))
            if min_len < 3:
                return jsonify({'error': '配对样本量至少需要3对'}), 400

            results = MeanComparisonTests.ttest_paired(paired1[:min_len], paired2[:min_len])

        elif test_type == 'one_sample':
            if not continuous_var or pop_mean is None:
                return jsonify({'error': '需要提供continuous_var和pop_mean'}), 400

            data = df[continuous_var].dropna().values
            if len(data) < 3:
                return jsonify({'error': '样本量至少需要3个'}), 400

            results = MeanComparisonTests.ttest_one_sample(data, pop_mean)

        else:
            return jsonify({'error': f'不支持的检验类型: {test_type}'}), 400

        return jsonify({'success': True, 'test_type': test_type, 'results': results})

    except Exception as e:
        print(f"t检验异常: {type(e).__name__}: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats/anova', methods=['POST'])
def stats_anova():
    """方差分析"""
    print("\n" + "="*60)
    print("【方差分析API】收到请求")
    print("="*60)
    try:
        session_id = session.get('id')
        if not session_id:
            return jsonify({'error': '没有上传数据'}), 400

        df, var_types = load_data(session_id)
        if df is None:
            return jsonify({'error': '数据加载失败'}), 400

        request_data = request.json if request.json else {}
        continuous_var = request_data.get('continuous_var')
        group_var = request_data.get('group_var')
        parametric = request_data.get('parametric', True)

        if not continuous_var or not group_var:
            return jsonify({'error': '需要提供continuous_var和group_var'}), 400

        groups = df[group_var].unique()
        group_data_list = [df[continuous_var][df[group_var] == g].dropna().values for g in groups]

        if len(group_data_list) < 2:
            return jsonify({'error': '分组至少需要2组'}), 400

        for i, gd in enumerate(group_data_list):
            if len(gd) < 2:
                return jsonify({'error': f'组{i+1}样本量至少需要2个'}), 400

        if parametric:
            results = MeanComparisonTests.anova_one_way(*group_data_list)
        else:
            results = MeanComparisonTests.kruskal_wallis(*group_data_list)

        results['groups'] = [{'name': str(g), 'n': len(gd)} for g, gd in zip(groups, group_data_list)]

        return jsonify({'success': True, 'results': results})

    except Exception as e:
        print(f"方差分析异常: {type(e).__name__}: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats/correlation', methods=['POST'])
def stats_correlation():
    """相关性分析"""
    print("\n" + "="*60)
    print("【相关性分析API】收到请求")
    print("="*60)
    try:
        session_id = session.get('id')
        if not session_id:
            return jsonify({'error': '没有上传数据'}), 400

        df, var_types = load_data(session_id)
        if df is None:
            return jsonify({'error': '数据加载失败'}), 400

        request_data = request.json if request.json else {}
        var1 = request_data.get('var1')
        var2 = request_data.get('var2')
        method = request_data.get('method', 'pearson')
        matrix = request_data.get('matrix', False)

        if matrix:
            numeric_cols = [c for c in df.columns if var_types.get(c) in ['continuous', 'count']]
            if len(numeric_cols) < 2:
                return jsonify({'error': '需要至少2个数值变量'}), 400

            corr_data = df[numeric_cols]
            if method == 'spearman':
                results = CorrelationTests.correlation_matrix(corr_data, method='spearman')
            else:
                results = CorrelationTests.correlation_matrix(corr_data, method='pearson')
            return jsonify({'success': True, 'results': results})

        elif var1 and var2:
            if var1 not in df.columns or var2 not in df.columns:
                return jsonify({'error': '变量不存在'}), 400

            data1 = df[var1].dropna().values
            data2 = df[var2].dropna().values

            min_len = min(len(data1), len(data2))
            if min_len < 3:
                return jsonify({'error': '有效样本量至少需要3对'}), 400

            if method == 'spearman':
                results = CorrelationTests.spearman_correlation(data1[:min_len], data2[:min_len])
            else:
                results = CorrelationTests.pearson_correlation(data1[:min_len], data2[:min_len])

            return jsonify({'success': True, 'var1': var1, 'var2': var2, 'method': method, 'results': results})

        else:
            return jsonify({'error': '需要提供(var1, var2)或设置matrix=true'}), 400

    except Exception as e:
        print(f"相关性分析异常: {type(e).__name__}: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats/proportion', methods=['POST'])
def stats_proportion():
    """比例检验"""
    print("\n" + "="*60)
    print("【比例检验API】收到请求")
    print("="*60)
    try:
        request_data = request.json if request.json else {}
        test_type = request_data.get('type', 'binom')

        if test_type == 'binom':
            n_success = request_data.get('n_success')
            n_trials = request_data.get('n_trials')
            p0 = request_data.get('p0', 0.5)

            if n_success is None or n_trials is None:
                return jsonify({'error': '需要提供n_success和n_trials'}), 400

            results = ProportionTests.binom_test_successes(n_success, n_trials, p0)
            return jsonify({'success': True, 'test_type': test_type, 'results': results})

        elif test_type == 'chi2':
            contingency = request_data.get('contingency_table')
            if not contingency:
                return jsonify({'error': '需要提供contingency_table'}), 400

            table = np.array(contingency)
            results = ProportionTests.chi_square_test(table)
            return jsonify({'success': True, 'test_type': test_type, 'results': results})

        elif test_type == 'fisher':
            table = request_data.get('table')
            if not table:
                return jsonify({'error': '需要提供table'}), 400

            table_arr = np.array(table)
            results = ProportionTests.fisher_exact_test(table_arr)
            return jsonify({'success': True, 'test_type': test_type, 'results': results})

        else:
            return jsonify({'error': f'不支持的检验类型: {test_type}'}), 400

    except Exception as e:
        print(f"比例检验异常: {type(e).__name__}: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats/multiple-comparison', methods=['POST'])
def stats_multiple_comparison():
    """多重比较校正"""
    print("\n" + "="*60)
    print("【多重比较校正API】收到请求")
    print("="*60)
    try:
        request_data = request.json if request.json else {}
        method = request_data.get('method', 'bonferroni')
        p_values = request_data.get('p_values', [])
        alpha = request_data.get('alpha', 0.05)

        if not p_values:
            return jsonify({'error': '需要提供p_values列表'}), 400

        if method == 'bonferroni':
            results = MultipleComparisons.bonferroni_correction(p_values, alpha)
        elif method == 'fdr':
            results = MultipleComparisons.false_discovery_rate(p_values, alpha)
        elif method == 'tukey':
            return jsonify({'error': 'Tukey HSD需要使用/api/stats/anova端点'}), 400
        else:
            return jsonify({'error': f'不支持的校正方法: {method}'}), 400

        return jsonify({'success': True, 'method': method, 'results': results})

    except Exception as e:
        print(f"多重比较校正异常: {type(e).__name__}: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats/effect-size', methods=['POST'])
def stats_effect_size():
    """效应量计算"""
    print("\n" + "="*60)
    print("【效应量计算API】收到请求")
    print("="*60)
    try:
        session_id = session.get('id')
        request_data = request.json if request.json else {}
        calc_type = request_data.get('type')

        if calc_type == 'cohens_d':
            if not session_id:
                return jsonify({'error': '没有上传数据'}), 400

            df, var_types = load_data(session_id)
            if df is None:
                return jsonify({'error': '数据加载失败'}), 400

            group1_var = request_data.get('group1')
            group2_var = request_data.get('group2')
            continuous_var = request_data.get('continuous_var')

            if not all([group1_var, group2_var, continuous_var]):
                return jsonify({'error': '需要提供group1, group2和continuous_var'}), 400

            group1_data = df[continuous_var][df[group1_var] == 1].dropna().values
            group2_data = df[continuous_var][df[group2_var] == 1].dropna().values

            d = EffectSizeCalculator.cohens_d(group1_data, group2_data)

            return jsonify({
                'success': True,
                'type': 'cohens_d',
                'cohens_d': float(d),
                'interpretation': '小效应量' if abs(d) < 0.5 else ('中等效应量' if abs(d) < 0.8 else '大效应量')
            })

        elif calc_type == 'eta_squared':
            f_stat = request_data.get('f_stat')
            df_between = request_data.get('df_between')
            df_within = request_data.get('df_within')

            if f_stat is None or df_between is None or df_within is None:
                return jsonify({'error': '需要提供f_stat, df_between, df_within'}), 400

            eta_sq = EffectSizeCalculator.eta_squared(f_stat, df_between, df_within)

            return jsonify({
                'success': True,
                'type': 'eta_squared',
                'eta_squared': float(eta_sq),
                'interpretation': '小效应量' if eta_sq < 0.06 else ('中等效应量' if eta_sq < 0.14 else '大效应量')
            })

        else:
            return jsonify({'error': f'不支持的计算类型: {calc_type}'}), 400

    except Exception as e:
        print(f"效应量计算异常: {type(e).__name__}: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.errorhandler(404)
def not_found(error):
    """处理404错误 - 对于JS/CSS/WASM文件请求返回正确的MIME类型"""
    path = request.path
    print(f"【404错误】路径: {path}, 来源: {request.referrer}, User-Agent: {request.user_agent}")
    
    if path.endswith('.js') or path.endswith('.mjs') or '@vite/client' in path:
        return "console.error('Resource not found: " + path + "');", 404, {'Content-Type': 'application/javascript'}
    elif path.endswith('.css'):
        return "", 404, {'Content-Type': 'text/css'}
    elif path.endswith('.wasm'):
        return "", 404, {'Content-Type': 'application/wasm'}
    else:
        return render_template('index.html')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5558))
    debug = os.environ.get('FLASK_DEBUG', 'False') == 'True'
    app.run(host='0.0.0.0', port=port, debug=debug)
