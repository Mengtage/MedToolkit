#!/usr/bin/env python3
# ============================================
# 高级医学统计分析系统 (集成 chart-visualization + data-analysis 技能)
# 医学统计分析自动化系统
#
# 使用方法:
# python run_advanced_analysis.py --data <数据文件> --missing <缺失值> --strata <分组变量>
#
# 示例:
# python run_advanced_analysis.py --data dataset.csv --missing 12345 --strata Group
# ============================================

import argparse
import os
import sys
import time
from datetime import datetime
import pandas as pd
import numpy as np

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_import import import_data
from quality_control import quality_control
from tableone import generate_tableone
from effect_size import calculate_effect_size
from export_results import export_results
from advanced_analysis import AdvancedAnalyzer
from enhanced_visualization import ChartVisualizer


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='高级医学统计分析系统（集成图表可视化）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python run_advanced_analysis.py --data dataset.csv --missing 12345 --strata Group
  python run_advanced_analysis.py --data data.csv --missing "12345,-999" --strata Treatment --viz
  python run_advanced_analysis.py --data data.csv --missing 12345 --strata Group --advanced --export
        """
    )
    
    parser.add_argument('--data', type=str, required=True,
                       help='数据文件路径')
    parser.add_argument('--strata', type=str, default=None,
                       help='分组变量名')
    parser.add_argument('--missing', type=str, default='12345',
                       help='缺失值标记（多个用逗号分隔，默认: 12345）')
    parser.add_argument('--output', type=str, default='./advanced_output',
                       help='输出目录（默认: ./advanced_output）')
    parser.add_argument('--encoding', type=str, default='UTF-8',
                       help='文件编码（默认: UTF-8）')
    parser.add_argument('--vars', type=str, default=None,
                       help='分析变量列表（逗号分隔，默认: 所有数值变量）')
    parser.add_argument('--advanced', action='store_true',
                       help='启用高级分析（DuckDB）')
    parser.add_argument('--viz', action='store_true',
                       help='启用高级可视化（chart-visualization）')
    parser.add_argument('--theme', type=str, default='default',
                       choices=['default', 'academy', 'dark'],
                       help='可视化主题（default/academy/dark）')
    parser.add_argument('--export', action='store_true',
                       help='导出详细结果')
    parser.add_argument('--verbose', action='store_true', default=True,
                       help='详细输出')
    
    return parser.parse_args()


def parse_missing_values(missing_str):
    """解析缺失值字符串"""
    if missing_str is None:
        return [12345]
    
    values = []
    for val in missing_str.split(','):
        val = val.strip()
        try:
            if '.' in val:
                values.append(float(val))
            else:
                values.append(int(val))
        except ValueError:
            values.append(val)
    
    return values


def run_advanced_analysis(args):
    """运行高级分析"""
    
    print("\n" + "="*70)
    print("🚀 MedStats-Automate 高级医学统计分析系统")
    print("="*70)
    print(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"数据文件: {args.data}")
    print(f"分组变量: {args.strata}")
    print(f"缺失值标记: {args.missing}")
    print("="*70 + "\n")
    
    # 创建输出目录
    os.makedirs(args.output, exist_ok=True)
    viz_dir = os.path.join(args.output, 'charts')
    os.makedirs(viz_dir, exist_ok=True)
    
    # 解析缺失值
    missing_values = parse_missing_values(args.missing)
    print(f"将识别以下值为缺失值: {missing_values}\n")
    
    # ============================================
    # 步骤 1: 数据导入
    # ============================================
    print("\n" + "="*70)
    print("[步骤 1/6] 数据导入")
    print("="*70)
    
    start_time = time.time()
    try:
        data = import_data(args.data, encoding=args.encoding, na_values=missing_values)
        data_import_time = time.time() - start_time
        print(f"\n✓ 数据导入成功! 耗时: {data_import_time:.2f}秒")
        print(f"  数据规模: {data.shape[0]} 行 × {data.shape[1]} 列")
    except Exception as e:
        print(f"\n✗ 数据导入失败: {e}")
        return None
    
    # ============================================
    # 步骤 2: 数据质量控制
    # ============================================
    print("\n" + "="*70)
    print("[步骤 2/6] 数据质量控制")
    print("="*70)
    
    start_time = time.time()
    qc_results = quality_control(data, verbose=False)
    qc_time = time.time() - start_time
    print(f"✓ 质量控制完成! 耗时: {qc_time:.2f}秒")
    
    total_missing = qc_results['missing']['total_missing']
    print(f"  总缺失值: {total_missing}")
    
    # ============================================
    # 步骤 3: 高级分析（可选）
    # ============================================
    analysis_results = None
    if args.advanced:
        print("\n" + "="*70)
        print("[步骤 3/6] 高级数据分析（DuckDB）")
        print("="*70)
        
        analyzer = AdvancedAnalyzer()
        analyzer.data = data
        
        # 数据结构检查
        schema = analyzer.inspect_schema()
        print(f"✓ 数据结构检查完成")
        print(f"  列数: {schema['total_columns']}")
        print(f"  行数: {schema['total_rows']}")
        print(f"  缺失率: {schema['missing_rate']:.2f}%")
        
        # 统计摘要
        summary = analyzer.statistical_summary()
        summary_path = os.path.join(args.output, 'statistical_summary.csv')
        analyzer.export_to_csv(summary, summary_path)
        print(f"✓ 统计摘要已保存: {summary_path}")
        
        # 分组分析
        if args.strata:
            group_stats = analyzer.group_analysis(args.strata)
            group_path = os.path.join(args.output, 'group_statistics.csv')
            analyzer.export_to_csv(group_stats, group_path)
            print(f"✓ 分组统计已保存: {group_path}")
        
        analysis_results = analyzer
        print(f"\n✓ 高级分析完成!")
    else:
        print("\n" + "="*70)
        print("[步骤 3/6] 高级分析 - 跳过（使用 --advanced 启用）")
        print("="*70)
    
    # ============================================
    # 步骤 4: TableOne基线资料表
    # ============================================
    print("\n" + "="*70)
    print("[步骤 4/6] TableOne基线资料表生成")
    print("="*70)
    
    # 确定分析变量
    vars_list = None
    if args.vars:
        vars_list = [v.strip() for v in args.vars.split(',')]
    else:
        vars_list = data.select_dtypes(include=[np.number]).columns.tolist()
    
    print(f"分析变量: {len(vars_list)} 个")
    
    start_time = time.time()
    tableone_results = generate_tableone(
        data,
        strata=args.strata,
        verbose=False
    )
    tableone_time = time.time() - start_time
    print(f"✓ TableOne生成完成! 耗时: {tableone_time:.2f}秒")
    
    # ============================================
    # 步骤 5: 效应量计算
    # ============================================
    print("\n" + "="*70)
    print("[步骤 5/6] 效应量计算")
    print("="*70)
    
    start_time = time.time()
    effect_size_results = calculate_effect_size(
        data,
        vars=vars_list,
        strata=args.strata,
        verbose=False
    )
    effect_time = time.time() - start_time
    print(f"✓ 效应量计算完成! 耗时: {effect_time:.2f}秒")
    
    # ============================================
    # 步骤 6: 高级可视化（可选）
    # ============================================
    viz_charts = None
    if args.viz:
        print("\n" + "="*70)
        print("[步骤 6/6] 高级可视化（chart-visualization 技能）")
        print("="*70)
        
        visualizer = ChartVisualizer(output_dir=viz_dir)
        
        # 生成可视化报告
        viz_charts = visualizer.create_medical_report(
            data=data,
            group_var=args.strata,
            vars_list=vars_list[:10],  # 限制变量数量
            output_prefix='medical_report'
        )
        
        # 生成 HTML 报告
        html_path = os.path.join(args.output, 'visualization_report.html')
        visualizer.generate_report_html(html_path)
        
        print(f"✓ 可视化报告已生成:")
        for chart_type, url in viz_charts.items():
            print(f"  - {chart_type}: {url}")
        print(f"  - HTML报告: {html_path}")
    else:
        print("\n" + "="*70)
        print("[步骤 6/6] 高级可视化 - 跳过（使用 --viz 启用）")
        print("="*70)
    
    # ============================================
    # 导出结果
    # ============================================
    print("\n" + "="*70)
    print("[导出] 结果保存")
    print("="*70)
    
    export_results(
        tableone=tableone_results,
        effect_size=effect_size_results,
        output_dir=args.output,
        filename_prefix='advanced_analysis',
        verbose=True
    )
    
    # ============================================
    # 分析总结
    # ============================================
    total_time = data_import_time + qc_time + tableone_time + effect_time
    
    print("\n" + "="*70)
    print("✅ 分析完成!")
    print("="*70)
    print(f"总耗时: {total_time:.2f}秒")
    print(f"输出目录: {args.output}")
    print("\n生成的文件:")
    print(f"  - advanced_analysis_tableone.xlsx")
    print(f"  - advanced_analysis_effect_size.xlsx")
    if args.advanced:
        print(f"  - statistical_summary.csv")
        if args.strata:
            print(f"  - group_statistics.csv")
    if args.viz:
        print(f"  - visualization_report.html")
        print(f"  - charts/")
    print("="*70 + "\n")
    
    return {
        'data': data,
        'quality_control': qc_results,
        'tableone': tableone_results,
        'effect_size': effect_size_results,
        'advanced_analysis': analysis_results,
        'visualization': viz_charts,
        'total_time': total_time
    }


def demo_visualization():
    """演示可视化功能"""
    print("\n" + "="*70)
    print("🎨 chart-visualization 技能演示")
    print("="*70)
    
    visualizer = ChartVisualizer()
    
    # 演示数据
    demo_data = [
        {'x': 1, 'y': 2, 'group': 'A'},
        {'x': 2, 'y': 4, 'group': 'A'},
        {'x': 3, 'y': 5, 'group': 'B'},
        {'x': 4, 'y': 7, 'group': 'B'},
        {'x': 5, 'y': 9, 'group': 'A'}
    ]
    
    # 生成散点图
    print("\n1. 生成散点图...")
    scatter_url = visualizer.generate_scatter_plot(
        demo_data,
        title='演示散点图',
        x_title='X轴',
        y_title='Y轴'
    )
    print(f"   URL: {scatter_url}")
    
    # 生成箱线图
    print("\n2. 生成箱线图...")
    boxplot_data = [
        {'category': 'Control', 'value': 10},
        {'category': 'Control', 'value': 12},
        {'category': 'Control', 'value': 15},
        {'category': 'Treatment', 'value': 18},
        {'category': 'Treatment', 'value': 20},
        {'category': 'Treatment', 'value': 22}
    ]
    boxplot_url = visualizer.generate_boxplot(
        boxplot_data,
        title='演示箱线图',
        x_title='组别',
        y_title='数值'
    )
    print(f"   URL: {boxplot_url}")
    
    print("\n" + "="*70)
    print("演示完成!")
    print("="*70)


if __name__ == '__main__':
    args = parse_arguments()
    
    # 检查数据文件是否存在
    if not os.path.exists(args.data):
        print(f"\n错误: 数据文件不存在: {args.data}")
        print("\n请确保文件路径正确")
        sys.exit(1)
    
    # 运行分析
    results = run_advanced_analysis(args)
    
    # 如果启用了可视化，显示演示
    if args.viz and results:
        print("\n" + "="*70)
        print("💡 提示: 要查看完整的图表可视化，请使用 --viz 参数")
        print("="*70)
