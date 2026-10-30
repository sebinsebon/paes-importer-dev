"""Font extraction and safe reader parity using fictional, generated PDFs."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from support import RUNTIME_ROOT as ROOT, WORK_ROOT
import pypdfium2 as pdfium
from pdf_assets import extract_styled_text, font_style


def styled_pdf(path):
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
               b'<< /Type /Pages /Count 1 /Kids [7 0 R] >>']
    for name in ['Helvetica', 'Helvetica-Bold', 'Helvetica-Oblique', 'Helvetica-BoldOblique']:
        objects.append(f'<< /Type /Font /Subtype /Type1 /BaseFont /{name} >>'.encode())
    stream = (b'BT /F1 12 Tf 25 350 Td (1. Choose the ) Tj /F2 12 Tf (INCORRECT) Tj '
              b'/F1 12 Tf ( statement.) Tj 0 -25 Td /F3 12 Tf (A. italic) Tj '
              b'0 -25 Td /F4 12 Tf (B. both) Tj ET')
    objects += [b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 400] /Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R /F4 6 0 R >> >> /Contents 8 0 R >>',
                b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream']
    payload = bytearray(b'%PDF-1.4\n'); offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(payload)); payload.extend(f'{index} 0 obj\n'.encode()+obj+b'\nendobj\n')
    xref=len(payload)
    payload.extend(f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode())
    for offset in offsets[1:]: payload.extend(f'{offset:010d} 00000 n \n'.encode())
    payload.extend(f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode())
    Path(path).write_bytes(payload)


class InlineEmphasisTests(unittest.TestCase):
    def test_digital_text_exact_and_styles_from_font_properties(self):
        with tempfile.TemporaryDirectory(dir=WORK_ROOT) as directory:
            source=Path(directory)/'styles.pdf'; styled_pdf(source)
            with pdfium.PdfDocument(source) as pdf:
                page=pdf[0]
                try:
                    result=extract_styled_text(page)
                    textpage=page.get_textpage()
                    try: self.assertEqual(result['text'],textpage.get_text_range())
                    finally: textpage.close()
                finally: page.close()
            self.assertIn('<b>INCORRECT</b>',result['styled_text'])
            self.assertIn('<i>A.</i>',result['styled_text'])
            self.assertIn('<b><i>B.</i></b>',result['styled_text'])
            self.assertEqual(result['format_status'],'pending')
            script="const R=require('./viewer/block-renderer.js');process.stdout.write(R.plainText(JSON.parse(process.argv[1])))"
            plain=subprocess.run(['node','-e',script,json.dumps(result['styled_text'])],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',check=True).stdout
            self.assertEqual(plain.replace('\r\n','\n'),result['text'].replace('\r\n','\n'))
            self.assertEqual(''.join(r['text'] for r in result['runs']),result['text'])

    def test_no_native_text_never_invents_format(self):
        from PIL import Image, ImageDraw
        with tempfile.TemporaryDirectory(dir=WORK_ROOT) as directory:
            source=Path(directory)/'image-only.pdf'
            image=Image.new('RGB',(400,400),'white')
            ImageDraw.Draw(image).text((20,20),'SCANNED TEXT - no native font metadata',fill='black')
            image.save(source,'PDF')
            with pdfium.PdfDocument(source) as pdf:
                page=pdf[0]
                try: result=extract_styled_text(page)
                finally: page.close()
            self.assertEqual(result['text'],''); self.assertEqual(result['styled_text'],'')
            self.assertIn('NO_NATIVE_TEXT_VISUAL_TRANSCRIPTION_REQUIRED',result['warnings'])

    def test_unknown_and_conflicting_metadata_remain_uncertain(self):
        self.assertEqual(font_style('ABCDEF+Unidentified',0,-1),(None,None))
        self.assertIsNone(font_style('Custom-Bold',0,400)[0])
        self.assertEqual(font_style('ABCDEF+Helvetica-BoldOblique',0,700),(True,True))

    def test_emphasis_does_not_create_math_variables_or_change_table_headers(self):
        from content_inventory import bare_variable, plain_prose, validate_inventory
        self.assertFalse(bare_variable('Una <b>palabra</b> en <i>prosa</i>.','b'))
        self.assertFalse(bare_variable('Una <b>palabra</b> en <i>prosa</i>.','i'))
        self.assertTrue(bare_variable('<b>x</b> = 2','x'))
        self.assertEqual(plain_prose('<b>x'),'<b>x')
        q={'id':'fiction','source_id':'source','stem':[{'type':'table','rows':[[[{'type':'text','text':'<b>Valor</b>'}]]]}], 'options':[], 'explanation':{'blocks':[]}}
        validate_inventory(q,{'content_inventory':[{'field':'stem','type':'table','count':1,'shape':{'rows':1,'columns':1,'headers':['Valor']}}]}, {})

    def test_reader_prose_convention_and_contract_compatibility(self):
        from test_contract_compatibility import fixture
        from package_io import validate
        for version in ('0.1.0','0.2.0'):
            data=fixture(version)
            data['questions'][0]['stem']=[{'type':'text','text':'A <b>bold</b> <i>italic</i>'}]
            data['questions'][0]['regions']=[{'page':1,'bbox':[0,0,100,100]}]
            data['questions'][0]['options']=[{'label':label,'blocks':[{'type':'text','text':label}]} for label in ('A','B')]
            validate(data)
        script="const R=require('./viewer/block-renderer.js');const a=require('node:assert/strict');a.equal(R.plainText('<b><i>x</i></b>'),'x');a.equal(R.plainText('<b>x'),'<'+'b>x');a.equal(R.plainText('<b><i>x</b></i>'),'<b><i>x</b></i>');"
        subprocess.run(['node','-e',script],cwd=ROOT,check=True,capture_output=True)


if __name__=='__main__': unittest.main()
