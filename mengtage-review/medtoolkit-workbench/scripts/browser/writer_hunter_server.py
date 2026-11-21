"""Synthetic completed Hunter fixture; real ledgers, HTTP and Writer."""
import json,os,sys,shutil
from pathlib import Path
root=Path(__file__).resolve().parents[2];sys.path[:0]=[str(root),str(root/'tests')]
from test_studies_prisma import StudyPrismaTests
from workbench.core import Store
from workbench.server import serve
fixture=StudyPrismaTests();fixture.setUp();fixture.save()
target=Path(sys.argv[1]);shutil.copytree(fixture.store.root,target,dirs_exist_ok=True)
(target/'fixture.json').write_text(json.dumps({'project':fixture.pid,'review':fixture.r,'human_token':fixture.h['token'],'model_token':fixture.m['token']}))
fixture.doCleanups();os.environ['GEMINI_API_KEY']='';os.environ['GEMINI_MODEL']='';serve(Store(target),int(sys.argv[2]))
