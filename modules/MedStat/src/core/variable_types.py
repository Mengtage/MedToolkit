"""
变量类型检测和管理模块
"""

import pandas as pd
import numpy as np


class VariableTypeDetector:
    """
    自动检测和管理变量类型
    """
    
    # 常见变量名与类型映射
    COMMON_TYPE_MAPS = {
        'text': ['name', 'names', '姓名', 'patient_name', 'patientid', 'id', 'pid', 
                'subject_id', 'record_id'],
        'categorical': ['sex', 'gender', '性别', 'group', 'group_id', 'grouping', 
                      'treatment', 'treat', 'arm', 'disease', 'diagnosis', 'stage', 
                      'grade', 'status', 'outcome', 'smoke', 'smoking', 'drink', 
                      'alcohol', 'hypertension', 'diabetes', 'comorbidity', 'race', 
                      'ethnicity', 'education', 'occupation', 'marital_status',
                      'yes_no', 'flag', 'indicator'],
        'numeric_continuous': ['age', '年龄', 'height', 'weight', 'bmi', 'sbp', 
                             'dbp', 'blood_pressure', 'heart_rate', 'cholesterol', 
                             'hdl', 'ldl', 'triglyceride', 'glucose', 'hemoglobin', 
                             'creatinine', 'bilirubin', 'albumin', 'duration', 
                             'time', 'score', 'value', 'level', 'count', 'percentage', 
                             'ratio', 'rate'],
        'datetime': ['date', 'dates', 'birthday', 'birth_date', 'diagnosis_date', 
                   'admission_date', 'discharge_date', 'follow_up_date', 'visit_date'],
    }
    
    def __init__(self, df):
        """
        初始化变量类型检测器
        
        Parameters:
        -----------
        df : pd.DataFrame
            输入数据
        """
        self.df = df
        self.type_mapping = {}
        self._detect_types()
    
    def _detect_types(self):
        """
        自动检测变量类型
        """
        for col in self.df.columns:
            col_lower = col.lower().strip()
            detected = False
            
            # 首先检查常见变量名
            for dtype, keywords in self.COMMON_TYPE_MAPS.items():
                if col_lower in keywords or any(kw in col_lower for kw in keywords):
                    self.type_mapping[col] = dtype
                    detected = True
                    break
            
            if detected:
                continue
            
            # 默认类型检测逻辑
            dtype = self.df[col].dtype
            unique_count = self.df[col].nunique(dropna=True)
            total_count = len(self.df[col])
            
            if pd.api.types.is_datetime64_any_dtype(dtype):
                self.type_mapping[col] = 'datetime'
            elif pd.api.types.is_numeric_dtype(dtype):
                if unique_count <= 10 or (unique_count / total_count < 0.05 and unique_count <= 20):
                    self.type_mapping[col] = 'numeric_discrete'
                else:
                    self.type_mapping[col] = 'numeric_continuous'
            elif pd.api.types.is_bool_dtype(dtype):
                self.type_mapping[col] = 'boolean'
            elif dtype == 'object':
                if unique_count <= 10 or (unique_count / total_count < 0.05 and unique_count <= 50):
                    self.type_mapping[col] = 'categorical'
                else:
                    self.type_mapping[col] = 'text'
            else:
                self.type_mapping[col] = 'text'
    
    def get_types(self):
        """
        获取类型映射字典
        
        Returns:
        --------
        dict
            列名到类型的映射
        """
        return self.type_mapping.copy()
    
    def set_type(self, column, new_type):
        """
        设置特定列的类型
        
        Parameters:
        -----------
        column : str
            列名
        new_type : str
            新类型 ('numeric_continuous', 'numeric_discrete', 'categorical', 
                     'datetime', 'boolean', 'text')
        """
        valid_types = ['numeric_continuous', 'numeric_discrete', 'categorical', 
                      'datetime', 'boolean', 'text']
        if new_type not in valid_types:
            raise ValueError(f"无效的类型: {new_type}. 必须是: {valid_types}")
        
        self.type_mapping[column] = new_type
    
    def get_columns_by_type(self, dtype):
        """
        获取特定类型的所有列
        
        Parameters:
        -----------
        dtype : str or list
            要筛选的类型
            
        Returns:
        --------
        list
            匹配的列名列表
        """
        if isinstance(dtype, str):
            dtype = [dtype]
        return [col for col, t in self.type_mapping.items() if t in dtype]
    
    def get_type_label(self, dtype):
        """
        获取类型的中文标签
        """
        labels = {
            'numeric_continuous': '连续数值',
            'numeric_discrete': '离散数值',
            'categorical': '分类',
            'datetime': '日期时间',
            'boolean': '布尔',
            'text': '文本'
        }
        return labels.get(dtype, '未知')
    
    def convert_column_type(self, df, column, target_type):
        """
        尝试转换列的数据类型
        
        Parameters:
        -----------
        df : pd.DataFrame
            数据框
        column : str
            列名
        target_type : str
            目标类型
            
        Returns:
        --------
        pd.DataFrame
            更新后的数据框
        """
        df = df.copy()
        
        try:
            if target_type in ['numeric_continuous', 'numeric_discrete']:
                df[column] = pd.to_numeric(df[column], errors='coerce')
            elif target_type == 'datetime':
                df[column] = pd.to_datetime(df[column], errors='coerce')
            elif target_type == 'categorical':
                df[column] = df[column].astype('category')
            elif target_type == 'boolean':
                df[column] = df[column].astype(bool)
            elif target_type == 'text':
                df[column] = df[column].astype(str)
        except Exception as e:
            raise Exception(f"类型转换失败: {str(e)}")
        
        return df
