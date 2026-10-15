"""Shared deterministic content checks: Python and the actual browser validator."""
import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'shared/scripts'))
from package_io import validate_structured_content


def document(blocks=None, options=None):
    q = {'id':'fictional-q','source_id':'source','number':'1',
         'regions':[{'page':1,'bbox':[0,0,100,100]}],
         'stem':blocks if blocks is not None else [{'type':'text','text':'Fictional content.'}],
         'options': options if options is not None else [
             {'label':'A','blocks':[{'type':'text','text':'1'}]},
             {'label':'B','blocks':[{'type':'text','text':'2'}]}],
         'answer':{'label':None,'status':'missing','origin':'none','source_ref':None},
         'explanation':{'blocks':[],'status':'missing'},
         'fidelity':{'status':'pending','review_ref':None},'issues':[],
         'curriculum':{'eje':'Números','subeje':'Porcentaje','en_temario':'si'}}
    return {'format':'paessed-benchmark','schema_version':'0.2.0','pipeline':'demo',
            'run':{'id':'fictional','cli':'synthetic','model':'none','created_at':'2026-01-01'},
            'exam':{'id':'fictional','title':'Fictional','scope':'demo',
                    'expected_questions':[{'id':q['id'],'source_id':'source','number':'1'}]},
            'sources':[{'id':'source','name':'fictional.pdf','sha256':'a'*64,'page_count':1,'role':'exam'}],
            'questions':[q],'assets':[],'evidence':[]}


class ValidationParityTests(unittest.TestCase):
    def test_contextual_content_matrix(self):
        cases = []
        def text(name, value, code=None):
            cases.append((name, document([{'type':'text','text':value}]), code))
        def math(name, value, code=None):
            cases.append((name, document([{'type':'math','latex':value,'display':True}]), code))
        text('currency','$11 000 y $80 000.')
        text('currency-spaces','Cuesta $ 11 000 y cuesta $ 80 000.')
        text('decimal-currency','Precio $1.234,50 por unidad.')
        text('blank','   ','EMPTY_CONTENT')
        text('empty','','EMPTY_CONTENT')
        text('inline-math','$x+1$','LATEX_IN_TEXT')
        text('raw-latex',r'Valor \sqrt{2}','LATEX_IN_TEXT')
        text('display-math','$$x$$','LATEX_IN_TEXT')
        text('markdown-header','| A | B |\n| --- | --- |','MARKDOWN_TABLE_IN_TEXT')
        text('markdown-rows','| A | B |\n| 1 | 2 |','MARKDOWN_TABLE_IN_TEXT')
        text('single-pipe','Eventos A|B')
        math('normal-root',r'-2\sqrt{3}')
        math('double-root',r'-2\\sqrt{3}','DOUBLE_ESCAPED_LATEX_COMMAND')
        math('double-vector',r'\\vec{x}','DOUBLE_ESCAPED_LATEX_COMMAND')
        math('aligned',r'\begin{aligned}x=2\\sin(x)=0\end{aligned}')
        math('cases',r'\begin{cases}x=2\\y=3\end{cases}')
        math('tag-display',r'\tag{1}x=2')
        math('dollar-delimited','$x$','MATH_DELIMITERS')
        math('paren-delimited',r'\(x\)','MATH_DELIMITERS')
        math('bracket-delimited',r'\[x\]','MATH_DELIMITERS')
        math('blank-math','   ','EMPTY_CONTENT')
        cases.append(('zeros',document(options=[{'label':label,'blocks':[{'type':'text','text':' 000'}]} for label in ('A','B')]),'TRUNCATED_NUMERIC_OPTIONS'))
        cases.append(('visual-placeholder',document(options=[{'label':label,'blocks':[{'type':'text','text':'Gráfico de la alternativa '+label}]} for label in ('A','B')]),'VISUAL_OPTION_PLACEHOLDER'))
        nested=document([{'type':'table','rows':[[[{'type':'text','text':'$x$'}],[{'type':'text','text':'2'}]]]}])
        cases.append(('nested-cell',nested,'LATEX_IN_TEXT'))
        script="const V=require('./viewer/validator.js');let input='';process.stdin.setEncoding('utf8');process.stdin.on('data',chunk=>input+=chunk);process.stdin.on('end',()=>console.log(JSON.stringify(JSON.parse(input).map(data=>{try{V.validateFinal(data);return null;}catch(error){return error.message;}}))));"
        result=subprocess.run(['node','-e',script],cwd=ROOT,input=json.dumps([row[1] for row in cases]),capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr)
        outputs=json.loads(result.stdout)
        for (name,data,code),js_error in zip(cases,outputs):
            with self.subTest(name=name):
                try:
                    validate_structured_content(data['questions'][0])
                    python_error=None
                except ValueError as error:
                    python_error=str(error)
                if code is None:
                    self.assertIsNone(python_error)
                    self.assertIsNone(js_error)
                else:
                    self.assertIn(code,python_error or '')
                    self.assertIn(code,js_error or '')

if __name__ == '__main__':
    unittest.main()
