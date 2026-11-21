"""Check rendered stress specimen text, repeated headers, page numbers and page bounds."""
import hashlib,json,re,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
folder=Path(sys.argv[1]);pdf=folder/'layout-stress.pdf'
info=subprocess.check_output(['pdfinfo',str(pdf)],text=True);assert '(A4)' in info
raw=subprocess.check_output(['pdftotext','-layout',str(pdf),'-'],text=True)
(folder/'layout.txt').write_text(raw)
assert [int(v) for v in re.findall(r'项目\s+(\d{2})',raw)]==list(range(1,66))
for token in ['中文','English','α','β','≤','≥','±','[E:e1]','作者审核记录']:
 assert token in raw,token
pages=raw.split('\f');pages=[p for p in pages if p.strip()]
for i,page in enumerate(pages,1):
 assert re.search(rf'{i}\s*/\s*{len(pages)}',page)
 if re.search(r'项目\s+\d{2}',page):assert 'Measure' in page and 'Notes' in page
xml=subprocess.check_output(['pdftotext','-bbox-layout',str(pdf),'-'])
tree=ET.fromstring(xml);ns={'x':'http://www.w3.org/1999/xhtml'}
for page in tree.findall('.//x:page',ns):
 width=float(page.attrib['width']);height=float(page.attrib['height'])
 for word in page.findall('.//x:word',ns):
  assert 15<float(word.attrib['xMin'])<float(word.attrib['xMax'])<width-15
  assert 15<float(word.attrib['yMin'])<float(word.attrib['yMax'])<height-15
summary={'status':'PASS','pages':len(pages),'paper':'A4','table_rows':65,'checks':['all 65 rows in order','Chinese English and symbols retained','table headers repeat on each table page','page fields correct','rendered word bounds inside pages'],'engine':'LibreOffice 26.2.6.3; not Microsoft Word','sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [pdf,folder/'layout-stress.docx']}}
(folder/'checks.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False))
