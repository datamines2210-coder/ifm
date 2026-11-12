"""Run with: python -m unittest discover -s tests -p test_release_packaging.py"""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('release_packaging',ROOT/'release_packaging.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class PackagingTests(unittest.TestCase):
    def test_exclusions(self):
        for name in ('scorer_data/scorer.db','.env','uploads/a.jpg','releases/a.zip','logs/server.log'):
            self.assertFalse(mod.safe(Path(name)),name)
        self.assertTrue(mod.safe(Path('app/scorer/router.py')))

    def test_application_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            original=mod.ROOT
            try:
                mod.ROOT=Path(tmp)
                p=mod.build('scorer',{'app/scorer/router.py':b'hello'},required=('app/scorer/router.py',))
                with ZipFile(p) as z:
                    manifest=json.loads(z.read('release-manifest.json'))
                    self.assertEqual(manifest['application'],'scorer')
                    self.assertIn('app/scorer/router.py',manifest['files'])
            finally:
                mod.ROOT=original
                p.unlink(missing_ok=True)

    def test_reject_path_traversal(self):
        with self.assertRaises(ValueError): mod.build('scorer',{'../unsafe':b'x'})

if __name__=='__main__':unittest.main()
