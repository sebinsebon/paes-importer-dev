"""Synthetic source indexing, figure boundaries and pending fidelity diagnostics."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from support import RUNTIME_ROOT as ROOT, DEV_ROOT, WORK_ROOT
sys.path.insert(0, str(ROOT/'shared/scripts'))
sys.path.insert(0, str(DEV_ROOT/'examples'))
import synthetic
from lab import configure_workspace, digest
from source_index import ensure_source_index, query_source_index, figure_candidates, crop_diagnostics
from content_inventory import source_diagnostics, math_text_candidates, explanation_coverage


class SourceOptimizationTests(unittest.TestCase):
    def test_regional_queries_preserve_native_spaces_and_line_breaks(self):
        import pypdfium2 as pdfium
        from source_index import native_page
        with tempfile.TemporaryDirectory(dir=WORK_ROOT) as temporary:
            source=Path(temporary)/'lines.pdf'
            synthetic.pdf(source,['BT /F1 12 Tf 20 350 Td (Line one) Tj 0 -20 Td (Line two) Tj ET'])
            with pdfium.PdfDocument(str(source)) as document:
                page=document[0]
                try: native=native_page(page,'exam',digest(source),1)
                finally: page.close()
            index={'version':'1.0.0','source_hashes':{'exam':digest(source)},'pages':[native]}
            expected=query_source_index(index,'exam',layout='text')['text']
            self.assertIn('\r\n',expected)
            for layout in ('text','compact','full'):
                result=query_source_index(index,'exam',regions=[{'page':1,'bbox':[0,0,400,400]}],layout=layout)
                self.assertEqual(result['text'],expected)

    def test_index_hash_region_and_rotated_objects(self):
        with tempfile.TemporaryDirectory(dir=WORK_ROOT) as temporary:
            home=Path(temporary); configure_workspace(home)
            source=home/'fiction.pdf'
            synthetic.pdf(source,['BT /F1 12 Tf 40 340 Td (Top label) Tj 0 -240 Td (Foreign prose) Tj ET 40 200 100 80 re S'])
            from lab import write
            write(home/'sources.local.json',{'exam':str(source)})
            catalog={'sources':[{'id':'exam','sha256':digest(source),'page_count':1}], 'pages':[]}
            write(home/'catalog.json',catalog)
            write(home/'sources.json',catalog['sources'])
            index=ensure_source_index(home)
            result=query_source_index(index,'exam',regions=[{'page':1,'bbox':[0,0,300,90]}])
            self.assertIn('Top label',result['text']); self.assertNotIn('Foreign',result['text'])
            self.assertEqual(result['source_sha256'],digest(source))
            self.assertTrue(result['pages'][0]['glyphs'])
            source.write_bytes(source.read_bytes()+b'\n')
            with self.assertRaisesRegex(ValueError,'changed|altered'):
                ensure_source_index(home)

    def test_index_context_limit_reports_later_pages_and_cache_tampering(self):
        with tempfile.TemporaryDirectory(dir=WORK_ROOT) as temporary:
            home=Path(temporary); configure_workspace(home); source=home/'fiction.pdf'
            synthetic.pdf(source,['BT /F1 12 Tf 20 340 Td (AB) Tj ET','BT /F1 12 Tf 20 340 Td (CD) Tj ET'])
            from lab import write,read
            sources=[{'id':'exam','sha256':digest(source),'page_count':2}]
            write(home/'sources.local.json',{'exam':str(source)}); write(home/'sources.json',sources)
            write(home/'catalog.json',{'sources':sources,'pages':[]})
            index=ensure_source_index(home)
            self.assertTrue(query_source_index(index,'exam',max_chars=2)['truncated'])
            self.assertIn('CD',query_source_index(index,'exam',max_chars=None)['text'])
            index['pages'][0]['glyphs'][0]['text']='Z'; write(home/'native-source-index.json',index)
            repaired=ensure_source_index(home)
            self.assertEqual(repaired['pages'][0]['glyphs'][0]['text'],'A')

    def test_figure_preserves_vector_extents_labels_excludes_foreign_text(self):
        page={'page':1,'source_id':'exam','width':400,'height':400,
              'objects':[{'id':'box','kind':'PdfPath','bbox':[100,100,200,200]}],
              'lines':[{'text':'x','bbox':[205,140,213,150]},
                       {'text':'Following question','bbox':[80,220,250,240]}]}
        assignment={'field':'stem','regions':[{'page':1,'bbox':[80,80,250,210]}],
                    'object_ids':['box'],'label_regions':[{'page':1,'bbox':[205,140,213,150]}],
                    'exclude_regions':[{'page':1,'bbox':[80,220,250,240]}]}
        candidates=figure_candidates(page,assignment)
        self.assertEqual(candidates[0]['bbox'],[100,100,213,200])
        diagnostic=crop_diagnostics(page,[70,110,260,245],assignment)
        self.assertIn('CROP_CLIPS_VECTOR',[d['code'] for d in diagnostic])
        self.assertIn('CROP_CONTAINS_FOREIGN_TEXT',[d['code'] for d in diagnostic])
        self.assertTrue(all(d['status']=='pending' for d in diagnostic))

    def test_native_vector_clip_has_no_glyph_clip_and_rotations_stay_bounded(self):
        import pypdfium2 as pdfium
        from source_index import native_page
        from pdf_assets import crop_text_warnings
        with tempfile.TemporaryDirectory(dir=WORK_ROOT) as temporary:
            home=Path(temporary); configure_workspace(home); source=home/'geometry.pdf'
            synthetic.pdf(source,['BT /F1 12 Tf 200 340 Td (Remote label) Tj ET 10 w 40 200 100 80 re S'])
            with pdfium.PdfDocument(str(source)) as document:
                page=document[0]
                try:
                    for rotation in (0,90,180,270):
                        page.set_rotation(rotation)
                        native=native_page(page,'exam',digest(source),1)
                        vector=native['objects'][0]['bbox']; crop=[vector[0]+5,vector[1]+5,vector[2]+5,vector[3]+5]
                        if rotation==0:
                            self.assertLessEqual(vector[0],35)
                            self.assertLessEqual(vector[1],115)
                            self.assertGreaterEqual(vector[2],145)
                            self.assertGreaterEqual(vector[3],205)
                        self.assertEqual(crop_text_warnings(page,crop)['clipped_text'],[])
                        self.assertIn('CROP_CLIPS_VECTOR',[d['code'] for d in crop_diagnostics(native,crop)])
                        for glyph in native['glyphs']:
                            self.assertGreaterEqual(min(glyph['bbox']),0)
                            self.assertLessEqual(glyph['bbox'][2],native['width'])
                            self.assertLessEqual(glyph['bbox'][3],native['height'])
                finally: page.close()

    def test_inventory_plain_prose_and_detected_native_figure(self):
        page={'source_id':'exam','page':1,'width':400,'height':400,'objects':[],
              'lines':[{'text':'Una pregunta sencilla','bbox':[10,10,150,30]}]}
        catalog={'pages':[page]}
        record={'source_id':'exam','content_inventory':[], 'source_fields':{'stem':[{'page':1,'bbox':[5,5,200,60]}]}}
        self.assertEqual(source_diagnostics(record,catalog),[])
        page['objects']=[{'id':'figure','kind':'PdfPath','bbox':[20,35,60,55]}]
        self.assertIn('INVENTORY_NATIVE_STRUCTURE_UNDECLARED',[d['code'] for d in source_diagnostics(record,catalog)])
        record['source_fields']['stem'][0]['bbox']=[0,0,400,400]
        self.assertIn('SOURCE_FIELD_WHOLE_PAGE',[d['code'] for d in source_diagnostics(record,catalog)])

    def test_math_candidates_do_not_treat_spanish_or_units_as_variables(self):
        self.assertEqual(math_text_candidates('La casa y el patio miden 5 m y 3 cm. El precio es $ 5.000.'),[])
        for text in ('Si m = 6 y n = 2', 'para todo x distinto de -4', 'M/N', 'La variable y es positiva',
                     'm', 'n', 'x', 'M', 'N', 'Si m y n son enteros', 'x²', 'a₁', '√2', 'x_2'):
            self.assertTrue(math_text_candidates(text),text)

    def test_figure_math_labels_do_not_require_editable_stem_math(self):
        record={'source_id':'exam','source_fields':{'stem':[{'page':1,'bbox':[10,10,200,200]}]},
                'content_inventory':[{'field':'stem','type':'image','count':1,'regions':[{'page':1,'bbox':[20,20,150,150]}]}]}
        catalog={'pages':[{'source_id':'exam','page':1,'width':400,'height':400,'objects':[],
                           'lines':[{'text':'x = 6','bbox':[30,30,60,40]}]}]}
        self.assertEqual(source_diagnostics(record,catalog),[])

    def test_shared_fields_need_localized_justification(self):
        regions=[{'page':1,'bbox':[10,10,50,50]}]
        record={'source_id':'exam','source_fields':{'stem':regions,'options/A':regions},'content_inventory':[]}
        catalog={'pages':[{'source_id':'exam','page':1,'width':400,'height':400}]}
        self.assertIn('SOURCE_FIELDS_OVERLAP_UNJUSTIFIED',[d['code'] for d in source_diagnostics(record,catalog)])
        record['shared_regions']=[{'fields':['stem','options/A'],'reason':'Shared legend','regions':regions}]
        self.assertEqual(source_diagnostics(record,catalog),[])

    def test_nested_table_and_option_math_diagnostics(self):
        question={'stem':[],'options':[{'label':'A','blocks':[{'type':'text','text':'M/N'}]}],
                  'explanation':{'blocks':[{'type':'table','rows':[[[{'type':'text','text':'m = 6'}]]]}]}}
        record={'source_id':'exam','content_inventory':[]}
        issues=source_diagnostics(record,{'pages':[]},question=question)
        self.assertEqual({d['field'] for d in issues},{'mapping','options/A','explanation'})

    def test_missing_source_fields_remains_pending(self):
        issues=source_diagnostics({'source_id':'exam','content_inventory':[]},{'pages':[]})
        self.assertEqual(issues[0]['code'],'NATIVE_MAP_FIELDS_REQUIRED')
        self.assertEqual(issues[0]['status'],'pending')

    def test_native_typography_exposes_font_matrix_and_script_candidates(self):
        import pypdfium2 as pdfium
        from source_index import native_page
        with tempfile.TemporaryDirectory(dir=WORK_ROOT) as temporary:
            home=Path(temporary); configure_workspace(home); source=home/'typeset.pdf'
            synthetic.pdf(source,['BT /F1 12 Tf 40 300 Td (x) Tj /F1 7 Tf 7 Ts (2) Tj 0 Ts /F1 12 Tf ( + y) Tj ET'])
            with pdfium.PdfDocument(str(source)) as document:
                page=document[0]
                try: native=native_page(page,'exam',digest(source),1)
                finally: page.close()
            variable=next(g for g in native['glyphs'] if g['text']=='x')
            exponent=next(g for g in native['glyphs'] if g['text']=='2')
            self.assertIn('Helvetica',variable['font_name'])
            self.assertEqual(variable['font_size'],12); self.assertEqual(exponent['font_size'],7)
            self.assertEqual(len(exponent['text_matrix']),6); self.assertEqual(len(exponent['origin_pdf']),2)
            self.assertTrue(any(h['script']=='superscript' and h['text']=='2' and h['status']=='pending'
                                for h in native['typography_hints']))

    def test_query_layout_modes_preserve_text_typography_and_reduce_transport(self):
        import pypdfium2 as pdfium
        from source_index import native_page,seal_index
        with tempfile.TemporaryDirectory(dir=WORK_ROOT) as temporary:
            home=Path(temporary); configure_workspace(home); source=home/'context.pdf'
            prose='Repeated source words with complete native typography. '*12
            synthetic.pdf(source,['BT /F1 12 Tf 20 300 Td ('+prose+') Tj /F1 7 Tf 7 Ts (2) Tj ET'])
            with pdfium.PdfDocument(str(source)) as document:
                page=document[0]
                try: native=native_page(page,'exam',digest(source),1)
                finally: page.close()
            index=seal_index({'version':'1.0.0','source_hashes':{'exam':digest(source)},'pages':[native]})
            layouts={name:query_source_index(index,'exam',max_chars=None,layout=name)
                     for name in ('full','compact','text')}
            self.assertEqual(len({result['text'] for result in layouts.values()}),1)
            self.assertTrue(all(not result['truncated'] for result in layouts.values()))
            full,compact,text=(layouts[name] for name in ('full','compact','text'))
            self.assertLess(len(json.dumps(compact)),len(json.dumps(full))*.5)
            self.assertLess(len(json.dumps(text)),len(json.dumps(compact)))
            compact_page=compact['pages'][0]
            self.assertNotIn('glyphs',compact_page); self.assertIn('glyphs',full['pages'][0])
            self.assertTrue(compact_page['styles']); self.assertTrue(compact_page['style_runs'])
            self.assertTrue(compact_page['typography_hints'])
            self.assertIn('Helvetica',compact_page['styles'][0]['font_name'])
            self.assertNotIn('positions',compact_page['lines'][0])
            self.assertIn('position_ranges',compact_page['lines'][0])
            self.assertNotIn('lines',text['pages'][0])
            with self.assertRaisesRegex(ValueError,'layout'):
                query_source_index(index,'exam',layout='invalid')

    def test_repeated_header_logo_and_vector_content_are_hints_never_suppressed(self):
        import pypdfium2 as pdfium
        from PIL import Image
        from source_index import native_page,seal_index,query_source_index
        with tempfile.TemporaryDirectory(dir=WORK_ROOT) as temporary:
            home=Path(temporary); configure_workspace(home); source=home/'repeated.pdf'
            synthetic.pdf(source,[f'BT /F1 12 Tf 20 370 Td (Shared header) Tj 0 -130 Td (Content {word}) Tj ET 40 100 100 80 re S'
                                  for word in ('one','two')])
            rewritten=home/'with-logo.pdf'
            with pdfium.PdfDocument(str(source)) as document:
                for i in range(len(document)):
                    page=document[i]; image=pdfium.PdfImage.new(document)
                    bitmap=pdfium.PdfBitmap.from_pil(Image.new('RGB',(10,10),'red'))
                    image.set_bitmap(bitmap); image.set_matrix(pdfium.PdfMatrix(20,0,0,20,340,350))
                    page.insert_obj(image); page.gen_content(); bitmap.close(); page.close()
                document.save(rewritten)
            pages=[]
            with pdfium.PdfDocument(str(rewritten)) as document:
                for i in range(len(document)):
                    page=document[i]
                    try: pages.append(native_page(page,'exam',digest(rewritten),i+1))
                    finally: page.close()
            index=seal_index({'version':'1.0.0','source_hashes':{'exam':digest(rewritten)},'pages':pages})
            for page in pages:
                hints=page['repetition_hints']
                self.assertTrue(any(h.get('text')=='Shared header' and h['location']=='top' for h in hints))
                self.assertFalse(any(h.get('text','').startswith('Content') for h in hints))
                self.assertTrue(any(h['kind']=='object' and h['location']=='interior' for h in hints))
                self.assertEqual(len(page['objects']),2)
                self.assertTrue(all(h['status']=='pending' for h in hints))
                self.assertTrue(any(o.get('image_sha256') for o in page['objects']))
            query=query_source_index(index,'exam',pages=[1],max_chars=None)
            self.assertTrue(query['pages'][0]['repetition_hints'])

    def test_explanation_coverage_flags_reformulation_without_solving(self):
        source='Primero se reemplaza el valor. Luego se calcula el producto y se obtiene el resultado.'
        self.assertEqual(explanation_coverage(source,source),[])
        result=explanation_coverage(source,'El resultado es correcto.')
        self.assertEqual(result[0]['code'],'EXPLANATION_SOURCE_COVERAGE')
        self.assertEqual(result[0]['status'],'pending')

    def test_lazy_native_images_materialize_only_selected_candidates(self):
        import pypdfium2 as pdfium
        from PIL import Image
        from lab import write,read
        from pdf_assets import source_record,prepare_catalog,materialize_assets
        with tempfile.TemporaryDirectory(dir=WORK_ROOT) as temporary:
            home=Path(temporary); configure_workspace(home); source=home/'images.pdf'
            with pdfium.PdfDocument.new() as document:
                page=document.new_page(400,400)
                for x,color in ((40.123456,'red'),(240.654321,'blue')):
                    image=pdfium.PdfImage.new(document)
                    bitmap=pdfium.PdfBitmap.from_pil(Image.new('RGB',(16,16),color))
                    image.set_bitmap(bitmap); image.set_matrix(pdfium.PdfMatrix(80,0,0,80,x,200))
                    page.insert_obj(image); bitmap.close()
                page.gen_content(); document.save(source); page.close()
            sources=[source_record('exam',source)]; write(home/'sources.json',sources)
            write(home/'sources.local.json',{'exam':str(source)})
            catalog=prepare_catalog(sources,{'exam':source},home,materialize_images=False)
            self.assertEqual(catalog['assets'],[]); self.assertEqual(len(catalog['asset_candidates']),2)
            self.assertFalse((home/'assets').exists())
            selected=catalog['asset_candidates'][0]['id']
            assets=materialize_assets(home,[selected])
            self.assertEqual(len(assets),1); self.assertEqual(assets[0]['source_id'],'exam')
            self.assertEqual(assets[0]['bbox'],[round(v,3) for v in catalog['asset_candidates'][0]['bbox']])
            self.assertEqual(len(list((home/'assets').rglob('*.png'))),1)
            self.assertEqual(materialize_assets(home,[selected]),assets)
            altered=read(home/'catalog.json'); altered['asset_candidates'][1]['bbox'][0]+=1
            write(home/'catalog.json',altered)
            with self.assertRaisesRegex(ValueError,'geometry changed'):
                materialize_assets(home,[altered['asset_candidates'][1]['id']])


if __name__=='__main__': unittest.main()
