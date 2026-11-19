
from typing import List, Dict
from deepseek_client import DeepSeekClient
from reference_processor import Reference

class PaperWriter:
    def __init__(self, llm_client: DeepSeekClient, references: List[Reference]):
        self.llm_client = llm_client
        self.references = references
    
    def _format_references_for_prompt(self) -&gt; str:
        ref_texts = []
        for i, ref in enumerate(self.references, 1):
            ref_text = f"""[参考文献{i}]
标题: {ref.title}
作者: {ref.first_author}
期刊: {ref.journal_name}
摘要: {ref.abstract}
关键数据: {ref.key_data}
优势局限: {ref.advantages_limitations}
未来方向: {ref.future_directions}
"""
            ref_texts.append(ref_text)
        return "\n".join(ref_texts)
    
    def write_introduction(self, paper_title: str, research_purpose: str) -&gt; Dict[str, str]:
        prompt = f"""请根据以下信息撰写SCI论文引言部分，要求中英文双语对照。

论文标题: {paper_title}
研究目的: {research_purpose}

参考文献信息:
{self._format_references_for_prompt()}

要求:
1. 参照SCI期刊标准，行文严谨、流畅、专业
2. 介绍本研究领域，重点解释本研究的价值和重要性
3. 最后一段介绍本研究的研究目的、假设和主要终点
4. 每一句都需要引用参考文献（在正文中用括号标注参考文献编号）
5. 禁止虚构、捏造、篡改等学术不端行为
6. 请提供中英文对照版本，中文在前，英文在后

请按以下格式输出:
【中文引言】
[中文内容]

【英文引言】
[英文内容]
"""
        response = self.llm_client.generate(prompt, temperature=0.7, max_tokens=4000)
        return self._parse_bilingual_response(response, "引言", "Introduction")
    
    def write_methods(self, research_protocol: str) -&gt; Dict[str, str]:
        prompt = f"""请根据以下研究方案撰写SCI论文方法部分，要求中英文双语对照。

研究方案:
{research_protocol}

要求:
1. 以符合SCI格式的方式撰写
2. 结构清晰，包括研究设计、研究对象、干预措施、观察指标、统计分析等部分
3. 请提供中英文对照版本，中文在前，英文在后

请按以下格式输出:
【中文方法】
[中文内容]

【英文方法】
[英文内容]
"""
        response = self.llm_client.generate(prompt, temperature=0.7, max_tokens=4000)
        return self._parse_bilingual_response(response, "方法", "Methods")
    
    def write_results(self, analysis_report: str) -&gt; Dict[str, str]:
        prompt = f"""请根据以下试验数据分析结果撰写SCI论文结果部分，要求中英文双语对照。

分析报告:
{analysis_report}

要求:
1. 以符合SCI格式的方式撰写
2. 客观描述研究结果，不要进行解释或讨论
3. 请提供中英文对照版本，中文在前，英文在后

请按以下格式输出:
【中文结果】
[中文内容]

【英文结果】
[英文内容]
"""
        response = self.llm_client.generate(prompt, temperature=0.7, max_tokens=4000)
        return self._parse_bilingual_response(response, "结果", "Results")
    
    def write_discussion(self, paper_title: str) -&gt; Dict[str, str]:
        prompt = f"""请根据以下信息撰写SCI论文讨论部分，要求中英文双语对照。

论文标题: {paper_title}

参考文献信息:
{self._format_references_for_prompt()}

要求:
1. 第一段总结本研究结果
2. 第二段对比本研究结果与既往类似研究的相似/不同，以及相应的原因
3. 第三段反思得出该结果的潜在机制，包括药理机制、生理机制等
4. 第四段反思本研究的局限性
5. 请提供中英文对照版本，中文在前，英文在后

请按以下格式输出:
【中文讨论】
[中文内容]

【英文讨论】
[英文内容]
"""
        response = self.llm_client.generate(prompt, temperature=0.7, max_tokens=4000)
        return self._parse_bilingual_response(response, "讨论", "Discussion")
    
    def write_conclusion(self) -&gt; Dict[str, str]:
        prompt = f"""请根据以下信息撰写SCI论文结论部分，要求中英文双语对照。

参考文献信息:
{self._format_references_for_prompt()}

要求:
1. 用2句话概括研究所得结果及意义
2. 请提供中英文对照版本，中文在前，英文在后

请按以下格式输出:
【中文结论】
[中文内容]

【英文结论】
[英文内容]
"""
        response = self.llm_client.generate(prompt, temperature=0.7, max_tokens=1000)
        return self._parse_bilingual_response(response, "结论", "Conclusion")
    
    def write_acknowledgements(self) -&gt; Dict[str, str]:
        chinese_ack = "本研究感谢[姓名1]、[姓名2]在研究过程中提供的帮助和支持。"
        english_ack = "We thank [Name1], [Name2] for their assistance and support during this study."
        return {"chinese": chinese_ack, "english": english_ack}
    
    def write_references(self) -&gt; Dict[str, str]:
        chinese_refs = []
        english_refs = []
        for i, ref in enumerate(self.references, 1):
            chinese_ref = f"{i}. {ref.first_author}. {ref.title}. {ref.journal_name}. {ref.publication_date}."
            english_ref = f"{i}. {ref.first_author}. {ref.title}. {ref.journal_name}. {ref.publication_date}."
            chinese_refs.append(chinese_ref)
            english_refs.append(english_ref)
        return {"chinese": "\n".join(chinese_refs), "english": "\n".join(english_refs)}
    
    def write_figure_legends(self, figures_info: List[Dict]) -&gt; List[Dict]:
        legends = []
        for fig in figures_info:
            prompt = f"""请为以下图表撰写中英文对照的图注。

图表信息:
编号: {fig.get('number', '')}
标题: {fig.get('title', '')}
描述: {fig.get('description', '')}
数据: {fig.get('data', '')}

要求:
1. 包括图片标题、介绍、缩写等信息
2. 请提供中英文对照版本

请按以下格式输出:
【中文图注】
[中文内容]

【英文图注】
[英文内容]
"""
            response = self.llm_client.generate(prompt, temperature=0.7, max_tokens=1000)
            parsed = self._parse_bilingual_response(response, "图注", "Figure Legend")
            legends.append({
                "number": fig.get('number', ''),
                "chinese_title": fig.get('title', ''),
                "english_title": fig.get('title', ''),
                "chinese_description": parsed.get("chinese", ""),
                "english_description": parsed.get("english", "")
            })
        return legends
    
    def write_supplement_tables(self, tables_info: List[Dict]) -&gt; List[Dict]:
        tables = []
        for tbl in tables_info:
            prompt = f"""请为以下附表撰写中英文对照的附表注。

附表信息:
编号: {tbl.get('number', '')}
标题: {tbl.get('title', '')}
描述: {tbl.get('description', '')}
数据: {tbl.get('data', '')}

要求:
1. 包括表格标题、介绍、缩写等信息
2. 请提供中英文对照版本

请按以下格式输出:
【中文附表注】
[中文内容]

【英文附表注】
[英文内容]
"""
            response = self.llm_client.generate(prompt, temperature=0.7, max_tokens=1000)
            parsed = self._parse_bilingual_response(response, "附表注", "Supplement Table")
            tables.append({
                "number": tbl.get('number', ''),
                "chinese_title": tbl.get('title', ''),
                "english_title": tbl.get('title', ''),
                "chinese_description": parsed.get("chinese", ""),
                "english_description": parsed.get("english", "")
            })
        return tables
    
    def _parse_bilingual_response(self, response: str, chinese_label: str, english_label: str) -&gt; Dict[str, str]:
        chinese_start = response.find(f"【中文{chinese_label}】")
        english_start = response.find(f"【英文{english_label}】")
        
        if chinese_start == -1 or english_start == -1:
            return {"chinese": response, "english": response}
        
        chinese_content = response[chinese_start + len(f"【中文{chinese_label}】"):english_start].strip()
        english_content = response[english_start + len(f"【英文{english_label}】"):].strip()
        
        return {"chinese": chinese_content, "english": english_content}

