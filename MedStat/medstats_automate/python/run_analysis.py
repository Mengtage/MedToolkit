#!/usr/bin/env python3
# ============================================
# MedStats-Automate 完整分析运行脚本
# 医学统计分析自动化系统
#
# 使用方法:
# python run_analysis.py --data <数据文件> --strata <分组变量> --missing <缺失值标记>
#
# 示例:
# python run_analysis.py --data dataset.csv --strata Group --missing 12345
#
# 作者: MedStats Team
# ============================================

import argparse
import os
import sys
import time
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_import import import_data, auto_detect_types, preview_data
from quality_control import quality_control
from mice_imputation import mice_imputation
from tableone import generate_tableone
from effect_size import calculate_effect_size
from export_results import export_results
from visualization import visualization_report
from roc_analysis import roc_analysis


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='医学统计分析自动化程序',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python run_analysis.py --data dataset.csv --strata Group --missing 12345
  python run_analysis.py --data data.xlsx --strata Treatment --missing -999
  python run_analysis.py --data data.csv --strata Group --missing 12345,999 --output results
        """
    )
    
    parser.add_argument('--data', type=str, required=True,
                       help='数据文件路径')
    parser.add_argument('--strata', type=str, default=None,
                       help='分组变量名（例如：Group, Treatment）')
    parser.add_argument('--missing', type=str, default='12345',
                       help='缺失值标记，多个值用逗号分隔（默认: 12345）')
    parser.add_argument('--output', type=str, default='./analysis_output',
                       help='输出目录（默认: ./analysis_output）')
    parser.add_argument('--encoding', type=str, default='UTF-8',
                       help='文件编码（默认: UTF-8）')
    parser.add_argument('--impute', action='store_true',
                       help='执行MICE多重插补')
    parser.add_argument('--impute_m', type=int, default=5,
                       help='MICE插补数据集数量（默认: 5）')
    parser.add_argument('--impute_vars', type=str, default=None,
                       help='需要插补的变量（逗号分隔，默认: 自动选择）')
    parser.add_argument('--effect_vars', type=str, default=None,
                       help='效应量计算变量（逗号分隔，默认: 所有数值变量）')
    parser.add_argument('--roc_predictor', type=str, default=None,
                       help='ROC分析预测变量')
    parser.add_argument('--roc_outcome', type=str, default=None,
                       help='ROC分析结局变量')
    parser.add_argument('--visualize', action='store_true',
                       help='生成可视化报告')
    parser.add_argument('--verbose', action='store_true', default=True,
                       help='详细输出')
    
    return parser.parse_args()


def parse_missing_values(missing_str):
    """解析缺失值字符串"""
    if missing_str is None:
        return [12345]  # 默认值
    
    values = []
    for val in missing_str.split(','):
        val = val.strip()
        try:
            # 尝试转换为数值
            if '.' in val:
                values.append(float(val))
            else:
                values.append(int(val))
        except ValueError:
            # 如果不是数值，保留为字符串
            values.append(val)
    
    return values


def run_full_analysis(args):
    """运行完整分析流程"""
    
    print("\n" + "="*70)
    print("MedStats-Automate 医学统计分析自动化系统")
    print("="*70)
    print(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"数据文件: {args.data}")
    print(f"分组变量: {args.strata}")
    print(f"缺失值标记: {args.missing}")
    print("="*70 + "\n")
    
    # 创建输出目录
    os.makedirs(args.output, exist_ok=True)
    
    # 解析缺失值
    missing_values = parse_missing_values(args.missing)
    print(f"将识别以下值为缺失值: {missing_values}\n")
    
    # ============================================
    # 步骤 1: 数据导入
    # ============================================
    print("\n" + "="*70)
    print("[步骤 1/7] 数据导入")
    print("="*70)
    
    start_time = time.time()
    try:
        data = import_data(args.data, encoding=args.encoding, na_values=missing_values)
        data_import_time = time.time() - start_time
        print(f"\n✓ 数据导入成功! 耗时: {data_import_time:.2f}秒")
    except Exception as e:
        print(f"\n✗ 数据导入失败: {e}")
        return None
    
    # 数据预览
    if args.verbose:
        preview_data(data)
    
    # ============================================
    # 步骤 2: 数据质量控制
    # ============================================
    print("\n" + "="*70)
    print("[步骤 2/7] 数据质量控制")
    print("="*70)
    
    start_time = time.time()
    qc_results = quality_control(data, verbose=args.verbose)
    qc_time = time.time() - start_time
    print(f"\n✓ 质量控制完成! 耗时: {qc_time:.2f}秒")
    
    # 统计缺失值情况
    total_missing = qc_results['missing']['total_missing']
    missing_rate = total_missing / (data.shape[0] * data.shape[1]) * 100
    print(f"  总缺失值: {total_missing} ({missing_rate:.2f}%)")
    
    # ============================================
    # 步骤 3: MICE多重插补（可选）
    # ============================================
    imputed_data = None
    if args.impute:
        print("\n" + "="*70)
        print("[步骤 3/7] MICE多重插补")
        print("="*70)
        
        # 确定需要插补的变量
        impute_vars = None
        if args.impute_vars:
            impute_vars = [v.strip() for v in args.impute_vars.split(',')]
        
        start_time = time.time()
        impute_results = mice_imputation(
            data,
            vars=impute_vars,
            m=args.impute_m,
            verbose=args.verbose
        )
        imputed_data = impute_results['data']
        mice_time = time.time() - start_time
        print(f"\n✓ MICE插补完成! 耗时: {mice_time:.2f}秒")
    else:
        print("\n" + "="*70)
        print("[步骤 3/7] MICE多重插补 - 跳过（使用 --impute 启用）")
        print("="*70)
    
    # 使用原始数据或插补后数据
    analysis_data = imputed_data if imputed_data is not None else data
    
    # ============================================
    # 步骤 4: TableOne基线资料表
    # ============================================
    print("\n" + "="*70)
    print("[步骤 4/7] TableOne基线资料表生成")
    print("="*70)
    
    start_time = time.time()
    tableone_results = generate_tableone(
        analysis_data,
        strata=args.strata,
        verbose=args.verbose
    )
    tableone_time = time.time() - start_time
    print(f"\n✓ TableOne生成完成! 耗时: {tableone_time:.2f}秒")
    
    # ============================================
    # 步骤 5: 效应量计算
    # ============================================
    print("\n" + "="*70)
    print("[步骤 5/7] 效应量计算")
    print("="*70)
    
    effect_vars = None
    if args.effect_vars:
        effect_vars = [v.strip() for v in args.effect_vars.split(',')]
    
    start_time = time.time()
    effect_size_results = calculate_effect_size(
        analysis_data,
        vars=effect_vars,
        strata=args.strata,
        verbose=args.verbose
    )
    effect_time = time.time() - start_time
    print(f"\n✓ 效应量计算完成! 耗时: {effect_time:.2f}秒")
    
    # ============================================
    # 步骤 6: ROC分析（可选）
    # ============================================
    roc_results = None
    if args.roc_predictor and args.roc_outcome:
        print("\n" + "="*70)
        print("[步骤 6/7] ROC曲线分析")
        print("="*70)
        
        start_time = time.time()
        roc_results = roc_analysis(
            analysis_data,
            predictor=args.roc_predictor,
            outcome=args.roc_outcome,
            verbose=args.verbose
        )
        roc_time = time.time() - start_time
        print(f"\n✓ ROC分析完成! 耗时: {roc_time:.2f}秒")
    else:
        print("\n" + "="*70)
        print("[步骤 6/7] ROC曲线分析 - 跳过（需指定 --roc_predictor 和 --roc_outcome）")
        print("="*70)
    
    # ============================================
    # 步骤 7: 可视化报告（可选）
    # ============================================
    viz_results = None
    if args.visualize:
        print("\n" + "="*70)
        print("[步骤 7/7] 可视化报告生成")
        print("="*70)
        
        start_time = time.time()
        viz_results = visualization_report(
            analysis_data,
            output_dir=args.output,
            vars=effect_vars,
            group_var=args.strata,
            verbose=args.verbose
        )
        viz_time = time.time() - start_time
        print(f"\n✓ 可视化报告完成! 耗时: {viz_time:.2f}秒")
    else:
        print("\n" + "="*70)
        print("[步骤 7/7] 可视化报告 - 跳过（使用 --visualize 启用）")
        print("="*70)
    
    # ============================================
    # 步骤 8: 导出结果
    # ============================================
    print("\n" + "="*70)
    print("[导出] 结果保存")
    print("="*70)
    
    export_results(
        tableone=tableone_results,
        effect_size=effect_size_results,
        roc=roc_results,
        output_dir=args.output,
        filename_prefix='analysis_result',
        verbose=True
    )
    
    # ============================================
    # 分析总结
    # ============================================
    total_time = data_import_time + qc_time + tableone_time + effect_time
    
    print("\n" + "="*70)
    print("分析完成!")
    print("="*70)
    print(f"总耗时: {total_time:.2f}秒")
    print(f"输出目录: {args.output}")
    print("\n生成的文件:")
    print(f"  - analysis_result_tableone.xlsx")
    print(f"  - analysis_result_effect_size.xlsx")
    if roc_results:
        print(f"  - ROC分析结果")
    if viz_results:
        print(f"  - {viz_results['plot_dir']}/")
        print("    (包含箱线图、直方图、Q-Q图、相关矩阵热图等)")
    print("="*70 + "\n")
    
    return {
        'data': analysis_data,
        'quality_control': qc_results,
        'tableone': tableone_results,
        'effect_size': effect_size_results,
        'roc': roc_results,
        'visualization': viz_results,
        'total_time': total_time
    }


if __name__ == '__main__':
    args = parse_arguments()
    
    # 检查数据文件是否存在
    if not os.path.exists(args.data):
        print(f"\n错误: 数据文件不存在: {args.data}")
        print("\n请确保:")
        print("1. 文件路径正确")
        print("2. 如果路径包含空格，请使用引号包裹")
        print("3. Windows系统使用反斜杠或双反斜杠，或使用正斜杠")
        print("\n例如:")
        print('  python run_analysis.py --data dataset.csv --strata Group --missing 12345')
        sys.exit(1)
    
    results = run_full_analysis(args)
