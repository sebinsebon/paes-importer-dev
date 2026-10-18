"""Synthetic localized evidence and deterministic geometry checks."""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from support import RUNTIME_ROOT as ROOT, DEV_ROOT, WORK_ROOT
sys.path.insert(0, str(ROOT/'shared/scripts'))
from lab import configure_workspace
from evidence import field_paths, validate_citations, validate_geometry
from quality import summarize, require_publishable

class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=WORK_ROOT)
        self.root = Path(self.tmp.name)
        configure_workspace(self.root)
        (self.root/'evidence').mkdir()
        blob = b'synthetic source evidence'
        (self.root/'evidence/page.png').write_bytes(blob)
        self.resource = {'id':'page', 'path':'evidence/page.png', 'sha256':hashlib.sha256(blob).hexdigest(),
                         'source_id':'exam','page':2,'bbox':[0,0,100,100]}
        self.q = {'id':'unrelated-q9','source_id':'exam','number':'9','regions':[{'page':2,'bbox':[0,0,100,100]}],
                  'stem':[{'type':'text','text':'Synthetic stem'}],
                  'options':[{'label':'A','blocks':[{'type':'text','text':'1'}]},{'label':'B','blocks':[{'type':'text','text':'2'}]}],
                  'explanation':{'blocks':[],'status':'missing'}, 'answer':{'status':'missing','label':None},
                  'fidelity':{'status':'pending'}, 'issues':[],
                  'curriculum':{'eje':None,'subeje':None,'en_temario':'dudoso'}}
        self.candidate = {'questions':[self.q],'assets':[],'evidence':[self.resource]}
    def tearDown(self): self.tmp.cleanup()
    def citation(self, dimension):
        fields = field_paths(self.q)[dimension]
        return {'field_paths':fields,'evidence':[{'id':'page','sha256':self.resource['sha256'],
                'observation':'Visible synthetic field','fields':fields}]}
    def test_cover_cannot_certify_other_page(self):
        self.resource['page'] = 1
        with self.assertRaisesRegex(ValueError,'does not cover'):
            validate_citations(self.q,'stem',self.citation('stem'),self.candidate,self.root)
    def test_all_option_fields_need_evidence(self):
        check = self.citation('options')
        check['evidence'][0]['fields'] = ['options/A']
        with self.assertRaisesRegex(ValueError,'fields without'):
            validate_citations(self.q,'options',check,self.candidate,self.root)
    def test_localized_fields_pass(self):
        self.assertTrue(validate_citations(self.q,'options',self.citation('options'),self.candidate,self.root))
    def test_geometry_bounds(self):
        catalog = {'pages':[{'source_id':'exam','page':2,'width':100,'height':100}]}
        validate_geometry(self.candidate,catalog)
        self.q['regions'][0]['bbox'] = [0,0,100000,100000]
        with self.assertRaisesRegex(ValueError,'exceeds page'): validate_geometry(self.candidate,catalog)
    def test_critical_blocks_but_pending_remains_partial(self):
        result = summarize(self.candidate)
        self.assertEqual(result['publication_eligibility'],'partial')
        self.q['issues'] = ['CRITICAL:SOURCE_SUBSTITUTED']
        with self.assertRaisesRegex(ValueError,'Critical'): require_publishable(summarize(self.candidate))

if __name__ == '__main__': unittest.main()
