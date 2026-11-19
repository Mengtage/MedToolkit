
import pandas as pd
import os
from typing import Dict, List, Tuple
from enum import Enum

class ReferenceValue(Enum):
    EXTREMELY_HIGH = "极高价值"
    HIGH = "较高价值"
    MODERATE = "一定价值"

class Reference:
    def __init__(self, data: Dict):
        self.pmid = data.get("PMID", "")
        self.publication_date = data.get("发表日期", "")
        self.journal_name = data.get("期刊名", "")
        self.impact_factor = data.get("期刊影响因子", "")
        self.first_author = data.get("第一作者名", "")
        self.abstract = data.get("摘要", "")
        self.key_data = data.get("关键数据", "")
        self.advantages_limitations = data.get("优势局限", "")
        self.future_directions = data.get("未来方向", "")
        self.link = data.get("文献链接", "")
        self.source = data.get("检索来源", "")
        self.title = data.get("标题", "")
        self.full_text_available = False
        self.value_classification = None

class ReferenceProcessor:
    def __init__(self, references_path: str):
        self.references_path = references_path
        self.references: List[Reference] = []
    
    def load_references(self) -&gt; List[Reference]:
        if not os.path.exists(self.references_path):
            raise FileNotFoundError(f"参考文献文件不存在: {self.references_path}")
        
        df = pd.read_excel(self.references_path) if self.references_path.endswith('.xlsx') else pd.read_csv(self.references_path)
        self.references = [Reference(row.to_dict()) for _, row in df.iterrows()]
        return self.references
    
    def classify_references(self, paper_title: str, llm_client) -&gt; Tuple[List[Reference], List[Reference], List[Reference]]:
        extremely_high_value = []
        high_value = []
        moderate_value = []
        
        for ref in self.references:
            prompt = f"""请根据以下论文标题和参考文献信息，对参考文献的价值进行分类。

论文标题: {paper_title}

参考文献信息:
标题: {ref.title}
摘要: {ref.abstract}
关键数据: {ref.key_data}

请从以下三个类别中选择一个:
1. 极高价值 - 与研究主题高度相关，方法学或结果具有重要参考意义
2. 较高价值 - 与研究主题相关，有一定参考价值
3. 一定价值 - 与研究主题有一定关联，可作为背景资料

请只返回类别编号（1、2或3），不要有其他文字。"""
            
            response = llm_client.generate(prompt, temperature=0.3, max_tokens=100)
            if "1" in response:
                ref.value_classification = ReferenceValue.EXTREMELY_HIGH
                extremely_high_value.append(ref)
            elif "2" in response:
                ref.value_classification = ReferenceValue.HIGH
                high_value.append(ref)
            else:
                ref.value_classification = ReferenceValue.MODERATE
                moderate_value.append(ref)
        
        return extremely_high_value, high_value, moderate_value
    
    def check_full_text_availability(self, references: List[Reference]) -&gt; List[Reference]:
        missing_full_text = []
        for ref in references:
            if not ref.full_text_available:
                missing_full_text.append(ref)
        return missing_full_text

