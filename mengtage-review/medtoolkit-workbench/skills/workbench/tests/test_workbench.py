import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('workbench', Path(__file__).parents[1]/'scripts/workbench.py')
w = importlib.util.module_from_spec(spec); spec.loader.exec_module(w)

class WorkbenchTest(unittest.TestCase):
    def test_duplicate_keeps_provenance_and_repeat_import_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'project'; w.initialize(root,'synthetic example')
            p=Path(d)/'in.csv'; p.write_text('source,title,doi\nA,Same,https://doi.org/10.1234/ABC\nB,Same,10.1234/abc\n')
            a=w.import_csv(root,p); b=w.import_csv(root,p)
            self.assertEqual(a['raw_records'],2); self.assertEqual(a['unique_records'],1)
            self.assertTrue(b['already_imported']);self.assertEqual(b['raw_records'],2)
            self.assertEqual(w.status(root)['stage'],'question_draft')
    def test_conflict_preserved(self):
        rows=w.parse_csv(b'source,title,doi,pmid\nA,X,10.1/x,1\nB,X,10.1/x,2\n','abc')
        out=w.group_records(rows)
        self.assertEqual(len(out),2); self.assertTrue(all(r['needs_review'] for r in out))
    def test_similar_titles_without_identifiers_not_deleted(self):
        rows=w.parse_csv(b'source,title\nA,Same title\nB,Same title\n','abc')
        self.assertEqual(len(w.group_records(rows)),2)
    def test_invalid_csv_does_not_create_raw(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'p';w.initialize(root,'test')
            p=Path(d)/'bad.csv';p.write_text('title\nBad\n')
            with self.assertRaises(ValueError):w.import_csv(root,p)
            self.assertEqual(list((root/'01_search/raw').iterdir()),[])
    def test_existing_project_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'p';w.initialize(root,'first')
            with self.assertRaises(FileExistsError):w.initialize(root,'second')
    def test_empty_identifiers_do_not_merge(self):
        rows=w.parse_csv(b'source,title,doi,pmid\nA,X,,\nB,Y,,\n','abc')
        self.assertEqual(len(w.group_records(rows)),2)

if __name__=='__main__': unittest.main()
