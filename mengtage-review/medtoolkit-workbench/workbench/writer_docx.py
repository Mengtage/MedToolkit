"""Local DOCX rendering of a frozen writer export with SCI three-line tables, native PRISMA 2020 Figure 1 flowchart, Vancouver references, and standalone Technical Supplement DOCX."""
import io
import json
import re
from docx import Document
from docx.shared import Pt, Mm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from .writer import order_citations, render_academic_text, format_vancouver_reference


def cells(line):
    """Small explicit Markdown table subset; escaped pipes are literal cell content."""
    value=line.strip()
    if not value.startswith('|') or not value.endswith('|'):return None
    return [v.strip().replace(r'\|','|') for v in re.split(r'(?<!\\)\|',value[1:-1])]


def add_inline(para,text):
    pattern=re.compile(r'(\*\*[^*\n]+\*\*|\*[^*\n]+\*)')
    pos=0
    for m in pattern.finditer(text):
        if m.start()>pos:para.add_run(text[pos:m.start()])
        token=m.group(0)
        if token.startswith('**'):
            r=para.add_run(token[2:-2]);r.bold=True
        else:
            r=para.add_run(token[1:-1]);r.italic=True
        pos=m.end()
    if pos<len(text):para.add_run(text[pos:])


def _set_border(container, edge, val='nil', sz=None, color='000000'):
    el=OxmlElement(f'w:{edge}')
    el.set(qn('w:val'),val)
    if sz is not None:
        el.set(qn('w:sz'),str(sz))
        el.set(qn('w:space'),'0')
        el.set(qn('w:color'),color)
    container.append(el)


def _set_cell_box_style(cell, border_color='126B64', fill_color='F1F8F7', border_sz=10):
    tcPr = cell._tc.get_or_add_tcPr()
    for old in tcPr.findall(qn('w:tcBorders')):
        tcPr.remove(old)
    cb = OxmlElement('w:tcBorders')
    for edge in ('top', 'left', 'bottom', 'right'):
        _set_border(cb, edge, 'single', border_sz, border_color)
    tcPr.append(cb)
    for old_shd in tcPr.findall(qn('w:shd')):
        tcPr.remove(old_shd)
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), fill_color)
    tcPr.append(shd)


def _set_cell_clear_borders(cell):
    tcPr = cell._tc.get_or_add_tcPr()
    for old in tcPr.findall(qn('w:tcBorders')):
        tcPr.remove(old)
    cb = OxmlElement('w:tcBorders')
    for edge in ('top', 'left', 'bottom', 'right'):
        _set_border(cb, edge, 'nil')
    tcPr.append(cb)


def add_prisma_flow_figure(doc, flow_json_str):
    """Render Figure 1 (PRISMA 2020 Standard Flow Diagram) natively as a structured two-column boxed flowchart inside Word."""
    try:
        d = json.loads(flow_json_str)
    except Exception:
        p = doc.add_paragraph()
        add_inline(p, flow_json_str)
        return

    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_before = Pt(8)
    cap.paragraph_format.space_after = Pt(6)
    r_cap = cap.add_run('图 1  PRISMA 2020 文献检索、筛选与纳入标准流程图（Figure 1. PRISMA 2020 Flow Diagram）')
    r_cap.bold = True
    r_cap.font.size = Pt(10.5)

    stages = [
        (
            f"【阶段 1：识别 Identification】\n数据库与注册库检索识别原始记录 (n = {d.get('records_identified', 0)})\n来源：{d.get('source_summary', '多数据库检索')}",
            '──────►',
            f"筛选前移除重复记录\n(n = {d.get('duplicates_removed', 0)})",
        ),
        (
            f"【阶段 2：初筛 Screening】\n题名与摘要独立双盲筛选记录\n(n = {d.get('records_screened', 0)})",
            '──────►',
            f"初筛排除不符合纳入标准记录\n(n = {d.get('records_excluded', 0)})",
        ),
        (
            f"【阶段 3：全文获取 Retrieval】\n拟获取全文进行资格评估报告\n(n = {d.get('reports_sought', 0)})",
            '──────►',
            f"未能获取全文报告\n(n = {d.get('reports_not_retrieved', 0)})",
        ),
        (
            f"【阶段 4：全文评估 Eligibility】\n全文资格评估报告\n(n = {d.get('reports_assessed', 0)})",
            '──────►',
            f"全文评估排除报告 (n = {d.get('reports_excluded', 0)})\n排除原因：{d.get('exclusion_breakdown', '不符合纳入标准')}",
        ),
        (
            f"【阶段 5：最终纳入 Included】\n纳入本综述定量与定性综合全文报告 (n = {d.get('reports_included', 0)})\n归属独立原始临床研究 (n = {d.get('studies_included', 0)})",
            '',
            '',
        ),
    ]

    # Build a 9-row x 3-column flowchart grid (5 stage rows interleaved with 4 downward arrow rows)
    table = doc.add_table(rows=len(stages) * 2 - 1, cols=3)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    tblPr = table._tbl.tblPr
    for old in tblPr.findall(qn('w:tblBorders')):
        tblPr.remove(old)
    borders = OxmlElement('w:tblBorders')
    for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        _set_border(borders, edge, 'nil')
    tblPr.append(borders)

    total_w = doc.sections[0].page_width - doc.sections[0].left_margin - doc.sections[0].right_margin
    col_widths = [int(total_w * 0.48), int(total_w * 0.10), int(total_w * 0.42)]

    for s_idx, (left_txt, arrow_txt, right_txt) in enumerate(stages):
        r_i = s_idx * 2
        row = table.rows[r_i]
        row._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
        c_left, c_mid, c_right = row.cells[0], row.cells[1], row.cells[2]
        for k, c in enumerate((c_left, c_mid, c_right)):
            c.width = col_widths[k]

        c_left.text = left_txt
        _set_cell_box_style(c_left, border_color='126B64', fill_color='F1F8F7', border_sz=10)
        for p in c_left.paragraphs:
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.line_spacing = 1.15
            for r in p.runs:
                r.font.size = Pt(9.5)

        c_mid.text = arrow_txt
        _set_cell_clear_borders(c_mid)
        c_mid.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        for r in c_mid.paragraphs[0].runs:
            r.bold = True
            r.font.size = Pt(10)

        c_right.text = right_txt
        if right_txt:
            _set_cell_box_style(c_right, border_color='8A4B12', fill_color='FDF7F2', border_sz=8)
            for p in c_right.paragraphs:
                p.paragraph_format.space_before = Pt(4)
                p.paragraph_format.space_after = Pt(4)
                p.paragraph_format.line_spacing = 1.15
                for r in p.runs:
                    r.font.size = Pt(9.5)
        else:
            _set_cell_clear_borders(c_right)

        if s_idx < len(stages) - 1:
            ar_row = table.rows[r_i + 1]
            ar_row._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
            for k, c in enumerate(ar_row.cells):
                c.width = col_widths[k]
                _set_cell_clear_borders(c)
            ar_row.cells[0].text = '▼'
            ar_row.cells[0].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            ar_row.cells[0].paragraphs[0].paragraph_format.space_before = Pt(1)
            ar_row.cells[0].paragraphs[0].paragraph_format.space_after = Pt(1)
            for r in ar_row.cells[0].paragraphs[0].runs:
                r.bold = True
                r.font.size = Pt(10)


def apply_three_line_table_borders(table):
    """Format a Word table as a standard medical SCI Three-Line Table (三线表)."""
    tblPr=table._tbl.tblPr
    for old in tblPr.findall(qn('w:tblBorders')):
        tblPr.remove(old)
    borders=OxmlElement('w:tblBorders')
    _set_border(borders,'top','single',12,'000000')
    _set_border(borders,'left','nil')
    _set_border(borders,'bottom','single',12,'000000')
    _set_border(borders,'right','nil')
    _set_border(borders,'insideH','nil')
    _set_border(borders,'insideV','nil')
    tblPr.append(borders)
    for c in table.rows[0].cells:
        tcPr=c._tc.get_or_add_tcPr()
        for old in tcPr.findall(qn('w:tcBorders')):
            tcPr.remove(old)
        cb=OxmlElement('w:tcBorders')
        _set_border(cb,'top','single',12,'000000')
        _set_border(cb,'bottom','single',6,'000000')
        _set_border(cb,'left','nil')
        _set_border(cb,'right','nil')
        tcPr.append(cb)
    if len(table.rows)>1:
        for c in table.rows[-1].cells:
            tcPr=c._tc.get_or_add_tcPr()
            for old in tcPr.findall(qn('w:tcBorders')):
                tcPr.remove(old)
            cb=OxmlElement('w:tcBorders')
            _set_border(cb,'bottom','single',12,'000000')
            _set_border(cb,'left','nil')
            _set_border(cb,'right','nil')
            tcPr.append(cb)


def add_body(doc,body):
    lines=body.splitlines();i=0;buf=[]
    def flush():
        if buf:
            p=doc.add_paragraph();add_inline(p,' '.join(buf));buf.clear()
    while i<len(lines):
        if lines[i].strip()==':::prisma-flow':
            flush()
            j=i+1;flow_lines=[]
            while j<len(lines) and lines[j].strip()!=':::':
                flow_lines.append(lines[j]);j+=1
            add_prisma_flow_figure(doc,'\n'.join(flow_lines))
            i=j+1 if j<len(lines) else j
            continue
        header=cells(lines[i]);divider=cells(lines[i+1]) if i+1<len(lines) else None
        if header and divider and len(header)==len(divider) and all(re.fullmatch(r':?-{3,}:?',v) for v in divider):
            rows=[];j=i+2
            while j<len(lines):
                row=cells(lines[j])
                if row is None or len(row)!=len(header):break
                rows.append(row);j+=1
            if rows:
                flush()
                table=doc.add_table(rows=1,cols=len(header))
                table.alignment=WD_TABLE_ALIGNMENT.CENTER;table.autofit=False
                weights=[max(8,min(40,max(len(v[k]) for v in [header]+rows))) for k in range(len(header))]
                width=doc.sections[0].page_width-doc.sections[0].left_margin-doc.sections[0].right_margin
                widths=[int(width*w/sum(weights)) for w in weights]
                for col,size in zip(table.columns,widths):col.width=size
                for c,value in zip(table.rows[0].cells,header):
                    c.text=''
                    add_inline(c.paragraphs[0],value)
                    for run in c.paragraphs[0].runs:run.bold=True
                prop=OxmlElement('w:tblHeader');table.rows[0]._tr.get_or_add_trPr().append(prop)
                for row in rows:
                    for c,value in zip(table.add_row().cells,row):
                        c.text=''
                        add_inline(c.paragraphs[0],value)
                apply_three_line_table_borders(table)
                for index,row in enumerate(table.rows):
                    row._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
                    for k,c in enumerate(row.cells):
                        c.width=widths[k]
                        for para in c.paragraphs:
                            para.paragraph_format.space_after=Pt(3);para.paragraph_format.space_before=Pt(3);para.paragraph_format.line_spacing=1.1
                            para.alignment=WD_ALIGN_PARAGRAPH.CENTER if divider[k].startswith(':') and divider[k].endswith(':') else WD_ALIGN_PARAGRAPH.RIGHT if divider[k].endswith(':') else WD_ALIGN_PARAGRAPH.LEFT
                            for run in para.runs:run.font.size=Pt(9.0)
                i=j;continue
        raw=lines[i].strip()
        if not raw:
            flush();i+=1;continue
        if raw.startswith('#### '):
            flush();p=doc.add_heading(level=3);add_inline(p,raw[5:].strip());i+=1;continue
        if raw.startswith('### '):
            flush();p=doc.add_heading(level=2);add_inline(p,raw[4:].strip());i+=1;continue
        if raw.startswith('## '):
            flush();p=doc.add_heading(level=1);add_inline(p,raw[3:].strip());i+=1;continue
        if re.match(r'^[-*]\s+\S',raw) or re.match(r'^\d+\.\s+\S',raw):
            flush();p=doc.add_paragraph();add_inline(p,raw);i+=1;continue
        if raw.startswith('|'):
            flush();p=doc.add_paragraph();add_inline(p,lines[i]);i+=1;continue
        buf.append(raw)
        i+=1
    flush()


def _init_styled_doc(title_text, subject_text):
    doc=Document()
    for name,east in [('Normal','宋体'),('Title','黑体'),('Heading 1','黑体'),('Heading 2','黑体'),('Heading 3','黑体')]:
        if name not in doc.styles:continue
        style=doc.styles[name];style.font.name='Times New Roman';style.element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'),east)
    section=doc.sections[0];section.page_width=Mm(210);section.page_height=Mm(297)
    section.top_margin=section.bottom_margin=Mm(20);section.left_margin=section.right_margin=Mm(22)
    section.footer_distance=Mm(10)
    normal=doc.styles['Normal'];normal.font.size=Pt(11)
    normal.paragraph_format.space_after=Pt(6);normal.paragraph_format.line_spacing=1.25;normal.paragraph_format.widow_control=True
    for name in ['Normal','Title','Heading 1','Heading 2','Heading 3']:
        if name not in doc.styles:continue
        fonts=doc.styles[name].element.get_or_add_rPr().get_or_add_rFonts()
        for attr in ['asciiTheme','hAnsiTheme','eastAsiaTheme','cstheme']:
            if qn('w:'+attr) in fonts.attrib:del fonts.attrib[qn('w:'+attr)]
    doc.core_properties.title=title_text;doc.core_properties.subject=subject_text;doc.core_properties.author='local_owner';doc.core_properties.last_modified_by='local_owner';doc.core_properties.comments='Local saved-version export; no translation or model calls.'
    title_h=doc.add_heading(title_text,0)
    title_h.alignment=WD_ALIGN_PARAGRAPH.CENTER
    return doc


def render(bundle, include_audit_appendix=True):
    m=bundle['manuscript']
    doc=_init_styled_doc(m['title'],'稿件版本 '+m['id'])
    label='已获作者批准' if bundle['status']=='approved' else '未批准草稿'
    bib_numbers,bib_refs,stat_ids,_=order_citations(m['sections'],bundle['evidence']['items'])
    for sec in m['sections']:
        doc.add_heading(sec['title'],1)
        # Keep :::prisma-flow block intact for add_body so Word renders native PRISMA Figure 1 flowchart boxes
        add_body(doc,render_academic_text(sec['body'],bib_numbers,stat_ids,convert_prisma_block=False))
    if bib_refs:
        doc.add_heading('参考文献 (References)',1)
        for idx,e in enumerate(bib_refs,1):
            rp=doc.add_paragraph()
            rp.paragraph_format.left_indent=Pt(18)
            rp.paragraph_format.first_line_indent=Pt(-18)
            rp.paragraph_format.space_after=Pt(4)
            rp.paragraph_format.line_spacing=1.15
            run=rp.add_run(f"[{idx}] {format_vancouver_reference(e)}")
            run.font.size=Pt(10)
    if include_audit_appendix:
        doc.add_page_break()
        doc.add_heading('附录：证据溯源与作者审核记录',1)
        doc.add_paragraph(label)
        doc.add_paragraph('稿件版本：'+m['id']);doc.add_paragraph('导出时间：'+bundle['exported_at'])
        if not bundle['is_current']:doc.add_paragraph('历史版本；审核状态对应本版，不代表最新稿件。')
        doc.add_heading('引用证据',2)
        for e in bundle['references']:
            v_tag=f" → [{bib_numbers[e['id']]}]" if e['id'] in bib_numbers else ''
            doc.add_paragraph(f"[E:{e['id']}]{v_tag} {e['source']}；{e['locator']}")
            doc.add_paragraph('摘录：'+e['excerpt']);doc.add_paragraph('支持性说明：'+e['support_note'])
            doc.add_paragraph('核验人声明：'+e['verified_by']);doc.add_paragraph('原件 SHA256：'+e['file_sha256'])
            if e.get('native_statistics'):
                b=e['native_statistics'];doc.add_paragraph('合成统计任务：'+b['job_id']);doc.add_paragraph('任务输入 SHA256：'+b['payload_sha256']);doc.add_paragraph('统计产物 SHA256：'+b['artifact_sha256'])
            if e.get('native_hunter'):
                b=e['native_hunter'];doc.add_paragraph('Hunter报告：'+b['report_id']);doc.add_paragraph('研究ID（限所选全文批次）：'+', '.join(b['study_ids']));doc.add_paragraph('全文裁决版本：'+b['screening_event_hash']);doc.add_paragraph('研究映射版本：'+b['mapping_event_hash'])
        doc.add_heading('作者审核记录',2)
        if not bundle['reviews']:doc.add_paragraph('本版尚无作者审核记录。')
        for event in bundle['reviews']:
            doc.add_paragraph(f"{event['timestamp']} · {event['author']} · "+('批准' if event['decision']=='approved' else '要求修改'))
            doc.add_paragraph(event['note'])
        checks=m['checks']
        if checks['blockers'] or checks['warnings']:
            doc.add_heading('待核对事项',2)
            for value in checks['blockers']+checks['warnings']:doc.add_paragraph(value)
        for para in doc.paragraphs:
            if any(key in para.text for key in ['SHA256','裁决版本：','映射版本：']):
                para.paragraph_format.keep_together=True
                for run in para.runs:run.font.size=Pt(9)
    footer=doc.sections[0].footer.paragraphs[0]
    footer.text=(label+' · '+m['id']+' · ') if include_audit_appendix else ''
    for instruction in ['PAGE','NUMPAGES']:
        if instruction=='NUMPAGES':footer.add_run(' / ')
        field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),instruction);footer._p.append(field)
    for run in footer.runs:run.font.size=Pt(8)
    footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
    output=io.BytesIO();doc.save(output);return output.getvalue()


def render_technical_supplement(bundle):
    """Render the standalone Technical Supplement (technical_supplement_markdown) into a formatted Word (.docx) document."""
    m = bundle['manuscript']
    supp_title = f"{m['title']} — 技术补充说明 (Technical Supplement)"
    doc = _init_styled_doc(supp_title, '技术补充说明 · 对应主稿版本 ' + m['id'])
    md_text = bundle.get('technical_supplement_markdown') or ''
    # Strip the top H1 line since _init_styled_doc already added the document title heading
    lines = md_text.splitlines()
    if lines and lines[0].startswith('# '):
        lines = lines[1:]
    add_body(doc, '\n'.join(lines))
    footer = doc.sections[0].footer.paragraphs[0]
    footer.text = f"Technical Supplement · Manuscript {m['id'][:8]} · "
    for instruction in ['PAGE', 'NUMPAGES']:
        if instruction == 'NUMPAGES':
            footer.add_run(' / ')
        field = OxmlElement('w:fldSimple')
        field.set(qn('w:instr'), instruction)
        footer._p.append(field)
    for run in footer.runs:
        run.font.size = Pt(8)
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    output = io.BytesIO()
    doc.save(output)
    return output.getvalue()
