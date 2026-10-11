"""Public contract dispatch and Python/JS parity, without PDF fixtures."""
import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'shared/scripts'))
from package_io import validate
from pipeline import empty_question


def fixture(version='0.2.0'):
    expected={'id':'foreign-q1','source_id':'source','number':'1'}
    question=empty_question(expected)
    if version=='0.1.0':
        question.pop('curriculum');question['issues']=['NOT_PROCESSED']
    return {'format':'paessed-benchmark','schema_version':version,'pipeline':'demo',
        'run':{'id':'demo','cli':'synthetic','model':'synthetic','created_at':'2026-01-01','input_mode':'demo'},
        'exam':{'id':'demo','title':'Synthetic','scope':'demo','expected_questions':[expected]},
        'sources':[{'id':'source','name':'synthetic.pdf','sha256':'a'*64,'page_count':1,'role':'exam'}],
        'questions':[question],'assets':[],'evidence':[]}

class ContractCompatibilityTests(unittest.TestCase):
    def js(self,data):
        script="let b='';process.stdin.setEncoding('utf8');process.stdin.on('data',x=>b+=x);process.stdin.on('end',()=>{try{require('./viewer/validator.js').validateFinal(JSON.parse(b));console.log('ok')}catch(e){console.error(e.message);process.exitCode=1}})"
        return subprocess.run(['node','-e',script],input=json.dumps(data,ensure_ascii=False),cwd=ROOT,encoding='utf-8',capture_output=True).returncode==0
    def test_versions_and_pending_roundtrip(self):
        for version in ('0.1.0','0.2.0'):
            data=fixture(version);validate(data);self.assertTrue(self.js(data))
    def test_invalid_cases_agree(self):
        invalid=[]
        data=fixture();data['questions'][0].pop('curriculum');invalid.append(data)
        data=fixture();data['questions'][0]['issues']=[];invalid.append(data)
        data=fixture();data['schema_version']='9.0.0';invalid.append(data)
        data=fixture();data['questions'][0]['curriculum']={'eje':'Números','subeje':'Función cuadrática','en_temario':'si'};invalid.append(data)
        data=fixture('0.1.0');data['questions'][0]['curriculum']={'eje':None,'subeje':None,'en_temario':'dudoso'};invalid.append(data)
        for data in invalid:
            with self.assertRaises(Exception):validate(data)
            self.assertFalse(self.js(data))
    def test_classified_ambiguous_is_not_pending(self):
        data=fixture();q=data['questions'][0];q['curriculum']={'eje':'Geometría','subeje':'Semejanza y proporcionalidad de figuras','en_temario':'dudoso'};q['issues']=['CURRICULUM_AMBIGUOUS']
        validate(data);self.assertTrue(self.js(data))

if __name__=='__main__':unittest.main()
