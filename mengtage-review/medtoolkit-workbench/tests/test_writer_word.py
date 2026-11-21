import io,base64,json,unittest,zipfile
from unittest.mock import patch
from docx import Document
from workbench.fulltext import sha,json_hash
import test_writer as fixture
class WriterWordTest(unittest.TestCase):
 setUp=fixture.WriterTest.setUp
 save=fixture.WriterTest.save
 approve=fixture.WriterTest.approve
 def test_docx_saved_version_tables_citations_and_audit(self):
  body='中文 & English <example> [E:e1]\n\n| 指标 | 值 |\n| --- | ---: |\n| 合成计数 | 42 [E:e1] |\n| 转义竖线 | a\\|b |'
  m=self.save(body);self.approve(m)
  with patch('urllib.request.urlopen',side_effect=AssertionError('No network')):out=self.s.export_word(self.pid,m['id'])
  raw=base64.b64decode(out['content_base64']);self.assertEqual(sha(raw),out['file_sha256']);self.assertEqual(raw,self.store.artifact(self.pid,out['filename']).read_bytes())
  doc=Document(io.BytesIO(raw));text='\n'.join(p.text for p in doc.paragraphs)
  self.assertIn('中文 & English <example> [1]',text);self.assertIn('[E:e1] → [1]',text);self.assertIn('已获作者批准',text);self.assertIn('Synthetic finding 42.',text);self.assertEqual(len(doc.tables),1);self.assertEqual(doc.tables[0].cell(2,1).text,'a|b');self.assertEqual(doc.tables[0].cell(1,1).text,'42 [1]')
  tbl_borders=doc.tables[0]._tbl.tblPr.xpath('.//w:tblBorders/w:insideV/@w:val')
  self.assertEqual(tbl_borders,['nil'])
  academic_doc=Document(io.BytesIO(base64.b64decode(out['academic_content_base64'])))
  academic_text='\n'.join(p.text for p in academic_doc.paragraphs)
  self.assertIn('中文 & English <example> [1]',academic_text);self.assertNotIn('原件 SHA256',academic_text)
  self.assertEqual(out['manifest']['audit_sha256'],json_hash(out['audit']));self.assertEqual(self.s.load(self.pid,out['manifest']['id'])['version'],m['id'])
  with zipfile.ZipFile(io.BytesIO(raw)) as z:
   self.assertIsNone(z.testzip());self.assertNotIn(b'TargetMode="External"',z.read('word/_rels/document.xml.rels'))
 def test_draft_and_historical_approval_are_distinct(self):
  m=self.save();draft=self.s.export_word(self.pid,m['id']);self.assertEqual(draft['manifest']['status'],'needs_human_review');self.assertIn('未批准草稿','\n'.join(p.text for p in Document(io.BytesIO(base64.b64decode(draft['content_base64']))).paragraphs));self.approve(m)
  self.save(manuscript_id=m['manuscript_id'],expected_version=m['id']);old=self.s.export_word(self.pid,m['id']);text='\n'.join(p.text for p in Document(io.BytesIO(base64.b64decode(old['content_base64']))).paragraphs);self.assertIn('历史版本',text);self.assertEqual(old['manifest']['status'],'approved')
 def test_cross_project_and_modified_source_refused(self):
  m=self.save();other=self.store.create('Other')
  with self.assertRaises(ValueError):self.s.export_word(other,m['id'])
  self.store.artifact(self.pid,self.doc['snapshot']['blob']).write_text('changed')
  with self.assertRaises(ValueError):self.s.export_word(self.pid,m['id'])
 def test_unsupported_table_literal_and_xml_controls(self):
  m=self.save('Malformed | table\n| a | b |\n| not divider | x |\n[E:e1]');out=self.s.export_word(self.pid,m['id']);doc=Document(io.BytesIO(base64.b64decode(out['content_base64'])));self.assertEqual(len(doc.tables),0);self.assertIn('| not divider | x |','\n'.join(p.text for p in doc.paragraphs))
  bad=self.save('Bad\x00text [E:e1]')
  with self.assertRaisesRegex(ValueError,'控制字符'):self.s.export_word(self.pid,bad['id'])
 def test_subheading_list_inline_and_soft_newlines(self):
  body='### 二级子标题\n\n第一行软换行\n第二行同一段落 **粗体** 与 *斜体* [E:e1]\n\n- 列表项一 [E:e1]\n- 列表项二 [E:e1]'
  m=self.save(body);out=self.s.export_word(self.pid,m['id']);doc=Document(io.BytesIO(base64.b64decode(out['content_base64'])))
  headings=[p.text for p in doc.paragraphs if p.style.name=='Heading 2']
  self.assertIn('二级子标题',headings)
  joined='\n'.join(p.text for p in doc.paragraphs)
  self.assertIn('第一行软换行 第二行同一段落 粗体 与 斜体 [1]',joined)
  self.assertNotIn('**粗体**',joined)
