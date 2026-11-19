"""
结果导出模块
"""

import pandas as pd
from io import BytesIO
import zipfile


class Exporter:
    """
    结果导出类
    """

    @staticmethod
    def export_dataframe(df, format='csv'):
        """
        导出DataFrame

        Parameters:
        -----------
        df : pd.DataFrame
            要导出的数据框
        format : str
            'csv' 或 'excel'

        Returns:
        --------
        BytesIO
            文件流
        """
        output = BytesIO()
        
        if format == 'csv':
            df.to_csv(output, index=False, encoding='utf-8-sig')
        elif format == 'excel':
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
        
        output.seek(0)
        return output
    
    @staticmethod
    def export_multiple_sheets(sheets_dict, format='excel'):
        """
        导出多工作表Excel文件
        
        Parameters:
        -----------
        sheets_dict : dict
            { 'sheet_name': DataFrame }
        format : str
            'excel'
            
        Returns:
        --------
        BytesIO
            文件流
        """
        output = BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for sheet_name, df in sheets_dict.items():
                df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
        
        output.seek(0)
        return output
    
    @staticmethod
    def tableone_to_dataframe(tableone_result):
        """
        将TableOne结果转换为导出用的DataFrame
        """
        df = tableone_result['table']
        
        p_df = pd.DataFrame(tableone_result.get('p_values', []))
        
        return df, p_df
    
    @staticmethod
    def prepare_export_package(session_data):
        """
        准备完整的导出包
        """
        sheets = {}

        if 'data' in session_data and session_data['data'] is not None:
            if isinstance(session_data['data'], pd.DataFrame):
                sheets['Raw_Data'] = session_data['data']
            else:
                sheets['Raw_Data'] = pd.DataFrame(session_data['data'])

        if 'tableone' in session_data and session_data['tableone'] is not None:
            tableone = session_data['tableone']
            # tableone可能是 {'headers': [...], 'rows': [...], 'n': ...} 格式
            if isinstance(tableone, dict):
                if 'rows' in tableone and 'headers' in tableone:
                    try:
                        df = pd.DataFrame(tableone['rows'], columns=tableone['headers'])
                        sheets['TableOne'] = df
                    except:
                        pass
                elif 'table' in tableone:
                    if isinstance(tableone['table'], pd.DataFrame):
                        sheets['TableOne'] = tableone['table']
                    else:
                        sheets['TableOne'] = pd.DataFrame(tableone['table'])
            elif isinstance(tableone, pd.DataFrame):
                sheets['TableOne'] = tableone

        if 'missing_analysis' in session_data and session_data['missing_analysis'] is not None:
            missing_data = session_data['missing_analysis']
            if isinstance(missing_data, dict):
                if 'stats' in missing_data:
                    sheets['Missing_Data'] = pd.DataFrame(missing_data['stats'])
                elif 'details' in missing_data:
                    sheets['Missing_Data'] = pd.DataFrame(missing_data['details'])
                else:
                    sheets['Missing_Data'] = pd.DataFrame([missing_data])
            elif isinstance(missing_data, list):
                sheets['Missing_Data'] = pd.DataFrame(missing_data)

        if 'outlier_detection' in session_data and session_data['outlier_detection'] is not None:
            outlier_data = session_data['outlier_detection']
            if isinstance(outlier_data, dict):
                if 'stats' in outlier_data:
                    sheets['Outliers'] = pd.DataFrame(outlier_data['stats'])
                elif 'details' in outlier_data:
                    sheets['Outliers'] = pd.DataFrame(outlier_data['details'])
                elif 'outliers' in outlier_data:
                    # outliers是字典格式
                    rows = []
                    for var, data in outlier_data['outliers'].items():
                        row = {'variable': var}
                        row.update(data)
                        rows.append(row)
                    sheets['Outliers'] = pd.DataFrame(rows)
            elif isinstance(outlier_data, list):
                sheets['Outliers'] = pd.DataFrame(outlier_data)

        if 'distribution_diagnostics' in session_data and session_data['distribution_diagnostics'] is not None:
            dist_data = session_data['distribution_diagnostics']
            if isinstance(dist_data, dict):
                if 'results' in dist_data:
                    sheets['Distribution'] = pd.DataFrame(dist_data['results'])
                else:
                    sheets['Distribution'] = pd.DataFrame([dist_data])
            elif isinstance(dist_data, list):
                sheets['Distribution'] = pd.DataFrame(dist_data)

        if 'group_analysis' in session_data and session_data['group_analysis'] is not None:
            group_data = session_data['group_analysis']
            if isinstance(group_data, dict):
                if 'methods' in group_data:
                    sheets['Group_Analysis'] = pd.DataFrame(group_data['methods'])
                else:
                    sheets['Group_Analysis'] = pd.DataFrame([group_data])
            elif isinstance(group_data, list):
                sheets['Group_Analysis'] = pd.DataFrame(group_data)

        if 'correlation_analysis' in session_data and session_data['correlation_analysis'] is not None:
            corr_data = session_data['correlation_analysis']
            if isinstance(corr_data, dict):
                if 'details' in corr_data:
                    sheets['Correlation'] = pd.DataFrame(corr_data['details'])
                elif 'correlation_matrix' in corr_data:
                    sheets['Correlation'] = pd.DataFrame(corr_data['correlation_matrix'])
            elif isinstance(corr_data, list):
                sheets['Correlation'] = pd.DataFrame(corr_data)

        if 'imputation_comparison' in session_data and session_data['imputation_comparison'] is not None:
            mice_data = session_data['imputation_comparison']
            if isinstance(mice_data, dict):
                if 'comparison' in mice_data:
                    sheets['MICE_Comparison'] = pd.DataFrame(mice_data['comparison'])
                else:
                    sheets['MICE_Comparison'] = pd.DataFrame([mice_data])
            elif isinstance(mice_data, list):
                sheets['MICE_Comparison'] = pd.DataFrame(mice_data)

        return sheets

    @staticmethod
    def export_to_zip(sheets_dict):
        """
        将多个DataFrame导出为zip文件

        Parameters:
        -----------
        sheets_dict : dict
            字典，键为sheet名称，值为DataFrame

        Returns:
        --------
        BytesIO
            zip文件流
        """
        output = BytesIO()
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zf:
            for sheet_name, df in sheets_dict.items():
                if isinstance(df, pd.DataFrame) and not df.empty:
                    csv_buffer = BytesIO()
                    df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
                    csv_buffer.seek(0)
                    safe_name = sheet_name.replace('/', '_').replace('\\', '_')[:50]
                    zf.writestr(f'{safe_name}.csv', csv_buffer.read())

        output.seek(0)
        return output
