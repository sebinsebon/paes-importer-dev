"""Synthetic curriculum and cross-language contract regression tests."""
import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'shared/scripts'))
from curriculum import catalog, catalog_hash, curriculum_hash, pending_curriculum, validate_question_curriculum, prepare_ledger
from jsonschema import Draft202012Validator

class CurriculumTests(unittest.TestCase):
    def test_catalog_complete_and_js_in_sync(self):
        data=catalog()
        self.assertEqual(len(data['ejes']),4)
        self.assertEqual(sum(len(a['subejes']) for a in data['ejes']),16)
        js=json.loads(subprocess.check_output(['node','-e',"console.log(JSON.stringify(require('./viewer/validator.js').CURRICULUM))"],cwd=ROOT,text=True,encoding='utf-8'))
        self.assertEqual(js,{a['eje']:a['subejes'] for a in data['ejes']})
    def test_all_pairs_and_membership_states(self):
        schema=json.loads((ROOT/'shared/schemas/final.schema.json').read_text(encoding='utf-8'))
        validator=Draft202012Validator(schema['$defs']['curriculum'])
        for axis in catalog()['ejes']:
            for sub in axis['subejes']:
                for status in ('si','no','dudoso'):
                    value={'eje':axis['eje'],'subeje':sub,'en_temario':status}
                    validator.validate(value)
                    self.assertTrue(validate_question_curriculum({'curriculum':value,'issues':[]}))
    def test_pending_and_invalid_pairs(self):
        self.assertFalse(validate_question_curriculum({'curriculum':pending_curriculum(),'issues':['CURRICULUM_PENDING']}))
        for value,issues in [(pending_curriculum(),[]),({'eje':'Números','subeje':None,'en_temario':'dudoso'},['CURRICULUM_PENDING']),({'eje':'Números','subeje':'Función cuadrática','en_temario':'si'},[])]:
            with self.assertRaises(ValueError): validate_question_curriculum({'curriculum':value,'issues':issues})
    def test_hash_separate_and_ledger_reason(self):
        q={'id':'foreign-id','source_id':'exam','regions':[{'page':1}],'issues':[], 'curriculum':{'eje':'Números','subeje':'Porcentaje','en_temario':'si'}}
        candidate={'questions':[q]}
        binding=curriculum_hash(q,'a'*64)
        changed=copy.deepcopy(q); changed['curriculum']['en_temario']='dudoso'
        self.assertNotEqual(binding,curriculum_hash(changed,'a'*64))
        with self.assertRaises(ValueError): prepare_ledger(candidate,{'questions':[q]},lambda *args:'a'*64,None)
        response={'questions':[q],'curriculum_provenance':{'foreign-id':{'reason':'Synthetic percentage requirement','evidence':[{'source_id':'exam','page':1,'observation':'Percent shown in stem'}]}}}
        ledger=prepare_ledger(candidate,response,lambda *args:'a'*64,None)
        self.assertEqual(ledger['foreign-id']['curriculum_sha256'],binding)
        response['curriculum_provenance']['foreign-id']['evidence'][0]['page']=2
        with self.assertRaises(ValueError): prepare_ledger(candidate,response,lambda *args:'a'*64,None)

if __name__=='__main__': unittest.main()
