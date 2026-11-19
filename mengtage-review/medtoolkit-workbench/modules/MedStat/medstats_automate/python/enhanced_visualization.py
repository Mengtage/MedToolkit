#!/usr/bin/env python3
# ============================================
# 高级可视化报告模块 (集成 chart-visualization 技能)
# 医学统计分析自动化系统
#
# 支持的图表类型:
# 1. 散点图 (scatter_chart)
# 2. 箱线图 (boxplot_chart)
# 3. 小提琴图 (violin_chart)
# 4. 折线图 (line_chart)
# 5. 热力图 (heatmap_chart)
# 6. 柱状图 (bar_chart)
# 7. 直方图 (histogram_chart)
# 8. 雷达图 (radar_chart)
# 9. 饼图 (pie_chart)
# ============================================

import pandas as pd
import numpy as np
import subprocess
import json
import os
from pathlib import Path

class ChartVisualizer:
    """基于 chart-visualization 技能的高级图表生成器"""
    
    def __init__(self, output_dir='./output/charts'):
        """初始化可视化器"""
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.script_path = "/data/user/skills/chart-visualization/scripts/generate.js"
        self.generated_charts = []
    
    def generate_chart(self, chart_type, data, title='', theme='default', **kwargs):
        """
        生成图表
        
        Parameters:
        -----------
        chart_type : str
            图表类型
        data : list
            图表数据
        title : str
            图表标题
        theme : str
            主题风格 ('default', 'academy', 'dark')
        **kwargs : 其他参数
            
        Returns:
        --------
        str : 图表 URL
        """
        # 构建 payload
        payload = {
            'tool': f'generate_{chart_type}',
            'args': {
                'data': data,
                'title': title,
                'theme': theme
            }
        }
        
        # 添加可选参数
        if 'width' in kwargs:
            payload['args']['width'] = kwargs['width']
        if 'height' in kwargs:
            payload['args']['height'] = kwargs['height']
        if 'axisXTitle' in kwargs:
            payload['args']['axisXTitle'] = kwargs['axisXTitle']
        if 'axisYTitle' in kwargs:
            payload['args']['axisYTitle'] = kwargs['axisYTitle']
        if 'palette' in kwargs:
            payload['args']['style'] = {'palette': kwargs['palette']}
        
        # 生成图表
        try:
            result = subprocess.run(
                ['node', self.script_path, json.dumps(payload)],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                chart_url = result.stdout.strip()
                self.generated_charts.append({
                    'type': chart_type,
                    'title': title,
                    'url': chart_url
                })
                return chart_url
            else:
                print(f"图表生成失败: {result.stderr}")
                return None
                
        except Exception as e:
            print(f"图表生成错误: {e}")
            return None
    
    def generate_scatter_plot(self, data, title='散点图', x_title='', y_title='', theme='default'):
        """生成散点图"""
        print(f"生成散点图: {title}")
        return self.generate_chart('scatter_chart', data, title, theme,
                                   axisXTitle=x_title, axisYTitle=y_title)
    
    def generate_boxplot(self, data, title='箱线图', x_title='', y_title='', theme='default'):
        """生成箱线图"""
        print(f"生成箱线图: {title}")
        return self.generate_chart('boxplot_chart', data, title, theme,
                                   axisXTitle=x_title, axisYTitle=y_title)
    
    def generate_violin_plot(self, data, title='小提琴图', x_title='', y_title='', theme='default'):
        """生成小提琴图"""
        print(f"生成小提琴图: {title}")
        return self.generate_chart('violin_chart', data, title, theme,
                                   axisXTitle=x_title, axisYTitle=y_title)
    
    def generate_line_chart(self, data, title='折线图', x_title='', y_title='', theme='default'):
        """生成折线图"""
        print(f"生成折线图: {title}")
        return self.generate_chart('line_chart', data, title, theme,
                                   axisXTitle=x_title, axisYTitle=y_title)
    
    def generate_bar_chart(self, data, title='柱状图', x_title='', y_title='', theme='default'):
        """生成柱状图"""
        print(f"生成柱状图: {title}")
        return self.generate_chart('bar_chart', data, title, theme,
                                   axisXTitle=x_title, axisYTitle=y_title)
    
    def generate_histogram(self, data, title='直方图', x_title='', y_title='', theme='default'):
        """生成直方图"""
        print(f"生成直方图: {title}")
        return self.generate_chart('histogram_chart', data, title, theme,
                                   axisXTitle=x_title, axisYTitle=y_title)
    
    def generate_pie_chart(self, data, title='饼图', theme='default'):
        """生成饼图"""
        print(f"生成饼图: {title}")
        return self.generate_chart('pie_chart', data, title, theme)
    
    def generate_radar_chart(self, data, title='雷达图', theme='default'):
        """生成雷达图"""
        print(f"生成雷达图: {title}")
        return self.generate_chart('radar_chart', data, title, theme)
    
    def generate_correlation_heatmap(self, data, title='相关矩阵热图', theme='default'):
        """生成相关矩阵热图"""
        print(f"生成热力图: {title}")
        return self.generate_chart('heatmap_chart', data, title, theme)
    
    def create_medical_report(self, data, group_var, vars_list, output_prefix='medical_report'):
        """
        创建完整的医学数据可视化报告
        
        Parameters:
        -----------
        data : pd.DataFrame
            数据框
        group_var : str
            分组变量
        vars_list : list
            可视化变量列表
        output_prefix : str
            输出文件前缀
            
        Returns:
        --------
        dict : 生成的图表信息
        """
        print("\n" + "="*70)
        print("开始生成医学数据可视化报告")
        print("="*70)
        
        charts = {}
        
        # 1. 生成箱线图
        if vars_list and len(vars_list) > 0:
            var = vars_list[0]
            boxplot_data = self.prepare_boxplot_data(data, var, group_var)
            boxplot_url = self.generate_boxplot(
                boxplot_data,
                title=f'{var} 分组箱线图',
                x_title=group_var,
                y_title=var
            )
            charts['boxplot'] = boxplot_url
        
        # 2. 生成小提琴图
        if vars_list and len(vars_list) > 0:
            var = vars_list[0]
            violin_data = self.prepare_violin_data(data, var, group_var)
            violin_url = self.generate_violin_plot(
                violin_data,
                title=f'{var} 分组小提琴图',
                x_title=group_var,
                y_title=var
            )
            charts['violin'] = violin_url
        
        # 3. 生成相关矩阵热图
        if len(vars_list) >= 2:
            heatmap_data = self.prepare_heatmap_data(data, vars_list)
            heatmap_url = self.generate_correlation_heatmap(
                heatmap_data,
                title='变量相关矩阵'
            )
            charts['heatmap'] = heatmap_url
        
        # 4. 生成散点图矩阵
        if len(vars_list) >= 2:
            scatter_data = self.prepare_scatter_data(data, vars_list[0], vars_list[1], group_var)
            scatter_url = self.generate_scatter_plot(
                scatter_data,
                title=f'{vars_list[0]} vs {vars_list[1]}',
                x_title=vars_list[0],
                y_title=vars_list[1]
            )
            charts['scatter'] = scatter_url
        
        # 5. 生成直方图
        if vars_list and len(vars_list) > 0:
            var = vars_list[0]
            hist_data = self.prepare_histogram_data(data, var)
            hist_url = self.generate_histogram(
                hist_data,
                title=f'{var} 分布直方图',
                x_title=var,
                y_title='频数'
            )
            charts['histogram'] = hist_url
        
        # 6. 生成分组柱状图
        if group_var:
            bar_data = self.prepare_bar_data(data, group_var)
            bar_url = self.generate_bar_chart(
                bar_data,
                title=f'{group_var} 分组分布',
                x_title=group_var,
                y_title='频数'
            )
            charts['bar'] = bar_url
        
        print("\n" + "="*70)
        print("可视化报告生成完成")
        print("="*70)
        
        return charts
    
    def prepare_boxplot_data(self, data, var, group_var):
        """准备箱线图数据"""
        boxplot_data = []
        for group in data[group_var].unique():
            if pd.isna(group):
                continue
            for val in data[data[group_var] == group][var].dropna():
                boxplot_data.append({
                    'category': str(group),
                    'value': float(val)
                })
        return boxplot_data
    
    def prepare_violin_data(self, data, var, group_var):
        """准备小提琴图数据"""
        return self.prepare_boxplot_data(data, var, group_var)
    
    def prepare_scatter_data(self, data, x_var, y_var, group_var=None):
        """准备散点图数据"""
        scatter_data = []
        for _, row in data.iterrows():
            if pd.notna(row[x_var]) and pd.notna(row[y_var]):
                point = {
                    'x': float(row[x_var]),
                    'y': float(row[y_var])
                }
                if group_var:
                    point['group'] = str(row[group_var])
                scatter_data.append(point)
        return scatter_data[:1000]
    
    def prepare_heatmap_data(self, data, vars_list):
        """准备热力图数据"""
        corr = data[vars_list].corr()
        heatmap_data = []
        for i, var1 in enumerate(vars_list):
            for j, var2 in enumerate(vars_list):
                heatmap_data.append({
                    'x': var1,
                    'y': var2,
                    'value': float(corr.loc[var1, var2])
                })
        return heatmap_data
    
    def prepare_histogram_data(self, data, var, bins=30):
        """准备直方图数据"""
        hist_data = []
        for val in data[var].dropna():
            hist_data.append({
                'x': float(val),
                'frequency': 1
            })
        return hist_data
    
    def prepare_bar_data(self, data, group_var):
        """准备柱状图数据"""
        counts = data[group_var].value_counts()
        bar_data = []
        for group, count in counts.items():
            if pd.notna(group):
                bar_data.append({
                    'x': str(group),
                    'y': int(count)
                })
        return bar_data
    
    def get_generated_charts(self):
        """获取所有生成的图表"""
        return self.generated_charts
    
    def generate_report_html(self, output_path='./visualization_report.html'):
        """生成 HTML 报告"""
        html = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MedStats-Automate 可视化报告</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        h1 {
            color: #2c3e50;
            text-align: center;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }
        h2 {
            color: #34495e;
            margin-top: 30px;
        }
        .chart-container {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .chart-image {
            max-width: 100%;
            height: auto;
            display: block;
            margin: 0 auto;
        }
        .chart-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
        }
        .chart-item {
            background: white;
            border-radius: 8px;
            padding: 15px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .chart-item img {
            width: 100%;
            height: auto;
        }
        .footer {
            text-align: center;
            margin-top: 40px;
            padding: 20px;
            color: #7f8c8d;
        }
    </style>
</head>
<body>
    <h1>📊 MedStats-Automate 可视化报告</h1>
    <p style="text-align: center; color: #7f8c8d;">
        生成时间: """ + pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S') + """
    </p>
    
    <div class="chart-grid">
"""
        
        for i, chart in enumerate(self.generated_charts):
            html += f"""
        <div class="chart-item">
            <h3>{chart['title']}</h3>
            <img src="{chart['url']}" alt="{chart['title']}" class="chart-image">
        </div>
"""
        
        html += """
    </div>
    
    <div class="footer">
        <p>由 MedStats-Automate 生成 | 医学统计分析自动化系统</p>
    </div>
</body>
</html>
"""
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"✓ HTML报告已生成: {output_path}")
        return output_path
