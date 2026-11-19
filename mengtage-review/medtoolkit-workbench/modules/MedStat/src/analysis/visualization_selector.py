"""
图表类型智能选择模块
根据变量类型自动选择合适的可视化方法
"""

import pandas as pd
import numpy as np


class VisualizationSelector:
    """
    可视化方法智能选择器
    根据变量类型和特征选择最合适的图表类型
    """
    
    @staticmethod
    def select_visualization(var_type, n_categories=None, data=None):
        """
        根据变量类型选择合适的可视化方法
        
        Parameters:
        -----------
        var_type : str
            变量类型
        n_categories : int
            类别数量
        data : pd.Series
            数据（可选，用于自动检测）
            
        Returns:
        --------
        list
            推荐的图表类型列表（按优先级排序）
        """
        if data is not None:
            var_type, n_categories = VisualizationSelector._auto_detect_type(data)
        
        recommendations = VisualizationSelector._get_recommendations(var_type, n_categories)
        
        return recommendations
    
    @staticmethod
    def _auto_detect_type(data):
        """自动检测变量类型"""
        if pd.api.types.is_numeric_dtype(data):
            unique_ratio = data.nunique() / len(data)
            if unique_ratio > 0.1 or data.nunique() > 20:
                var_type = 'numeric_continuous'
            else:
                var_type = 'numeric_discrete'
            n_categories = None
        else:
            var_type = 'categorical'
            n_categories = data.nunique()
        
        return var_type, n_categories
    
    @staticmethod
    def _get_recommendations(var_type, n_categories):
        """根据变量类型获取推荐图表"""
        if var_type in ['numeric_continuous', 'numeric_discrete']:
            return [
                {
                    'type': 'histogram',
                    'label': '直方图',
                    'description': '展示数据分布',
                    'suitable': True
                },
                {
                    'type': 'boxplot',
                    'label': '箱线图',
                    'description': '展示数据分布和异常值',
                    'suitable': True
                },
                {
                    'type': 'qqplot',
                    'label': 'Q-Q图',
                    'description': '检验正态性',
                    'suitable': True
                },
                {
                    'type': 'violin',
                    'label': '小提琴图',
                    'description': '结合箱线图和核密度',
                    'suitable': True
                }
            ]
        
        elif var_type == 'categorical':
            if n_categories is None or n_categories <= 5:
                return [
                    {
                        'type': 'bar_chart',
                        'label': '柱状图',
                        'description': '展示各类别频数',
                        'suitable': True
                    },
                    {
                        'type': 'pie_chart',
                        'label': '饼图',
                        'description': '展示各类别占比',
                        'suitable': True
                    }
                ]
            else:
                return [
                    {
                        'type': 'bar_chart',
                        'label': '柱状图',
                        'description': '展示各类别频数',
                        'suitable': True
                    },
                    {
                        'type': 'treemap',
                        'label': '树状图',
                        'description': '展示层级结构',
                        'suitable': True
                    }
                ]
        
        elif var_type == 'ordinal':
            return [
                {
                    'type': 'stacked_bar',
                    'label': '堆叠柱状图',
                    'description': '展示有序类别分布',
                    'suitable': True
                },
                {
                    'type': 'diverging_bar',
                    'label': '发散柱状图',
                    'description': '展示与参考值的差异',
                    'suitable': True
                }
            ]
        
        elif var_type == 'binary':
            return [
                {
                    'type': 'bar_chart',
                    'label': '柱状图',
                    'description': '展示两组比例',
                    'suitable': True
                },
                {
                    'type': 'forest_plot',
                    'label': '森林图',
                    'description': '展示效应量及置信区间',
                    'suitable': True
                }
            ]
        
        else:
            return [
                {
                    'type': 'bar_chart',
                    'label': '柱状图',
                    'description': '通用展示',
                    'suitable': True
                }
            ]
    
    @staticmethod
    def select_grouped_visualization(var_type, group_type='categorical', n_groups=2):
        """
        根据变量类型和分组类型选择合适的分组分析图表
        
        Parameters:
        -----------
        var_type : str
            结果变量类型
        group_type : str
            分组变量类型
        n_groups : int
            组数
            
        Returns:
        --------
        list
            推荐的图表配置列表
        """
        recommendations = []
        
        # 连续结果变量
        if var_type in ['numeric_continuous', 'numeric_discrete']:
            if n_groups <= 5:
                recommendations.extend([
                    {
                        'type': 'boxplot',
                        'label': '箱线图',
                        'suitable': True,
                        'description': '展示各组分布和异常值'
                    },
                    {
                        'type': 'violin',
                        'label': '小提琴图',
                        'suitable': True,
                        'description': '展示各组分布密度'
                    },
                    {
                        'type': 'strip',
                        'label': '散点条图',
                        'suitable': True,
                        'description': '展示原始数据点'
                    }
                ])
            else:
                recommendations.extend([
                    {
                        'type': 'violin',
                        'label': '小提琴图',
                        'suitable': True,
                        'description': '展示各组分布密度'
                    },
                    {
                        'type': 'boxplot',
                        'label': '箱线图',
                        'suitable': True,
                        'description': '展示各组分布和异常值'
                    }
                ])
        
        # 分类结果变量
        elif var_type == 'categorical':
            recommendations.extend([
                {
                    'type': 'grouped_bar',
                    'label': '分组柱状图',
                    'suitable': True,
                    'description': '展示各组各类别频数'
                },
                {
                    'type': 'stacked_bar',
                    'label': '堆叠柱状图',
                    'suitable': True,
                    'description': '展示各组各类别占比'
                },
                {
                    'type': 'mosaic',
                    'label': '马赛克图',
                    'suitable': True,
                    'description': '展示分组与结果的关联'
                },
                {
                    'type': 'boxplot',
                    'label': '箱线图',
                    'suitable': False,
                    'reason': '分类变量不适合使用箱线图',
                    'description': '分类变量应使用柱状图或饼图'
                }
            ])
        
        # 二分类结果变量
        elif var_type == 'binary':
            recommendations.extend([
                {
                    'type': 'grouped_bar',
                    'label': '分组柱状图',
                    'suitable': True,
                    'description': '展示各组阳性率'
                },
                {
                    'type': 'forest_plot',
                    'label': '森林图',
                    'suitable': True,
                    'description': '展示效应量及置信区间'
                },
                {
                    'type': 'boxplot',
                    'label': '箱线图',
                    'suitable': False,
                    'reason': '二分类变量不适合使用箱线图',
                    'description': '二分类变量应使用柱状图或森林图'
                }
            ])
        
        return recommendations
    
    @staticmethod
    def is_chart_suitable(var_type, chart_type):
        """
        检查图表类型是否适合变量类型
        
        Parameters:
        -----------
        var_type : str
            变量类型
        chart_type : str
            图表类型
            
        Returns:
        --------
        tuple
            (是否适合, 原因)
        """
        # 不适合的组合
        unsuitable_combinations = {
            'categorical': ['boxplot', 'violin', 'qqplot', 'strip'],
            'binary': ['boxplot', 'violin', 'qqplot', 'strip'],
            'ordinal': ['boxplot', 'violin', 'qqplot', 'strip']
        }
        
        if var_type in unsuitable_combinations:
            if chart_type in unsuitable_combinations[var_type]:
                return False, f'{var_type}类型变量不适合使用{chart_type}'
        
        return True, None