import tempfile
import unittest
from unittest.mock import patch
from workbench.core import Store


class WritePreflightTest(unittest.TestCase):
    def test_invalid_writing_input_never_persisted(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict('os.environ', {'GEMINI_API_KEY': 'test-placeholder', 'GEMINI_MODEL': 'test-placeholder'}):
            store = Store(folder)
            pid = store.create('Public evidence validation')
            item = {'id': 'e1', 'source': 'doi:test', 'locator': 'p1', 'excerpt': 'test', 'classification': 'public', 'verified': True}
            bad = [
                {'section': '', 'evidence': [item]},
                {'section': 'x', 'evidence': 42},
                {'section': 'x', 'evidence': { 'e1': item }},
                {'section': 'x', 'evidence': [{**item, 'id': f'e{i}', 'excerpt': 'x' * 6000} for i in range(4)]},
            ]
            for payload in bad:
                with self.subTest(payload_type=type(payload['evidence']).__name__):
                    with self.assertRaises(ValueError):
                        store.enqueue(pid, 'write', {**payload, 'external_processing_approved': True})
            self.assertEqual(store.jobs(pid), [])
