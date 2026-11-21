"""
文档生成器服务
生成符合格式要求的Word文档

设计依据：MedPaperWriter 设计审查 3.1 / 6.4 节
    - 导出件不能含未声明的占位内容：缺摘要、缺参考文献都要显式写出并回传 warnings
    - 参考文献从会话的结构化条目渲染，而不是固定传空列表
    - 未撰写/未审核的章节要在导出结果里明确列出，避免"看起来完整"
"""

from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from typing import Any, Dict, List

from core.reference_formatter import ReferenceFormatter
from core.translator import translator
from services.logger import logger


LANGUAGE_ALIASES = {
    "中文": "中文", "chinese": "中文", "zh": "中文", "zh-cn": "中文",
    "英文": "英文", "english": "英文", "en": "英文",
    "中英文双语": "中英文双语", "bilingual": "中英文双语", "双语": "中英文双语",
}

ABSTRACT_TITLES = ("摘要", "abstract")
KEYWORD_TITLES = ("关键词", "关键字", "keywords", "key words")


class DocumentGenerator:
    """Word文档生成器"""

    def __init__(self):
        self.doc = Document()
        self.ref_formatter = ReferenceFormatter("vancouver")
        self.progress_callback = None

    # ------------------------------------------------------------------ 基础设施
    def set_progress_callback(self, callback):
        self.progress_callback = callback

    def _report_progress(self, message, progress=0):
        if self.progress_callback:
            self.progress_callback(message, progress)

    @staticmethod
    def _normalize_language(language: str) -> str:
        return LANGUAGE_ALIASES.get((language or "").strip().lower(), language or "中文")

    def _set_east_asian_font(self, run, font_name: str = "宋体"):
        """设置中文字体（rPr 缺失时安全跳过，避免 AttributeError）"""
        try:
            run.font.name = "Times New Roman"
            rpr = run._element.get_or_add_rPr()
            rfonts = rpr.get_or_add_rFonts()
            rfonts.set(qn("w:eastAsia"), font_name)
        except Exception:  # pragma: no cover - 仅样式兼容
            pass

    def set_chinese_style(self):
        """设置中文样式"""
        style = self.doc.styles['Normal']
        style.font.name = 'Times New Roman'
        try:
            rpr = style.element.get_or_add_rPr()
            rpr.get_or_add_rFonts().set(qn('w:eastAsia'), '宋体')
        except Exception:  # pragma: no cover
            pass
        style.font.size = Pt(12)
        style.paragraph_format.line_spacing = 1.5
        style.paragraph_format.first_line_indent = Inches(0.3)

    def set_english_style(self):
        """设置英文样式"""
        style = self.doc.styles['Normal']
        style.font.name = 'Times New Roman'
        style.font.size = Pt(12)
        style.paragraph_format.line_spacing = 1.5
        style.paragraph_format.first_line_indent = Inches(0.3)

    # ------------------------------------------------------------------ 内容元素
    def add_title(self, title: str, subtitle: str = ""):
        heading = self.doc.add_heading(title, level=0)
        heading.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        for run in heading.runs:
            self._set_east_asian_font(run)
            run.font.size = Pt(16)
            run.font.bold = True

        if subtitle:
            sub_heading = self.doc.add_paragraph(subtitle)
            sub_heading.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
            for run in sub_heading.runs:
                run.font.name = 'Times New Roman'
                run.font.size = Pt(12)

    def add_section_heading(self, text: str, level: int = 1):
        heading = self.doc.add_heading(text, level=level)
        for run in heading.runs:
            self._set_east_asian_font(run)
            run.font.size = Pt(14 if level == 1 else 12)

    def add_paragraph(self, text: str, indent: bool = True):
        para = self.doc.add_paragraph()
        if indent:
            para.paragraph_format.first_line_indent = Inches(0.3)
        run = para.add_run(text)
        self._set_east_asian_font(run)
        run.font.size = Pt(12)
        return para

    def add_note(self, text: str):
        """导出件中的显式标注（占位/待补充说明），用斜体与正文区分"""
        para = self.doc.add_paragraph()
        run = para.add_run(text)
        run.font.name = 'Times New Roman'
        run.font.size = Pt(10)
        run.italic = True
        return para

    def add_bilingual_paragraph(self, chinese: str, english: str):
        para = self.doc.add_paragraph()
        para.paragraph_format.first_line_indent = Inches(0.3)

        if chinese:
            run_zh = para.add_run(chinese)
            self._set_east_asian_font(run_zh)
            run_zh.font.size = Pt(12)
        if chinese and english:
            para.add_run("\n")
        if english:
            run_en = para.add_run(english)
            run_en.font.name = 'Times New Roman'
            run_en.font.size = Pt(12)

    def add_table(self, data: list, headers: list = None):
        if not data:
            return

        rows = len(data) + (1 if headers else 0)
        cols = len(data[0]) if isinstance(data[0], list) else 1

        table = self.doc.add_table(rows=rows, cols=cols)
        table.style = 'Table Grid'

        current_row = 0

        if headers:
            for i, header in enumerate(headers):
                cell = table.rows[current_row].cells[i]
                cell.text = header
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        run.font.bold = True
                        run.font.name = 'Times New Roman'
                        run.font.size = Pt(10)
            current_row += 1

        for row_data in data:
            if isinstance(row_data, list):
                for i, cell_data in enumerate(row_data):
                    cell = table.rows[current_row].cells[i]
                    cell.text = str(cell_data)
                    for paragraph in cell.paragraphs:
                        for run in paragraph.runs:
                            run.font.name = 'Times New Roman'
                            run.font.size = Pt(10)
            current_row += 1

        self._apply_three_line_borders(table)
        return table

    @staticmethod
    def _apply_three_line_borders(table):
        """应用医学 SCI 标准三线表边框（顶线 1.5pt、表头底线 0.75pt、底线 1.5pt，无竖线）"""
        def _border(container, edge, val="nil", sz=None):
            el = OxmlElement(f"w:{edge}")
            el.set(qn("w:val"), val)
            if sz is not None:
                el.set(qn("w:sz"), str(sz))
                el.set(qn("w:space"), "0")
                el.set(qn("w:color"), "000000")
            container.append(el)

        tbl_pr = table._tbl.tblPr
        for old in tbl_pr.findall(qn("w:tblBorders")):
            tbl_pr.remove(old)
        borders = OxmlElement("w:tblBorders")
        _border(borders, "top", "single", 12)
        _border(borders, "left", "nil")
        _border(borders, "bottom", "single", 12)
        _border(borders, "right", "nil")
        _border(borders, "insideH", "nil")
        _border(borders, "insideV", "nil")
        tbl_pr.append(borders)
        if table.rows:
            for c in table.rows[0].cells:
                tc_pr = c._tc.get_or_add_tcPr()
                for old in tc_pr.findall(qn("w:tcBorders")):
                    tc_pr.remove(old)
                cb = OxmlElement("w:tcBorders")
                _border(cb, "top", "single", 12)
                _border(cb, "bottom", "single", 6)
                _border(cb, "left", "nil")
                _border(cb, "right", "nil")
                tc_pr.append(cb)

    def add_references(self, references: List[Dict[str, Any]], style: str = "vancouver",
                       language: str = "中文") -> List[str]:
        """添加参考文献；返回警告列表（未提供条目时给出明确说明）"""
        warnings: List[str] = []
        self.doc.add_page_break()
        if language == "英文":
            self.add_section_heading("References", level=1)
        elif language == "中英文双语":
            self.add_section_heading("参考文献 / References", level=1)
        else:
            self.add_section_heading("参考文献", level=1)

        self.ref_formatter = ReferenceFormatter(style)

        if not references:
            self.add_note(
                "本稿未提供结构化参考文献条目。请在导出前补充参考文献，"
                "或从文献检索模块导入带 PMID/DOI 的记录后重新导出。"
            )
            warnings.append("未提供参考文献条目，参考文献章节已明确标注为待补充")
            return warnings

        for index, ref in enumerate(references, 1):
            formatted = self.ref_formatter.format_reference(ref)
            para = self.doc.add_paragraph()
            para.paragraph_format.first_line_indent = Inches(-0.3)
            para.paragraph_format.left_indent = Inches(0.3)

            run = para.add_run(f"{index}. {formatted}")
            self._set_east_asian_font(run)
            run.font.size = Pt(10)

        return warnings

    def save(self, output_path: str):
        self.doc.save(output_path)

    # ------------------------------------------------------------------ 论文组装
    def generate_paper(
        self,
        session,
        output_path: str,
        language: str = "中文",
        ref_style: str = "vancouver"
    ) -> Dict[str, Any]:
        """生成完整论文

        Returns:
            {"warnings": [...], "sections_written": int, "empty_sections": [...],
             "references": int, "language": str}
        """
        language = self._normalize_language(language)
        warnings: List[str] = []

        self._report_progress("开始生成文档...", 5)

        if language == "英文":
            self.set_english_style()
        else:
            self.set_chinese_style()

        title = session.research_topic or session.research_question or "医学论文"
        research_context = title
        if language == "英文":
            self._report_progress("正在翻译标题...", 8)
            title = translator.translate_to_english(title, research_context)
        self.add_title(title, "")

        self.doc.add_paragraph()
        self.add_paragraph("[作者姓名]", indent=False)
        self.add_paragraph("[单位地址]", indent=False)
        self.doc.add_paragraph()

        warnings += self._write_front_matter(session, language)
        self.doc.add_paragraph()

        self._report_progress("正在处理章节内容...", 15)

        if session.outline:
            content_warnings = self._generate_content_from_outline(session.outline, language, research_context)
        else:
            content_warnings = self._generate_sections(session.sections, language, research_context)
        warnings += content_warnings["warnings"]

        self._report_progress("正在添加参考文献...", 90)
        warnings += self.add_references(
            getattr(session, "references", []) or [], style=ref_style, language=language
        )

        # 翻译失败时不能悄悄保留原文：语言不符是必须告知的导出缺陷
        if getattr(translator, "last_error", None):
            warnings.append(f"部分内容翻译失败（{translator.last_error}），导出件已保留原文")
            translator.last_error = None

        # 未审核章节提示：导出不等于通过审核，必须让用户知道
        unapproved = self._unapproved_titles(session)
        if unapproved:
            warnings.append(f"{len(unapproved)} 个章节尚未审核通过：" + "、".join(unapproved[:6]))

        self._report_progress("正在保存文档...", 95)
        self.save(output_path)
        self._report_progress("文档生成完成", 100)

        logger.info(
            "[document_generator] export finished",
            output_path=output_path,
            warnings=len(warnings),
            sections_written=content_warnings["written"],
        )

        return {
            "warnings": warnings,
            "sections_written": content_warnings["written"],
            "empty_sections": content_warnings["empty"],
            "references": len(getattr(session, "references", []) or []),
            "language": language,
        }

    def _write_front_matter(self, session, language: str) -> List[str]:
        """写摘要与关键词：优先取提纲中的对应章节，没有就显式标注缺失"""
        warnings: List[str] = []
        abstract_zh, abstract_en = self._find_section(session, ABSTRACT_TITLES)
        keywords_zh, keywords_en = self._find_section(session, KEYWORD_TITLES)

        if language == "英文":
            self.add_section_heading("Abstract", level=1)
            if abstract_en:
                self.add_paragraph(abstract_en)
            elif abstract_zh:
                self.add_paragraph(translator.translate_to_english(abstract_zh, session.research_topic or ""))
                warnings.append("英文摘要由中文摘要机器翻译生成，需人工核对")
            else:
                self.add_note("[Abstract pending: no abstract section found in the outline]")
                warnings.append("未找到摘要章节，导出件中的摘要是待补充标记")

            self.add_section_heading("Keywords", level=2)
            if keywords_en or keywords_zh:
                self.add_paragraph(keywords_en or keywords_zh, indent=False)
            else:
                self.add_note("[Keywords pending: please provide 3-8 keywords]")
                warnings.append("未找到关键词，导出件中的关键词是待补充标记")

        elif language == "中英文双语":
            self.add_section_heading("摘要 / Abstract", level=1)
            if abstract_zh:
                self.add_paragraph(abstract_zh)
            else:
                self.add_note("【摘要待补充：提纲中未找到摘要章节】")
                warnings.append("未找到中文摘要，导出件中的摘要是待补充标记")
            if abstract_en:
                self.add_paragraph(abstract_en)
            elif abstract_zh:
                self.add_paragraph(translator.translate_to_english(abstract_zh, session.research_topic or ""))
                warnings.append("英文摘要由中文摘要机器翻译生成，需人工核对")

            self.add_section_heading("关键词 / Keywords", level=2)
            if keywords_zh or keywords_en:
                self.add_paragraph(keywords_zh or keywords_en, indent=False)
            else:
                self.add_note("【关键词待补充】")
                warnings.append("未找到关键词，导出件中的关键词是待补充标记")

        else:
            self.add_section_heading("摘要", level=1)
            if abstract_zh:
                self.add_paragraph(abstract_zh)
            elif abstract_en:
                self.add_paragraph(translator.translate_to_chinese(abstract_en, session.research_topic or ""))
                warnings.append("中文摘要由英文摘要机器翻译生成，需人工核对")
            else:
                self.add_note("【摘要待补充：提纲中未找到摘要章节】")
                warnings.append("未找到摘要章节，导出件中的摘要是待补充标记")

            self.add_section_heading("关键词", level=2)
            if keywords_zh or keywords_en:
                self.add_paragraph(keywords_zh or keywords_en, indent=False)
            else:
                self.add_note("【关键词待补充：建议 3-8 个】")
                warnings.append("未找到关键词，导出件中的关键词是待补充标记")

        return warnings

    @staticmethod
    def _find_section(session, titles: tuple):
        """在提纲中查找摘要/关键词章节，返回 (中文, 英文)"""
        if not getattr(session, "outline", None):
            return "", ""
        for node in session.iter_outline_nodes():
            name = (node.title or "").strip().lower()
            if any(name.startswith(t) or t in name for t in titles):
                return node.content_zh or "", node.content_en or ""
        return "", ""

    @staticmethod
    def _unapproved_titles(session) -> List[str]:
        if not getattr(session, "outline", None):
            return [s.get("chapter", "") for s in getattr(session, "sections", [])
                    if s.get("status") not in ("approved", None)]
        from services.session_manager import SectionStatus
        return [
            node.title for node in session.iter_outline_nodes()
            if node.status != SectionStatus.APPROVED and (node.content_zh or node.content_en)
        ]

    # ------------------------------------------------------------------ 正文
    def _generate_content_from_outline(self, outline_node, language="中文", research_context=""):
        """从提纲生成内容，返回写入/空章节统计"""
        written = 0
        empty: List[str] = []
        warnings: List[str] = []

        for child in outline_node.children:
            skip_title = bool(child.title) and (
                "核心内容" in child.title or "关键要点" in child.title
                or child.title.strip().endswith("核心内容")
                or child.title.strip().endswith("关键要点")
            )

            if not skip_title:
                display_title = child.title
                if language == "英文":
                    display_title = child.title_en or translator.translate_outline_title(child.title, research_context)

                if child.level in (1, 2, 3):
                    self.add_section_heading(display_title, level=child.level)

            display_content = ""
            if language == "中英文双语":
                if child.content_zh or child.content_en:
                    zh = child.content_zh
                    en = child.content_en
                    if zh and not en:
                        warnings.append(f"章节「{child.title}」缺少英文稿，双语导出仅含中文")
                    self.add_bilingual_paragraph(zh, en)
                    written += 1
            elif language == "英文":
                if child.content_en:
                    display_content = child.content_en
                elif child.content_zh:
                    logger.info("[document_generator] translating Chinese content to English", content_length=len(child.content_zh))
                    display_content = translator.translate_to_english(child.content_zh, research_context)
                if display_content:
                    self.add_paragraph(display_content)
                    written += 1
            else:
                if child.content_zh:
                    display_content = child.content_zh
                elif child.content_en:
                    display_content = translator.translate_to_chinese(child.content_en, research_context)
                if display_content:
                    self.add_paragraph(display_content)
                    written += 1

            if not display_content and not child.content_zh and not child.content_en:
                if not child.children and child.level >= 2:
                    empty.append(child.title)

            if child.children:
                sub = self._generate_content_from_outline(child, language, research_context)
                written += sub["written"]
                empty.extend(sub["empty"])
                warnings.extend(sub["warnings"])

        if empty:
            warnings.append(f"{len(empty)} 个章节尚无正文：" + "、".join(empty[:6]))

        return {"written": written, "empty": empty, "warnings": warnings}

    def _generate_sections(self, sections: list, language="中文", research_context=""):
        """从章节列表（RCT 模式）生成内容"""
        written = 0
        empty: List[str] = []
        warnings: List[str] = []
        total_sections = max(len(sections), 1)

        for index, section in enumerate(sections):
            if isinstance(section, dict):
                title = section.get("title") or section.get("chapter") or "章节"
                content_zh = section.get("content_zh", "")
                content_en = section.get("content_en", "")
                content = section.get("content", "")
            else:
                title = "章节"
                content_zh = content_en = ""
                content = str(section)

            progress = 15 + int((index / total_sections) * 70)
            self._report_progress(f"正在处理章节: {title} ({index + 1}/{total_sections})", progress)

            display_title = title
            if language == "英文":
                display_title = translator.translate_outline_title(title, research_context)

            display_content = ""
            if language == "中英文双语" and (content_zh or content_en):
                self.add_section_heading(display_title, level=2)
                self.add_bilingual_paragraph(content_zh, content_en)
                written += 1
                continue
            if language == "英文":
                if content_en:
                    display_content = content_en
                elif content_zh:
                    display_content = translator.translate_to_english(content_zh, research_context)
                elif content:
                    display_content = translator.translate_to_english(content, research_context)
            else:
                display_content = content_zh or content
                if not display_content and content_en:
                    display_content = translator.translate_to_chinese(content_en, research_context)

            self.add_section_heading(display_title, level=2)
            if display_content:
                self.add_paragraph(display_content)
                written += 1
            else:
                empty.append(title)

        if empty:
            warnings.append(f"{len(empty)} 个章节尚无正文：" + "、".join(empty[:6]))

        return {"written": written, "empty": empty, "warnings": warnings}
