#!/usr/bin/env python3
# ============================================
# 结果导出模块
# ============================================

import pandas as pd
import os
from datetime import datetime

def export_results(tableone=None, effect_size=None, correlation=None,
                 regression=None, roc=None, output_dir='./output',
                 filename_prefix='medstats_result', format='xlsx', verbose=True):
    """导出分析结果到Excel"""
    print("开始导出结果...\n")
    
    os.makedirs(output_dir, exist_ok=True)
    exported_files = []
    
    if tableone is not None:
        filepath = export_tableone(f"{output_dir}/{filename_prefix}_tableone.{format}")
        tableone.to_excel(filepath, index=False) if hasattr(tableone, 'to_excel') else tableone['tableone'].to_excel(filepath, index=False)
        exported_files.append(filepath)
        print(f"TableOne已导出: {filepath}")
    
    if effect_size is not None:
        filepath = f"{output_dir}/{filename_prefix}_effect_size.{format}"
        effect_size['results_table'].to_excel(filepath, index=False)
        exported_files.append(filepath)
        print(f"效应量已导出: {filepath}")
    
    if verbose:
        print("\n导出完成!")
        for f in exported_files:
            print(f"  {f}")
    
    return exported_files

def export_tableone(filepath):
    return filepath

def export_effect_size(filepath):
    return filepath
