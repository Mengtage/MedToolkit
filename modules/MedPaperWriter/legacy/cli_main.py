
import os
import sys
from typing import Optional
from deepseek_client import DeepSeekClient
from reference_processor import ReferenceProcessor, Reference
from paper_writer import PaperWriter
from word_generator import WordGenerator

class MedPaperWriter:
    def __init__(self):
        self.base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.references_path = os.path.join(self.base_path, "MedPaperHunter", "output")
        self.medstat_path = os.path.join(self.base_path, "MedStat", "output")
        self.llm_client = None
        self.reference_processor = None
        self.paper_writer = None
        self.target_journal = ""
        self.paper_title = ""
        self.research_protocol = ""
        self.analysis_report = ""
    
    def initialize(self):
        print("=" * 60)
        print("医学论文初稿编写自动化工具")
        print("=" * 60)
        
        self.llm_client = DeepSeekClient()
        print("[1/5] 已加载DeepSeek API客户端")
        
        ref_file = self._find_reference_file()
        if ref_file:
            self.reference_processor = ReferenceProcessor(ref_file)
            self.reference_processor.load_references()
            print(f"[2/5] 已加载参考文献: {len(self.reference_processor.references)} 篇")
        else:
            print("[警告] 未找到参考文献文件")
        
        self.analysis_report = self._load_analysis_report()
        print("[3/5] 已加载试验数据分析报告")
    
    def _find_reference_file(self) -&gt; Optional[str]:
        if not os.path.exists(self.references_path):
            return None
        files = os.listdir(self.references_path)
        for f in files:
            if f.endswith('.xlsx') or f.endswith('.csv'):
                return os.path.join(self.references_path, f)
        return None
    
    def _load_analysis_report(self) -&gt; str:
        if not os.path.exists(self.medstat_path):
            return ""
        report_path = os.path.join(self.medstat_path, "analysis_report.txt")
        if os.path.exists(report_path):
            with open(report_path, 'r', encoding='utf-8') as f:
                return f.read()
        return ""
    
    def step1_overview_materials(self):
        print("\n" + "=" * 60)
        print("步骤1: 总览已有材料")
        print("=" * 60)
        
        if self.reference_processor and self.reference_processor.references:
            print(f"\n参考文献信息:")
            print(f"  - 数量: {len(self.reference_processor.references)} 篇")
            print(f"  - 来源: {self.references_path}")
        
        if self.analysis_report:
            print(f"\n试验数据分析报告:")
            print(f"  - 已加载")
            print(f"  - 来源: {self.medstat_path}")
    
    def step2_ask_user_info(self):
        print("\n" + "=" * 60)
        print("步骤2: 收集用户信息")
        print("=" * 60)
        
        self.target_journal = input("\n请输入目标期刊标题: ").strip()
        self.paper_title = input("请输入论文标题: ").strip()
        
        has_protocol = input("是否有研究方案可以提供？(y/n): ").strip().lower()
        if has_protocol == 'y':
            protocol_path = input("请输入研究方案文件路径: ").strip()
            if os.path.exists(protocol_path):
                with open(protocol_path, 'r', encoding='utf-8') as f:
                    self.research_protocol = f.read()
                print("研究方案已加载")
            else:
                print("文件不存在，请手动输入研究方案:")
                self.research_protocol = input().strip()
        else:
            print("请输入研究方案（按Ctrl+D或Ctrl+Z结束输入）:")
            try:
                lines = []
                while True:
                    line = input()
                    lines.append(line)
                self.research_protocol = '\n'.join(lines)
            except EOFError:
                pass
    
    def step3_classify_and_check_references(self) -&gt; bool:
        print("\n" + "=" * 60)
        print("步骤3: 参考文献分类与检查")
        print("=" * 60)
        
        if not self.reference_processor or not self.reference_processor.references:
            print("错误: 没有参考文献可处理")
            return False
        
        print("\n正在对参考文献进行分类...")
        extremely_high, high, moderate = self.reference_processor.classify_references(
            self.paper_title, self.llm_client
        )
        
        print(f"\n分类结果:")
        print(f"  - 极高价值: {len(extremely_high)} 篇")
        print(f"  - 较高价值: {len(high)} 篇")
        print(f"  - 一定价值: {len(moderate)} 篇")
        
        print("\n正在检查极高价值文献的全文获取情况...")
        missing = self.reference_processor.check_full_text_availability(extremely_high)
        
        if missing:
            print("\n" + "!" * 60)
            print("警告: 以下极高价值文献无法获取全文，请补充:")
            for ref in missing:
                print(f"  - {ref.title} (PMID: {ref.pmid})")
            print("!" * 60)
            return False
        else:
            print("\n" + "*" * 60)
            print("资料准备充足，请批准开始")
            print("*" * 60)
            return True
    
    def step4_generate_paper(self):
        print("\n" + "=" * 60)
        print("步骤4: 生成论文")
        print("=" * 60)
        
        approval = input("\n请批准开始生成论文？(y/n): ").strip().lower()
        if approval != 'y':
            print("操作已取消")
            return
        
        output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "medical_paper.docx")
        word_gen = WordGenerator(output_path)
        self.paper_writer = PaperWriter(self.llm_client, self.reference_processor.references)
        
        print("\n正在生成论文各部分...")
        
        word_gen.add_title(self.paper_title, self.paper_title)
        word_gen.add_authors("[作者姓名]")
        
        print("  [1/12] 生成标题和作者... 完成")
        
        print("  [2/12] 生成摘要...")
        abstract_prompt = f"""请为以下论文撰写中英文对照的摘要。
        
论文标题: {self.paper_title}
目标期刊: {self.target_journal}

要求:
1. 结构清晰，包括目的、方法、结果、结论
2. 中英文对照
"""
        abstract_response = self.llm_client.generate(abstract_prompt, max_tokens=2000)
        word_gen.add_abstract("摘要内容", "Abstract content")
        
        print("  [3/12] 生成关键词...")
        keywords_prompt = f"请为论文'{self.paper_title}'提供5-8个中英文对照的关键词。"
        keywords_response = self.llm_client.generate(keywords_prompt, max_tokens=500)
        word_gen.add_keywords("关键词1, 关键词2", "Keyword1, Keyword2")
        
        print("  [4/12] 生成引言...")
        intro = self.paper_writer.write_introduction(self.paper_title, "研究目的")
        word_gen.add_section("引言", "Introduction", intro["chinese"], intro["english"])
        
        print("  [5/12] 生成方法...")
        methods = self.paper_writer.write_methods(self.research_protocol)
        word_gen.add_section("方法", "Methods", methods["chinese"], methods["english"])
        
        print("  [6/12] 生成结果...")
        results = self.paper_writer.write_results(self.analysis_report)
        word_gen.add_section("结果", "Results", results["chinese"], results["english"])
        
        print("  [7/12] 生成讨论...")
        discussion = self.paper_writer.write_discussion(self.paper_title)
        word_gen.add_section("讨论", "Discussion", discussion["chinese"], discussion["english"])
        
        print("  [8/12] 生成结论...")
        conclusion = self.paper_writer.write_conclusion()
        word_gen.add_section("结论", "Conclusion", conclusion["chinese"], conclusion["english"])
        
        print("  [9/12] 生成致谢...")
        ack = self.paper_writer.write_acknowledgements()
        word_gen.add_section("致谢", "Acknowledgements", ack["chinese"], ack["english"])
        
        print("  [10/12] 生成参考文献...")
        refs = self.paper_writer.write_references()
        word_gen.add_section("参考文献", "References", refs["chinese"], refs["english"])
        
        print("  [11/12] 生成图注...")
        figures_info = [{"number": 1, "title": "图1", "description": "主要研究结果"}]
        figure_legends = self.paper_writer.write_figure_legends(figures_info)
        for legend in figure_legends:
            word_gen.add_figure_legend(
                legend["number"],
                legend["chinese_title"],
                legend["english_title"],
                legend["chinese_description"],
                legend["english_description"]
            )
        
        print("  [12/12] 生成附表注...")
        tables_info = [{"number": 1, "title": "附表1", "description": "补充数据"}]
        supplement_tables = self.paper_writer.write_supplement_tables(tables_info)
        for table in supplement_tables:
            word_gen.add_supplement_table(
                table["number"],
                table["chinese_title"],
                table["english_title"],
                table["chinese_description"],
                table["english_description"]
            )
        
        word_gen.save()
        print(f"\n论文已保存至: {output_path}")
        print("\n" + "=" * 60)
        print("完成!")
        print("=" * 60)
    
    def run(self):
        try:
            self.initialize()
            self.step1_overview_materials()
            self.step2_ask_user_info()
            if self.step3_classify_and_check_references():
                self.step4_generate_paper()
        except Exception as e:
            print(f"\n错误: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    app = MedPaperWriter()
    app.run()

