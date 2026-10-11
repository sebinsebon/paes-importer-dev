"""Synthetic PDF/source/result viewer generation without certifying content."""
import hashlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT/'examples'))
import synthetic
from render_review import build_review

class RenderReviewTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'tmp').mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'tmp')
        self.home=Path(self.temp.name)
        self.exam,_=synthetic.create(self.home/'sources')
        source={'id':'exam','name':'fictional.pdf','sha256':hashlib.sha256(self.exam.read_bytes()).hexdigest(),'page_count':2,'role':'exam'}
        self.data={'format':'paessed-benchmark','schema_version':'0.2.0','pipeline':'demo',
            'run':{'id':'fictional','cli':'synthetic','model':'synthetic','created_at':'2026-10-11T00:00:00Z'},
            'exam':{'id':'fictional','title':'Fictional exam','scope':'demo','expected_questions':[{'id':f'q{i}','source_id':'exam','number':str(i)} for i in (1,2)]},
            'sources':[source],'assets':[],'evidence':[],
            'questions':[{'id':f'q{i}','source_id':'exam','number':str(i),'regions':[{'page':1,'bbox':[0,0,400,400]}],
                'stem':[{'type':'text','text':'Fictional <script> text & notation'},{'type':'math','latex':'2+2','display':False},
                        {'type':'table','rows':[[[{'type':'text','text':'Fictional cell'}]]]}],
                'options':[{'label':'A','blocks':[{'type':'text','text':'3'}]},{'label':'B','blocks':[{'type':'text','text':'4'}]}],
                'answer':{'label':'B','status':'provisional','origin':'model','source_ref':None},
                'explanation':{'blocks':[{'type':'text','text':'Fictional arithmetic explanation'}],'status':'provisional'},
                'fidelity':{'status':'pending','review_ref':None},'issues':[],
                'curriculum':{'eje':'Números','subeje':'Conjunto de los números enteros y racionales','en_temario':'si'}} for i in (1,2)]}
        self.candidate=self.home/'candidate.json'
        self.candidate.write_text(json.dumps(self.data,ensure_ascii=False),encoding='utf-8')
    def tearDown(self):self.temp.cleanup()
    def test_shared_page_rendered_once_and_content_safe(self):
        output=self.home/'review'
        before=self.exam.read_bytes()
        result=build_review(self.candidate,{'exam':self.exam},output,scale=.5)
        self.assertEqual(result['pages_rendered'],1)
        self.assertEqual(self.exam.read_bytes(),before)
        self.assertEqual(result['certification'],'not_performed')
        html=(output/'index.html').read_text(encoding='utf-8')
        embedded=re.search(r'<script id="review-data" type="application/json">(.*?)</script>',html,re.S).group(1)
        self.assertNotIn('<script>',embedded)
        decoded=json.loads(embedded)
        self.assertEqual(decoded['candidate'],self.data)
        self.assertTrue((output/'vendor/katex/dist/katex.min.css').exists())
        self.assertTrue((output/'vendor/katex/dist/fonts').is_dir())
        self.assertEqual(len(list((output/'pages').glob('*.png'))),1)
        self.assertFalse(list(output.glob('*.pdf')))
    def test_wrong_source_hash_or_missing_source_writes_nothing(self):
        output=self.home/'invalid'
        with self.assertRaises(ValueError):build_review(self.candidate,{},output)
        self.assertFalse(output.exists())
        self.exam.write_bytes(self.exam.read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):build_review(self.candidate,{'exam':self.exam},output)
        self.assertFalse(output.exists())
    def test_bad_geometry_rejected_before_write(self):
        self.data['questions'][0]['regions'][0]['bbox']=[0,0,500,500]
        self.candidate.write_text(json.dumps(self.data))
        output=self.home/'bad-geometry'
        with self.assertRaises(ValueError):build_review(self.candidate,{'exam':self.exam},output)
        self.assertFalse(output.exists())
    def test_output_cannot_escape_or_overwrite(self):
        with self.assertRaises(ValueError):build_review(self.candidate,{'exam':self.exam},self.home)
        with self.assertRaises(ValueError):build_review(self.candidate,{'exam':self.exam},ROOT/'development/private-review')

if __name__=='__main__':unittest.main()
