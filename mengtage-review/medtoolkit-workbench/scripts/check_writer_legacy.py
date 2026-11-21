"""Execute the two real legacy route bodies in isolation without model startup."""
import ast,asyncio,json,sys
from pathlib import Path
from unittest.mock import Mock
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'modules/MedPaperWriter'))
source=ast.parse((root/'modules/MedPaperWriter/api/routes_export.py').read_text())
funcs=[f for f in source.body if isinstance(f,ast.AsyncFunctionDef) and f.name in ('get_reference_styles','preview_references')]
assert len(funcs)==2
for f in funcs:f.decorator_list=[]
namespace={'logger':Mock(),'JSONResponse':lambda content,**kw:content,'Form':lambda x:x}
exec(compile(ast.Module(body=funcs,type_ignores=[]),'legacy-routes','exec'),namespace)
assert 'vancouver' in asyncio.run(namespace['get_reference_styles']())['styles']
result=asyncio.run(namespace['preview_references'](json.dumps([{'title':'Synthetic reference','authors':['Test Author'],'year':'2026'}]),'vancouver'))
assert result['success'] and 'Synthetic reference' in result['formatted'][0]
print('PASS: two actual legacy reference route bodies; no FastAPI app startup, no model calls')
