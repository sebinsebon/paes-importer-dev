"""Create private source/result review artifacts, never certify or import by AI."""
import argparse
import html
import json
import sys
from pathlib import Path
from dev_paths import DEV_ROOT, RUNTIME_ROOT, output_path

sys.path.insert(0,str(DEV_ROOT/'tests'))
from test_inline_emphasis import styled_pdf
from pdf_assets import extract_styled_text
from lab import digest
import pypdfium2 as pdfium


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--web',required=True,type=Path)
    parser.add_argument('--pdf',type=Path)
    parser.add_argument('--page',type=int,default=1)
    args=parser.parse_args(); output=output_path(args.output)
    if output.exists(): raise ValueError('Preserve existing evidence; select a new directory')
    output.mkdir(parents=True)
    source=args.pdf
    if source is None:
        source=output/'synthetic-styles.pdf'; styled_pdf(source)
    with pdfium.PdfDocument(source) as pdf:
        page=pdf[args.page-1]
        try:
            extracted=extract_styled_text(page)
            bitmap=page.render(scale=1.6)
            try: bitmap.to_pil().save(output/'source.png')
            finally: bitmap.close()
        finally: page.close()
    (output/'extraction.json').write_text(json.dumps(extracted,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    title='Synthetic source/result comparison' if args.pdf is None else 'Private PDF extraction review (not a question import)'
    # Exact native page text, no inferred reading order or reconstructed math.
    blocks=[{'type':'text','text':extracted['styled_text']}]
    js=json.dumps(blocks,ensure_ascii=True).replace('<','\\u003c')
    portable=(RUNTIME_ROOT/'viewer/block-renderer.js').read_text(encoding='utf-8')
    web=(args.web/'lib/paessed-runtime/block-renderer.js').read_text(encoding='utf-8')
    document='<!doctype html><meta charset="utf-8"><title>'+html.escape(title)+'</title><style>body{font:16px Arial;margin:24px;background:#f1f5f9;color:#172033}main{display:grid;grid-template-columns:1fr 1fr;gap:24px}section{background:white;padding:20px;border:1px solid #cbd5e1}img{width:100%}.paessed-text{white-space:pre-wrap}.paessed-paragraph{margin:0}h1{font-size:22px}p{line-height:1.5}</style><h1>'+html.escape(title)+'</h1><p>Format pending visual review. No Gold certification. Mathematical layout is intentionally not reconstructed by native extraction.</p><main><section><h2>PDF source</h2><img src="source.png" alt="Rendered source page"></section><section><h2>Portable reader</h2><div id="portable"></div><h2>PAESSED reader</h2><div id="web"></div></section></main><script>'+portable+'\nconst Portable=window.PaessedBlocks;</script><script>'+web+'\nconst blocks='+js+';Portable.renderBlocks(document.getElementById("portable"),blocks);window.PaessedBlocks.renderBlocks(document.getElementById("web"),blocks);</script>'
    (output/'comparison.html').write_text(document,encoding='utf-8')
    if args.pdf is None:
        from test_contract_compatibility import fixture
        from package_io import validate, pack
        from lab import configure_workspace
        data=fixture(); q=data['questions'][0]
        data['sources'][0].update(name=source.name,sha256=digest(source))
        data['exam']['title']='Synthetic PDF typography review - pending'
        q['regions']=[{'page':1,'bbox':[0,0,400,400]}]
        # Fictional prose only. These styles are also present in the extracted runs.
        q['stem']=[{'type':'text','text':extracted['styled_text'].splitlines()[0]}]
        q['options']=[{'label':'A','blocks':[{'type':'text','text':'<i>italic</i>'}]},{'label':'B','blocks':[{'type':'text','text':'<b><i>both</i></b>'}]}]
        q['issues']=['TEXT_FORMAT_PENDING','SYNTHETIC_SOURCE_NOT_GOLD','CURRICULUM_PENDING']
        validate(data)
        (output/'demo.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        configure_workspace(output)
        pack(output/'demo.json')
    print(str(output/'comparison.html'))


if __name__=='__main__': main()
