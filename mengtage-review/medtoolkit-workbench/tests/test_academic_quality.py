"""Unit tests for Stage 3 & Stage 4: Dual-scope first-use abbreviation expansion, 6 academic quality gates (covering all 10 user review comments), PRISMA Figure 1 native DOCX rendering, and Manuscript vs Technical Supplement separation."""
import base64
import io
import tempfile
import unittest
from docx import Document

from workbench.core import Store
from workbench.writer import WriterService, citation_check
from workbench.abbreviation import normalize_manuscript_abbreviations, find_undefined_first_abbreviations


class AcademicQualityGatesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(self.tmp.name)
        self.pid = self.store.create('学术写作6大门禁与10条批注正反例测试')
        self.writer = WriterService(self.store)
        self.evidence_items = []
        for idx in range(1, 10):
            txt = f'Study {idx} enrolled 120 surgical patients and evaluated AUROC 0.85.'
            doc = self.writer.document(self.pid, f's{idx}.txt', base64.b64encode(txt.encode()).decode(), f'Study {idx} DOI', 'public', True)
            self.evidence_items.append({
                'id': f'R0{idx}',
                'document_id': doc['id'],
                'locator': 'p:1',
                'excerpt': txt,
                'support_note': f'Study {idx}',
                'verified_by': 'Mengtage',
                'report_id': '',
                'study_ids': [],
            })
        self.pkg = self.writer.evidence(self.pid, '测试证据包', self.evidence_items)

    def test_comment_2_dual_scope_abbreviation_expansion_and_gate_4(self):
        # Unexpanded abbreviations in Abstract and Body should be flagged by Gate 4
        raw_sections = [
            {'title': '摘要', 'body': '本研究应用 LLM 与 NLP 评估术后 PACU 患者的 AUROC。'},
            {'title': '1. 引言', 'body': '在 PACU 中应用 LLM、NLP 与 NOL 指数具有临床价值 [E:R01]。'},
        ]
        undef = find_undefined_first_abbreviations(raw_sections)
        self.assertEqual(len(undef), 2)
        checks_before = citation_check(raw_sections, self.pkg['items'])
        self.assertTrue(any('首次出现的缩略语未提供全称定义' in b for b in checks_before['blockers']))

        # After normalize_manuscript_abbreviations, BOTH Abstract and Body independently expand first occurrence
        norm_sections = normalize_manuscript_abbreviations(raw_sections)
        self.assertIn('大语言模型（Large Language Model, LLM）', norm_sections[0]['body'])
        self.assertIn('自然语言处理（Natural Language Processing, NLP）', norm_sections[0]['body'])
        self.assertIn('麻醉后监测治疗室（Post-Anesthesia Care Unit, PACU）', norm_sections[0]['body'])
        # Body also independently expands LLM, NLP, PACU, NOL on its own first occurrence
        self.assertIn('大语言模型（Large Language Model, LLM）', norm_sections[1]['body'])
        self.assertIn('伤害性感受水平指数（Nociception Level Index, NOL）', norm_sections[1]['body'])
        self.assertEqual(find_undefined_first_abbreviations(norm_sections), [])
        checks_after = citation_check(norm_sections, self.pkg['items'])
        self.assertEqual(checks_after['blockers'], [])

    def test_comment_3_gate_1_blocks_broad_citation_dumping_over_6_refs(self):
        # 8 citations clustered on one generic statement -> blocked
        dump_tags = ''.join(f'[E:R0{i}]' for i in range(1, 9))
        sections = [
            {'title': '1. 引言', 'body': f'既往文献在人群与结局指标定义上存在显著差异 {dump_tags}。'},
        ]
        checks = citation_check(sections, self.pkg['items'])
        self.assertTrue(any('宽泛无效堆砌' in b for b in checks['blockers']))

        # Also blocks literal pre-rendered numeric range [1–37]
        sections_range = [
            {'title': '1. 引言', 'body': '既往文献在人群与结局上存在差异 [1–37] [E:R01]。'},
        ]
        checks_rng = citation_check(sections_range, self.pkg['items'])
        self.assertTrue(any('宽泛无效范围引用' in b for b in checks_rng['blockers']))

    def test_comment_5_and_6_gate_5_blocks_engineering_and_sci_self_attestation_jargon(self):
        for forbidden in [
            '所有检索快照均通过 SHA-256 哈希冻结保存 [E:R01]。',
            '原始题录基于规范化 PMID、DOI 与题名进行确定性去重 [E:R01]。',
            '定量汇总使用工作台统计模块完成，极小 P 值按医学 SCI 规范表述为 P < 0.001 [E:R01]。',
        ]:
            checks = citation_check([{'title': '2. 方法', 'body': forbidden}], self.pkg['items'])
            self.assertTrue(
                any('学术主稿严禁包含软件工程哈希、去重算法或排版规则自述词汇' in b for b in checks['blockers']),
                f'Failed to block: {forbidden}',
            )

    def test_comment_8_gate_2_and_gate_3_block_study_bullet_lists_english_excerpts_and_placeholders(self):
        # 1. Study-by-study bullet laundry list (- **Uslu Bayhan 等（2026）**：...)
        bullet_body = (
            '### 3.2 大语言模型\n\n'
            '- **Uslu Bayhan 等（2026）**（前瞻性队列）：评估了术后镇痛建议 [E:R01]。\n'
            '- **Zhang 等（2025）**（单盲对照）：评估了术前焦虑缓解 [E:R02]。'
        )
        checks_bullet = citation_check([{'title': '3. 结果', 'body': bullet_body}], self.pkg['items'])
        self.assertTrue(any('严禁使用无序列表' in b for b in checks_bullet['blockers']))

        # 2. Untranslated English sentence (>= 8 consecutive English words) in Chinese Results
        mixed_en_body = '研究结果显示 Regional block presence was not independently associated with opioid recommendations generated by any system [E:R01]。'
        checks_en = citation_check([{'title': '3. 结果', 'body': mixed_en_body}], self.pkg['items'])
        self.assertTrue(any('未翻译的连续英文原句' in b for b in checks_en['blockers']))

        # 3. Perfunctory placeholder '详见正文' or ellipsis truncation '...'
        placeholder_body = '| 作者 | 样本量与定量结果 |\n| :--- | :--- |\n| Zhang (2025) | 详见正文 [E:R01] |'
        checks_ph = citation_check([{'title': '3. 结果', 'body': placeholder_body}], self.pkg['items'])
        self.assertTrue(any('详见正文' in b for b in checks_ph['blockers']))

        trunc_body = '该研究发现术后疼痛评分显著下降且伴随较低的焦虑评分与较好的临床满意度... [E:R01]'
        checks_tr = citation_check([{'title': '3. 结果', 'body': trunc_body}], self.pkg['items'])
        self.assertTrue(any('省略号截断' in b for b in checks_tr['blockers']))

    def test_comment_7_and_dual_document_export_with_prisma_figure1_and_technical_supplement(self):
        prisma_block = (
            ':::prisma-flow\n'
            '{"records_identified": 50, "source_summary": "PubMed: 45; Europe PMC: 5", "duplicates_removed": 5, '
            '"records_screened": 45, "records_excluded": 8, "reports_sought": 37, "reports_not_retrieved": 0, '
            '"reports_assessed": 37, "reports_excluded": 0, "exclusion_breakdown": "无", "reports_included": 37, "studies_included": 36}\n'
            ':::'
        )
        sections = normalize_manuscript_abbreviations([
            {'title': '摘要', 'body': '**目的**：评估术后疼痛管理。\n**方法**：检索文献。\n**结果**：纳入 36 项研究。\n**结论**：具备临床价值。'},
            {'title': '关键词', 'body': '术后急性疼痛；人工智能'},
            {'title': '1. 引言', 'body': '术后急性疼痛管理需要客观监测 [E:R01][E:R02]。'},
            {'title': '2. 方法', 'body': '采用双人独立盲筛与 Python SciPy 1.14 统计检验。'},
            {'title': '3. 结果', 'body': f'检索共识别 50 条记录，完整流程见图 1 [E:R01]。\n\n{prisma_block}\n\n纳入研究样本量 N = 144，模型 AUROC = 0.85，术后疼痛评分降低 1.5 分达到 MCID [E:R01][E:R02]。'},
            {'title': '4. 讨论', 'body': '给药时机对齐是跨越 MCID 的核心机制 [E:R01]。'},
            {'title': '5. 结论', 'body': '多模态监测需结合多中心外部验证。'},
            {'title': '6. 声明', 'body': '作者声明无利益冲突，技术细节详见《技术补充说明》。'},
        ])
        m = self.writer.save(self.pid, '双文档分离与图1流程图测试稿', sections, self.pkg['id'])
        self.assertEqual(m['checks']['blockers'], [])
        self.writer.review(self.pid, m['id'], 'approved', 'Mengtage', 'Approved clean SCI manuscript', True)

        md_out = self.writer.export(self.pid, m['id'])
        # Clean academic manuscript has Figure 1 and zero SHA-256
        self.assertIn('图 1  PRISMA 2020 文献检索、筛选与纳入标准流程图', md_out['academic_markdown'])
        self.assertNotIn('SHA-256', md_out['academic_markdown'])
        self.assertNotIn('SHA256', md_out['academic_markdown'])
        # Technical supplement has SHA-256 and deduplication state machine details
        self.assertIn('技术补充说明与可复现性审计附录', md_out['technical_supplement_markdown'])
        self.assertIn('SHA-256', md_out['technical_supplement_markdown'])
        self.assertIn('确定性去重', md_out['technical_supplement_markdown'])

        word_out = self.writer.export_word(self.pid, m['id'])
        acad_doc = Document(io.BytesIO(base64.b64decode(word_out['academic_content_base64'])))
        acad_paras = '\n'.join(p.text for p in acad_doc.paragraphs)
        self.assertIn('图 1  PRISMA 2020 文献检索、筛选与纳入标准流程图', acad_paras)
        self.assertNotIn('SHA256', acad_paras)
        # Verify the native PRISMA 2020 flowchart table was rendered into the Word document
        self.assertGreaterEqual(len(acad_doc.tables), 1)
        flow_table_text = '\n'.join(c.text for row in acad_doc.tables[0].rows for c in row.cells)
        self.assertIn('阶段 1：识别 Identification', flow_table_text)
        self.assertIn('阶段 5：最终纳入 Included', flow_table_text)

        supp_doc = Document(io.BytesIO(base64.b64decode(word_out['technical_supplement_content_base64'])))
        supp_paras = '\n'.join(p.text for p in supp_doc.paragraphs)
        self.assertIn('技术补充说明', supp_paras)
        self.assertIn('SHA-256', supp_paras)


if __name__ == '__main__':
    unittest.main()
