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
from mice_imputation import mice_imputation, simple_impute
from tableone import generate_tableone
from effect_size import calculate_effect_size
from export_results import export_results
from visualization import visualization_report
from roc_analysis import roc_analysis
from ancova import ancova_compare, ancova_to_dataframe, format_mean_sd, format_median_iqr
from survival import survival_analysis
from correlation_regression import correlation_regression


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
                       help='执行MICE多重插补（默认关闭）')
    parser.add_argument('--impute_m', type=int, default=20,
                       help='MICE插补数据集数量（默认20，SAP建议不少于缺失个案百分比）')
    parser.add_argument('--impute_maxit', type=int, default=10,
                       help='MICE每套数据的链式迭代次数（默认10）')
    parser.add_argument('--simple_impute', action='store_true',
                       help='改用简单插补（中位数/众数，臂内；SAP备选方案）')
    parser.add_argument('--force_mice', action='store_true',
                       help='即使缺失率低于 5%% 也强制执行 MICE（默认低于阈值时按 SAP 回退简单插补）')
    parser.add_argument('--impute_vars', type=str, default=None,
                       help='需要插补的变量（逗号分隔，默认: 自动选择）')
    parser.add_argument('--primary_outcome', type=str, default=None,
                       help='主要结局变量（用于基线校正的组间比较，如 score_w12）')
    parser.add_argument('--primary_baseline', type=str, default=None,
                       help='主要结局的基线值变量（ANCOVA 校正用，如 score_bl）')
    parser.add_argument('--covariates', type=str, default=None,
                       help='额外协变量（逗号分隔，如 age,sex）')
    parser.add_argument('--adjust_method', type=str, default='holm',
                       help='两两比较校正方法: holm / bonferroni / fdr_bh（默认 holm）')
    parser.add_argument('--effect_vars', type=str, default=None,
                       help='效应量计算变量（逗号分隔，默认: 所有数值变量）')
    parser.add_argument('--survival_time', type=str, default=None,
                       help='生存分析：随访时间变量名')
    parser.add_argument('--survival_event', type=str, default=None,
                       help='生存分析：事件指示变量名（1=事件，0=删失）')
    parser.add_argument('--survival_covariates', type=str, default=None,
                       help='Cox 模型协变量（逗号分隔）')
    parser.add_argument('--event_coding', type=str, default=None,
                       help='事件变量的原始事件取值（逗号分隔，如 1 或 2；默认 [1]）')
    parser.add_argument('--time_unit', type=str, default='weeks',
                       help='随访时间单位，仅用于表头（默认 weeks）')
    parser.add_argument('--regression_binary', type=str, default=None,
                       help='Logistic 回归的二分类结局变量名')
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


def export_adjusted_results(adjusted: dict, output_dir: str, impute_meta: dict) -> str:
    """导出基线校正组间比较结果（三张 sheet：比较结果 / 描述统计 / 分析信息）。"""
    import pandas as pd

    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "analysis_result_adjusted.xlsx")

    rows = []
    for row in adjusted["adjusted"]:
        is_or = row["measure"] == "OR"
        est_txt = (f"OR {row['estimate']:.2f} ({row['ci_lower']:.2f} to "
                   f"{row['ci_upper']:.2f})") if is_or else \
                  (f"{row['estimate']:.2f} ({row['ci_lower']:.2f} to "
                   f"{row['ci_upper']:.2f})")
        rows.append({
            "Comparison": row["comparison"],
            "Estimate (95% CI)": est_txt,
            "P value": _fmt_p(row["p_value"]),
            f"Adjusted P value ({adjusted['adjust_method']})":
                _fmt_p(row.get("p_adjusted")),
        })
    comparisons_df = pd.DataFrame(rows)

    desc_rows = []
    for arm, d in adjusted["descriptive"].items():
        desc_rows.append({
            "Arm": arm,
            "n": d["n"],
            "mean (SD)": format_mean_sd(d),
            "median (IQR)": format_median_iqr(d),
        })
    descriptives_df = pd.DataFrame(desc_rows)

    info_df = pd.DataFrame([
        {"Item": "Outcome", "Value": adjusted["outcome"]},
        {"Item": "Model", "Value": adjusted["model"]},
        {"Item": "Reference arm", "Value": adjusted["reference"]},
        {"Item": "Omnibus P (Wald)", "Value": _fmt_p(adjusted["omnibus_p"])},
        {"Item": "Imputation strategy", "Value": impute_meta.get("strategy", "none")},
        {"Item": "Imputed datasets (m)", "Value": impute_meta.get("m", 1)},
        {"Item": "MICE converged", "Value": impute_meta.get("converged", "—")},
        {"Item": "Multiple-comparison adjustment", "Value": adjusted["adjust_method"]},
        {"Item": "Note", "Value": "Estimates pooled across imputed datasets using "
                                  "Rubin's rules (Barnard-Rubin df)."},
    ])

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        comparisons_df.to_excel(writer, sheet_name="Adjusted comparisons", index=False)
        descriptives_df.to_excel(writer, sheet_name="Descriptives", index=False)
        info_df.to_excel(writer, sheet_name="Analysis info", index=False)

    return path


def _fmt_p(p) -> str:
    if p is None or (isinstance(p, float) and p != p):  # NaN
        return ""
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def export_survival_results(survival: dict, output_dir: str, time_unit: str = "weeks") -> str:
    """导出生存分析结果（生存表 / 两两 log-rank / Cox / PH 检验 / 数据告警）。"""
    import pandas as pd

    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "analysis_result_survival.xlsx")

    cox_df = survival.get("cox")
    if cox_df is not None and len(cox_df):
        cox_out = cox_df.copy()
        cox_out["HR (95% CI)"] = cox_out.apply(
            lambda r: f"{r['HR']:.2f} ({r['CI_low']:.2f} to {r['CI_high']:.2f})", axis=1
        )
        cox_out["P value"] = cox_out["p"].map(_fmt_p)
        cox_out = cox_out[["term", "HR (95% CI)", "P value"]]
    else:
        cox_out = pd.DataFrame([{"term": "—", "HR (95% CI)": "模型未拟合", "P value": ""}])

    pair_out = survival.get("pairwise")
    if pair_out is None or not len(pair_out):
        pair_out = pd.DataFrame([{"comparison": "—", "p_raw": None, "p_adjusted": None}])
    else:
        pair_out = pair_out.copy()
        pair_out["p_raw"] = pair_out["p_raw"].map(_fmt_p)
        pair_out["p_adjusted"] = pair_out["p_adjusted"].map(_fmt_p)

    ph_out = survival.get("ph_test")
    if ph_out is None or not len(ph_out):
        ph_out = pd.DataFrame([{"term": "—", "p": None, "violated": ""}])
    else:
        ph_out = ph_out.copy()
        ph_out["p"] = ph_out["p"].map(_fmt_p)

    warn_df = pd.DataFrame({"Warning": survival.get("warnings") or ["无"]})

    info_df = pd.DataFrame([
        {"Item": "Sample size (n)", "Value": survival.get("n_used")},
        {"Item": "Total events", "Value": survival.get("events_total")},
        {"Item": "Overall log-rank P", "Value": _fmt_p(survival.get("overall_p"))},
        {"Item": "Time unit", "Value": time_unit},
        {"Item": "Note", "Value": "Cox HR pooled across imputed datasets on the log-HR "
                                  "scale using Rubin's rules; median survival CI from "
                                  "Greenwood variance."},
    ])

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        survival["table"].to_excel(writer, sheet_name="Survival table", index=False)
        pair_out.to_excel(writer, sheet_name="Pairwise log-rank", index=False)
        cox_out.to_excel(writer, sheet_name="Cox model", index=False)
        ph_out.to_excel(writer, sheet_name="PH assumption", index=False)
        warn_df.to_excel(writer, sheet_name="Warnings", index=False)
        info_df.to_excel(writer, sheet_name="Analysis info", index=False)

    return path


def export_regression_results(reg: dict, output_dir: str) -> str:
    """导出相关矩阵、线性/Logistic 回归与共线性诊断。"""
    import pandas as pd

    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "analysis_result_regression.xlsx")

    corr = reg.get("correlation")
    linear = reg.get("linear")
    logistic = reg.get("logistic")
    vif = reg.get("vif")

    def _model_sheet(df):
        if df is None or not len(df):
            return pd.DataFrame([{"term": "—", "effect": "未估计", "p_text": ""}])
        out = df[["term", "effect", "p_text"]].copy()
        out.columns = ["Term", "Effect (95% CI)", "P value"]
        return out

    note_df = pd.DataFrame({"Note": reg.get("notes") or ["无"]})

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        if corr is not None and len(corr):
            corr.to_excel(writer, sheet_name="Correlation")
        _model_sheet(linear).to_excel(writer, sheet_name="Linear regression", index=False)
        _model_sheet(logistic).to_excel(writer, sheet_name="Logistic regression", index=False)
        if vif is not None and len(vif):
            vif.to_excel(writer, sheet_name="Collinearity (VIF)", index=False)
        note_df.to_excel(writer, sheet_name="Notes", index=False)

    return path


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
    qc_results = quality_control(
        data,
        strata=args.strata,
        outcome_var=args.primary_outcome,
        verbose=args.verbose,
    )
    qc_time = time.time() - start_time
    print(f"\n✓ 质量控制完成! 耗时: {qc_time:.2f}秒")
    
    # 统计缺失值情况
    total_missing = qc_results['missing']['total_missing']
    missing_rate = total_missing / (data.shape[0] * data.shape[1]) * 100
    print(f"  总缺失值: {total_missing} ({missing_rate:.2f}%)")
    
    # ============================================
    # 步骤 3: 缺失数据处理（MICE / 简单插补）
    # ============================================
    imputed_data = None
    analysis_datasets = None
    impute_meta = {}
    if args.impute or args.simple_impute:
        print("\n" + "="*70)
        mode = "简单插补" if args.simple_impute else "MICE多重插补"
        print(f"[步骤 3/7] {mode}")
        print("="*70)
        
        # 确定需要插补的变量
        impute_vars = None
        if args.impute_vars:
            impute_vars = [v.strip() for v in args.impute_vars.split(',')]
        
        start_time = time.time()
        if args.simple_impute:
            filled = simple_impute(data, cols=impute_vars, strata=args.strata,
                                   verbose=args.verbose)
            impute_results = {'data': filled, 'datasets': [filled],
                              'strategy': 'simple', 'vars_imputed': impute_vars or [],
                              'methods': {}, 'converged': True, 'details': {}}
        else:
            impute_results = mice_imputation(
                data,
                vars=impute_vars,
                m=args.impute_m,
                maxit=args.impute_maxit,
                strata=args.strata,
                force=args.force_mice,
                verbose=args.verbose,
            )
        imputed_data = impute_results['data']
        analysis_datasets = impute_results['datasets']
        impute_meta = {
            'strategy': impute_results.get('strategy', 'mice'),
            'm': len(analysis_datasets),
            'converged': impute_results.get('converged', True),
            'methods': impute_results.get('methods', {}),
        }
        mice_time = time.time() - start_time
        print(f"\n✓ 插补完成! 耗时: {mice_time:.2f}秒"
              f"（{impute_meta['strategy']}, m={impute_meta['m']}）")
    else:
        print("\n" + "="*70)
        print("[步骤 3/7] 缺失数据处理 - 跳过（使用 --impute 或 --simple_impute 启用）")
        print("="*70)
    
    # 使用原始数据或插补后数据（描述性统计用第一套插补数据）
    analysis_data = imputed_data if imputed_data is not None else data
    datasets_for_pooling = analysis_datasets if analysis_datasets is not None else [data]
    
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
    # 步骤 5.5: 基线校正的组间比较（ANCOVA + Rubin's rules）
    # ============================================
    adjusted_results = None
    if args.primary_outcome and args.strata:
        print("\n" + "="*70)
        print("[步骤 5.5] 基线校正的组间比较（ANCOVA + Rubin）")
        print("="*70)

        covariates = [c.strip() for c in args.covariates.split(',')] if args.covariates else None
        try:
            start_time = time.time()
            adjusted_results = ancova_compare(
                datasets_for_pooling,
                outcome=args.primary_outcome,
                group=args.strata,
                baseline=args.primary_baseline,
                covariates=covariates,
                adjust=args.adjust_method,
            )
            adj_time = time.time() - start_time

            print(f"  模型: {adjusted_results['model']}")
            print(f"  数据集数: {adjusted_results['n_datasets']}")
            for arm in adjusted_results['arms']:
                d = adjusted_results['descriptive'].get(arm, {})
                print(f"  {arm}: n={d.get('n', 0)}, "
                      f"mean(SD)={format_mean_sd(d)}, "
                      f"median(IQR)={format_median_iqr(d)}")
            print(f"  总体检验 P = {adjusted_results['omnibus_p']:.4f}")
            for row in adjusted_results['adjusted']:
                unit = "OR" if row['measure'] == "OR" else ""
                est = row['estimate']
                lo, hi = row['ci_lower'], row['ci_upper']
                print(f"  {row['comparison']}: {unit} {est:.2f} "
                      f"({lo:.2f} to {hi:.2f}), P={row['p_value']:.4f}, "
                      f"校正后 P={row.get('p_adjusted', float('nan')):.4f}")
            print(f"\n✓ 校正比较完成! 耗时: {adj_time:.2f}秒")
        except Exception as exc:
            print(f"\n✗ 校正比较失败: {exc}")
            adjusted_results = None
    else:
        print("\n" + "="*70)
        print("[步骤 5.5] 基线校正比较 - 跳过"
              "（需 --primary_outcome 与 --strata；建议同时给 --primary_baseline）")
        print("="*70)

    # ============================================
    # 步骤 5.6: 生存分析（可选）
    # ============================================
    survival_results = None
    if args.survival_time and args.survival_event:
        print("\n" + "="*70)
        print("[步骤 5.6] 生存分析（KM / log-rank / Cox）")
        print("="*70)

        start_time = time.time()
        try:
            surv_cov = [c.strip() for c in args.survival_covariates.split(',')] \
                if args.survival_covariates else None
            event_coding = [int(x) for x in args.event_coding.split(',')] \
                if args.event_coding else [1]

            survival_results = survival_analysis(
                datasets_for_pooling,
                time_var=args.survival_time,
                event_var=args.survival_event,
                group_var=args.strata,
                covariates=surv_cov,
                event_coding=event_coding,
                time_unit=args.time_unit,
                correction=args.adjust_method,
                verbose=args.verbose,
            )
            surv_time = time.time() - start_time

            print("\n" + survival_results['table'].to_string(index=False))
            if len(survival_results['pairwise']):
                print("\n两两 log-rank：")
                print(survival_results['pairwise'].to_string(index=False))
            if len(survival_results['ph_test']):
                print("\n比例风险假设检验：")
                print(survival_results['ph_test'].to_string(index=False))
            print(f"\n✓ 生存分析完成! 耗时: {surv_time:.2f}秒")
        except Exception as exc:
            print(f"\n✗ 生存分析失败: {exc}")
            survival_results = None
    else:
        print("\n" + "="*70)
        print("[步骤 5.6] 生存分析 - 跳过（需 --survival_time 与 --survival_event）")
        print("="*70)

    # ============================================
    # 步骤 5.7: 相关与回归分析
    # ============================================
    regression_results = None
    if args.primary_outcome:
        print("\n" + "="*70)
        print("[步骤 5.7] 相关与回归分析")
        print("="*70)

        start_time = time.time()
        reg_config = {
            'primary_outcome': args.primary_outcome,
            'strata': args.strata,
            'primary_baseline': args.primary_baseline,
            'regression': {
                'correlation_method': 'auto',
                'independents': [c.strip() for c in args.covariates.split(',')]
                                if args.covariates else [],
                'binary_outcome': args.regression_binary,
            },
        }
        try:
            regression_results = correlation_regression(
                data=analysis_data,
                config=reg_config,
                datasets=datasets_for_pooling,
                verbose=args.verbose,
            )
            if len(regression_results['linear']):
                print("\n线性回归：")
                print(regression_results['linear'][['term', 'effect', 'p_text']]
                      .to_string(index=False))
            if len(regression_results['logistic']):
                print("\nLogistic 回归：")
                print(regression_results['logistic'][['term', 'effect', 'p_text']]
                      .to_string(index=False))
            reg_time = time.time() - start_time
            print(f"\n✓ 相关与回归完成! 耗时: {reg_time:.2f}秒")
        except Exception as exc:
            print(f"\n✗ 相关与回归失败: {exc}")
            regression_results = None
    else:
        print("\n" + "="*70)
        print("[步骤 5.7] 相关与回归 - 跳过（需 --primary_outcome）")
        print("="*70)

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

    # 导出基线校正比较结果（对应 SAP 表 2/3 风格）
    adjusted_path = None
    if adjusted_results:
        adjusted_path = export_adjusted_results(
            adjusted_results, args.output, impute_meta
        )
        print(f"  - {os.path.basename(adjusted_path)}")

    # 导出生存分析结果
    survival_path = None
    if survival_results:
        survival_path = export_survival_results(
            survival_results, args.output, time_unit=args.time_unit
        )
        print(f"  - {os.path.basename(survival_path)}")

    # 导出相关与回归结果
    regression_path = None
    if regression_results:
        regression_path = export_regression_results(regression_results, args.output)
        print(f"  - {os.path.basename(regression_path)}")
    
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
    if survival_results:
        print(f"  - analysis_result_survival.xlsx")
    if regression_results:
        print(f"  - analysis_result_regression.xlsx")
    if viz_results:
        print(f"  - {viz_results['plot_dir']}/")
        print("    (包含箱线图、直方图、Q-Q图、相关矩阵热图等)")
    print("="*70 + "\n")
    
    return {
        'data': analysis_data,
        'datasets': datasets_for_pooling,
        'imputation': impute_meta,
        'quality_control': qc_results,
        'tableone': tableone_results,
        'effect_size': effect_size_results,
        'adjusted': adjusted_results,
        'survival': survival_results,
        'regression': regression_results,
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
