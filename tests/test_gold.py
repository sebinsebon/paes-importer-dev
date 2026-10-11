"""Synthetic Gold inventory and boundary tests; no real exam dependencies."""
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import gold

def write_package(file, extras=True):
    data = {'questions': [{'id':'fiction-q1','source_id':'exam','number':'1',
                          'answer':{'status':'verified'},'explanation':{'status':'verified'},'fidelity':{'status':'reviewed'}}],
            'exam':{'expected_questions':[{'id':'fiction-q1'}]}, 'assets':[], 'evidence':[], 'sources':[]}
    blobs = {'final.json':json.dumps(data).encode()}
    if extras:
        blobs['audit/notes.json'] = b'{"review":"pending"}'
    manifest = {'format':'paessed-package','schema_version':'0.1.0','files':[
        {'path':name,'sha256':gold.sha(blob),'bytes':len(blob)} for name,blob in blobs.items()]}
    with zipfile.ZipFile(file,'w') as archive:
        for name,blob in blobs.items():
            archive.writestr(name,blob)
        archive.writestr('manifest.json',json.dumps(manifest))

class GoldTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'tmp').mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'tmp')
        self.home=Path(self.temp.name)
        self.package=self.home/'reference.zip'
        write_package(self.package)
    def tearDown(self):
        self.temp.cleanup()
    def test_inventory_never_certifies_inherited_statuses(self):
        before=self.package.read_bytes()
        report=gold.inventory(self.package)
        self.assertEqual(report['questions'],1)
        self.assertEqual(report['inherited_status_counts']['answer'],1)
        self.assertEqual(report['certification']['status'],'pending')
        self.assertEqual(before,self.package.read_bytes())
    def test_derivative_removes_extras_and_preserves_final_bytes(self):
        before=self.package.read_bytes()
        output=self.home/'dossier'
        with patch('package_io.inspect_package',return_value={'valid':True}):
            report=gold.prepare(self.package,output)
        with zipfile.ZipFile(output/'package.zip') as derived,zipfile.ZipFile(self.package) as original:
            self.assertEqual(derived.read('final.json'),original.read('final.json'))
            self.assertEqual(set(derived.namelist()),{'final.json','manifest.json'})
            gold.checked_archive(derived)
        self.assertEqual((output/'package.zip').read_bytes(),(output/'package.paessed').read_bytes())
        self.assertEqual(before,self.package.read_bytes())
        self.assertTrue((output/'original-extras/audit/notes.json').exists())
        self.assertEqual(report['certification']['independent_review'],'not_performed')
    def test_invalid_derivative_writes_nothing(self):
        output=self.home/'invalid'
        with patch('package_io.inspect_package',side_effect=ValueError('invalid')):
            with self.assertRaises(ValueError):gold.prepare(self.package,output)
        self.assertFalse(output.exists())
    def test_boundaries_and_no_overwrite(self):
        with self.assertRaises(ValueError):gold.safe_output(ROOT/'development'/'private')
        with self.assertRaises(ValueError):gold.safe_output(self.home)
    def test_tampered_manifest_rejected(self):
        damaged=self.home/'damaged.zip'
        with zipfile.ZipFile(self.package) as src,zipfile.ZipFile(damaged,'w') as dst:
            for name in src.namelist():dst.writestr(name,src.read(name)+(b' ' if name=='final.json' else b''))
        with self.assertRaisesRegex(ValueError,'integrity'):gold.inventory(damaged)
    def test_taxonomy_coverage(self):
        taxonomy=self.home/'taxonomy.json'
        taxonomy.write_text('{"questions":{}}')
        with self.assertRaisesRegex(ValueError,'coverage'):gold.inventory(self.package,taxonomy)

if __name__=='__main__':unittest.main()
