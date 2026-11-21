"""Synthetic stress specimen for actual Office-compatible rendering."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workbench.writer_docx import render
root=Path(__file__).resolve().parents[1]
bundle=json.loads((root/'reports/writer-hunter-browser/hunter-audit.json').read_text())['audit']
bundle['manuscript']['title']='MedToolkit 排版验收 / Office layout — 合成材料'
paragraph='这是合成排版材料，用于检查中文、English、希腊字母 α β、置信区间 95% CI、符号 ≤ ≥ ± 与引用 [E:e1]。所有数字仅用于版式检查，不是临床结论。'
rows=['| 指标 / Measure | 合成值 | 说明 / Notes |','| --- | ---: | --- |']+[f'| 项目 {i:02d} | {i/10:.2f} | 合成表格行，检查跨页表头与行完整性。 [E:e1] |' for i in range(1,66)]
bundle['manuscript']['sections']=[{'title':'一、中文与英文混排','body':'\n\n'.join([paragraph]*7)},{'title':'二、跨页表格 / Multipage table','body':'\n'.join(rows)},{'title':'三、长引用及特殊字符','body':'Special <tags> & quotes "example" remain literal. [E:e1]\n\n'+paragraph}]
bundle['evidence']['items'][0]['source']='合成来源 · 中文题名 & English DOI 10.0000/synthetic-layout-not-real'
bundle['references'][0]['source']=bundle['evidence']['items'][0]['source']
output=Path(sys.argv[1]);output.mkdir(parents=True,exist_ok=True)
(output/'layout-stress.docx').write_bytes(render(bundle))
(output/'layout-fixture.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2))
