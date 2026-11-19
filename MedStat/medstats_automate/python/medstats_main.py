#!/usr/bin/env python3
# ============================================
# 医学统计分析自动化主程序 (Python版本)
# MedStats-Automate v1.0.0
# 
# 使用方法:
# python medstats_main.py --data <数据文件> --config <配置文件> --output <输出目录>
#
# 作者: MedStats Team
# ============================================

import argparse
import yaml
import os
import sys
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_import import import_data, auto_detect_types
from quality_control import quality_control
from mice_imputation import mice_imputation
from tableone import generate_tableone
from effect_size import calculate_effect_size
from export_results import export_results
from visualization import visualization_report
try:
    from correlation_regression import correlation_regression
except ImportError:  # 该模块尚未移植：主流程其余步骤仍可用
    correlation_regression = None
from roc_analysis import roc_analysis

def main():
    parser = argparse.ArgumentParser(description='医学统计分析自动化程序')
    parser.add_argument('--data', type=str, required=True, help='数据文件路径')
    parser.add_argument('--config', type=str, default='config.yaml', help='配置文件路径')
    parser.add_argument('--output', type=str, default='./output', help='输出目录')
    parser.add_argument('--groups', type=int, default=2, help='实验组数(1/2/3+)')
    parser.add_argument('--strata', type=str, default=None, help='分组变量名')
    parser.add_argument('--impute_vars', type=str, default=None, help='需要插补的变量(逗号分隔)')
    parser.add_argument('--effect_vars', type=str, default=None, help='效应量计算变量(逗号分隔)')
    parser.add_argument('--roc_var_a', type=str, default=None, help='ROC分析变量a(诊断指标)')
    parser.add_argument('--roc_var_b', type=str, default=None, help='ROC分析变量b(诊断标准)')
    parser.add_argument('--verbose', action='store_true', help='详细输出')
    
    args = parser.parse_args()
    
    # 创建输出目录
    if not os.path.exists(args.output):
        os.makedirs(args.output, exist_ok=True)
    
    # 加载配置文件
    if os.path.exists(args.config):
        with open(args.config, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    else:
        config = {}
    
    print("\n" + "="*50)
    print("医学统计分析自动化程序")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50 + "\n")
    
    # Step 1: 数据导入
    print("[Step 1/9] 数据导入...")
    data = import_data(args.data)
    
    # Step 2: 数据质量控制
    print("[Step 2/9] 数据质量控制与清洗...")
    qc_report = quality_control(data)
    
    # Step 3: 多重插补
    if args.impute_vars is not None or config.get('auto_impute', False):
        print("[Step 3/9] 多重插补(MICE)...")
        impute_vars = args.impute_vars.split(',') if args.impute_vars else None
        imp_result = mice_imputation(
            data, 
            vars=impute_vars,
            m=config.get('mice_m', 5),
            maxit=config.get('mice_maxit', 10)
        )
        data = imp_result['data']
    
    # Step 4: TableOne生成
    print("[Step 4/9] 生成TableOne基线资料表...")
    tableone_result = generate_tableone(
        data=data,
        groups=args.groups,
        strata=args.strata,
        config=config
    )
    
    # Step 5: 效应量计算
    print("[Step 5/9] 计算效应量与95%CI...")
    effect_vars = args.effect_vars.split(',') if args.effect_vars else None
    effect_result = calculate_effect_size(
        data=data,
        vars=effect_vars,
        groups=args.groups,
        strata=args.strata,
        config=config
    )
    
    # Step 6: 导出结果
    print("[Step 6/9] 导出Excel结果...")
    export_results(
        tableone=tableone_result,
        effect_size=effect_result,
        output_dir=args.output
    )
    
    # Step 7: 可视化
    print("[Step 7/9] 生成可视化报告...")
    visualization_report(
        data=data,
        output_dir=args.output,
        config=config
    )
    
    # Step 8: 相关与回归分析
    reg_result = None
    if correlation_regression is None:
        print("[Step 8/9] 相关与回归分析 - 跳过（correlation_regression 模块缺失）")
    else:
        print("[Step 8/9] 相关与回归分析...")
        reg_result = correlation_regression(
            data=data,
            config=config
        )
        has_result = False
        if reg_result:
            for _key in ("correlation", "linear", "logistic"):
                _val = reg_result.get(_key)
                if _val is not None and len(_val) > 0:
                    has_result = True
                    break
        if has_result:
            from run_analysis import export_regression_results
            path = export_regression_results(reg_result, args.output)
            print(f"相关与回归结果已导出: {path}")
    
    # Step 9: ROC分析
    if args.roc_var_a is not None and args.roc_var_b is not None:
        print("[Step 9/9] ROC曲线分析...")
        roc_result = roc_analysis(
            data=data,
            predictor=args.roc_var_a,
            outcome=args.roc_var_b,
            output_dir=args.output
        )
    
    print("\n" + "="*50)
    print("分析完成!")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"输出目录: {args.output}")
    print("="*50 + "\n")

if __name__ == "__main__":
    main()
