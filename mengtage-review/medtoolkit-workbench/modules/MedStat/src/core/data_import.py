"""
数据导入模块
"""

import pandas as pd
import os
from io import BytesIO
from werkzeug.datastructures import FileStorage


class DataImporter:
    """
    数据导入类，支持 CSV 和 Excel 文件导入
    """
    
    def __init__(self):
        self.allowed_extensions = {'csv', 'xlsx', 'xls'}
        self.na_values = ['', 'NA', 'N/A', 'n/a', 'na', 'null', 'NULL',
                         'None', 'none', 'NaN', 'nan', '.', '-', '-999',
                         '-9999', 'missing', 'Missing', 'MISSING', 'N/A']
    
    def is_allowed_file(self, filename):
        """
        检查文件扩展名是否允许
        """
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in self.allowed_extensions
    
    def read_file(self, file, filename):
        """
        从文件对象读取数据
        
        Parameters:
        -----------
        file : FileStorage or file-like object
            文件对象
        filename : str
            文件名
            
        Returns:
        --------
        pd.DataFrame
            读取的数据
        """
        if not self.is_allowed_file(filename):
            raise ValueError(f"不支持的文件格式: {filename}")
        
        file_ext = filename.rsplit('.', 1)[1].lower()
        
        try:
            if file_ext == 'csv':
                df = pd.read_csv(
                    file,
                    na_values=self.na_values,
                    keep_default_na=True
                )
            else:
                df = pd.read_excel(file)
                df = df.replace(self.na_values, pd.NA)
            
            return df
        except Exception as e:
            raise Exception(f"文件读取失败: {str(e)}")
    
    def read_from_path(self, filepath):
        """
        从文件路径读取数据
        
        Parameters:
        -----------
        filepath : str
            文件路径
            
        Returns:
        --------
        pd.DataFrame
            读取的数据
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"文件不存在: {filepath}")
        
        filename = os.path.basename(filepath)
        with open(filepath, 'rb') as f:
            return self.read_file(f, filename)
